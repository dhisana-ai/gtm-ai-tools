"""Utility to push company information to a Dhisana webhook."""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
from typing import Optional

import aiohttp

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


async def push_company_to_dhisana_webhook(
    company_name: str,
    primary_domain: str = "",
    linkedin_url: str = "",
    tags: str = "",
    notes: str = "",
    webhook_url: Optional[str] = None,
) -> bool:
    """Send company details to the Dhisana webhook.

    Returns ``True`` when a request was made. If neither ``linkedin_url`` nor
    ``primary_domain`` is provided the function returns ``False`` without calling
    the webhook. ``tags`` and ``notes`` are optional strings that will be
    included in the payload if provided.
    """

    if not linkedin_url and not primary_domain:
        logger.info("Skipping push because no linkedin_url or primary_domain provided")
        return False

    api_key = os.getenv("DHISANA_API_KEY")
    if not api_key:
        raise RuntimeError("DHISANA_API_KEY environment variable is not set")

    if not webhook_url:
        webhook_url = os.getenv("DHISANA_COMPANY_INPUT_URL")
    if not webhook_url:
        raise RuntimeError(
            "Webhook URL not provided and DHISANA_COMPANY_INPUT_URL is not set"
        )

    payload = [
        {
            "organization_name": company_name,
            "organization_linkedin_url": linkedin_url,
            "primary_domain_of_organization": primary_domain,
            "organization_tags": tags,
            "organization_notes": notes,
        }
    ]

    headers = {"X-API-Key": api_key, "Content-Type": "application/json"}

    async with aiohttp.ClientSession() as session:
        async with session.post(webhook_url, headers=headers, json=payload) as resp:
            resp.raise_for_status()
            logger.info("Company pushed to Dhisana webhook")
            return True


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Push a company to a Dhisana webhook"
    )
    parser.add_argument("company_name", help="Organization name")
    parser.add_argument("--primary_domain", default="", help="Primary domain")
    parser.add_argument("--linkedin_url", default="", help="LinkedIn organization URL")
    parser.add_argument("--tags", default="", help="Comma separated tags")
    parser.add_argument("--notes", default="", help="Additional notes")
    parser.add_argument(
        "--webhook_url",
        help="Webhook URL (defaults to DHISANA_COMPANY_INPUT_URL)",
    )
    args = parser.parse_args()

    asyncio.run(
        push_company_to_dhisana_webhook(
            args.company_name,
            args.primary_domain,
            args.linkedin_url,
            args.tags,
            args.notes,
            args.webhook_url,
        )
    )


if __name__ == "__main__":
    main()
