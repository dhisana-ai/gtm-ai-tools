import asyncio
import csv
import pytest
from utils import extract_from_webpage as mod


async def fake_fetch_lead(url: str):
    return "<html><a href='https://linkedin.com/in/john-doe'></a></html>"


async def fake_get_lead(prompt: str, model):
    return mod.LeadList(leads=[mod.Lead(first_name="John", last_name="Doe")]), "SUCCESS"


async def fake_fetch_company(url: str):
    return "<html><a href='http://linkedin.com/company/acme'></a></html>"


async def fake_get_company(prompt: str, model):
    return mod.CompanyList(companies=[mod.Company(organization_name="Acme")]), "SUCCESS"


def test_extract_lead_from_webpage_linkedin(monkeypatch):
    monkeypatch.setattr(mod, "_fetch_and_clean", fake_fetch_lead)
    monkeypatch.setattr(mod, "_get_structured_data_internal", fake_get_lead)
    lead = asyncio.run(mod.extract_lead_from_webpage("http://x.com"))
    assert lead.user_linkedin_url == "https://www.linkedin.com/in/john-doe"


def test_extract_company_from_webpage_linkedin(monkeypatch):
    monkeypatch.setattr(mod, "_fetch_and_clean", fake_fetch_company)
    monkeypatch.setattr(mod, "_get_structured_data_internal", fake_get_company)
    company = asyncio.run(mod.extract_comapy_from_webpage("http://y.com"))
    assert company.organization_linkedin_url == "https://www.linkedin.com/company/acme"


def test_extract_companies_with_pagination(monkeypatch):
    pages = {
        "http://start.com": "<html><a href='http://linkedin.com/company/acme'></a><a class='next' href='page2'></a></html>",
        "http://start.com/page2": "<html><a href='http://linkedin.com/company/beta'></a></html>",
    }

    async def fake_fetch(url: str):
        return pages[url]

    results = [
        mod.CompanyList(companies=[mod.Company(organization_name="Acme")]),
        mod.CompanyList(companies=[mod.Company(organization_name="Beta")]),
    ]

    async def fake_get(prompt: str, model):
        return results.pop(0), "SUCCESS"

    monkeypatch.setattr(mod, "_fetch_and_clean", fake_fetch)
    monkeypatch.setattr(mod, "_get_structured_data_internal", fake_get)
    companies = asyncio.run(
        mod.extract_multiple_companies_from_webpage("http://start.com", ".next", 1)
    )
    names = [c.organization_name for c in companies]
    assert names == ["Acme", "Beta"]


def test_parse_instructions_in_prompt(monkeypatch):
    monkeypatch.setattr(mod, "_fetch_and_clean", fake_fetch_lead)

    captured = {}

    async def fake_get(prompt: str, model):
        captured["prompt"] = prompt
        return mod.LeadList(leads=[mod.Lead(first_name="Jane")]), "SUCCESS"

    monkeypatch.setattr(mod, "_get_structured_data_internal", fake_get)
    asyncio.run(
        mod.extract_lead_from_webpage(
            "http://x.com",
            parse_instructions="Look carefully",
        )
    )
    assert "Look carefully" in captured["prompt"]


def test_extract_from_webpage_from_csv(tmp_path, monkeypatch):
    async def fake_many(url, *a, **k):
        return [mod.Lead(first_name=url)]

    monkeypatch.setattr(
        mod,
        "extract_multiple_leads_from_webpage",
        fake_many,
    )
    in_file = tmp_path / "in.csv"
    in_file.write_text("website_url\nhttp://a.com\nhttp://b.com\n")
    out_file = tmp_path / "out.csv"
    mod.extract_from_webpage_from_csv(in_file, out_file)
    rows = list(csv.DictReader(out_file.open()))
    assert [r["first_name"] for r in rows] == ["http://a.com", "http://b.com"]


def test_extract_from_webpage_from_csv_missing_col(tmp_path):
    bad = tmp_path / "bad.csv"
    bad.write_text("foo\n1\n")
    with pytest.raises(ValueError):
        mod.extract_from_webpage_from_csv(bad, tmp_path / "o.csv")
