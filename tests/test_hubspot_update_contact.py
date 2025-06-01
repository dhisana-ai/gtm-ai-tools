import asyncio
from utils import hubspot_update_contact as mod

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
        self.patches = []
    async def __aenter__(self):
        return self
    async def __aexit__(self, exc_type, exc, tb):
        pass
    def patch(self, url, headers=None, json=None):
        self.patches.append((url, json))
        return DummyResponse({"ok": True})


def test_update_contact(monkeypatch):
    session = DummySession()
    monkeypatch.setattr(mod.aiohttp, "ClientSession", lambda: session)
    monkeypatch.setenv("HUBSPOT_API_KEY", "x")
    result = asyncio.run(mod.update_contact("7", {"phone": "1"}))
    assert session.patches[0][0].endswith("/contacts/7")
    assert session.patches[0][1]["properties"]["phone"] == "1"
    assert result["ok"] is True
