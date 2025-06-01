import asyncio
from utils import salesforce_update_contact as mod


class DummyResponse:
    def __init__(self, data, status=204):
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
        self.patches = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        pass

    def patch(self, url, headers=None, json=None):
        self.patches.append((url, json))
        return DummyResponse({}, status=204)


def test_update_contact(monkeypatch):
    session = DummySession()
    monkeypatch.setattr(mod.aiohttp, "ClientSession", lambda: session)
    monkeypatch.setenv("SALESFORCE_INSTANCE_URL", "http://x")
    monkeypatch.setenv("SALESFORCE_ACCESS_TOKEN", "t")
    result = asyncio.run(mod.update_contact("7", {"Phone": "1"}))
    assert session.patches[0][0].endswith("/Contact/7")
    assert session.patches[0][1]["Phone"] == "1"
    assert result["success"] is True
