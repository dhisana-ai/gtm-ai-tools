import asyncio
from utils import push_lead_to_dhisana_webhook as mod

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

def test_push_lead(monkeypatch):
    session = DummySession()
    monkeypatch.setattr(mod.aiohttp, "ClientSession", lambda: session)
    monkeypatch.setenv("DHISANA_API_KEY", "key")
    result = asyncio.run(
        mod.push_lead_to_dhisana_webhook(
            "John Doe",
            linkedin_url="https://linkedin.com/in/johndoe",
            tags="vip",
            notes="important",
            webhook_url="http://hook",
        )
    )
    assert result is True
    assert session.calls[0][0] == "http://hook"
    assert session.calls[0][1]["X-API-Key"] == "key"
    payload = session.calls[0][2][0]
    assert payload["user_linkedin_url"] == "https://linkedin.com/in/johndoe"
    assert payload["tags"] == "vip"
    assert payload["notes"] == "important"

def test_skip_if_no_data(monkeypatch):
    session = DummySession()
    monkeypatch.setattr(mod.aiohttp, "ClientSession", lambda: session)
    monkeypatch.setenv("DHISANA_API_KEY", "key")
    result = asyncio.run(mod.push_lead_to_dhisana_webhook("Jane" , webhook_url="http://hook"))
    assert result is False
    assert session.calls == []
