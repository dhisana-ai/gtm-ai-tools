import asyncio
import csv
import json
import pytest
from utils import apollo_info as mod

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
        self.gets = []
    async def __aenter__(self):
        return self
    async def __aexit__(self, exc_type, exc, tb):
        pass
    def post(self, url, headers=None, json=None):
        self.posts.append((url, json))
        return DummyResp(self.data)
    def get(self, url, headers=None):
        self.gets.append(url)
        return DummyResp(self.data)


def test_get_person_info(monkeypatch):
    payload = {
        "person": {
            "name": "John Doe",
            "first_name": "John",
            "last_name": "Doe",
            "email": "john@doe.com",
            "linkedin_url": "https://linkedin.com/in/johndoe",
            "organization": {
                "name": "Acme",
                "primary_domain": "acme.com",
            },
        }
    }
    session = DummySession(payload)
    monkeypatch.setattr(mod.aiohttp, "ClientSession", lambda: session)
    monkeypatch.setenv("APOLLO_API_KEY", "x")
    result = asyncio.run(mod.get_person_info(email="a@b.com"))
    assert session.posts[0][0].endswith("/people/match")
    assert session.posts[0][1] == {"email": "a@b.com"}
    assert result["full_name"] == "John Doe"
    assert result["user_linkedin_url"] == "https://linkedin.com/in/johndoe"
    assert result["organization_name"] == "Acme"
    assert result["primary_domain_of_organization"] == "acme.com"


def test_get_person_info_by_name_and_domain(monkeypatch):
    payload = {"person": {"name": "Jane", "first_name": "Jane"}}
    session = DummySession(payload)
    monkeypatch.setattr(mod.aiohttp, "ClientSession", lambda: session)
    monkeypatch.setenv("APOLLO_API_KEY", "x")
    result = asyncio.run(
        mod.get_person_info(full_name="John Doe", company_domain="https://foo.com")
    )
    assert session.posts[0][1] == {"name": "John Doe", "domain": "foo.com"}
    assert result["full_name"] == "Jane"


def test_get_company_info(monkeypatch):
    session = DummySession({"id": "org"})
    monkeypatch.setattr(mod.aiohttp, "ClientSession", lambda: session)
    monkeypatch.setenv("APOLLO_API_KEY", "y")
    result = asyncio.run(mod.get_company_info(company_url="https://foo.com"))
    assert session.gets[0].endswith("domain=foo.com")
    assert result["id"] == "org"


def test_missing_api_key(monkeypatch):
    monkeypatch.delenv("APOLLO_API_KEY", raising=False)
    with pytest.raises(RuntimeError):
        asyncio.run(mod.get_person_info(email="e@x.com"))


async def fake_get_person_info(linkedin_url="", email="", full_name="", company_domain=""):
    return {"user_linkedin_url": linkedin_url, "email": email}


def test_apollo_info_from_csv(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "get_person_info", fake_get_person_info)
    in_file = tmp_path / "in.csv"
    in_file.write_text("user_linkedin_url,email\nhttps://linkedin.com/in/foo,foo@x.com\n")
    out_file = tmp_path / "out.csv"
    mod.apollo_info_from_csv(in_file, out_file)
    with out_file.open() as fh:
        rows = list(csv.DictReader(fh))
    assert rows[0]["email"] == "foo@x.com"
    assert rows[0]["user_linkedin_url"] == "https://linkedin.com/in/foo"


def test_apollo_info_from_csv_missing_cols(tmp_path):
    bad = tmp_path / "bad.csv"
    bad.write_text("foo,bar\n1,2\n")
    with pytest.raises(ValueError):
        mod.apollo_info_from_csv(bad, tmp_path / "out.csv")
