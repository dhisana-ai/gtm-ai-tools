"""Send a simple email via SMTP."""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import uuid
from dataclasses import dataclass
from email.mime.text import MIMEText

try:
    import aiosmtplib
except Exception:  # pragma: no cover - falls back if library not installed
    aiosmtplib = None  # type: ignore


@dataclass
class SendEmailContext:
    """Information required to send an e-mail."""

    sender_name: str
    sender_email: str
    recipient: str
    subject: str
    body: str


async def send_email_via_smtp_async(
    ctx: SendEmailContext,
    smtp_server: str,
    smtp_port: int,
    username: str,
    password: str,
    *,
    use_starttls: bool = True,
) -> str:
    """Send a single e-mail over SMTP and return the Message-ID."""

    if aiosmtplib is None:
        raise RuntimeError("aiosmtplib is not installed")

    msg = MIMEText(ctx.body, _charset="utf-8")
    msg["From"] = f"{ctx.sender_name} <{ctx.sender_email}>"
    msg["To"] = ctx.recipient
    msg["Subject"] = ctx.subject

    domain_part = ctx.sender_email.split("@", 1)[-1] or "local"
    generated_id = f"<{uuid.uuid4()}@{domain_part}>"
    msg["Message-ID"] = generated_id

    smtp_kwargs = dict(
        hostname=smtp_server,
        port=smtp_port,
        username=username,
        password=password,
    )
    if use_starttls:
        smtp_kwargs["start_tls"] = True
    else:
        smtp_kwargs["tls"] = True

    try:
        await aiosmtplib.send(msg, **smtp_kwargs)
        logging.info("SMTP send OK \u2013 msg id %s", generated_id)
        await asyncio.sleep(20)
        return generated_id
    except Exception:
        logging.exception("SMTP send failed")
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description="Send an e-mail via SMTP")
    parser.add_argument("recipient", help="Recipient e-mail address")
    parser.add_argument("--subject", default="", help="E-mail subject")
    parser.add_argument("--body", default="", help="E-mail body")
    parser.add_argument("--sender_name", default="", help="Name of the sender")
    parser.add_argument(
        "--sender_email",
        default=os.getenv("SMTP_SENDER_EMAIL", ""),
        help="Sender e-mail address (defaults to SMTP_SENDER_EMAIL)",
    )
    parser.add_argument(
        "--use_starttls",
        action="store_true",
        help="Use STARTTLS instead of TLS",
    )
    args = parser.parse_args()

    smtp_server = os.getenv("SMTP_SERVER")
    smtp_port = int(os.getenv("SMTP_PORT", "0"))
    smtp_username = os.getenv("SMTP_USERNAME")
    smtp_password = os.getenv("SMTP_PASSWORD")

    if not all([smtp_server, smtp_port, smtp_username, smtp_password]):
        raise RuntimeError(
            "SMTP_SERVER, SMTP_PORT, SMTP_USERNAME and SMTP_PASSWORD must be set"
        )
    if not args.sender_email:
        raise RuntimeError(
            "Sender e-mail address must be provided via --sender_email or SMTP_SENDER_EMAIL"
        )

    ctx = SendEmailContext(
        sender_name=args.sender_name or args.sender_email,
        sender_email=args.sender_email,
        recipient=args.recipient,
        subject=args.subject,
        body=args.body,
    )
    asyncio.run(
        send_email_via_smtp_async(
            ctx,
            smtp_server,
            smtp_port,
            smtp_username,
            smtp_password,
            use_starttls=args.use_starttls,
        )
    )


if __name__ == "__main__":
    main()
