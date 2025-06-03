import asyncio
from utils import push_to_clay_table as mod

class DummyResponse:
    async def __aenter__(self):
        return self
    async def __aexit__(self, exc_type, exc, tb):
        pass
    def raise_for_status(self):
        pass

class DummySession:
    def __init__(self):
        self.calls = []
    async def __aenter__(self):
        return self
    async def __aexit__(self, exc_type, exc, tb):
        pass
    def post(self, url, headers=None, json=None):
        self.calls.append((url, headers, json))
        return DummyResponse()

def test_push(monkeypatch):
    session = DummySession()
    monkeypatch.setattr(mod.aiohttp, "ClientSession", lambda: session)
    monkeypatch.setenv("CLAY_API_KEY", "k")
    monkeypatch.setenv("CLAY_WEBHOOK_URL", "http://hook")
    result = asyncio.run(mod.push_to_clay_table({"name": "Foo"}))
    assert result is True
    assert session.calls[0][0] == "http://hook"
    assert session.calls[0][1]["x-clay-webhook-auth"] == "k"
    assert session.calls[0][2] == {"name": "Foo"}

def test_missing_env(monkeypatch):
    session = DummySession()
    monkeypatch.setattr(mod.aiohttp, "ClientSession", lambda: session)
    monkeypatch.delenv("CLAY_API_KEY", raising=False)
    monkeypatch.delenv("CLAY_WEBHOOK_URL", raising=False)
    result = asyncio.run(
        mod.push_to_clay_table({"x": 1}, webhook_url="http://h", api_key="k")
    )
    assert result is True
    assert session.calls[0][0] == "http://h"
    assert session.calls[0][1]["x-clay-webhook-auth"] == "k"
