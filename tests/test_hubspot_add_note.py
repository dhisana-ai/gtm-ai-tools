import asyncio
from utils import hubspot_add_note as mod

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
        return DummyResponse({"noteId": "n"})


def test_add_note(monkeypatch):
    session = DummySession()
    monkeypatch.setattr(mod.aiohttp, "ClientSession", lambda: session)
    monkeypatch.setenv("HUBSPOT_API_KEY", "x")
    result = asyncio.run(mod.add_note("7", "hi"))
    assert session.posts[0][0].endswith("/crm/v3/objects/notes")
    assert session.posts[0][1]["associations"][0]["to"]["id"] == "7"
    assert result["noteId"] == "n"
