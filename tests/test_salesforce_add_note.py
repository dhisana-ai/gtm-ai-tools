import asyncio
from utils import salesforce_add_note as mod


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
        self.posts = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        pass

    def post(self, url, headers=None, json=None):
        self.posts.append((url, json))
        return DummyResponse({"id": "n"})


def test_add_note(monkeypatch):
    session = DummySession()
    monkeypatch.setattr(mod.aiohttp, "ClientSession", lambda: session)
    monkeypatch.setenv("SALESFORCE_INSTANCE_URL", "http://x")
    monkeypatch.setenv("SALESFORCE_ACCESS_TOKEN", "t")
    result = asyncio.run(mod.add_note("7", "hi"))
    assert session.posts[0][0].endswith("/sobjects/Note")
    assert session.posts[0][1]["ParentId"] == "7"
    assert result["id"] == "n"
