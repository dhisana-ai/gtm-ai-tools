from pathlib import Path
from utils import linkedin_search_to_csv as mod

async def fake_search(*args, **kwargs):
    return [
        {"link": "https://www.linkedin.com/in/jane"},
        {"link": "https://example.com"},
    ]

def test_linkedin_search_to_csv(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "search_google_serper", fake_search)
    out_file = tmp_path / "out.csv"
    mod.linkedin_search_to_csv("query", 2, str(out_file))
    content = out_file.read_text().splitlines()
    assert content[0].strip() == "user_linkedin_url"
    assert "https://www.linkedin.com/in/jane" in content[1]

