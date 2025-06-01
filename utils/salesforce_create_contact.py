"""Create a Salesforce contact if one with the same email doesn't already exist."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from typing import Optional

import aiohttp

API_VERSION = "v59.0"


async def find_existing(session, headers, email: str = "") -> Optional[str]:
    if not email:
        return None
    q = f"SELECT Id FROM Contact WHERE Email='{email}' LIMIT 1"
    url = f"{os.getenv('SALESFORCE_INSTANCE_URL')}/services/data/{API_VERSION}/query/"
    async with session.get(url, headers=headers, params={"q": q}) as resp:
        data = await resp.json()
        records = data.get("records", [])
        return records[0]["Id"] if records else None


async def create_contact(email: str = "", first_name: str = "", last_name: str = "", phone: str = "") -> dict:
    instance = os.getenv("SALESFORCE_INSTANCE_URL")
    token = os.getenv("SALESFORCE_ACCESS_TOKEN")
    if not instance or not token:
        raise RuntimeError(
            "SALESFORCE_INSTANCE_URL and SALESFORCE_ACCESS_TOKEN must be set"
        )

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    async with aiohttp.ClientSession() as session:
        existing = await find_existing(session, headers, email)
        if existing:
            return {"id": existing, "existing": True}

        props = {}
        if first_name:
            props["FirstName"] = first_name
        if last_name:
            props["LastName"] = last_name
        if email:
            props["Email"] = email
        if phone:
            props["Phone"] = phone

        url = f"{instance}/services/data/{API_VERSION}/sobjects/Contact"
        async with session.post(url, headers=headers, json=props) as resp:
            return await resp.json()


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a Salesforce contact")
    parser.add_argument("--email", default="", help="Contact email")
    parser.add_argument("--first_name", default="", help="First name")
    parser.add_argument("--last_name", default="", help="Last name")
    parser.add_argument("--phone", default="", help="Phone number")
    args = parser.parse_args()

    result = asyncio.run(create_contact(args.email, args.first_name, args.last_name, args.phone))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
