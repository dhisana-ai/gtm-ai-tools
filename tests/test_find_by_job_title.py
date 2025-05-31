import asyncio
from utils import find_user_by_job_title as mod

async def fake_search(*args, **kwargs):
    return [{"link": "https://www.linkedin.com/in/jane-doe"}]

def test_find_user_by_job_title(monkeypatch):
    monkeypatch.setattr(mod, "search_google_serper", fake_search)
    url = asyncio.run(mod.find_user_linkedin_url_by_job_title("CEO", "Acme"))
    assert url == "https://www.linkedin.com/in/jane-doe"
