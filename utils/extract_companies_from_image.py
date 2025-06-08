"""Detect company logos in an image and fetch company details.

Provide an image URL which is downloaded and sent to OpenAI's vision API to
identify company names present in logos or text. For each company name found it
performs a Google search via Serper.dev to discover the organization's website,
domain and LinkedIn URL.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import logging
import os
import tempfile
from pathlib import Path
from typing import List
from urllib import request
from urllib.parse import urlparse

from openai import OpenAI

from utils import common, find_company_info

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


def _encode_image(path: Path) -> str:
    """Return the base64 string for the image at ``path``."""
    with path.open("rb") as fh:
        return base64.b64encode(fh.read()).decode("utf-8")


def _download_image(url: str) -> Path:
    """Download ``url`` to a temporary file and return its path."""
    parsed = urlparse(url)
    suffix = Path(parsed.path).suffix or ".png"
    fd, tmp = tempfile.mkstemp(suffix=suffix)
    with request.urlopen(url) as resp, os.fdopen(fd, "wb") as fh:
        fh.write(resp.read())
    return Path(tmp)


def extract_company_names(image_path: Path) -> List[str]:
    """Return company names detected in the image."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY environment variable is not set")

    client = OpenAI(api_key=api_key)
    b64 = _encode_image(image_path)
    response = client.responses.create(
        model=common.get_openai_model(),
        input=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": (
                            "List the company names visible in this image. "
                            "Reply with a JSON array of names."
                        ),
                    },
                    {
                        "type": "input_image",
                        "image_url": f"data:image/png;base64,{b64}",
                        "detail": "low",
                    },
                ],
            }
        ],
    )
    text = response.output_text or ""
    try:
        data = json.loads(text)
    except json.JSONDecodeError:  # pragma: no cover - network issues
        logger.exception("Failed to parse response: %s", text)
        return []
    if not isinstance(data, list):
        return []
    return [str(item) for item in data]


async def _lookup_details(names: List[str]) -> List[dict]:
    results: List[dict] = []
    for name in names:
        info = await find_company_info.find_company_details(name)
        info["company_name"] = name
        results.append(info)
    return results


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Extract company names from an image and look up websites "
            "and LinkedIn pages"
        )
    )
    parser.add_argument("image_url", help="URL of the image file")
    args = parser.parse_args()

    img_path = _download_image(args.image_url)
    names = extract_company_names(img_path)
    try:
        os.remove(img_path)
    except Exception:
        pass
    details = asyncio.run(_lookup_details(names))
    print(json.dumps(details, indent=2))


if __name__ == "__main__":
    main()
