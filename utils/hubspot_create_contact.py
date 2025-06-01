"""Create a HubSpot contact if one with the same email or LinkedIn URL does not exist."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from typing import Optional

import aiohttp

API_BASE = "https://api.hubapi.com"


async def find_existing(session, headers, email: str = "", linkedin_url: str = "") -> Optional[str]:
    filters = []
    if email:
        filters.append({"propertyName": "email", "operator": "EQ", "value": email})
    if linkedin_url:
        filters.append({"propertyName": "hs_linkedin_url", "operator": "EQ", "value": linkedin_url})
    if not filters:
        return None
    payload = {"filterGroups": [{"filters": filters}], "limit": 1}
    url = f"{API_BASE}/crm/v3/objects/contacts/search"
    async with session.post(url, headers=headers, json=payload) as resp:
        data = await resp.json()
        results = data.get("results", [])
        return results[0]["id"] if results else None


async def create_contact(email: str = "", linkedin_url: str = "", first_name: str = "", last_name: str = "", phone: str = "") -> dict:
    api_key = os.getenv("HUBSPOT_API_KEY")
    if not api_key:
        raise RuntimeError("HUBSPOT_API_KEY environment variable is not set")

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    async with aiohttp.ClientSession() as session:
        existing = await find_existing(session, headers, email, linkedin_url)
        if existing:
            return {"id": existing, "existing": True}

        props = {}
        if email:
            props["email"] = email
        if linkedin_url:
            props["hs_linkedin_url"] = linkedin_url
        if first_name:
            props["firstname"] = first_name
        if last_name:
            props["lastname"] = last_name
        if phone:
            props["phone"] = phone

        url = f"{API_BASE}/crm/v3/objects/contacts"
        async with session.post(url, headers=headers, json={"properties": props}) as resp:
            return await resp.json()


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a HubSpot contact")
    parser.add_argument("--email", default="", help="Contact email")
    parser.add_argument("--linkedin_url", default="", help="LinkedIn profile URL")
    parser.add_argument("--first_name", default="", help="First name")
    parser.add_argument("--last_name", default="", help="Last name")
    parser.add_argument("--phone", default="", help="Phone number")
    args = parser.parse_args()

    result = asyncio.run(create_contact(args.email, args.linkedin_url, args.first_name, args.last_name, args.phone))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
