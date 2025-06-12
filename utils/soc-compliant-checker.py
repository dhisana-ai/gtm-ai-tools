import os
import requests
from bs4 import BeautifulSoup
from openai import OpenAI
import base64
from playwright.sync_api import sync_playwright

# Set your OpenAI API key
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def capture_screenshot(url, output_path="screenshot.png"):
    """Captures full-page screenshot of a website."""
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--single-process",
                "--no-zygote"
            ]
        )
        page = browser.new_page()
        try:
            page.goto(url, wait_until="networkidle")
            #Scrolling to the bottom and right most corner to make sure all the images are loaded
            page.evaluate("""
                window.scrollTo(document.body.scrollWidth, document.body.scrollHeight);
            """)
            page.wait_for_timeout(5000) 
            page.screenshot(path=output_path, full_page=True)
            print(f"✅ Screenshot saved: {output_path}")
        except Exception as e:
            print(f"❌ Failed to load page: {e}")
            raise
        finally:
            browser.close()


def look_for_soc2_images(image_path):
    with open(image_path, "rb") as image_file:
        image_data = base64.b64encode(image_file.read()).decode("utf-8")

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {"role": "system", "content": "You are a visual design assistant."},
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "Verify whether this image has a SOC type II logo or not? Respond with yes or no with a 1 liner reasoning."
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{image_data}"
                        }
                    }
                ]
            }
        ],
        max_tokens=300
    )
    return response.choices[0].message.content.strip()

def fetch_url_text(url):
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        for tag in soup(['script', 'style']):
            tag.decompose()
        return soup.get_text(separator='\n', strip=True)
    except Exception as e:
        return f"Error fetching URL: {e}"

def look_for_soc2_content(text_content):
    try:
        prompt = (
            "Given a webpage data, determine if it appears to be SOC 2 compliant or not "
            "Just answer 'Yes' or 'No' followed by a reason in 1 liner.\n\n"
            f"Content:\n{text_content}"
        )

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            store=True,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        return response.choices[0].message.content.strip()

    except Exception as e:
        return f"Error calling OpenAI API: {e}"

def check_sco2_compliance_via_text(url):
    print(f"And now checking SOC2 compliance via text: {url}")
    page_text = fetch_url_text(url)
    if "Error" in page_text:
        return page_text
    return look_for_soc2_content(page_text)

def check_soc2_compliance_via_image(url, output_path):
    print(f"Checking SOC2 compliance via image: {url}")
    capture_screenshot(url, output_path)
    return look_for_soc2_images(output_path);

if __name__ == "__main__":
    url_input = input("Enter the URL to check for SCO2 compliance: ")
    image_path = f"/workspace/{domain_name}_full_shot.png"
    image_compliance = check_soc2_compliance_via_image(url_input, image_path)
    text_compliance = check_sco2_compliance_via_text(url_input);
    print("\nImage Result:\n", image_compliance)
    print("\nText Result:\n", text_compliance)
