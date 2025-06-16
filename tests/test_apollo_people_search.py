import csv
import asyncio
from utils import apollo_people_search as mod


class DummyResp:
    def __init__(self, data):
        self.data = data

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        pass

    async def json(self):
        return self.data


class DummySession:
    def __init__(self, data):
        self.data = data
        self.posts = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        pass

    def post(self, url, headers=None, json=None):
        self.posts.append((url, json))
        return DummyResp(self.data)


class MultiSession:
    def __init__(self, data_list):
        self.data_list = data_list
        self.posts = []
        self.idx = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        pass

    def post(self, url, headers=None, json=None):
        data = self.data_list[min(self.idx, len(self.data_list) - 1)]
        self.idx += 1
        self.posts.append((url, json))
        return DummyResp(data)


def sample_payload():
    return {
        "contacts": [
            {
                "id": "1",
                "first_name": "Jane",
                "last_name": "Doe",
                "linkedin_url": "https://linkedin.com/in/janedoe",
                "email": "jane@example.com",
                "title": "CEO",
                "organization": {"name": "Acme", "primary_domain": "acme.com"},
            }
        ],
        "pagination": {"page": 1, "per_page": 1, "total_entries": 1, "total_pages": 1},
    }


def test_apollo_people_search(monkeypatch):
    data = sample_payload()
    session = DummySession(data)
    monkeypatch.setattr(mod.aiohttp, "ClientSession", lambda: session)
    monkeypatch.setattr(mod.asyncio, "sleep", lambda x: None)
    monkeypatch.setenv("APOLLO_API_KEY", "x")
    results = asyncio.run(mod.apollo_people_search(number_of_leads=1))
    assert session.posts[0][0].endswith("/mixed_people/search")
    assert results[0]["user_linkedin_url"] == "https://linkedin.com/in/janedoe"
    assert results[0]["organization_name"] == "Acme"
    assert results[0]["primary_domain_of_organization"] == "acme.com"


def test_apollo_people_search_to_csv(tmp_path, monkeypatch):
    data = sample_payload()
    session = DummySession(data)
    monkeypatch.setattr(mod.aiohttp, "ClientSession", lambda: session)
    monkeypatch.setattr(mod.asyncio, "sleep", lambda x: None)
    monkeypatch.setenv("APOLLO_API_KEY", "y")
    out_file = tmp_path / "out.csv"
    mod.apollo_people_search_to_csv(out_file, number_of_leads=1)
    rows = list(csv.DictReader(out_file.open()))
    assert rows[0]["user_linkedin_url"] == "https://linkedin.com/in/janedoe"


def test_apollo_people_search_pagination(monkeypatch):
    first = sample_payload()
    first["pagination"]["total_pages"] = 2
    second = sample_payload()
    second["contacts"][0]["id"] = "2"
    session = MultiSession([first, second])
    monkeypatch.setattr(mod.aiohttp, "ClientSession", lambda: session)
    sleeps = []

    async def fake_sleep(x):
        sleeps.append(x)

    monkeypatch.setattr(mod.asyncio, "sleep", fake_sleep)
    monkeypatch.setenv("APOLLO_API_KEY", "z")
    results = asyncio.run(mod.apollo_people_search(number_of_leads=2))
    assert len(session.posts) == 2
    assert sleeps == [10]
    assert len(results) == 2
