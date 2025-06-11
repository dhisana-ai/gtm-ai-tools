import csv
from pathlib import Path
from utils import find_users_by_name_and_keywords as mod

async def fake_find(full_name: str, search_keywords: str = ""):
    return {
        "full_name": full_name,
        "user_linkedin_url": f"https://www.linkedin.com/in/{full_name.lower().replace(' ', '')}",
        "first_name": full_name.split()[0],
        "last_name": full_name.split()[-1],
        "job_title": "CEO",
        "linkedin_follower_count": 0,
        "lead_location": "",
        "summary_about_lead": "",
    }

def test_find_users(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "find_user_linkedin_url", fake_find)
    input_file = tmp_path / "in.csv"
    with input_file.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["full_name", "search_keywords"])
        writer.writeheader()
        writer.writerow({"full_name": "John Doe", "search_keywords": ""})
    output_file = tmp_path / "out.csv"
    mod.find_users(input_file, output_file)
    rows = list(csv.DictReader(output_file.open()))
    assert rows[0]["user_linkedin_url"] == "https://www.linkedin.com/in/johndoe"
    assert rows[0]["first_name"] == "John"

