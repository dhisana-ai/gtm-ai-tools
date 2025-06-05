import asyncio
import pytest
from utils import apollo_info as mod

class DummyResp:
    def __init__(self, data):
        self.data = data
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
        self.gets = []
    async def __aenter__(self):
        return self
    async def __aexit__(self, exc_type, exc, tb):
        pass
    def post(self, url, headers=None, json=None):
        self.posts.append((url, json))
        return DummyResp(self.data)
    def get(self, url, headers=None):
        self.gets.append(url)
        return DummyResp(self.data)


def test_get_person_info(monkeypatch):
    session = DummySession({"person": {"id": "1"}})
    monkeypatch.setattr(mod.aiohttp, "ClientSession", lambda: session)
    monkeypatch.setenv("APOLLO_API_KEY", "x")
    result = asyncio.run(mod.get_person_info(email="a@b.com"))
    assert session.posts[0][0].endswith("/people/match")
    assert session.posts[0][1] == {"email": "a@b.com"}
    assert result["person"]["id"] == "1"


def test_get_company_info(monkeypatch):
    session = DummySession({"id": "org"})
    monkeypatch.setattr(mod.aiohttp, "ClientSession", lambda: session)
    monkeypatch.setenv("APOLLO_API_KEY", "y")
    result = asyncio.run(mod.get_company_info(company_url="https://foo.com"))
    assert session.gets[0].endswith("domain=foo.com")
    assert result["id"] == "org123"


def test_missing_api_key(monkeypatch):
    monkeypatch.delenv("APOLLO_API_KEY", raising=False)
    with pytest.raises(RuntimeError):
        asyncio.run(mod.get_person_info(email="e@x.com"))
