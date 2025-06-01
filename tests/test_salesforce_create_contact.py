import asyncio
from utils import salesforce_create_contact as mod


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

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        pass

    def get(self, url, headers=None, params=None):
        self.calls.append(("get", url, params))
        return DummyResponse({"records": []})

    def post(self, url, headers=None, json=None):
        self.calls.append(("post", url, json))
        return DummyResponse({"id": "5"})


def test_create_contact(monkeypatch):
    session = DummySession()
    monkeypatch.setattr(mod.aiohttp, "ClientSession", lambda: session)
    monkeypatch.setenv("SALESFORCE_INSTANCE_URL", "http://x")
    monkeypatch.setenv("SALESFORCE_ACCESS_TOKEN", "t")
    result = asyncio.run(mod.create_contact(email="e@x.com", first_name="A"))
    assert any(c[0] == "get" and "query" in c[1] for c in session.calls)
    assert any(c[0] == "post" and c[1].endswith("/sobjects/Contact") for c in session.calls)
    assert result["id"] == "5"
