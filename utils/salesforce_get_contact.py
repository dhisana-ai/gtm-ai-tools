"""Retrieve a Salesforce contact by ID or email."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from typing import Optional

import aiohttp

API_VERSION = "v59.0"


async def get_contact(contact_id: str = "", email: str = "") -> Optional[dict]:
    """Return the first matching contact or ``None`` if not found."""
    instance = os.getenv("SALESFORCE_INSTANCE_URL")
    token = os.getenv("SALESFORCE_ACCESS_TOKEN")
    if not instance or not token:
        raise RuntimeError(
            "SALESFORCE_INSTANCE_URL and SALESFORCE_ACCESS_TOKEN must be set"
        )

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    async with aiohttp.ClientSession() as session:
        if contact_id:
            url = f"{instance}/services/data/{API_VERSION}/sobjects/Contact/{contact_id}"
            async with session.get(url, headers=headers) as resp:
                if resp.status == 404:
                    return None
                return await resp.json()

        if email:
            q = (
                "SELECT Id, FirstName, LastName, Email FROM Contact "
                f"WHERE Email='{email}' LIMIT 1"
            )
            url = f"{instance}/services/data/{API_VERSION}/query/"
            async with session.get(url, headers=headers, params={"q": q}) as resp:
                data = await resp.json()
                records = data.get("records", [])
                return records[0] if records else None

        raise RuntimeError("Provide contact_id or email")


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch a Salesforce contact")
    parser.add_argument("--id", dest="contact_id", default="", help="Salesforce contact ID")
    parser.add_argument("--email", default="", help="Contact email")
    args = parser.parse_args()

    result = asyncio.run(get_contact(args.contact_id, args.email))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
