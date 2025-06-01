"""Log a note on an existing HubSpot contact."""

from __future__ import annotations

import argparse
import asyncio
import json
import os

import aiohttp

API_BASE = "https://api.hubapi.com"


async def add_note(contact_id: str, note: str) -> dict:
    api_key = os.getenv("HUBSPOT_API_KEY")
    if not api_key:
        raise RuntimeError("HUBSPOT_API_KEY environment variable is not set")

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    url = f"{API_BASE}/crm/v3/objects/notes"
    payload = {
        "properties": {"hs_note_body": note},
        "associations": [
            {
                "to": {"id": contact_id, "type": "contact"},
                "types": [
                    {"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 202}
                ],
            }
        ],
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=payload) as resp:
            return await resp.json()


def main() -> None:
    parser = argparse.ArgumentParser(description="Add a note to a HubSpot contact")
    parser.add_argument("--id", required=True, help="HubSpot contact ID")
    parser.add_argument("--note", required=True, help="Note text")
    args = parser.parse_args()

    result = asyncio.run(add_note(args.id, args.note))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
