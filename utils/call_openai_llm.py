"""OpenAI tools for GTM workflows.

Send a prompt with optional web search to summarize content, research companies
or uncover new leads."""

from __future__ import annotations

import argparse
import os

from utils import common
import csv
from pathlib import Path

from openai import OpenAI


def _call_openai(prompt: str) -> str:
    """Return the LLM response text for ``prompt``."""

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY environment variable is not set")

    client = OpenAI(api_key=api_key)
    response = client.responses.create(
        model=common.get_openai_model(),
        input=prompt,
        tools=[{"type": "web_search_preview"}],
    )
    return response.output_text


def call_openai_llm_from_csv(
    input_file: str | Path, output_file: str | Path, prompt: str
) -> None:
    """Run the LLM with ``prompt`` + each CSV row and write results."""

    in_path = Path(input_file)
    out_path = Path(output_file)

    with in_path.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        fieldnames = reader.fieldnames or []
        rows = list(reader)

    out_fields = fieldnames + ["llm_output"]
    processed: list[dict[str, str]] = []
    for row in rows:
        row_prompt = f"{prompt}{str(row)}"
        result = _call_openai(row_prompt)
        row["llm_output"] = result
        processed.append(row)

    with out_path.open("w", newline="", encoding="utf-8") as out_fh:
        writer = csv.DictWriter(out_fh, fieldnames=out_fields)
        writer.writeheader()
        for row in processed:
            writer.writerow(row)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Use OpenAI to answer a prompt with web search assistance"
    )
    parser.add_argument("prompt", help="Prompt text to send")
    args = parser.parse_args()

    print(_call_openai(args.prompt))


if __name__ == "__main__":
    main()
