"""Utility to find a company's website, primary domain and LinkedIn URL."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import re
import urllib.parse
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


async def find_company_details(company_name: str, company_location: Optional[str] = None) -> dict:
    """Return website, primary domain and LinkedIn URL for a company."""
    logger.info("Finding details for company '%s'", company_name)
    linkedin_url = await find_organization_linkedin_url(company_name, company_location)
    website = await get_company_website_from_linkedin_url(linkedin_url)
    if not website:
        website = await find_company_website(company_name, company_location)
    domain = extract_domain(website)
    result = {
        "company_website": website,
        "company_domain": domain,
        "linkedin_url": linkedin_url,
    }
    logger.info("Lookup result: %s", result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Find company website, domain and LinkedIn URL using Google search",
    )
    parser.add_argument("company_name", help="Name of the company to search for")
    parser.add_argument("-l", "--location", help="Optional company location")
    args = parser.parse_args()

    logger.info("Starting company lookup: %s", args.company_name)

    result = asyncio.run(find_company_details(args.company_name, args.location))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
