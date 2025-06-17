import asyncio
import csv
from utils import find_company_info as mod

async def fake_search(query: str, *args, **kwargs):
    if "site:linkedin.com" in query:
        return [{"link": "https://www.linkedin.com/company/foo"}]
    return [{"link": "https://foo.com"}]

async def fake_get_external_links(url: str):
    return ["https://www.linkedin.com/redir/redirect?url=https%3A%2F%2Ffoo.com%2F&trk=about_website"]

def test_find_company_details(monkeypatch):
    monkeypatch.setattr(mod, "search_google_serper", fake_search)
    monkeypatch.setattr(mod, "get_external_links", fake_get_external_links)
    result = asyncio.run(mod.find_company_details("Foo"))
    assert result["organization_linkedin_url"] == "https://www.linkedin.com/company/foo"
    assert result["organization_website"] == "https://foo.com/"
    assert result["primary_domain_of_organization"] == "foo.com"


async def fake_details(name, location=None, organization_linkedin_url="", organization_website=""):
    return {
        "organization_name": name,
        "organization_website": "https://foo.com/",
        "primary_domain_of_organization": "foo.com",
        "organization_linkedin_url": "https://www.linkedin.com/company/foo",
    }


def test_find_company_info_from_csv(tmp_path, monkeypatch):
    in_file = tmp_path / "in.csv"
    in_file.write_text("organization_name\nFoo\n")
    out_file = tmp_path / "out.csv"
    monkeypatch.setattr(mod, "find_company_details", fake_details)
    mod.find_company_info_from_csv(in_file, out_file)
    rows = list(csv.DictReader(out_file.open()))
    assert rows[0]["organization_linkedin_url"].endswith("/foo")


