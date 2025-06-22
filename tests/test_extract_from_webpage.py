import asyncio
import csv
import pytest
from utils import extract_from_webpage as mod
from utils import fetch_html_playwright as fhp


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


def test_extract_from_webpage_from_csv_dedup_leads(tmp_path, monkeypatch):
    calls = 0

    async def fake_many(url, *a, **k):
        nonlocal calls
        calls += 1
        if calls == 1:
            return [
                mod.Lead(first_name="A1", user_linkedin_url="u1", organization_name="Acme"),
                mod.Lead(first_name="A2", user_linkedin_url="u2", organization_name="Beta"),
            ]
        return [
            mod.Lead(first_name="B1", user_linkedin_url="u1", organization_name="Acme"),
            mod.Lead(first_name="B2", user_linkedin_url="u3", organization_name="Beta"),
            mod.Lead(first_name="B3", email="x@example.com", organization_name="Gamma"),
        ]

    monkeypatch.setattr(mod, "extract_multiple_leads_from_webpage", fake_many)
    in_file = tmp_path / "in.csv"
    in_file.write_text("website_url\nhttp://a.com\nhttp://b.com\n")
    out_file = tmp_path / "out.csv"
    mod.extract_from_webpage_from_csv(in_file, out_file)
    rows = list(csv.DictReader(out_file.open()))
    assert len(rows) == 3
    assert {r["organization_name"] for r in rows} == {"Acme", "Beta", "Gamma"}


def test_extract_from_webpage_from_csv_dedup_companies(tmp_path, monkeypatch):
    calls = 0

    async def fake_many(url, *a, **k):
        nonlocal calls
        calls += 1
        if calls == 1:
            return [mod.Company(organization_name="Acme")]
        return [mod.Company(organization_name="Acme"), mod.Company(organization_name="Beta")]

    monkeypatch.setattr(mod, "extract_multiple_companies_from_webpage", fake_many)
    in_file = tmp_path / "in.csv"
    in_file.write_text("website_url\nhttp://a.com\nhttp://b.com\n")
    out_file = tmp_path / "out.csv"
    mod.extract_from_webpage_from_csv(in_file, out_file, mode="companies")
    rows = list(csv.DictReader(out_file.open()))
    assert len(rows) == 2
    assert {r["organization_name"] for r in rows} == {"Acme", "Beta"}


def test_run_js_on_page(monkeypatch):
    captured = {}

    async def fake_fetch(*a, **k):
        return [mod.PageData("<html></html>", "hello world")]

    monkeypatch.setattr(mod, "_fetch_pages", fake_fetch)

    async def fake_get(prompt: str, model):
        captured["prompt"] = prompt
        return mod.LeadList(leads=[mod.Lead(first_name="x")]), "SUCCESS"

    monkeypatch.setattr(mod, "_get_structured_data_internal", fake_get)

    asyncio.run(mod.extract_lead_from_webpage("http://x.com", run_js_on_page="js"))
    assert "hello world" in captured["prompt"]


def test_run_js_logs_output(monkeypatch):
    class DummyLogger:
        def __init__(self):
            self.messages = []

        def info(self, msg, *args, **kwargs):
            self.messages.append(msg % args)

        def exception(self, *a, **kw):
            pass

        def debug(self, *a, **kw):
            pass

    dummy_logger = DummyLogger()
    monkeypatch.setattr(mod, "logger", dummy_logger)

    class DummyPage:
        async def goto(self, *a, **kw):
            pass

        async def content(self):
            return "<html></html>"

        async def evaluate(self, script):
            return "js result"

    class DummyContext:
        async def new_page(self):
            return DummyPage()

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            pass

    class DummyCtxMgr:
        async def __aenter__(self):
            return DummyContext()

        async def __aexit__(self, exc_type, exc, tb):
            pass

    monkeypatch.setattr(fhp, "browser_ctx", lambda proxy=None: DummyCtxMgr())

    async def noop(*a, **kw):
        return None

    monkeypatch.setattr(fhp, "apply_stealth", noop)

    class BasicSoup:
        def __init__(self, text="", *a, **kw):
            self.text = text

        def __call__(self, *args, **kw):
            return []

        def find_all(self, *a, **kw):
            return []

        def select_one(self, *a, **kw):
            return None

        def get_text(self, *a, **kw):
            return self.text

    monkeypatch.setattr(mod, "BeautifulSoup", BasicSoup)

    async def fake_get(prompt: str, model):
        return mod.LeadList(leads=[mod.Lead(first_name="z")]), "SUCCESS"

    monkeypatch.setattr(mod, "_get_structured_data_internal", fake_get)

    asyncio.run(mod.extract_lead_from_webpage("http://x.com", run_js_on_page="js"))

    assert any("js result" in m for m in dummy_logger.messages)

