import csv
import json
from utils import generate_email as mod


class DummyEmail(mod.EmailCopy):
    pass


async def fake_structured(prompt: str, model):
    return DummyEmail(subject="Hi", body="Body"), "SUCCESS"


def test_generate_email(monkeypatch):
    monkeypatch.setattr(mod, "_get_structured_data_internal", fake_structured)
    result = mod.generate_email({"name": "John"}, "Say hi")
    assert result["subject"] == "Hi"
    assert result["body"] == "Body"


def test_generate_emails_from_csv(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "generate_email", lambda row, ins: {"subject": "S", "body": "B"})
    in_file = tmp_path / "in.csv"
    in_file.write_text("name\nJohn\n")
    out_file = tmp_path / "out.csv"
    mod.generate_emails_from_csv(in_file, out_file, "Ins")
    rows = list(csv.DictReader(out_file.open()))
    assert rows[0]["email_subject"] == "S"
    assert rows[0]["email_body"] == "B"
