import asyncio
import csv
from utils import check_email_zero_bounce as mod


class DummyResp:
    def __init__(self, data, status=200):
        self.data = data
        self.status = status

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        pass

    async def json(self):
        return self.data


class DummySession:
    def __init__(self, data):
        self.data = data
        self.get_calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        pass

    def get(self, url):
        self.get_calls.append(url)
        return DummyResp(self.data)


def test_valid(monkeypatch):
    session = DummySession({"status": "valid"})
    monkeypatch.setattr(mod.aiohttp, "ClientSession", lambda: session)
    monkeypatch.setenv("ZERO_BOUNCE_API_KEY", "x")
    result = asyncio.run(mod.check_email("a@b.com"))
    assert session.get_calls
    assert result["confidence"] == "high"
    assert result["is_valid"] is True


def test_invalid(monkeypatch):
    session = DummySession({"status": "invalid"})
    monkeypatch.setattr(mod.aiohttp, "ClientSession", lambda: session)
    monkeypatch.setenv("ZERO_BOUNCE_API_KEY", "x")
    result = asyncio.run(mod.check_email("a@b.com"))
    assert result["confidence"] == "low"
    assert result["is_valid"] is False


async def fake_check_email(email: str) -> dict:
    return {"email": email, "confidence": "high", "is_valid": True}


def test_check_emails_from_csv(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "check_email", fake_check_email)
    in_file = tmp_path / "in.csv"
    in_file.write_text("email,name\na@b.com,John\n")
    out_file = tmp_path / "out.csv"
    monkeypatch.setenv("ZERO_BOUNCE_API_KEY", "k")
    mod.check_emails_from_csv(in_file, out_file)
    rows = list(csv.DictReader(out_file.open()))
    assert rows[0]["is_email_valid"] == "true"
    assert rows[0]["email_confidence"] == "high"
