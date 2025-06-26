"""Scrape a web page's HTML using Playwright.

Great for capturing content from any site to feed into lead extraction or
research workflows."""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import random
from contextlib import asynccontextmanager
from typing import Any, Dict, Optional
from urllib.parse import urlparse

import httpx
from openai import OpenAI
from playwright.async_api import TimeoutError as PwTimeout
from playwright.async_api import async_playwright
from playwright_stealth import Stealth  # Stealth 2.0 API

from utils import common
from utils import large_token_parsing

COOKIE_FILE = str(common.get_output_dir() / "playwright_state.json")
CF_TITLE_JS = "document.title.toLowerCase().includes('just a moment')"

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36",
]
VIEWPORTS = [
    {"width": 1920, "height": 1080},
    {"width": 1366, "height": 768},
    {"width": 1440, "height": 900},
]
LOCALES = ["en-US", "en-GB", "en"]
CHALLENGE_INDICATORS = [
    "cf-turnstile",
    "hcaptcha.com",
    "recaptcha",
    "just a moment",
    "cloudflare",
    "challenge",
]

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Playwright stealth helper
stealth = Stealth()


async def apply_stealth(page_or_context) -> None:
    """Compatibility wrapper to apply stealth evasions."""
    await stealth.apply_stealth_async(page_or_context)


def parse_proxy(proxy_url: str) -> Dict[str, str]:
    u = urlparse(proxy_url)
    return {
        "server": f"{u.scheme}://{u.hostname}:{u.port}",
        "username": u.username or "",
        "password": u.password or "",
    }


def fingerprint() -> Dict[str, Any]:
    return {
        "user_agent": random.choice(USER_AGENTS),
        "viewport": random.choice(VIEWPORTS),
        "locale": random.choice(LOCALES),
        "timezone_id": "America/Los_Angeles",
        "geolocation": {"latitude": 37.7749, "longitude": -122.4194},
        "permissions": ["geolocation", "notifications"],
    }


async def _submit_and_poll(
    method: str, sitekey: str, page_url: str, api_key: str
) -> Optional[str]:
    data = {
        "key": api_key,
        "method": method,
        "googlekey" if method == "userrecaptcha" else "sitekey": sitekey,
        "pageurl": page_url,
        "json": 1,
    }
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post("http://2captcha.com/in.php", data=data)
        j = r.json()
        if j.get("status") != 1:
            logger.error("2Captcha submit error: %s", j)
            return None
        cap_id = j["request"]
        for _ in range(24):
            await asyncio.sleep(5)
            res = await client.get(
                "http://2captcha.com/res.php",
                params={"key": api_key, "action": "get", "id": cap_id, "json": 1},
            )
            jr = res.json()
            if jr.get("status") == 1:
                return jr["request"]
            if jr.get("request") != "CAPCHA_NOT_READY":
                logger.error("2Captcha error: %s", jr)
                return None
        return None


async def solve_any_captcha(page, url: str, api_key: Optional[str]):
    if not api_key:
        logger.info("No captcha key provided, skipping captcha check")
        return
    logger.info("Checking page for captcha challenges")
    ts_div = await page.query_selector("div.cf-turnstile[data-sitekey]")
    if ts_div:
        sk = await ts_div.get_attribute("data-sitekey")
        logger.info("Solving Cloudflare Turnstile captcha")
        token = await _submit_and_poll("turnstile", sk, url, api_key)
        if token:
            await page.evaluate(
                "(tok)=>{window.postMessage({cf-turnstile-response:tok},'*');}", token
            )
            await asyncio.sleep(2)
            logger.info("Turnstile captcha solved")
            return
    h_iframe = await page.query_selector("iframe[src*='hcaptcha.com']")
    if h_iframe:
        src = await h_iframe.get_attribute("src") or ""
        if "sitekey=" in src:
            sk = src.split("sitekey=")[1].split("&")[0]
            logger.info("Solving hCaptcha challenge")
            js = "(tok)=>{let el=document.querySelector('[name=\"h-captcha-response\"]')||document.createElement('textarea');el.name='h-captcha-response';el.style.display='none';el.value=tok;document.body.appendChild(el);}"
            token = await _submit_and_poll("hcaptcha", sk, url, api_key)
            if token:
                await page.evaluate(js, token)
                await asyncio.sleep(2)
                logger.info("hCaptcha solved")
                return
    r_iframe = await page.query_selector("iframe[src*='recaptcha']")
    if r_iframe:
        src = await r_iframe.get_attribute("src") or ""
        if "k=" in src:
            sk = src.split("k=")[1].split("&")[0]
            logger.info("Solving reCAPTCHA challenge")
            js = "(tok)=>{let el=document.querySelector('[name=\"g-recaptcha-response\"]')||document.createElement('textarea');el.name='g-recaptcha-response';el.style.display='none';el.value=tok;document.body.appendChild(el);}"
            token = await _submit_and_poll("userrecaptcha", sk, url, api_key)
            if token:
                await page.evaluate(js, token)
                await asyncio.sleep(2)
                logger.info("reCAPTCHA solved")


@asynccontextmanager
async def browser_ctx(proxy_url: Optional[str]):
    fp = fingerprint()
    async with async_playwright() as p:
        headless = os.getenv("HEADLESS", "true").lower() != "false"
        logger.info("Launching browser headless=%s", headless)
        launch: Dict[str, Any] = {
            "headless": headless,
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--ignore-certificate-errors",
            ],
        }
        if proxy_url:
            logger.info("Using proxy")
            launch["proxy"] = parse_proxy(proxy_url)
        browser = await p.chromium.launch(**launch)
        try:
            storage = COOKIE_FILE if os.path.exists(COOKIE_FILE) else None
            ctx = await browser.new_context(
                user_agent=fp["user_agent"],
                viewport=fp["viewport"],
                locale=fp["locale"],
                timezone_id=fp["timezone_id"],
                geolocation=fp["geolocation"],
                permissions=fp["permissions"],
                storage_state=storage,
                ignore_https_errors=True,
            )
            # Apply Stealth evasions to every page in the context
            await stealth.apply_stealth_async(ctx)
            yield ctx
            await ctx.storage_state(path=COOKIE_FILE)
        finally:
            await browser.close()


