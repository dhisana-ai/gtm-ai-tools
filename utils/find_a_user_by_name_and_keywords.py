"""Find a person's LinkedIn profile by searching their name with keywords."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
from typing import Optional
from urllib.parse import urlparse, urlunparse

from utils.common import search_google_serper, extract_user_linkedin_page

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

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
