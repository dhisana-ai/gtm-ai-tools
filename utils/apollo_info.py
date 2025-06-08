"""Look up people and companies in Apollo.io for lead enrichment."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from typing import Any, Dict
from pathlib import Path
import csv

import aiohttp

from utils.find_company_info import extract_domain

API_BASE = "https://api.apollo.io/api/v1"


def fill_in_properties_with_preference(
    input_user_properties: dict, person_data: dict
) -> dict:
    """Map person information to standard output properties."""

    def is_empty(value: Any) -> bool:
        return value is None or (isinstance(value, str) and not value.strip())

    # Email
    if is_empty(input_user_properties.get("email")):
        input_user_properties["email"] = person_data.get("email", "")

    # Phone
    if is_empty(input_user_properties.get("phone")):
        input_user_properties["phone"] = (
            (person_data.get("contact", {}) or {}).get("sanitized_phone", "")
        )

    # Full name
    if is_empty(input_user_properties.get("full_name")) and person_data.get("name"):
        input_user_properties["full_name"] = person_data["name"]

    # First name
    if (
        is_empty(input_user_properties.get("first_name"))
        and person_data.get("first_name")
    ):
        input_user_properties["first_name"] = person_data["first_name"]

    # Last name
    if (
        is_empty(input_user_properties.get("last_name"))
        and person_data.get("last_name")
    ):
        input_user_properties["last_name"] = person_data["last_name"]

    # LinkedIn URL
    if (
        is_empty(input_user_properties.get("user_linkedin_url"))
        and person_data.get("linkedin_url")
    ):
        input_user_properties["user_linkedin_url"] = person_data["linkedin_url"]

    # Organization data
    org_data = person_data.get("organization") or {}
    if org_data:
        if (
            is_empty(input_user_properties.get("primary_domain_of_organization"))
            and org_data.get("primary_domain")
        ):
            input_user_properties["primary_domain_of_organization"] = org_data[
                "primary_domain"
            ]

        if (
            is_empty(input_user_properties.get("organization_name"))
            and org_data.get("name")
        ):
            input_user_properties["organization_name"] = org_data["name"]

        if (
            is_empty(input_user_properties.get("organization_linkedin_url"))
            and org_data.get("linkedin_url")
        ):
            input_user_properties["organization_linkedin_url"] = org_data[
                "linkedin_url"
            ]

        if (
            is_empty(input_user_properties.get("organization_website"))
            and org_data.get("website_url")
        ):
            input_user_properties["organization_website"] = org_data[
                "website_url"
            ]

        if is_empty(input_user_properties.get("keywords")) and org_data.get(
            "keywords"
        ):
            input_user_properties["keywords"] = ", ".join(org_data["keywords"])

    # Job title
    if is_empty(input_user_properties.get("job_title")) and person_data.get("title"):
        input_user_properties["job_title"] = person_data["title"]

    # Headline
    if (
        is_empty(input_user_properties.get("headline"))
        and person_data.get("headline")
    ):
        input_user_properties["headline"] = person_data["headline"]

    if (
        is_empty(input_user_properties.get("summary_about_lead"))
        and person_data.get("headline")
    ):
        input_user_properties["summary_about_lead"] = person_data["headline"]

    # City/State -> lead_location
    city = person_data.get("city", "")
    state = person_data.get("state", "")
    if is_empty(input_user_properties.get("lead_location")) and (city or state):
        lead_location = f"{city}, {state}".strip(", ")
        input_user_properties["lead_location"] = lead_location

    if (
        input_user_properties.get("email")
        and "domain.com" in input_user_properties["email"].lower()
    ):
        input_user_properties["email"] = ""

    return input_user_properties


async def get_person_info(
    linkedin_url: str = "",
    email: str = "",
    full_name: str = "",
    company_domain: str = "",
) -> Dict[str, Any]:
    """Return person details from Apollo.io.

    Either ``linkedin_url`` or ``email`` must be supplied. As an alternative,
    ``full_name`` together with ``company_domain`` can be used to look up a
    person.
    """
    api_key = os.getenv("APOLLO_API_KEY")
    if not api_key:
        raise RuntimeError("APOLLO_API_KEY environment variable is not set")

    if not linkedin_url and not email and not (full_name and company_domain):
        raise RuntimeError(
            "Provide linkedin_url, email, or full_name with company_domain"
        )

    headers = {"X-Api-Key": api_key, "Content-Type": "application/json"}
    payload: Dict[str, Any] = {}
    if linkedin_url:
        payload["linkedin_url"] = linkedin_url
    if email:
        payload["email"] = email
    if full_name and company_domain:
        payload["name"] = full_name
        payload["domain"] = extract_domain(company_domain)

    async with aiohttp.ClientSession() as session:
        url = f"{API_BASE}/people/match"
        async with session.post(url, headers=headers, json=payload) as resp:
            data = await resp.json()

    person_data = data.get("person") or {}
    if person_data:
        mapped = fill_in_properties_with_preference({}, person_data)
        return mapped
    return data


async def get_company_info(company_url: str = "", primary_domain: str = "") -> Dict[str, Any]:
    """Return organization details from Apollo.io using company URL or domain."""
    api_key = os.getenv("APOLLO_API_KEY")
    if not api_key:
        raise RuntimeError("APOLLO_API_KEY environment variable is not set")

    domain = primary_domain or ""
    if company_url and not domain:
        domain = extract_domain(company_url)
    if not domain:
        raise RuntimeError("Provide company_url or primary_domain")

    headers = {"X-Api-Key": api_key, "Content-Type": "application/json"}
    async with aiohttp.ClientSession() as session:
        url = f"{API_BASE}/organizations/enrich?domain={domain}"
        async with session.get(url, headers=headers) as resp:
            return await resp.json()


def apollo_info_from_csv(input_file: str | Path, output_file: str | Path) -> None:
    """Run ``get_person_info`` for rows in ``input_file`` and write results."""

    in_path = Path(input_file)
    out_path = Path(output_file)

    with in_path.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        fieldnames = reader.fieldnames or []
        if "user_linkedin_url" not in fieldnames and "email" not in fieldnames:
            raise ValueError("upload csv with user_linkedin_url or email column")
        rows = list(reader)

    with out_path.open("w", newline="", encoding="utf-8") as out_fh:
        writer = csv.DictWriter(out_fh, fieldnames=fieldnames + ["properties"])
        writer.writeheader()
        for row in rows:
            linkedin = (row.get("user_linkedin_url") or "").strip()
            email = (row.get("email") or "").strip()
            if not linkedin and not email:
                row["properties"] = ""
                writer.writerow(row)
                continue
            result = asyncio.run(
                get_person_info(
                    linkedin,
                    email,
                    row.get("full_name", ""),
                    row.get("company_domain", ""),
                )
            )
            row["properties"] = json.dumps(result)
            writer.writerow(row)


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch info from Apollo.io")
    parser.add_argument("--linkedin_url", default="", help="Person LinkedIn URL")
    parser.add_argument("--email", default="", help="Person email")
    parser.add_argument("--full_name", default="", help="Person full name")
    parser.add_argument(
        "--company_domain", default="", help="Company domain for person search"
    )
    parser.add_argument("--company_url", default="", help="Company website URL")
    parser.add_argument("--primary_domain", default="", help="Company domain")
    args = parser.parse_args()

    if args.linkedin_url or args.email or (args.full_name and args.company_domain):
        result = asyncio.run(
            get_person_info(
                args.linkedin_url,
                args.email,
                args.full_name,
                args.company_domain,
            )
        )
    else:
        result = asyncio.run(get_company_info(args.company_url, args.primary_domain))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
