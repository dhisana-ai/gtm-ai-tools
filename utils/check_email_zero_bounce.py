"""Verify an email address with ZeroBounce before adding it to campaigns."""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import os
from pathlib import Path
from typing import Any, Dict

import aiohttp


def _map_status_to_confidence(status: str) -> str:
    status = status.lower()
    if status == "valid":
        return "high"
    if status in ("catch-all", "unknown"):
        return "medium"
    return "low"


async def check_email(email: str) -> Dict[str, Any]:
    """Return ZeroBounce validation result for ``email``."""
    api_key = os.getenv("ZERO_BOUNCE_API_KEY")
    if not api_key:
        raise RuntimeError("ZERO_BOUNCE_API_KEY environment variable is not set")

    url = f"https://api.zerobounce.net/v2/validate?api_key={api_key}&email={email}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            data = await resp.json()
    confidence = _map_status_to_confidence(data.get("status", ""))
    return {
        "email": email,
        "confidence": confidence,
        "is_valid": confidence == "high",
    }


def check_emails_from_csv(input_file: str | Path, output_file: str | Path) -> None:
    """Validate each e-mail in ``input_file`` and write results to ``output_file``.

    The input CSV must have an ``email`` column. All existing columns are
    preserved in the output, with two additional columns added:

    ``is_email_valid`` - ``true`` or ``false`` indicating if the e-mail is valid
    ``email_confidence`` - ``low``/``medium``/``high`` confidence score
    """

    in_path = Path(input_file)
    out_path = Path(output_file)

    with in_path.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        fieldnames = reader.fieldnames or []
        if "email" not in fieldnames:
            raise ValueError("upload csv with email column")
        rows = list(reader)

    out_fields = fieldnames + ["is_email_valid", "email_confidence"]

    processed: list[dict[str, Any]] = []
    for row in rows:
        email = (row.get("email") or "").strip()
        if email:
            result = asyncio.run(check_email(email))
            row["is_email_valid"] = str(result.get("is_valid", False)).lower()
            row["email_confidence"] = result.get("confidence", "")
        else:
            row["is_email_valid"] = ""
            row["email_confidence"] = ""
        processed.append(row)

    with out_path.open("w", newline="", encoding="utf-8") as out_fh:
        writer = csv.DictWriter(out_fh, fieldnames=out_fields)
        writer.writeheader()
        for row in processed:
            writer.writerow(row)


def main() -> None:
    parser = argparse.ArgumentParser(description="Check e-mail validity via ZeroBounce")
    parser.add_argument("email", help="E-mail address to validate")
    args = parser.parse_args()

    result = asyncio.run(check_email(args.email))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
