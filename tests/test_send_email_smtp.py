import asyncio
from utils import send_email_smtp as mod

class DummySMTP:
    def __init__(self):
        self.sent = []
    async def send(self, msg, **kwargs):
        self.sent.append((msg, kwargs))
        return (250, b"OK")

async def no_sleep(*args, **kwargs):
    return None

def test_send_email(monkeypatch):
    dummy = DummySMTP()
    monkeypatch.setattr(mod, "aiosmtplib", type("S", (), {"send": dummy.send}))
    monkeypatch.setattr(mod.asyncio, "sleep", no_sleep)
    ctx = mod.SendEmailContext(
        sender_name="S",
        sender_email="s@example.com",
        recipient="r@example.com",
        subject="Hello",
        body="Body",
    )
    msg_id = asyncio.run(
        mod.send_email_via_smtp_async(
            ctx,
            "smtp.example.com",
            587,
            "user",
            "pass",
        )
    )
    msg, kwargs = dummy.sent[0]
    assert msg["Subject"] == "Hello"
    assert kwargs["hostname"] == "smtp.example.com"
    assert msg_id.startswith("<")
