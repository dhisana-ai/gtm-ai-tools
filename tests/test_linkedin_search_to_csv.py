from pathlib import Path
import csv
import pytest
from utils import linkedin_search_to_csv as mod

async def fake_search(*args, **kwargs):
    return [
        {"link": "https://www.linkedin.com/in/jane", "title": "Jane Doe", "snippet": "CEO"},
        {"link": "https://example.com"},
    ]

async def fake_structured(text: str):
    return mod.LeadSearchResult(first_name="Jane", last_name="Doe")

def test_linkedin_search_to_csv(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "search_google_serper", fake_search)
    monkeypatch.setattr(mod, "get_structured_output", fake_structured)
    out_file = tmp_path / "out.csv"
    mod.linkedin_search_to_csv("query", 2, str(out_file))
    rows = list(csv.DictReader(out_file.open()))
    assert rows[0]["user_linkedin_url"] == "https://www.linkedin.com/in/jane"
    assert rows[0]["first_name"] == "Jane"


def test_linkedin_search_to_csv_from_csv(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "search_google_serper", fake_search)
    monkeypatch.setattr(mod, "get_structured_output", fake_structured)
    in_file = tmp_path / "in.csv"
    in_file.write_text("search_query,number_of_responses\nfoo,2\n")
    out_file = tmp_path / "out.csv"
    mod.linkedin_search_to_csv_from_csv(in_file, out_file)
    rows = list(csv.DictReader(out_file.open()))
    assert rows[0]["user_linkedin_url"].endswith("/jane")
    assert rows[0]["first_name"] == "Jane"


def test_linkedin_search_to_csv_from_csv_missing_cols(tmp_path):
    bad_file = tmp_path / "bad.csv"
    bad_file.write_text("foo,bar\n1,2\n")
    with pytest.raises(ValueError):
        mod.linkedin_search_to_csv_from_csv(bad_file, tmp_path / "out.csv")

