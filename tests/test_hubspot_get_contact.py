import asyncio
from utils import hubspot_get_contact as mod

class DummyResponse:
    def __init__(self, data):
        self.data = data
    async def __aenter__(self):
        return self
    async def __aexit__(self, exc_type, exc, tb):
        pass
    async def json(self):
        return self.data

class DummySession:
    def __init__(self):
        self.get_calls = []
        self.post_calls = []
    async def __aenter__(self):
        return self
    async def __aexit__(self, exc_type, exc, tb):
        pass
    def get(self, url, headers=None):
        self.get_calls.append(url)
        return DummyResponse({"id": "123"})
    def post(self, url, headers=None, json=None):
        self.post_calls.append((url, json))
        return DummyResponse({"results": [{"id": "321"}]})


def test_get_by_id(monkeypatch):
    session = DummySession()
    monkeypatch.setattr(mod.aiohttp, "ClientSession", lambda: session)
    monkeypatch.setenv("HUBSPOT_API_KEY", "x")
    result = asyncio.run(mod.get_contact(hubspot_id="1"))
    assert session.get_calls[0].endswith("/contacts/1")
    assert result["id"] == "123"


def test_get_by_email(monkeypatch):
    session = DummySession()
    monkeypatch.setattr(mod.aiohttp, "ClientSession", lambda: session)
    monkeypatch.setenv("HUBSPOT_API_KEY", "x")
    result = asyncio.run(mod.get_contact(email="a@b.com"))
    assert "search" in session.post_calls[0][0]
    payload = session.post_calls[0][1]
    assert payload["filterGroups"][0]["filters"][0]["propertyName"] == "email"
    assert result["id"] == "321"
