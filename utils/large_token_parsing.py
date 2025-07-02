import tiktoken
import time
from openai import OpenAI
from utils import common
from openai._exceptions import RateLimitError


MAX_INPUT_TOKENS = 25000
DELAY_BETWEEN_REQUESTS = 20

MODEL = common.get_openai_model()
enc = tiktoken.get_encoding("cl100k_base")

def num_tokens(text):
    return len(enc.encode(text))

def split_text_to_token_chunks(text, max_tokens=MAX_INPUT_TOKENS):
    words = text.split()
    chunks, current_chunk, current_tokens = [], [], 0

    for word in words:
        token_len = len(enc.encode(word + " "))
        if current_tokens + token_len > max_tokens:
            chunks.append(" ".join(current_chunk))
            current_chunk = [word]
            current_tokens = token_len
        else:
            current_chunk.append(word)
            current_tokens += token_len
    if current_chunk:
        chunks.append(" ".join(current_chunk))
    return chunks

def get_openai_client():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY environment variable is not set")

    client = OpenAI(api_key=api_key)
    return client

def send_chunk_with_context(chunk, chunk_index, total_chunks, instructions, previous_outputs, retry_count):
    retry_count += 1
    system_prompt = (
        f"You will receive a long input broken into {total_chunks} parts. "
        f"Follow this instruction throughout all parts: '{instructions}'. "
        f"This is part {chunk_index + 1}."
        f"If this is not the final part, wait for more inputs. Do not finalize yet."
    )

    messages = [{"role": "system", "content": system_prompt}]
    
    for i, output in enumerate(previous_outputs):
        messages.append({
            "role": "assistant",
            "content": f"Previous output part {i+1}: {output}"
        })

    messages.append({
        "role": "user",
        "content": chunk
    })

    client = get_openai_client();
    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages
        )
        return response.choices[0].message.content
    except RateLimitError:
        # Max retry limit is 3 times
        if (retry_count < 4):
            print("Rate limit hit. Waiting 60 seconds...")
            time.sleep(10)
            return send_chunk_with_context(chunk, chunk_index, total_chunks, instructions, previous_outputs, retry_count)

def finalize_output(previous_outputs):
    messages = [
        {"role": "system", "content": "You have received a multi-part input. Combine the partial outputs below into a final coherent result as per the instructions given before. Don't return anything extra other than mentioned in the instrcutions"}
    ]
    for i, output in enumerate(previous_outputs):
        messages.append({
            "role": "assistant",
            "content": f"Part {i+1}: {output}"
        })

    messages.append({
        "role": "user",
        "content": "Please merge and finalize the output now."
    })

    client = get_openai_client();
    response = client.chat.completions.create(
        model=MODEL,
        messages=messages
    )
    return response.choices[0].message.content

def process_large_text(text: str, instructions: str):
    chunks = split_text_to_token_chunks(text)
    print(f"Split input into {len(chunks)} chunks.")
    partial_outputs = []

    for i, chunk in enumerate(chunks):
        print(f"Processing chunk {i+1}/{len(chunks)}...")
        output = send_chunk_with_context(chunk, i, len(chunks), instructions, partial_outputs, 0)
        partial_outputs.append(output)
        time.sleep(DELAY_BETWEEN_REQUESTS)

    print("Merging outputs into final result...")
    final = finalize_output(partial_outputs)
    return final

def handle_text_with_instruction(text, instruction):
    input_tokens = num_tokens(text)

    if input_tokens > MAX_INPUT_TOKENS:
        print(f"⚠️ Input is {input_tokens} tokens — chunking required.")
        return process_large_text(text, instruction)
    else:
        print(f"✅ Input is {input_tokens} tokens — sending directly.")

        try:
            response = client.responses.create(
                model=MODEL,
                input=f"{instructions}\n\n{text}"
            )
            return getattr(response, "output_text", "")
        except Exception as e:
            print(f"Error in direct call: {e}")
            return None