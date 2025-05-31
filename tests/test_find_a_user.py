import asyncio
from utils import find_a_user_by_name_and_keywords as mod

async def fake_search(*args, **kwargs):
    return [{"link": "https://www.linkedin.com/in/john-doe"}]

def test_find_user_linkedin_url(monkeypatch):
    monkeypatch.setattr(mod, "search_google_serper", fake_search)
    url = asyncio.run(mod.find_user_linkedin_url("John Doe"))
    assert url == "https://www.linkedin.com/in/john-doe"

