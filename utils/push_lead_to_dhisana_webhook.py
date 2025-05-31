"""Utility to push lead information to a Dhisana webhook."""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
from typing import Optional

import aiohttp

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


async def push_lead_to_dhisana_webhook(
    full_name: str,
    linkedin_url: str = "",
    email: str = "",
    webhook_url: Optional[str] = None,
) -> bool:
    """Send lead details to the Dhisana webhook.

    Returns ``True`` when a request was made. If neither ``linkedin_url`` nor
    ``email`` is provided the function returns ``False`` without calling the
    webhook.
    """

    if not linkedin_url and not email:
        logger.info("Skipping push because no linkedin_url or email provided")
        return False

    api_key = os.getenv("DHISANA_API_KEY")
    if not api_key:
        raise RuntimeError("DHISANA_API_KEY environment variable is not set")

    if not webhook_url:
        webhook_url = os.getenv("DHISANA_WEBHOOK_URL")
    if not webhook_url:
        raise RuntimeError(
            "Webhook URL not provided and DHISANA_WEBHOOK_URL is not set"
        )

    payload = [
        {
            "full_name": full_name,
            "email": email,
            "user_linkedin_url": linkedin_url,
        }
    ]

    headers = {"X-API-Key": api_key, "Content-Type": "application/json"}

    async with aiohttp.ClientSession() as session:
        async with session.post(webhook_url, headers=headers, json=payload) as resp:
            resp.raise_for_status()
            logger.info("Lead pushed to Dhisana webhook")
            return True


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Push a lead to a Dhisana webhook"
    )
    parser.add_argument("full_name", help="Lead's full name")
    parser.add_argument("--linkedin_url", default="", help="LinkedIn profile URL")
    parser.add_argument("--email", default="", help="Email address")
    parser.add_argument(
        "--webhook_url",
        help="Webhook URL (defaults to DHISANA_WEBHOOK_URL)",
    )
    args = parser.parse_args()

    asyncio.run(
        push_lead_to_dhisana_webhook(
            args.full_name, args.linkedin_url, args.email, args.webhook_url
        )
    )


if __name__ == "__main__":
    main()
