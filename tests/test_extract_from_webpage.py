import sys
import json
import asyncio
import types

# Provide a dummy openai module with AsyncOpenAI and OpenAI so imports succeed
openai_stub = types.SimpleNamespace(
    AsyncOpenAI=lambda api_key=None: None,
    OpenAI=lambda api_key=None: None,
)
sys.modules['openai'] = openai_stub

from utils import extract_from_webpage as mod

async def fake_multi(url: str):
    return [mod.Company(organization_name="Acme")]

async def fake_single(url: str):
    return mod.Company(organization_name="Acme")

def test_extract_company(monkeypatch):
    monkeypatch.setattr(mod, "extract_multiple_companies_from_webpage", fake_multi)
    company = asyncio.run(mod.extract_company_from_webpage("http://e.com"))
    assert company.organization_name == "Acme"

def test_main_company(monkeypatch, capsys):
    monkeypatch.setattr(mod, "extract_company_from_webpage", fake_single)
    monkeypatch.setattr(sys, "argv", ["extract_from_webpage.py", "--company", "http://e.com"])
    mod.main()
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["organization_name"] == "Acme"
