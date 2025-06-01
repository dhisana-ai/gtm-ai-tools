"""Update fields on a Salesforce contact."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from typing import Dict

import aiohttp

API_VERSION = "v59.0"


async def update_contact(contact_id: str, properties: Dict[str, str]) -> dict:
    instance = os.getenv("SALESFORCE_INSTANCE_URL")
    token = os.getenv("SALESFORCE_ACCESS_TOKEN")
    if not instance or not token:
        raise RuntimeError(
            "SALESFORCE_INSTANCE_URL and SALESFORCE_ACCESS_TOKEN must be set"
        )

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    url = f"{instance}/services/data/{API_VERSION}/sobjects/Contact/{contact_id}"
    async with aiohttp.ClientSession() as session:
        async with session.patch(url, headers=headers, json=properties) as resp:
            if resp.status == 204:
                return {"success": True}
            return await resp.json()


def main() -> None:
    parser = argparse.ArgumentParser(description="Update a Salesforce contact")
    parser.add_argument("--id", required=True, help="Salesforce contact ID")
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
