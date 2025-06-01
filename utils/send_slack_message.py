"""Post a message to Slack via an incoming webhook."""

from __future__ import annotations

import argparse
import logging
import os
from typing import Optional

import requests

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


def send_slack_message(message: str, webhook: Optional[str] = None) -> None:
    """Send ``message`` to Slack if the webhook URL is configured."""

    webhook = webhook or os.getenv("SLACK_WEBHOOK_URL")
    if not webhook:
        logger.info("SLACK_WEBHOOK_URL not configured; skipping Slack message")
        return

    try:
        requests.post(webhook, json={"text": message}, timeout=5)
        logger.info("Sent Slack message")
    except requests.RequestException as exc:
        logger.error("Failed to send Slack message: %s", exc)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Send a message to Slack via webhook"
    )
    parser.add_argument("message", help="Message text to send")
    parser.add_argument(
        "--webhook",
        help="Webhook URL (defaults to SLACK_WEBHOOK_URL)"
    )
    args = parser.parse_args()

    send_slack_message(args.message, args.webhook)


if __name__ == "__main__":
    main()
