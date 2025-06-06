"""Locate a LinkedIn profile by job title at a target company."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from urllib.parse import urlparse

from utils.common import search_google_serper, extract_user_linkedin_page

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


async def find_user_linkedin_url_by_job_title(
    job_title: str,
    company_name: str,
    search_keywords: str = "",
    exclude_profiles_intitle: bool = False,
) -> str:
    """Return the LinkedIn profile URL for a title at a given company."""
    if not job_title or not company_name:
        return ""

    query = f'site:linkedin.com/in "{company_name}" "{job_title}"'
    if search_keywords:
        query += f' "{search_keywords}"'
    if exclude_profiles_intitle:
        query += ' -intitle:"profiles"'

    logger.info("Querying Google: %s", query)
    results = await search_google_serper(query.strip(), 3)
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
        description="Find a LinkedIn profile by job title and company using Google search",
    )
    parser.add_argument("job_title", help="User's job title")
    parser.add_argument("company_name", help="Company name")
    parser.add_argument(
        "search_keywords",
        nargs="?",
        default="",
        help="Additional keywords to refine the search",
    )
    parser.add_argument(
        "--exclude_profiles_intitle",
        action="store_true",
        default=False,
        help="Exclude results where the page title includes 'profiles' (adds -intitle:\"profiles\", default: False)",
    )
    args = parser.parse_args()

    url = asyncio.run(
        find_user_linkedin_url_by_job_title(
            args.job_title,
            args.company_name,
            args.search_keywords,
            args.exclude_profiles_intitle,
        )
    )
    result = {
        "job_title": args.job_title,
        "company_name": args.company_name,
        "user_linkedin_url": url,
        "search_keywords": args.search_keywords,
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
