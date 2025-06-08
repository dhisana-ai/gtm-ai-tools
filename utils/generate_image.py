"""Create an image from a prompt with optional source image.

The script uses the OpenAI responses API for generation and editing. Provide a
text prompt and optionally an image URL to edit. The `OPENAI_API_KEY`
environment variable must be set.
"""
from __future__ import annotations

import argparse
import base64
import os
from urllib import request
from openai import OpenAI
from utils import common


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
            img_data = resp.read()
        b64_image = base64.b64encode(img_data).decode()
        response = client.responses.create(
            model=common.get_openai_model(),
            input=[
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": args.prompt},
                        {
                            "type": "input_image",
                            "image_url": f"data:image/png;base64,{b64_image}",
                        },
                    ],
                }
            ],
            tools=[{"type": "image_generation"}],
        )
        image_data = [
            output.result
            for output in getattr(response, "output", [])
            if getattr(output, "type", "") == "image_generation_call"
        ]
        b64 = image_data[0] if image_data else None
    else:
        response = client.responses.create(
            model=common.get_openai_model(),
            input=args.prompt,
            tools=[{"type": "image_generation"}],
        )
        image_data = [
            output.result
            for output in getattr(response, "output", [])
            if getattr(output, "type", "") == "image_generation_call"
        ]
        b64 = image_data[0] if image_data else None

    if b64:
        print(b64)
    else:
        print("No image data returned")


if __name__ == "__main__":
    main()
