"""Get a prospect's email and phone number using Findymail."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
from typing import Any, Dict

import aiohttp

API_BASE = "https://app.findymail.com/api"

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


async def find_email_and_phone(full_name: str, domain: str) -> Dict[str, Any]:
    """Return e-mail and phone number for ``full_name`` at ``domain``."""
    api_key = os.getenv("FINDYMAIL_API_KEY")
    if not api_key:
        raise RuntimeError("FINDYMAIL_API_KEY environment variable is not set")

    if not full_name or not domain:
        return {"email": "", "phone": "", "contact_info": ""}

    url = f"{API_BASE}/search/name"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {"name": full_name, "domain": domain}

    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=payload) as resp:
            data = await resp.json()

    contact = data.get("contact") or {}
    email = contact.get("email", "")
    phone = ""
    for key in [
        "phone",
        "phone_number",
        "phoneNumber",
        "phoneNumbers",
        "phones",
        "mobile",
    ]:
        val = contact.get(key)
        if isinstance(val, str) and val:
            phone = val
            break
        if isinstance(val, list) and val:
            phone = val[0]
            break

    return {
        "email": email,
        "phone": phone,
        "contact_info": json.dumps(contact) if contact else "",
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Find a person's e-mail and phone number using Findymail"
    )
    parser.add_argument("full_name", help="Person's full name")
    parser.add_argument("company_domain", help="Company domain")
    args = parser.parse_args()

    result = asyncio.run(find_email_and_phone(args.full_name, args.company_domain))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
