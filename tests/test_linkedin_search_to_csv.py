from pathlib import Path
import pytest
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


def test_linkedin_search_to_csv_from_csv(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "search_google_serper", fake_search)
    in_file = tmp_path / "in.csv"
    in_file.write_text("search_query,number_of_responses\nfoo,2\n")
    out_file = tmp_path / "out.csv"
    mod.linkedin_search_to_csv_from_csv(in_file, out_file)
    lines = out_file.read_text().splitlines()
    assert lines[0].strip() == "user_linkedin_url"
    assert "linkedin.com/in/jane" in lines[1]


def test_linkedin_search_to_csv_from_csv_missing_cols(tmp_path):
    bad_file = tmp_path / "bad.csv"
    bad_file.write_text("foo,bar\n1,2\n")
    with pytest.raises(ValueError):
        mod.linkedin_search_to_csv_from_csv(bad_file, tmp_path / "out.csv")

