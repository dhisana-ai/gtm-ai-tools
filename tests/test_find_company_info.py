import asyncio
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
    assert result["linkedin_url"] == "https://www.linkedin.com/company/foo"
    assert result["company_website"] == "https://foo.com/"
    assert result["company_domain"] == "foo.com"

