"""Generate an email subject and body using OpenAI."""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import logging
from pathlib import Path
from typing import Any, Dict

try:
    from pydantic import BaseModel
except ImportError:  # pragma: no cover - tests use stub
    from pydantic_stub import BaseModel

from utils.extract_from_webpage import _get_structured_data_internal

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class EmailCopy(BaseModel):
    subject: str
    body: str


async def _generate_email_async(
    lead: Dict[str, Any], email_generation_instructions: str
) -> EmailCopy:
    """Return ``EmailCopy`` generated for ``lead`` using ``email_generation_instructions``."""

    prompt = (
        "Compose a short sales email as JSON.\n"
        f"Email generation instructions:\n{email_generation_instructions}\n\n"
        f"Lead information:\n{json.dumps(lead)}\n\n"
        "Return valid JSON with keys 'subject' and 'body'."
    )
    result, status = await _get_structured_data_internal(prompt, EmailCopy)
    if status != "SUCCESS" or result is None:
        logger.error("Failed to generate email from LLM")
        raise RuntimeError("LLM email generation failed")
    return result


def generate_email(
    lead: Dict[str, Any], email_generation_instructions: str
) -> Dict[str, str]:
    """Generate an email synchronously for ``lead``."""
    result = asyncio.run(
        _generate_email_async(lead, email_generation_instructions)
    )
    return json.loads(result.model_dump_json())


def generate_emails_from_csv(
    input_file: str | Path,
    output_file: str | Path,
    email_generation_instructions: str,
) -> None:
    """Generate emails for each row of ``input_file`` and write results."""

    in_path = Path(input_file)
    out_path = Path(output_file)

    with in_path.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        fieldnames = reader.fieldnames or []
        rows = list(reader)

    out_fields = list(fieldnames)
    if "email_subject" not in out_fields:
        out_fields.append("email_subject")
    if "email_body" not in out_fields:
        out_fields.append("email_body")

    processed: list[dict[str, str]] = []
    for row in rows:
        result = generate_email(row, email_generation_instructions)
        row["email_subject"] = result.get("subject", "")
        row["email_body"] = result.get("body", "")
        processed.append(row)

    with out_path.open("w", newline="", encoding="utf-8") as out_fh:
        writer = csv.DictWriter(out_fh, fieldnames=out_fields)
        writer.writeheader()
        for row in processed:
            writer.writerow(row)

    logger.info("Wrote generated emails to %s", out_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate an email using OpenAI")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--lead", help="JSON string with lead info")
    group.add_argument("--csv", help="Input CSV file with leads")
    parser.add_argument(
        "--email_generation_instructions",
        required=True,
        help="Email generation instructions",
    )
    parser.add_argument("--output_csv", help="Output CSV path when using --csv")
    args = parser.parse_args()

    if args.lead:
        try:
            data = json.loads(args.lead)
        except json.JSONDecodeError as exc:
            raise ValueError("lead must be valid JSON") from exc
        result = generate_email(data, args.email_generation_instructions)
        print(json.dumps(result, indent=2))
    else:
        if not args.output_csv:
            raise ValueError("--output_csv is required when using --csv")
        generate_emails_from_csv(
            args.csv, args.output_csv, args.email_generation_instructions
        )


if __name__ == "__main__":
    main()
