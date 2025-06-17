"""Discover a company's website, domain and LinkedIn page to build account lists."""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import logging
import re
import urllib.parse
from pathlib import Path
from typing import List, Optional
from urllib.parse import urlparse, urlunparse

import aiohttp
from bs4 import BeautifulSoup
from utils.common import search_google_serper

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)




def extract_company_page(url: str) -> str:
    """Return the canonical LinkedIn company page URL."""
    if not url:
        return ""

    normalized = re.sub(
        r"(https?://)?([\w\-]+\.)?linkedin\.com",
        "https://www.linkedin.com",
        url,
    )

    parsed = urlparse(normalized)
    parts = parsed.path.strip("/").split("/")

    if len(parts) >= 2 and parts[0] == "company":
        slug = parts[1]
        return f"https://www.linkedin.com/company/{slug}"

    return ""


async def find_organization_linkedin_url(
    company_name: str,
    company_location: Optional[str] = None,
) -> str:
    """Find the LinkedIn URL for a company using Google search."""

    if not company_name:
        return ""

    logger.info(
        "Searching LinkedIn URL for '%s'%s",
        company_name,
        f" in {company_location}" if company_location else "",
    )

    if company_location:
        queries = [
            f'site:linkedin.com/company "{company_name}" {company_location} -intitle:"jobs" ',
            f'site:linkedin.com/company {company_name} {company_location} -intitle:"jobs" ',
        ]
    else:
        queries = [
            f'site:linkedin.com/company "{company_name}" -intitle:"jobs" ',
            f'site:linkedin.com/company {company_name} -intitle:"jobs" '
        ]

    for query in queries:
        query = query.strip()
        logger.info("Querying Google: %s", query)
        results = await search_google_serper(query, 3)
        for item in results:
            link = item.get("link", "")
            if not link:
                continue
            parsed = urlparse(link)
            if "linkedin.com/company" in (parsed.netloc + parsed.path):
                clean = extract_company_page(link)
                logger.info("Found LinkedIn page: %s", clean)
                return clean
    logger.info("LinkedIn URL not found")
    return ""


async def get_external_links(url: str) -> List[str]:
    """Return external links found on the given page."""
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(url, allow_redirects=True) as response:
                if response.status == 200:
                    content = await response.text()
                    soup = BeautifulSoup(content, "html.parser")
                    links: List[str] = []
                    for tag in soup.find_all("a", href=True):
                        href = tag["href"]
                        if href.startswith("http") and not href.startswith(url):
                            links.append(href)
                    return links
    except Exception:
        logger.exception("Failed to fetch external links")
    return []


async def get_company_website_from_linkedin_url(linkedin_url: str) -> str:
    """Attempt to extract a company's website from its LinkedIn page."""
    if not linkedin_url:
        return ""
    logger.info("Fetching website from LinkedIn page: %s", linkedin_url)
    links = await get_external_links(linkedin_url)
    for link in links:
        if "trk=about_website" in link:
            parsed_link = urllib.parse.urlparse(link)
            query_params = urllib.parse.parse_qs(parsed_link.query)
            if "url" in query_params:
                encoded_url = query_params["url"][0]
                website = urllib.parse.unquote(encoded_url)
                logger.info("Found website via LinkedIn: %s", website)
                return website
    return ""


async def find_company_website(company_name: str, company_location: Optional[str] = None) -> str:
    """Search Google for the company's official website."""
    if company_location:
        query = f'"{company_name}" {company_location} official website'
    else:
        query = f'"{company_name}" official website'
    logger.info("Searching company website with query: %s", query)

    results = await search_google_serper(query, 5)
    for item in results:
        link = item.get("link", "")
        if not link:
            continue
        if any(domain in link for domain in ["linkedin.com", "facebook.com", "instagram.com", "twitter.com"]):
            continue
        logger.info("Found website via Google: %s", link)
        return link
    return ""


def extract_domain(url: str) -> str:
    """Extract the domain from a URL."""
    if not url:
        return ""
    parsed = urlparse(url)
    return parsed.netloc.lower()


async def find_company_details(
    organization_name: str = "",
    organization_location: Optional[str] = None,
    organization_linkedin_url: str = "",
    organization_website: str = "",
) -> dict:
    """Return website, domain and LinkedIn URL for a company."""

    logger.info("Finding details for company '%s'", organization_name)

    linkedin_url = extract_company_page(organization_linkedin_url)
    website = organization_website.strip()

    if not linkedin_url and organization_name:
        linkedin_url = await find_organization_linkedin_url(
            organization_name, organization_location
        )

    if not website and linkedin_url:
        website = await get_company_website_from_linkedin_url(linkedin_url)

    if not website and organization_name:
        website = await find_company_website(organization_name, organization_location)

    domain = extract_domain(website)

    result = {
        "organization_name": organization_name,
        "organization_website": website,
        "primary_domain_of_organization": domain,
        "organization_linkedin_url": linkedin_url,
    }
    logger.info("Lookup result: %s", result)
    return result


def find_company_info_from_csv(input_file: str | Path, output_file: str | Path) -> None:
    """Look up company details for each row of ``input_file`` and write results."""

    in_path = Path(input_file)
    out_path = Path(output_file)

    with in_path.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        fieldnames = reader.fieldnames or []
        rows = list(reader)

    if not any(
        f in fieldnames
        for f in ["organization_name", "organization_linkedin_url", "organization_website"]
    ):
        raise ValueError(
            "upload csv with organization_name, organization_linkedin_url or organization_website column"
        )

    extra_fields = [
        "organization_name",
        "organization_website",
        "primary_domain_of_organization",
        "organization_linkedin_url",
    ]

    out_fields = list(fieldnames)
    for f in extra_fields:
        if f not in out_fields:
            out_fields.append(f)

    processed: list[dict] = []
    for row in rows:
        info = asyncio.run(
            find_company_details(
                row.get("organization_name", ""),
                None,
                row.get("organization_linkedin_url", ""),
                row.get("organization_website", ""),
            )
        )
        for key, value in info.items():
            if value and not row.get(key):
                row[key] = value
        processed.append(row)

    with out_path.open("w", newline="", encoding="utf-8") as out_fh:
        writer = csv.DictWriter(out_fh, fieldnames=out_fields)
        writer.writeheader()
        for row in processed:
            writer.writerow(row)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Find company website, domain and LinkedIn URL using Google search",
    )
    parser.add_argument("--organization_name", default="", help="Organization name")
    parser.add_argument("--location", default="", help="Organization location")
    parser.add_argument(
        "--organization_linkedin_url", default="", help="Organization LinkedIn URL"
    )
    parser.add_argument(
        "--organization_website",
        default="",
        help="Organization website URL",
    )
    args = parser.parse_args()

    if not (
        args.organization_name or args.organization_linkedin_url or args.organization_website
    ):
        parser.error(
            "provide organization_name, organization_linkedin_url or organization_website"
        )

    logger.info("Starting company lookup")

    result = asyncio.run(
        find_company_details(
            args.organization_name,
            args.location,
            args.organization_linkedin_url,
            args.organization_website,
        )
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
