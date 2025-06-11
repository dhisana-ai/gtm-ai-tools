"""Bulk search LinkedIn profiles from a CSV of names and keywords."""

from __future__ import annotations

import argparse
import asyncio
import csv
import logging
from pathlib import Path

from utils.find_a_user_by_name_and_keywords import find_user_linkedin_url, LeadSearchResult

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


def read_input_rows(input_file: Path) -> list[dict[str, str]]:
    """Return rows from the CSV as dictionaries."""
    rows: list[dict[str, str]] = []
    with input_file.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            rows.append(row)
    return rows


def write_output_rows(output_file: Path, rows: list[dict[str, str]]) -> None:
    """Write result rows to CSV."""
    with output_file.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "full_name",
                "user_linkedin_url",
                "first_name",
                "last_name",
                "job_title",
                "linkedin_follower_count",
                "lead_location",
                "summary_about_lead",
                "search_keywords",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)


def find_users(input_file: Path, output_file: Path) -> None:
    """Process each row of the input CSV and write LinkedIn URLs."""
    rows = read_input_rows(input_file)
    results: list[dict[str, str]] = []

    for row in rows:
        full_name = (row.get("full_name") or "").strip()
        search_keywords = (row.get("search_keywords") or "").strip()
        logger.info("Searching LinkedIn for %s", full_name)
        info = asyncio.run(find_user_linkedin_url(full_name, search_keywords))
        if not info.get("full_name"):
            info["full_name"] = full_name
        info["search_keywords"] = search_keywords
        results.append(info)

    write_output_rows(output_file, results)
    logger.info("Wrote results to %s", output_file)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Look up LinkedIn profiles from a CSV of names and search keywords"
        )
    )
    parser.add_argument(
        "input_file",
        type=Path,
        help="CSV with full_name and search_keywords",
    )
    parser.add_argument("output_file", type=Path, help="CSV file to create")
    args = parser.parse_args()

    find_users(args.input_file, args.output_file)


if __name__ == "__main__":
    main()
