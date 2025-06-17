"""Locate a LinkedIn profile by job title at a target organization."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from urllib.parse import urlparse

from pathlib import Path
import csv
from utils.common import search_google_serper, extract_user_linkedin_page

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


async def find_user_linkedin_url_by_job_title(
    job_title: str,
    organization_name: str,
    search_keywords: str = "",
    exclude_profiles_intitle: bool = False,
) -> str:
    """Return the LinkedIn profile URL for a title at a given organization."""
    if not job_title or not organization_name:
        return ""

    query = f'site:linkedin.com/in "{organization_name}" "{job_title}"'
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


def _get_organization_name(row: dict[str, str]) -> str:
    """Extract an organization name from common CSV columns."""
    for key in ("organization_name", "company_name"):
        name = (row.get(key) or "").strip()
        if name:
            return name
    website = (row.get("website") or row.get("website_url") or "").strip()
    if website:
        parsed = urlparse(website)
        host = parsed.netloc.lower()
        if host.startswith("www."):
            host = host[4:]
        return host.split(".")[0]
    linkedin = (row.get("organization_linkedin_url") or "").strip()
    if linkedin:
        parsed = urlparse(linkedin)
        parts = parsed.path.strip("/").split("/")
        if len(parts) >= 2 and parts[0] == "company":
            return parts[1]
    return ""


def find_user_by_job_title_from_csv(
    input_file: str | Path,
    output_file: str | Path,
    *,
    job_title: str = "",
    organization_name: str = "",
    search_keywords: str = "",
    exclude_profiles_intitle: bool = False,
) -> None:
    """Look up LinkedIn profiles for rows in ``input_file`` and write CSV."""

    in_path = Path(input_file)
    out_path = Path(output_file)

    with in_path.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        fieldnames = reader.fieldnames or []
        rows = list(reader)

    if not any(
        f in fieldnames
        for f in [
            "company_name",
            "organization_name",
            "organization_linkedin_url",
            "website",
            "website_url",
        ]
    ):
        raise ValueError(
            "upload csv with organization_name or organization_linkedin_url or website column"
        )

    out_fields = ["job_title", "organization_name", "user_linkedin_url", "search_keywords"]
    processed: list[dict[str, str]] = []
    seen: set[str] = set()

    for row in rows:
        organization = _get_organization_name(row) or organization_name
        row_job_title = (row.get("job_title") or job_title).strip()
        if not row_job_title or not organization:
            continue
        keywords = (row.get("search_keywords") or search_keywords).strip()
        url = asyncio.run(
            find_user_linkedin_url_by_job_title(
                row_job_title,
                organization,
                keywords,
                exclude_profiles_intitle,
            )
        )
        if not url or url in seen:
            continue
        seen.add(url)
        processed.append(
            {
                "job_title": row_job_title,
                "organization_name": organization,
                "user_linkedin_url": url,
                "search_keywords": keywords,
            }
        )

    with out_path.open("w", newline="", encoding="utf-8") as out_fh:
        writer = csv.DictWriter(out_fh, fieldnames=out_fields)
        writer.writeheader()
        for row in processed:
            writer.writerow(row)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Find a LinkedIn profile by job title and organization using Google search",
    )
    parser.add_argument("job_title", help="User's job title")
    parser.add_argument("organization_name", help="Organization name")
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
            args.organization_name,
            args.search_keywords,
            args.exclude_profiles_intitle,
        )
    )
    result = {
        "job_title": args.job_title,
        "organization_name": args.organization_name,
        "user_linkedin_url": url,
        "search_keywords": args.search_keywords,
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
