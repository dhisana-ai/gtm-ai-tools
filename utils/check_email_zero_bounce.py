"""Check e-mail validity using the ZeroBounce API."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from typing import Any, Dict

import aiohttp


def _map_status_to_confidence(status: str) -> str:
    status = status.lower()
    if status == "valid":
        return "high"
    if status in ("catch-all", "unknown"):
        return "medium"
    return "low"


async def check_email(email: str) -> Dict[str, Any]:
    """Return ZeroBounce validation result for ``email``."""
    api_key = os.getenv("ZERO_BOUNCE_API_KEY")
    if not api_key:
        raise RuntimeError("ZERO_BOUNCE_API_KEY environment variable is not set")

    url = f"https://api.zerobounce.net/v2/validate?api_key={api_key}&email={email}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            data = await resp.json()
    confidence = _map_status_to_confidence(data.get("status", ""))
    return {
        "email": email,
        "confidence": confidence,
        "is_valid": confidence == "high",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Check e-mail validity via ZeroBounce")
    parser.add_argument("email", help="E-mail address to validate")
    args = parser.parse_args()

    result = asyncio.run(check_email(args.email))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
