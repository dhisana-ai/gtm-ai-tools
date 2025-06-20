import csv
from pathlib import Path
from utils import find_user_by_job_title as mod

async def fake_find(job_title: str, organization_name: str, search_keywords: str = "", exclude_profiles_intitle: bool = False):
    return f"https://www.linkedin.com/in/{organization_name.lower()}-{job_title.lower()}"

def test_find_user_by_job_title_from_csv(tmp_path, monkeypatch):
    in_file = tmp_path / "in.csv"
    with in_file.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh, fieldnames=["job_title", "organization_name", "search_keywords"]
        )
        writer.writeheader()
        writer.writerow({
            "job_title": "CEO",
            "organization_name": "Acme",
            "search_keywords": "sales",
        })
        writer.writerow({
            "job_title": "CEO",
            "organization_name": "Acme",
            "search_keywords": "sales",
        })
        writer.writerow({
            "job_title": "CTO",
            "organization_name": "Beta",
            "search_keywords": "",
        })
    out_file = tmp_path / "out.csv"
    monkeypatch.setattr(mod, "find_user_linkedin_url_by_job_title", fake_find)
    mod.find_user_by_job_title_from_csv(in_file, out_file)
    rows = list(csv.DictReader(out_file.open()))
    assert len(rows) == 2
    assert rows[0]["organization_name"] == "Acme"
    assert rows[0]["job_title"] == "CEO"
    assert rows[0]["user_linkedin_url"].endswith("acme-ceo")
