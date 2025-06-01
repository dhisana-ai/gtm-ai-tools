import asyncio
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


def test_find_email_and_phone(monkeypatch):
    data = {"contact": {"email": "e@x.com", "phoneNumbers": ["123"]}}
    session = DummySession(data)
    monkeypatch.setattr(mod.aiohttp, "ClientSession", lambda: session)
    monkeypatch.setenv("FINDYMAIL_API_KEY", "key")
    result = asyncio.run(mod.find_email_and_phone("John Doe", "example.com"))
    assert session.posts[0][0].endswith("/search/name")
    assert result["email"] == "e@x.com"
    assert result["phone"] == "123"


def test_missing_api_key(monkeypatch):
    monkeypatch.delenv("FINDYMAIL_API_KEY", raising=False)
    with pytest.raises(RuntimeError):
        asyncio.run(mod.find_email_and_phone("A", "b.com"))

