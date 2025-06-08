"""Create an image from a prompt with optional source image.

The script uses the OpenAI images API. Provide a text prompt and optionally
an image URL to edit. The `OPENAI_API_KEY` environment variable must be set.
"""
from __future__ import annotations

import argparse
import io
import os
from typing import Optional
from urllib import request
from openai import OpenAI


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate an image from a prompt using OpenAI"
    )
    parser.add_argument("prompt", help="Text prompt describing the image")
    parser.add_argument(
        "--image-url",
        help="Optional URL of a source image to edit",
    )
    args = parser.parse_args()

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY environment variable is not set")

    client = OpenAI(api_key=api_key)

    if args.image_url:
        with request.urlopen(args.image_url) as resp:
            img_bytes = io.BytesIO(resp.read())
        img_bytes.name = "image.png"
        result = client.images.edit(
            model="gpt-image-1",
            image=[img_bytes],
            prompt=args.prompt,
            size="1024x1024",
            quality="standard",
            response_format="b64_json",
            n=1,
        )
    else:
        result = client.images.generate(
            model="gpt-image-1",
            prompt=args.prompt,
            size="1024x1024",
            quality="standard",
            response_format="b64_json",
            n=1,
        )

    b64 = getattr(result.data[0], "b64_json", None)
    if b64:
        print(b64)
    else:
        print("No image data returned")


if __name__ == "__main__":
    main()
