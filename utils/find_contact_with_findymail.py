"""Get a prospect's email and phone number using Findymail."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
from typing import Any, Dict
from pathlib import Path
import csv

import aiohttp

API_BASE = "https://app.findymail.com/api"

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


async def find_email_and_phone(
    full_name: str = "",
    primary_domain_of_organization: str = "",
    linkedin_url: str = "",
) -> Dict[str, Any]:
    """Return e-mail and phone number for a lead.

    If ``linkedin_url`` is provided it is used to query Findymail directly.
    Otherwise ``full_name`` together with ``primary_domain_of_organization`` is
    used.
    """
    api_key = os.getenv("FINDYMAIL_API_KEY")
    if not api_key:
        raise RuntimeError("FINDYMAIL_API_KEY environment variable is not set")

    if not linkedin_url and not (full_name and primary_domain_of_organization):
        return {"email": "", "phone": "", "contact_info": ""}

    if linkedin_url:
        url = f"{API_BASE}/search/linkedin"
        payload = {"linkedin_url": linkedin_url}
    else:
        url = f"{API_BASE}/search/name"
        payload = {
            "name": full_name,
            "domain": primary_domain_of_organization,
        }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

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


def find_contact_with_findymail_from_csv(
    input_file: str | Path, output_file: str | Path
) -> None:
    """Look up contact details for each row of ``input_file`` and write results."""

    in_path = Path(input_file)
    out_path = Path(output_file)

    with in_path.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        fieldnames = reader.fieldnames or []
        rows = list(reader)

    if "full_name" not in fieldnames:
        raise ValueError("upload csv with full_name column")

    extra_fields = ["email", "phone", "contact_info"]
    out_fields = list(fieldnames)
    for f in extra_fields:
        if f not in out_fields:
            out_fields.append(f)

    processed: list[dict[str, str]] = []
    for row in rows:
        linkedin_url = (row.get("linkedin_url") or row.get("user_linkedin_url") or "").strip()
        domain = (
            row.get("primary_domain_of_organization")
            or row.get("company_domain")
            or ""
        ).strip()
        result = asyncio.run(
            find_email_and_phone(row.get("full_name", ""), domain, linkedin_url)
        )
        row.update(result)
        processed.append(row)

    with out_path.open("w", newline="", encoding="utf-8") as out_fh:
        writer = csv.DictWriter(out_fh, fieldnames=out_fields)
        writer.writeheader()
        for row in processed:
            writer.writerow(row)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Find a person's e-mail and phone number using Findymail"
    )
    parser.add_argument("full_name", help="Person's full name")
    parser.add_argument(
        "primary_domain_of_organization",
        nargs="?",
        default="",
        help="Company domain",
    )
    parser.add_argument("--linkedin_url", default="", help="LinkedIn profile URL")
    args = parser.parse_args()

    result = asyncio.run(
        find_email_and_phone(
            args.full_name,
            args.primary_domain_of_organization,
            args.linkedin_url,
        )
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
