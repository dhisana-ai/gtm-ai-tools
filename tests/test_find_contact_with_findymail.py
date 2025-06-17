import asyncio
import csv
import pytest
from utils import find_contact_with_findymail as mod


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
        self.posts = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        pass

    def post(self, url, headers=None, json=None):
        self.posts.append((url, json))
        return DummyResp(self.data)


def test_find_email_and_phone_by_linkedin(monkeypatch):
    data = {"contact": {"email": "e@x.com", "phoneNumbers": ["123"]}}
    session = DummySession(data)
    monkeypatch.setattr(mod.aiohttp, "ClientSession", lambda: session)
    monkeypatch.setenv("FINDYMAIL_API_KEY", "key")
    result = asyncio.run(
        mod.find_email_and_phone(
            "John Doe",
            "example.com",
            linkedin_url="https://linkedin.com/in/foo",
        )
    )
    assert session.posts[0][0].endswith("/search/linkedin")
    assert result["email"] == "e@x.com"
    assert result["phone"] == "123"


def test_find_email_and_phone_by_name(monkeypatch):
    data = {"contact": {"email": "e@x.com"}}
    session = DummySession(data)
    monkeypatch.setattr(mod.aiohttp, "ClientSession", lambda: session)
    monkeypatch.setenv("FINDYMAIL_API_KEY", "key")
    result = asyncio.run(
        mod.find_email_and_phone("John Doe", "example.com")
    )
    assert session.posts[0][0].endswith("/search/name")
    assert result["email"] == "e@x.com"


def test_missing_api_key(monkeypatch):
    monkeypatch.delenv("FINDYMAIL_API_KEY", raising=False)
    with pytest.raises(RuntimeError):
        asyncio.run(mod.find_email_and_phone("A", "b.com"))


async def fake_find_email_and_phone(full_name="", domain="", linkedin_url=""):
    return {"email": "e@x.com", "phone": "123", "contact_info": "{}"}


def test_from_csv(tmp_path, monkeypatch):
    in_file = tmp_path / "in.csv"
    in_file.write_text(
        "full_name,linkedin_url,primary_domain_of_organization\n"
        "John Doe,https://linkedin.com/in/johndoe,example.com\n"
    )
    out_file = tmp_path / "out.csv"
    monkeypatch.setattr(mod, "find_email_and_phone", fake_find_email_and_phone)
    mod.find_contact_with_findymail_from_csv(in_file, out_file)
    rows = list(csv.DictReader(out_file.open()))
    assert rows[0]["email"] == "e@x.com"

