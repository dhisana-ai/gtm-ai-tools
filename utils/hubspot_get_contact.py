"""Find a HubSpot contact by ID, email or LinkedIn URL."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from typing import Optional

import aiohttp


API_BASE = "https://api.hubapi.com"


async def get_contact(hubspot_id: str = "", email: str = "", linkedin_url: str = "") -> Optional[dict]:
    """Return the first matching contact or ``None`` if not found."""
    api_key = os.getenv("HUBSPOT_API_KEY")
    if not api_key:
        raise RuntimeError("HUBSPOT_API_KEY environment variable is not set")

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    async with aiohttp.ClientSession() as session:
        if hubspot_id:
            url = f"{API_BASE}/crm/v3/objects/contacts/{hubspot_id}"
            async with session.get(url, headers=headers) as resp:
                return await resp.json()

        filters = []
        if email:
            filters.append({"propertyName": "email", "operator": "EQ", "value": email})
        if linkedin_url:
            filters.append({"propertyName": "hs_linkedin_url", "operator": "EQ", "value": linkedin_url})
        if not filters:
            raise RuntimeError("Provide hubspot_id, email or linkedin_url")

        payload = {"filterGroups": [{"filters": filters}], "limit": 1}
        url = f"{API_BASE}/crm/v3/objects/contacts/search"
        async with session.post(url, headers=headers, json=payload) as resp:
            data = await resp.json()
            results = data.get("results", [])
            return results[0] if results else None


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch a HubSpot contact")
    parser.add_argument("--id", dest="hubspot_id", default="", help="HubSpot contact ID")
    parser.add_argument("--email", default="", help="Contact email")
    parser.add_argument("--linkedin_url", default="", help="LinkedIn profile URL")
    args = parser.parse_args()

    result = asyncio.run(get_contact(args.hubspot_id, args.email, args.linkedin_url))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
