import asyncio
from utils import extract_from_webpage as mod

async def fake_fetch_lead(url: str):
    return "<html><a href='https://linkedin.com/in/john-doe'></a></html>"

async def fake_get_lead(prompt: str, model):
    return mod.LeadList(leads=[mod.Lead(first_name='John', last_name='Doe')]), "SUCCESS"

async def fake_fetch_company(url: str):
    return "<html><a href='http://linkedin.com/company/acme'></a></html>"

async def fake_get_company(prompt: str, model):
    return mod.CompanyList(companies=[mod.Company(organization_name='Acme')]), "SUCCESS"


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
