"""Add a note to an existing Salesforce contact."""

from __future__ import annotations

import argparse
import asyncio
import json
import os

import aiohttp

API_VERSION = "v59.0"


async def add_note(contact_id: str, note: str, title: str = "Note") -> dict:
    instance = os.getenv("SALESFORCE_INSTANCE_URL")
    token = os.getenv("SALESFORCE_ACCESS_TOKEN")
    if not instance or not token:
        raise RuntimeError(
            "SALESFORCE_INSTANCE_URL and SALESFORCE_ACCESS_TOKEN must be set"
        )

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    url = f"{instance}/services/data/{API_VERSION}/sobjects/Note"
    payload = {"Title": title, "Body": note, "ParentId": contact_id}
    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=payload) as resp:
            return await resp.json()


def main() -> None:
    parser = argparse.ArgumentParser(description="Add a note to a Salesforce contact")
    parser.add_argument("--id", required=True, help="Salesforce contact ID")
    parser.add_argument("--note", required=True, help="Note text")
    args = parser.parse_args()

    result = asyncio.run(add_note(args.id, args.note))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
