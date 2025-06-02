"""OpenAI tools for GTM workflows.

Send a prompt with optional web search to summarize content, research companies
or uncover new leads."""

from __future__ import annotations

import argparse
import os

from utils import common

from openai import OpenAI


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Use OpenAI to answer a prompt with web search assistance"
    )
    parser.add_argument("prompt", help="Prompt text to send")
    args = parser.parse_args()

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY environment variable is not set")

    client = OpenAI(api_key=api_key)
    response = client.responses.create(
        model=common.get_openai_model(),
        input=args.prompt,
        tools=[{"type": "web_search_preview"}]
    )
    print(response.output_text)


if __name__ == "__main__":
    main()
