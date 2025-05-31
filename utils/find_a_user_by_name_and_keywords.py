"""Utility to find a LinkedIn profile URL using a person's name and optional search keywords."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
from typing import List, Optional
from urllib.parse import urlparse, urlunparse

import aiohttp


logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


async def search_google_serper(
    query: str,
    number_of_results: int = 10,
    offset: int = 0,
    as_oq: Optional[str] = None,
) -> List[dict]:
    """Query Google via Serper.dev and return results as dictionaries."""

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
    """Return the canonical LinkedIn profile URL without query parameters."""
    parsed = urlparse(url)
    clean = parsed._replace(query="", fragment="")
    return urlunparse(clean)


async def find_user_linkedin_url(full_name: str, search_keywords: str = "") -> str:
    """Return the LinkedIn profile URL for a person using Google search."""

    if not full_name:
        return ""

    query = f'site:linkedin.com/in "{full_name}"'
    if search_keywords:
        query += f' "{search_keywords}"'

    logger.info("Querying Google: %s", query)
    results = await search_google_serper(query, 3)
    for item in results:
        link = item.get("link", "")
        if not link:
            continue
        parsed = urlparse(link)
        if "linkedin.com/in" in (parsed.netloc + parsed.path):
            return extract_user_linkedin_page(link)
    logger.info("LinkedIn profile not found")
    return ""


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Find a LinkedIn profile URL using the person's name and optional search keywords"
        )
    )
    parser.add_argument("full_name", help="Person's full name")
    parser.add_argument(
        "search_keywords",
        nargs="?",
        default="",
        help="Additional keywords to refine the search",
    )
    args = parser.parse_args()

    url = asyncio.run(find_user_linkedin_url(args.full_name, args.search_keywords))
    result = {
        "full_name": args.full_name,
        "user_linkedin_url": url,
        "search_keywords": args.search_keywords,
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
