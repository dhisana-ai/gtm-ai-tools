"""Sample utility that sends a prompt to OpenAI through an MCP server."""

from __future__ import annotations

import argparse
import os
from openai import OpenAI

from utils import common


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Send a prompt to OpenAI with an MCP server tool"
    )
    parser.add_argument("prompt", help="Prompt text to send")
    args = parser.parse_args()

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY environment variable is not set")

    server_label = os.getenv("MCP_SERVER_LABEL", "")
    server_url = os.getenv("MCP_SERVER_URL")
    header_name = os.getenv("MCP_API_KEY_HEADER_NAME")
    header_value = os.getenv("MCP_API_KEY_HEADER_VALUE")

    if not (server_url and header_name and header_value):
        raise RuntimeError("MCP server environment variables are not set")

    client = OpenAI(api_key=api_key)
    response = client.responses.create(
        model=common.get_openai_model(),
        input=args.prompt,
        tools=[
            {
                "type": "mcp",
                "server_label": server_label,
                "server_url": server_url,
                "headers": {header_name: header_value},
                "require_approval": "never",
            }
        ],
        tool_choice="auto",
    )
    print(getattr(response, "output_text", ""))


if __name__ == "__main__":
    main()
