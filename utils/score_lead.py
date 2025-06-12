"""Score a lead using OpenAI with custom instructions.

The module provides functions to score a single lead dictionary or all
rows in a CSV file. The score ranges from 0 to 5 and is returned in the
``lead_score`` field. When scoring from a CSV the output file will
contain all original columns plus ``lead_score``.
"""

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
except ImportError:  # pragma: no cover - fallback for tests
    from pydantic_stub import BaseModel

from utils.extract_from_webpage import _get_structured_data_internal

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class LeadScore(BaseModel):
    lead_score: int


async def _score_lead_async(lead: Dict[str, Any], instructions: str) -> int:
    """Return an integer score from 0 to 5 for ``lead``."""

    prompt = (
        "You are an expert sales assistant scoring leads.\n"
        "Score the lead from 0 (poor) to 5 (excellent) following these instructions:\n"
        f"{instructions}\n\n"
        f"Lead information:\n{json.dumps(lead)}\n\n"
        "Return valid JSON with key 'lead_score'."
    )
    result, status = await _get_structured_data_internal(prompt, LeadScore)
    if status != "SUCCESS" or result is None:
        logger.error("Failed to get lead score from LLM")
        raise RuntimeError("LLM scoring failed")
    score = result.lead_score
    # clamp just in case
    if score < 0:
        score = 0
    if score > 5:
        score = 5
    return score


def score_lead(lead: Dict[str, Any], instructions: str) -> int:
    """Score ``lead`` synchronously using ``instructions``."""
    return asyncio.run(_score_lead_async(lead, instructions))


def score_leads_from_csv(
    input_file: str | Path,
    output_file: str | Path,
    instructions: str,
) -> None:
    """Score each row in ``input_file`` and write results to ``output_file``."""

    in_path = Path(input_file)
    out_path = Path(output_file)

    with in_path.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        fieldnames = reader.fieldnames or []
        rows = list(reader)

    out_fields = list(fieldnames)
    if "lead_score" not in out_fields:
        out_fields.append("lead_score")

    processed = []
    for row in rows:
        score = score_lead(row, instructions)
        row["lead_score"] = score
        processed.append(row)

    with out_path.open("w", newline="", encoding="utf-8") as out_fh:
        writer = csv.DictWriter(out_fh, fieldnames=out_fields)
        writer.writeheader()
        for row in processed:
            writer.writerow(row)

    logger.info("Wrote scored leads to %s", out_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Score leads using OpenAI")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--lead", help="JSON string with lead data")
    group.add_argument("--csv", help="Input CSV file containing leads")
    parser.add_argument(
        "--instructions",
        required=True,
        help="Instructions on how to score the lead(s)",
    )
    parser.add_argument("--output_csv", help="Output CSV path when --csv is used")
    args = parser.parse_args()

    if args.lead:
        try:
            data = json.loads(args.lead)
        except json.JSONDecodeError as exc:
            raise ValueError("lead must be valid JSON") from exc
        score = score_lead(data, args.instructions)
        print(json.dumps({"lead_score": score}))
    else:
        if not args.output_csv:
            raise ValueError("--output_csv is required when using --csv")
        score_leads_from_csv(args.csv, args.output_csv, args.instructions)


if __name__ == "__main__":
    main()
