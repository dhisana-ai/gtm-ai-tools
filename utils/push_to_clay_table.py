"""Push data to a Clay table via webhook."""

from __future__ import annotations

import argparse
import asyncio
import os
from typing import Optional, Dict

import aiohttp
import logging

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


async def push_to_clay_table(
    data: Dict[str, str],
    webhook_url: Optional[str] = None,
    api_key: Optional[str] = None,
) -> bool:
    """Send ``data`` to a Clay webhook.

    ``webhook_url`` defaults to ``CLAY_WEBHOOK_URL`` and ``api_key`` defaults to
    ``CLAY_API_KEY`` from the environment. Raises ``RuntimeError`` if required
    values are missing.
    """

    api_key = api_key or os.getenv("CLAY_API_KEY")
    if not api_key:
        raise RuntimeError("CLAY_API_KEY environment variable is not set")

    webhook_url = webhook_url or os.getenv("CLAY_WEBHOOK_URL")
    if not webhook_url:
        raise RuntimeError(
            "Webhook URL not provided and CLAY_WEBHOOK_URL is not set"
        )

    headers = {"x-clay-webhook-auth": api_key, "Content-Type": "application/json"}

    async with aiohttp.ClientSession() as session:
        async with session.post(webhook_url, headers=headers, json=data) as resp:
            resp.raise_for_status()
            logger.info("Data pushed to Clay table")
            return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Push data to a Clay webhook")
    parser.add_argument("data", nargs="+", help="key=value pairs")
    parser.add_argument(
        "--webhook_url",
        help="Webhook URL (defaults to CLAY_WEBHOOK_URL)",
    )
    parser.add_argument("--api_key", help="API key (defaults to CLAY_API_KEY)")
    args = parser.parse_args()

    payload: Dict[str, str] = {}
    for item in args.data:
        if "=" in item:
            k, v = item.split("=", 1)
            payload[k] = v

    asyncio.run(push_to_clay_table(payload, args.webhook_url, args.api_key))


if __name__ == "__main__":
    main()
