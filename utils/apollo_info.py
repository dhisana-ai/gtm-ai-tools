"""Utilities for fetching person and company info from Apollo.io."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from typing import Any, Dict

import aiohttp

from utils.find_company_info import extract_domain

API_BASE = "https://api.apollo.io/api/v1"


async def get_person_info(linkedin_url: str = "", email: str = "") -> Dict[str, Any]:
    """Return person details from Apollo.io using LinkedIn URL or email."""
    api_key = os.getenv("APOLLO_API_KEY")
    if not api_key:
        raise RuntimeError("APOLLO_API_KEY environment variable is not set")

    if not linkedin_url and not email:
        raise RuntimeError("Provide linkedin_url or email")

    headers = {"X-Api-Key": api_key, "Content-Type": "application/json"}
    payload: Dict[str, Any] = {}
    if linkedin_url:
        payload["linkedin_url"] = linkedin_url
    if email:
        payload["email"] = email

    async with aiohttp.ClientSession() as session:
        url = f"{API_BASE}/people/match"
        async with session.post(url, headers=headers, json=payload) as resp:
            return await resp.json()


async def get_company_info(company_url: str = "", primary_domain: str = "") -> Dict[str, Any]:
    """Return organization details from Apollo.io using company URL or domain."""
    api_key = os.getenv("APOLLO_API_KEY")
    if not api_key:
        raise RuntimeError("APOLLO_API_KEY environment variable is not set")

    domain = primary_domain or ""
    if company_url and not domain:
        domain = extract_domain(company_url)
    if not domain:
        raise RuntimeError("Provide company_url or primary_domain")

    headers = {"X-Api-Key": api_key, "Content-Type": "application/json"}
    async with aiohttp.ClientSession() as session:
        url = f"{API_BASE}/organizations/enrich?domain={domain}"
        async with session.get(url, headers=headers) as resp:
            return await resp.json()


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch info from Apollo.io")
    parser.add_argument("--linkedin_url", default="", help="Person LinkedIn URL")
    parser.add_argument("--email", default="", help="Person email")
    parser.add_argument("--company_url", default="", help="Company website URL")
    parser.add_argument("--primary_domain", default="", help="Company domain")
    args = parser.parse_args()

    if args.linkedin_url or args.email:
        result = asyncio.run(get_person_info(args.linkedin_url, args.email))
    else:
        result = asyncio.run(get_company_info(args.company_url, args.primary_domain))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
