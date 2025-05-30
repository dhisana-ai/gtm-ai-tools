"""Simple utility demonstrating the OpenAI Responses API."""

from __future__ import annotations

import argparse
import os

from openai import OpenAI


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Send a prompt to OpenAI and print the response"
    )
    parser.add_argument("prompt", help="Prompt text to send")
    args = parser.parse_args()

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY environment variable is not set")

    client = OpenAI(api_key=api_key)
    response = client.responses.create(
        model="gpt-4.1-mini",
        input=[
            {"role": "system", "content": "You are a concise, helpful assistant."},
            {"role": "user", "content": args.prompt},
        ],
        text={"format": "markdown"},
        store=False,
    )
    print(response.choices[0].message.content)


if __name__ == "__main__":
    main()
