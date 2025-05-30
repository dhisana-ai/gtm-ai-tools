"""Simple utility to call the OpenAI API with a prompt."""

import os
import argparse
import openai


def main() -> None:
    parser = argparse.ArgumentParser(description="Send a prompt to OpenAI and print the response")
    parser.add_argument("prompt", help="Prompt text to send")
    args = parser.parse_args()

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY environment variable is not set")

    openai.api_key = api_key
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": args.prompt}],
    )
    print(response.choices[0].message.content)


if __name__ == "__main__":
    main()
