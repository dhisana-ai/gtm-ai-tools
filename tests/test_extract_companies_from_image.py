import sys
import json
from types import SimpleNamespace
import asyncio
from utils import extract_companies_from_image as mod

class DummyClient:
    def __init__(self):
        self.kwargs = None
        self.responses = SimpleNamespace(create=self.create)

    def create(self, **kwargs):
        self.kwargs = kwargs
        return SimpleNamespace(output_text='["Acme"]')

async def fake_details(name, location=None):
    return {
        "company_website": "https://acme.com",
        "company_domain": "acme.com",
        "linkedin_url": "https://www.linkedin.com/company/acme",
    }


def test_main(monkeypatch, tmp_path, capsys):
    dummy = DummyClient()
    monkeypatch.setattr(mod, "OpenAI", lambda api_key=None: dummy)
    monkeypatch.setenv("OPENAI_API_KEY", "x")
    monkeypatch.setattr(mod.find_company_info, "find_company_details", fake_details)

    img = tmp_path / "logo.png"
    img.write_bytes(b"img")

    monkeypatch.setattr(sys, "argv", ["extract_companies_from_image.py", str(img)])
    mod.main()
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data[0]["company_name"] == "Acme"
    assert data[0]["company_domain"] == "acme.com"
    assert "input" in dummy.kwargs