async def _extra_evasions(page):
    """Tiny manual evasions layered on top of Stealth."""
    await page.add_init_script(
        """
        Object.defineProperty(navigator, 'webdriver', { get: () => false });
        window.chrome = { runtime: {} };
        Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
        Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
        """
    )


async def new_page(context):
    """Create a new page with extra evasions applied."""
    page = await context.new_page()
    await _extra_evasions(page)
    return page


async def wait_for_cf_clearance(context, host: str, timeout: int = 60_000) -> bool:
    """Poll context cookies until the `cf_clearance` cookie appears."""
    for _ in range(int(timeout / 1_000)):
        for c in await context.cookies():
            if c["name"] == "cf_clearance" and host.endswith(c["domain"].lstrip(".")):
                logger.info("cf_clearance cookie present \u2714")
                return True
        await asyncio.sleep(1)
    logger.warning("cf_clearance cookie not set within timeout.")
    return False


async def _do_fetch(
    url: str, proxy_url: Optional[str], captcha_key: Optional[str]
) -> str:
    async with browser_ctx(proxy_url) as ctx:
        page = await new_page(ctx)

        # Human-like mouse movement
        await page.mouse.move(120, 120)
        await asyncio.sleep(0.4)

        for attempt in (1, 2):
            try:
                await page.goto(url, timeout=120_000, wait_until="domcontentloaded")
                break
            except PwTimeout:
                if attempt == 2:
                    raise
                logger.warning("Nav timeout, retrying…")

        if proxy_url:
            logger.info("Applying proxy fallback")
            if await page.evaluate(CF_TITLE_JS):
                logger.info("Waiting out Cloudflare JS challenge…")
                try:
                    await page.wait_for_function(f"!({CF_TITLE_JS})", timeout=60_000)
                except PwTimeout:
                    logger.warning("CF title never cleared (60 s)")

            await wait_for_cf_clearance(ctx, urlparse(url).hostname)
            await solve_any_captcha(page, url, captcha_key)
            logger.info("Proxy and captcha handling complete")

        # Lazy scroll and click "Show more" buttons
        last_height = None
        await asyncio.sleep(15)
        for _ in range(6):
            await page.mouse.wheel(0, 300)
            await asyncio.sleep(3)
            height = await page.evaluate("document.body.scrollHeight")
            if height == last_height:
                break
            last_height = height
        for btn in (await page.query_selector_all("text='Show more'"))[:3]:
            try:
                await btn.click()
                await asyncio.sleep(1)
            except Exception:
                pass

        logger.info("✓ Done  Title: %s", await page.title())
        wait_time = 30 if os.getenv("HEADLESS", "true").lower() == "false" else 5
        await asyncio.sleep(wait_time)
        return await page.content()


async def fetch_html(
    url: str, proxy_url: Optional[str] = None, captcha_key: Optional[str] = None
) -> str:
    if not proxy_url:
        logger.info("\ud83d\udd17 No proxy available, fetching directly")
        return await _do_fetch(url, None, captcha_key)

    try:
        logger.info("\ud83d\udd17 First attempting without proxy")
        html = await _do_fetch(url, None, captcha_key)
        html_lower = html.lower()

        if (
            "linkedin.com/in/" in html_lower
            or "linkedin.com/company" in html_lower
            or ("<a" in html_lower and 'target="_blank"' in html_lower)
        ):
            logger.info("\u2713 LinkedIn or target=_blank: returning direct content")
            return html

        if not any(marker in html_lower for marker in CHALLENGE_INDICATORS):
            logger.info("\u2713 Successful fetch without proxy")
            return html

        logger.info("\ud83d\udd33 Challenge detected, retrying with proxy %s", proxy_url)
    except Exception as exc:
        logger.warning("Initial fetch without proxy failed: %s", exc)

    logger.info("\U0001f310 Using proxy for fetch")
    return await _do_fetch(url, proxy_url, captcha_key)


def summarize_html(text: str, instructions: str) -> str:
    """Return a summary of ``text`` using the OpenAI Responses API."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY environment variable is not set")
    client = OpenAI(api_key=api_key)
    response = client.responses.create(
        model=common.get_openai_model(),
        input=f"{instructions}\n\n{text}",
    )
    return getattr(response, "output_text", "")

def fetch_external(text: str) -> str:
    instructions = "Attached is the data from a website link, can you please list all the external links in the data with name and their contacts or link? Don't give any extra details"

    # Handles text either by chunking or directly based on the number of tokens
    return large_token_parsing.handle_text_with_instruction(text, instructions);

def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch HTML using Playwright")
    parser.add_argument("url", help="URL to fetch")
    parser.add_argument("--summarize", action="store_true", help="Summarize content")
    parser.add_argument(
        "--instructions",
        default="Summarize the following text",
        help="Summarization instructions",
    )
    args = parser.parse_args()
    proxy_url = os.getenv("PROXY_URL")
    captcha = os.getenv("TWO_CAPTCHA_API_KEY")
    html = asyncio.run(fetch_html(args.url, proxy_url, captcha))
    if args.summarize:
        output = summarize_html(html, args.instructions)
    elif args.fetchExternal:
        output = fetch_external(html)
    elif:
        output = html
    print(output)


if __name__ == "__main__":
    main()
