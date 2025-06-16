"""Search and export leads using Apollo.io people search."""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import os
from pathlib import Path
from typing import Any, Dict, List


def _clean_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Remove empty list/str/None values from payload."""
    clean: Dict[str, Any] = {}
    for key, value in payload.items():
        if value is None:
            continue
        if isinstance(value, list) and not value:
            continue
        if isinstance(value, str) and value == "":
            continue
        if value is False:
            # skip false booleans (assume API default)
            continue
        clean[key] = value
    return clean

import aiohttp

from utils.apollo_info import fill_in_properties_with_preference

API_BASE = "https://api.apollo.io/api/v1"


async def _search_page(params: Dict[str, Any]) -> Dict[str, Any]:
    """Call the Apollo.io people search endpoint and return JSON."""
    api_key = os.getenv("APOLLO_API_KEY")
    if not api_key:
        raise RuntimeError("APOLLO_API_KEY environment variable is not set")

    headers = {"X-Api-Key": api_key, "Content-Type": "application/json"}
    url = f"{API_BASE}/mixed_people/search"
    print(f"Querying {url} with payload: {json.dumps(params)}")
    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=params) as resp:
            status = getattr(resp, "status", "unknown")
            data = await resp.json()

    # Show more detail if the response contains an error
    if "error" in data:
        print(f"Apollo API returned status {status}: {data['error']}")
    else:
        print(f"Received response with keys: {list(data.keys())}")

    return data


def _add_extra_fields(base: Dict[str, Any], contact: Dict[str, Any]) -> Dict[str, Any]:
    """Return mapping of contact data flattened into ``base`` dict."""
    for key, value in contact.items():
        if key in base:
            continue
        if isinstance(value, (dict, list)):
            base[key] = json.dumps(value)
        else:
            base[key] = value
    return base


async def apollo_people_search(number_of_leads: int = 10, **params: Any) -> List[Dict[str, Any]]:
    """Search Apollo people and return a list of mapped dictionaries."""
    per_page = 100 if number_of_leads > 10 else number_of_leads
    page = 1
    results: List[Dict[str, Any]] = []

    print(f"Starting search with params: {params}, number_of_leads={number_of_leads}")

    while len(results) < number_of_leads:
        payload = dict(params)
        payload.update({"page": page, "per_page": per_page})
        payload = _clean_payload(payload)
        data = await _search_page(payload)
        contacts = data.get("contacts") or []
        people = data.get("people") or []
        combined = contacts + people
        print(
            f"Page {page}: found {len(contacts)} contacts and {len(people)} people"
        )
        for contact in combined:
            mapped = fill_in_properties_with_preference({}, contact)
            mapped = _add_extra_fields(mapped, contact)
            results.append(mapped)
            if len(results) >= number_of_leads:
                break
        pagination = data.get("pagination") or {}
        total_pages = pagination.get("total_pages", page)
        if page >= total_pages or not combined:
            break
        page += 1
        if len(results) < number_of_leads:
            await asyncio.sleep(10)
    print(f"Total results collected: {len(results[:number_of_leads])}")
    return results[:number_of_leads]


def apollo_people_search_to_csv(output_file: str | Path, **params: Any) -> None:
    """Run ``apollo_people_search`` and write the results to ``output_file``."""
    out_path = Path(output_file)
    print(f"Writing results to {out_path}")
    results = asyncio.run(apollo_people_search(**params))
    fieldnames: List[str] = []
    for row in results:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)

    with out_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in results:
            writer.writerow(row)
    print(f"Wrote {len(results)} rows to {out_path}")


def _parse_list(value: str) -> List[str]:
    """Return list of items split on commas or semicolons."""
    value = value.strip()
    if not value:
        return []
    if ";" in value:
        return [v.strip() for v in value.split(";") if v.strip()]
    return [v.strip() for v in value.split(",") if v.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description="Search people in Apollo.io")
    parser.add_argument("output_file", help="CSV file to create")
    parser.add_argument("--person_titles", default="", help="Comma separated job titles")
    parser.add_argument("--person_locations", default="", help="Comma separated locations")
    parser.add_argument("--person_seniorities", default="", help="Comma separated seniorities")
    parser.add_argument("--organization_locations", default="", help="Comma separated organization HQ locations")
    parser.add_argument("--organization_domains", default="", help="Comma separated organization domains")
    parser.add_argument("--include_similar_titles", action="store_true", default=False, help="Include similar titles")
    parser.add_argument("--contact_email_status", default="", help="Comma separated email statuses")
    parser.add_argument("--organization_ids", default="", help="Comma separated organization IDs")
    parser.add_argument("--organization_num_employees_ranges", default="", help="Comma separated employee ranges like 1,10")
    parser.add_argument("--q_organization_keyword_tags", default="", help="Comma separated organization keyword tags")
    parser.add_argument("--q_keywords", default="", help="Keyword filter")
    parser.add_argument("--num_leads", type=int, default=10, help="Number of leads to fetch")
    args = parser.parse_args()

    params = {
        "person_titles": _parse_list(args.person_titles),
        "person_locations": _parse_list(args.person_locations),
        "person_seniorities": _parse_list(args.person_seniorities),
        "organization_locations": _parse_list(args.organization_locations),
        "q_organization_domains_list": _parse_list(args.organization_domains),
        "include_similar_titles": args.include_similar_titles,
        "contact_email_status": _parse_list(args.contact_email_status),
        "organization_ids": _parse_list(args.organization_ids),
        "organization_num_employees_ranges": _parse_list(args.organization_num_employees_ranges),
        "q_organization_keyword_tags": _parse_list(args.q_organization_keyword_tags),
        "q_keywords": args.q_keywords,
        "number_of_leads": args.num_leads,
    }

    apollo_people_search_to_csv(args.output_file, **params)


if __name__ == "__main__":
    main()
