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
from utils.extract_from_webpage import _get_structured_data_internal

try:
    from pydantic import BaseModel
except ImportError:  # pragma: no cover - tests use stub
    from pydantic_stub import BaseModel

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class LeadSearchResult(BaseModel):
    first_name: str = ""
    last_name: str = ""
    full_name: str = ""
    job_title: str = ""
    follower_count: int = 0
    lead_location: str = ""
    summary_about_lead: str = ""
    user_linkedin_url: str = ""


async def get_structured_output(text: str) -> LeadSearchResult:
    """Parse ``text`` into ``LeadSearchResult`` using OpenAI."""

    prompt = (
        "Extract lead details from the text below.\n"
        f"Return JSON matching this schema:\n{json.dumps(LeadSearchResult.model_json_schema(), indent=2)}\n\n"
        f"Text:\n{text}"
    )
    result, status = await _get_structured_data_internal(prompt, LeadSearchResult)
    if status != "SUCCESS" or result is None:
        return LeadSearchResult()
    return result

async def find_user_linkedin_url(full_name: str, search_keywords: str = "") -> dict:
    """Return lead info including the LinkedIn profile URL using Google search."""

    if not full_name:
        return json.loads(LeadSearchResult().model_dump_json())

    query = f'site:linkedin.com/in "{full_name}"'
    if search_keywords:
        query += f' "{search_keywords}"'

    logger.info("Querying Google: %s", query)
    results = await search_google_serper(query, 3)
    for item in results:
        text = " ".join(
            [item.get("title", ""), item.get("subtitle", ""), item.get("snippet", "")]
        ).strip()
        structured = await get_structured_output(text)
        link = item.get("link", "")
        if not link:
            continue
        parsed = urlparse(link)
        if "linkedin.com/in" in (parsed.netloc + parsed.path):
            structured.user_linkedin_url = extract_user_linkedin_page(link)
            return json.loads(structured.model_dump_json())
    logger.info("LinkedIn profile not found")
    return json.loads(LeadSearchResult().model_dump_json())


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

    info = asyncio.run(find_user_linkedin_url(args.full_name, args.search_keywords))
    info["search_keywords"] = args.search_keywords
    if not info.get("full_name"):
        info["full_name"] = args.full_name
    print(json.dumps(info, indent=2))


if __name__ == "__main__":
    main()
