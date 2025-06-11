"""Extract primary and secondary colors from any web page.

This module scrapes a page with Playwright and then asks an LLM to return
primary and secondary colors used in the web page."""
import os
import openai
import base64
import argparse
import uuid
import asyncio
from playwright.async_api import async_playwright
from contextlib import asynccontextmanager
# Configuration
API_KEY = os.getenv("OPENAI_API_KEY")
openai.api_key = API_KEY

@asynccontextmanager
async def playwright_browser():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
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
        try:
            yield browser
        finally:
            await browser.close()

async def capture_screenshot_async(url, output_path="screenshot.png"):
    """Captures full-page screenshot of a website using async Playwright."""
    async with playwright_browser() as browser:
        page = await browser.new_page()
        try:
            await page.goto(url, wait_until="load", timeout=30000)
            await page.screenshot(path=output_path, full_page=True)
            print(f"✅ Screenshot saved: {output_path}")
        except Exception as e:
            print(f"❌ Failed to load page: {e}")
            raise
        finally:
            await page.close()
            
def analyze_colors_with_gpt(image_path):
    """Sends screenshot to GPT-4o to analyze primary and secondary colors."""
    with open(image_path, "rb") as image_file:
        image_data = base64.b64encode(image_file.read()).decode("utf-8")

    response = openai.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are a visual design assistant."},
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "What are the primary and secondary colors used in this website design? Respond with color names or hex codes."
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

def main():
    parser = argparse.ArgumentParser(
        description="Get primary and secondary colors used across a website"
    )
    parser.add_argument("url", nargs="?", help="Website URL")
    args = parser.parse_args()

    url = args.url
    if not url:
        url = input("Enter website URL: ").strip()
    # Generate a random name for the screenshot file instead of using tldextract
    domain_name = str(uuid.uuid4())[:10]
    image_path = f"/workspace/{domain_name}_screenshot.png"
    asyncio.run(capture_screenshot_async(url, image_path))

    print("🔍 Analyzing image with GPT-4o...")
    result = analyze_colors_with_gpt(image_path)

    print("\n🎨 Color Analysis Result:")
    print(result)

    # Delete the screenshot after analysis
    if os.path.exists(image_path):
        os.remove(image_path)

if __name__ == "__main__":
    main()