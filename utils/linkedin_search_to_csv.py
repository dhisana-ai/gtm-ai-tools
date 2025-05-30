"""Utility to fetch LinkedIn profile URLs from Google via SerpAPI and write them to CSV."""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import logging
import os
from typing import List, Optional
from urllib.parse import urlparse, urlunparse

import aiohttp


logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


async def search_google_serpai(
    query: str,
    number_of_results: int = 10,
    offset: int = 0,
    as_oq: Optional[str] = None,
) -> List[dict]:
    """Query Google via SerpAPI and return results as dictionaries."""

    serpapi_key = os.getenv("SERAPI_API_KEY")
    if not serpapi_key:
        raise RuntimeError("SERAPI_API_KEY environment variable is not set")

    base_url = "https://serpapi.com/search"
    page_size = 100
    start_index = offset
    all_items: list[dict] = []
    seen_links: set[str] = set()

    def _extract_block_results(block: str, data: list[dict]) -> list[dict]:
        mapped: list[dict] = []
        if block == "organic_results":
            for it in data:
                link = it.get("link")
                if link:
                    mapped.append(it)
        elif block == "inline_images":
            for it in data:
                link = it.get("source")
                if link:
                    mapped.append({
                        "title": it.get("title"),
                        "link": link,
                        "type": "inline_image",
                        "source_name": it.get("source_name"),
                        "thumbnail": it.get("thumbnail"),
                    })
        elif block == "news_results":
            for it in data:
                link = it.get("link")
                if link:
                    mapped.append(it)
        return mapped

    async with aiohttp.ClientSession() as session:
        while len(all_items) < number_of_results:
            to_fetch = min(page_size, number_of_results - len(all_items))
            params = {
                "engine": "google",
                "api_key": serpapi_key,
                "q": query,
                "num": to_fetch,
                "start": start_index,
                "location": "United States",
            }
            if as_oq:
                params["as_oq"] = as_oq

            async with session.get(base_url, params=params) as resp:
                resp.raise_for_status()
                result = await resp.json()

            page_items: list[dict] = []
            for block_name in ("organic_results", "inline_images", "news_results"):
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

            start_index += to_fetch

    return all_items[:number_of_results]


def extract_user_linkedin_page(url: str) -> str:
    """Return the canonical LinkedIn profile URL without query parameters."""
    parsed = urlparse(url)
    clean = parsed._replace(query="", fragment="")
    return urlunparse(clean)


def linkedin_search_to_csv(query: str, number_of_results: int, output_file: str) -> None:
    """Search Google for LinkedIn profile URLs and write them to a CSV."""

    results = asyncio.run(search_google_serpai(query, number_of_results))
    linkedin_urls: List[str] = []

    for item in results:
        link = item.get("link", "")
        if not link:
            continue
        parsed_url = urlparse(link)
        if "linkedin.com/in" in (parsed_url.netloc + parsed_url.path):
            linkedin_urls.append(extract_user_linkedin_page(link))

    with open(output_file, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["user_linkedin_url"])
        writer.writeheader()
        for url in linkedin_urls:
            writer.writerow({"user_linkedin_url": url})

    logger.info("Wrote %d LinkedIn URLs to %s", len(linkedin_urls), output_file)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Search Google via SerpAPI for LinkedIn profile URLs and output them to CSV"
    )
    parser.add_argument("query", help="Google search query")
    parser.add_argument("output_file", help="CSV file to create")
    parser.add_argument(
        "-n",
        "--num",
        type=int,
        default=10,
        help="Number of search results to fetch",
    )
    args = parser.parse_args()

    linkedin_search_to_csv(args.query, args.num, args.output_file)


if __name__ == "__main__":
    main()

