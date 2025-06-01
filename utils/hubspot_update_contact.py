"""Update fields on a HubSpot contact."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from typing import Dict

import aiohttp

API_BASE = "https://api.hubapi.com"


async def update_contact(contact_id: str, properties: Dict[str, str]) -> dict:
    api_key = os.getenv("HUBSPOT_API_KEY")
    if not api_key:
        raise RuntimeError("HUBSPOT_API_KEY environment variable is not set")

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    url = f"{API_BASE}/crm/v3/objects/contacts/{contact_id}"
    async with aiohttp.ClientSession() as session:
        async with session.patch(url, headers=headers, json={"properties": properties}) as resp:
            return await resp.json()


def main() -> None:
    parser = argparse.ArgumentParser(description="Update a HubSpot contact")
    parser.add_argument("--id", required=True, help="HubSpot contact ID")
    parser.add_argument("properties", nargs="+", help="key=value pairs")
    args = parser.parse_args()

    props = {}
    for item in args.properties:
        if "=" in item:
            k, v = item.split("=", 1)
            props[k] = v
    result = asyncio.run(update_contact(args.id, props))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
