import asyncio
from utils import salesforce_get_contact as mod


class DummyResponse:
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
    def __init__(self):
        self.get_calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        pass

    def get(self, url, headers=None, params=None):
        self.get_calls.append((url, params))
        if "query" in url:
            return DummyResponse({"records": [{"Id": "321"}]})
        return DummyResponse({"Id": "123"})


def test_get_by_id(monkeypatch):
    session = DummySession()
    monkeypatch.setattr(mod.aiohttp, "ClientSession", lambda: session)
    monkeypatch.setenv("SALESFORCE_INSTANCE_URL", "http://x")
    monkeypatch.setenv("SALESFORCE_ACCESS_TOKEN", "t")
    result = asyncio.run(mod.get_contact(contact_id="1"))
    assert session.get_calls[0][0].endswith("/Contact/1")
    assert result["Id"] == "123"


def test_get_by_email(monkeypatch):
    session = DummySession()
    monkeypatch.setattr(mod.aiohttp, "ClientSession", lambda: session)
    monkeypatch.setenv("SALESFORCE_INSTANCE_URL", "http://x")
    monkeypatch.setenv("SALESFORCE_ACCESS_TOKEN", "t")
    result = asyncio.run(mod.get_contact(email="a@b.com"))
    assert "query" in session.get_calls[0][0]
    assert result["Id"] == "321"
