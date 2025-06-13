"""Analyze website content, SEO, and visual appearance using Playwright and GPT-4o.

This module crawls a website, captures screenshots, extracts SEO-relevant information (such as title, meta description, canonical, robots, and H1 tags), and sends both the screenshots and extracted data to an LLM (GPT-4o) to answer user questions about the website, including SEO compliance, company details, and visual analysis.
"""
import os
import openai
import base64
import argparse
import uuid
import asyncio
from playwright.async_api import async_playwright
from contextlib import asynccontextmanager
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import aiohttp
import requests

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
            
async def extract_internal_links(page, base_url, max_links=4):
    """Extract up to max_links internal links from the page."""
    html = await page.content()
    soup = BeautifulSoup(html, "html.parser")
    links = set()
    base_domain = urlparse(base_url).netloc
    for a in soup.find_all("a", href=True):
        href = a["href"]
        abs_url = urljoin(base_url, href)
        if urlparse(abs_url).netloc == base_domain and abs_url.startswith("http"):
            links.add(abs_url)
        if len(links) >= max_links:
            break
    return list(links)

def extract_seo_info(html):
    """Extract SEO-relevant info from HTML."""
    soup = BeautifulSoup(html, "html.parser")
    seo = {}
    seo['title'] = soup.title.string.strip() if soup.title and soup.title.string else ''
    seo['meta_description'] = ''
    seo['meta_robots'] = ''
    seo['canonical'] = ''
    seo['h1'] = []
    for tag in soup.find_all('meta'):
        if tag.get('name', '').lower() == 'description':
            seo['meta_description'] = tag.get('content', '').strip()
        if tag.get('name', '').lower() == 'robots':
            seo['meta_robots'] = tag.get('content', '').strip()
    link_canonical = soup.find('link', rel='canonical')
    if link_canonical:
        seo['canonical'] = link_canonical.get('href', '').strip()
    seo['h1'] = [h1.get_text(strip=True) for h1 in soup.find_all('h1')]
    return seo

def fetch_robots_txt(base_url):
    """Fetch robots.txt content for a given base URL."""
    from urllib.parse import urlparse
    import requests
    parsed = urlparse(base_url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    try:
        resp = requests.get(robots_url, timeout=10)
        if resp.status_code == 200:
            return resp.text.strip()
        else:
            return f"robots.txt not found (status {resp.status_code})"
    except Exception as e:
        return f"Error fetching robots.txt: {e}"

async def crawl_and_capture_screenshots(start_url, out_dir, max_pages=5):
    """Crawl up to max_pages internal pages and capture screenshots and SEO info."""
    screenshots = []
    seo_infos = []
    visited = set()
    to_visit = [start_url]
    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    domain_name = urlparse(start_url).netloc.replace('.', '_')
    robots_txt = fetch_robots_txt(start_url)
    # Remove urlparse, use uuid for unique screenshot names
    async with playwright_browser() as browser:
        try:
            context = await browser.new_context(user_agent=user_agent)
            while to_visit and len(screenshots) < max_pages:
                url = to_visit.pop(0)
                if url in visited:
                    continue
                visited.add(url)
                try:
                    page = await context.new_page()
                    await page.goto(url, wait_until="load", timeout=30000)
                    img_path = f"/workspace/{uuid.uuid4().hex[:10]}_screenshot.png"
                    await page.screenshot(path=img_path, full_page=True)
                    screenshots.append(img_path)
                    html = await page.content()
                    seo_infos.append({'url': url, 'seo': extract_seo_info(html)})
                    # Extract more links from this page
                    if len(screenshots) < max_pages:
                        links = await extract_internal_links(page, url, max_links=max_pages-len(screenshots))
                        for link in links:
                            if link not in visited and link not in to_visit:
                                to_visit.append(link)
                    print(f"✅ Screenshot saved: {img_path}")
                    await asyncio.sleep(1)  # Add a short delay between page loads
                except Exception as e:
                    print(f"❌ Failed to process page {url}: {e}")
                finally:
                    try:
                        await page.close()
                    except Exception as close_err:
                        print(f"⚠️ Error closing page: {close_err}")
            await context.close()
        except Exception as main_err:
            print(f"❌ Error during crawling: {main_err}")
    return screenshots, seo_infos, robots_txt

def analyze_questions_with_gpt(image_paths, questions, seo_infos=None, robots_txt=None):
    """Sends screenshots, SEO info, and user questions to GPT-4o and returns answers."""
    images_content = []
    for image_path in image_paths:
        with open(image_path, "rb") as image_file:
            image_data = base64.b64encode(image_file.read()).decode("utf-8")
            images_content.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_data}"}})

    # Combine all questions into a single user message
    questions_text = "\n".join(f"Q{i+1}: {q}" for i, q in enumerate(questions))
    seo_text = ""
    if seo_infos:
        seo_text = "\nSEO Information for crawled pages:\n"
        for info in seo_infos:
            seo = info['seo']
            seo_text += f"URL: {info['url']}\nTitle: {seo.get('title','')}\nMeta Description: {seo.get('meta_description','')}\nMeta Robots: {seo.get('meta_robots','')}\nCanonical: {seo.get('canonical','')}\nH1s: {', '.join(seo.get('h1', []))}\n---\n"
    robots_text = f"\nrobots.txt:\n{robots_txt}\n" if robots_txt else ""
    messages = [
        {"role": "system", "content": "You are a web analysis assistant. Given screenshots, SEO information, and robots.txt of a website, answer the user's questions about the company, its products, SEO, partnerships, or any other visible information. If asked about SEO, use the provided SEO data and robots.txt."},
        {"role": "user", "content": [
            {"type": "text", "text": seo_text + robots_text + "\nPlease answer the following questions about this website. Respond clearly and concisely.\n" + questions_text},
            *images_content
        ]}
    ]

    response = openai.chat.completions.create(
        model="gpt-4o",
        messages=messages,
        max_tokens=1200
    )
    return response.choices[0].message.content.strip()

def main():
    parser = argparse.ArgumentParser(
        description="Get answers to questions about a list of websites using GPT-4o visual analysis"
    )
    parser.add_argument("url", help="Single website URL (string)")
    parser.add_argument("questions", help="Comma-separated questions string")
    args = parser.parse_args()

    # Read URLs
    urls = [args.url.strip()]

    # Read questions (comma-separated string)
    questions = [q.strip() for q in args.questions.split(",") if q.strip()]

    import tempfile
    import os
    results = []
    for url in urls:
        with tempfile.TemporaryDirectory() as tmpdir:
            screenshots, seo_infos, robots_txt = asyncio.run(crawl_and_capture_screenshots(url, tmpdir, max_pages=5))
            print(f"\n🔍 Analyzing {url} with GPT-4o...")
            answer = analyze_questions_with_gpt(screenshots, questions, seo_infos, robots_txt)
            results.append((url, answer))
            # Delete screenshots after analysis
            for img_path in screenshots:
                try:
                    os.remove(img_path)
                except Exception as e:
                    print(f"⚠️ Could not delete screenshot {img_path}: {e}")
    print("\n================= Website Analysis Results =================\n")
    for url, answer in results:
        print(f"🌐 Website: {url}\n------------------------------\n{answer}\n")

if __name__ == "__main__":
    main()