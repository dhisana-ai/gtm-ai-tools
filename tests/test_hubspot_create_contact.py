import asyncio
from utils import hubspot_create_contact as mod

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
        self.calls = []
        self.payloads = []
    async def __aenter__(self):
        return self
    async def __aexit__(self, exc_type, exc, tb):
        pass
    def post(self, url, headers=None, json=None):
        self.calls.append(url)
        self.payloads.append(json)
        if "search" in url:
            return DummyResponse({"results": []})
        return DummyResponse({"id": "5"})


def test_create_contact(monkeypatch):
    session = DummySession()
    monkeypatch.setattr(mod.aiohttp, "ClientSession", lambda: session)
    monkeypatch.setenv("HUBSPOT_API_KEY", "x")
    result = asyncio.run(mod.create_contact(email="e@x.com", first_name="A"))
    assert "search" in session.calls[0]
    assert session.calls[1].endswith("/crm/v3/objects/contacts")
    assert result["id"] == "5"
