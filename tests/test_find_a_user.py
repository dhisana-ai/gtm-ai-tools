import asyncio
from utils import find_a_user_by_name_and_keywords as mod

async def fake_search(*args, **kwargs):
    return [
        {
            "link": "https://www.linkedin.com/in/john-doe",
            "title": "John Doe - CEO",
            "snippet": "1k followers New York",
        }
    ]

async def fake_structured(text: str):
    return mod.LeadSearchResult(first_name="John", last_name="Doe")

def test_find_user_linkedin_url(monkeypatch):
    monkeypatch.setattr(mod, "search_google_serper", fake_search)
    monkeypatch.setattr(mod, "get_structured_output", fake_structured)
    data = asyncio.run(mod.find_user_linkedin_url("John Doe"))
    assert data["user_linkedin_url"] == "https://www.linkedin.com/in/john-doe"
    assert data["first_name"] == "John"

