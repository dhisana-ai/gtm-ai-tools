from __future__ import annotations

import os
import re
import aiohttp
from typing import List, Optional
from urllib.parse import urlparse, urlunparse


async def search_google_serper(
    query: str,
    number_of_results: int = 10,
    offset: int = 0,
    as_oq: Optional[str] = None,
) -> List[dict]:
    """Query Google via Serper.dev and return results as dictionaries."""

    # Remove any Byte Order Mark or extraneous whitespace
    query = query.replace("\ufeff", "").strip()

    serper_key = os.getenv("SERPER_API_KEY")
    if not serper_key:
        raise RuntimeError("SERPER_API_KEY environment variable is not set")

    base_url = "https://google.serper.dev/search"
    page = offset + 1
    all_items: list[dict] = []
    seen_links: set[str] = set()

    def _extract_block_results(block: str, data: list[dict]) -> list[dict]:
        mapped: list[dict] = []
        if block == "organic":
            for it in data:
                link = it.get("link")
                if link:
                    mapped.append(it)
        elif block == "images":
            for it in data:
                link = it.get("imageUrl") or it.get("link") or it.get("source")
                if link:
                    mapped.append(
                        {
                            "title": it.get("title"),
                            "link": link,
                            "type": "image",
                            "thumbnail": it.get("thumbnailUrl") or it.get("thumbnail"),
                        }
                    )
        elif block == "news":
            for it in data:
                link = it.get("link")
                if link:
                    mapped.append(it)
        return mapped

    async with aiohttp.ClientSession() as session:
        while len(all_items) < number_of_results:
            payload = {
                "q": query if not as_oq else f"{query} {as_oq}",
                "gl": "us",
                "hl": "en",
                "autocorrect": True,
                "page": page,
                "type": "search",
            }
            headers = {"X-API-KEY": serper_key, "Content-Type": "application/json"}

            async with session.post(base_url, headers=headers, json=payload) as resp:
                resp.raise_for_status()
                result = await resp.json()

            page_items: list[dict] = []
            for block_name in ("organic", "images", "news"):
                data = result.get(block_name) or []
                page_items.extend(_extract_block_results(block_name, data))

            new_added = 0
            for it in page_items:
                link = it["link"]
                if link not in seen_links:
                    seen_links.add(link)
                    all_items.append(it)
                    new_added += 1
                    if len(all_items) >= number_of_results:
                        break
            if new_added == 0:
                break

            page += 1

    return all_items[:number_of_results]


def extract_user_linkedin_page(url: str) -> str:
    """Return the canonical LinkedIn profile URL."""
    if not url:
        return ""

    # Replace different schemes or subdomains with the standard one
    normalized = re.sub(
        r"(https?://)?([\w\-]+\.)?linkedin\.com",
        "https://www.linkedin.com",
        url,
    )

    parsed = urlparse(normalized)
    parts = parsed.path.strip("/").split("/")

    if len(parts) >= 2 and parts[0] in {"in", "pub"}:
        slug = parts[1]
        return f"https://www.linkedin.com/in/{slug}"

    return ""


def get_openai_model() -> str:
    """Return the OpenAI model name from the environment or the default."""
    return os.getenv("OPENAI_MODEL_NAME", "gpt-4.1")


def get_output_dir() -> Path:
    """Return a directory for writing outputs and intermediate files."""
    import tempfile
    from pathlib import Path

    data_root = Path("/data")
    if data_root.is_dir():
        out_dir = data_root / "interim_tool_outputs"
    else:
        out_dir = Path(tempfile.gettempdir())
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def make_temp_csv_filename(tool: str) -> str:
    """Return a lowercase CSV path like ``toolname_YYYYMMDD_HHMMSS.csv``."""
    import datetime
    from pathlib import Path

    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    name = f"{tool}_{ts}.csv".lower()
    path = get_output_dir() / name
    path.touch()
    return str(path)
