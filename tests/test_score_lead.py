import csv
import json
from utils import score_lead as mod


class DummyModel(mod.LeadScore):
    pass


async def fake_structured(prompt: str, model):
    return DummyModel(lead_score=4), "SUCCESS"


def test_score_lead(monkeypatch):
    monkeypatch.setattr(mod, "_get_structured_data_internal", fake_structured)
    score = mod.score_lead({"name": "John"}, "Score him")
    assert score == 4


def test_score_leads_from_csv(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "score_lead", lambda row, ins: 5)
    in_file = tmp_path / "in.csv"
    in_file.write_text("name\nJohn\n")
    out_file = tmp_path / "out.csv"
    mod.score_leads_from_csv(in_file, out_file, "Score them")
    rows = list(csv.DictReader(out_file.open()))
    assert rows[0]["lead_score"] == "5"
