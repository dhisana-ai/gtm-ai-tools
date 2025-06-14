"""Extract companies and leads from any web page.

This module scrapes a page with Playwright and then asks an LLM to return
structured company or lead data."""

from __future__ import annotations

import os
import logging
import argparse
import asyncio
import json
from typing import List, Optional, Tuple, Type
from urllib.parse import urljoin

from bs4 import BeautifulSoup

try:
    from pydantic import BaseModel
except ImportError:  # pragma: no cover - fall back for tests without pydantic
    from pydantic_stub import BaseModel
from openai import AsyncOpenAI

from utils import fetch_html_playwright, common, find_company_info
from utils.call_openai_llm import _call_openai

logger = logging.getLogger(__name__)


class Company(BaseModel):
    organization_name: str = ""
    organization_website: str = ""
    primary_domain_of_organization: str = ""
    link_to_more_information: str = ""
    organization_linkedin_url: str = ""


class CompanyList(BaseModel):
    companies: List[Company]


class Lead(BaseModel):
    first_name: str = ""
    last_name: str = ""
    user_linkedin_url: str = ""
    organization_name: str = ""
    organization_website: str = ""
    primary_domain_of_organization: str = ""
    link_to_more_information: str = ""
    organization_linkedin_url: str = ""
    email: str = ""
    phone: str = ""
    linkedin_follower_count: int = 0


class LeadList(BaseModel):
    leads: List[Lead]


async def _get_structured_data_internal(
    prompt: str, model: Type[BaseModel]
) -> Tuple[Optional[BaseModel], str]:
    """Send ``prompt`` to OpenAI and parse the response as ``model``."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY environment variable is not set")

    client = AsyncOpenAI(api_key=api_key)
    try:
        response = await client.chat.completions.create(
            model=common.get_openai_model(),
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
        )
        text = response.choices[0].message.content or ""
        if not text:
            return None, "ERROR"
        return model.model_validate_json(text), "SUCCESS"
    except Exception:  # pragma: no cover - network failures etc.
        logger.exception("OpenAI call failed")
        return None, "ERROR"


async def _fetch_and_clean(url: str) -> str:
    html = await fetch_html_playwright.fetch_html(url)
    soup = BeautifulSoup(html or "", "html.parser")
    for tag in soup(["script", "style", "meta", "code", "svg"]):
        tag.decompose()
    return str(soup)


def _extract_linkedin_links(html: str) -> tuple[str, str]:
    """Return first user and company LinkedIn URLs found in HTML."""
    soup = BeautifulSoup(html or "", "html.parser")
    user_url = ""
    company_url = ""
    for tag in soup.find_all("a", href=True):
        href = tag["href"]
        if not user_url and "linkedin.com/in" in href:
            user_url = common.extract_user_linkedin_page(href)
        if not company_url and "linkedin.com/company" in href:
            company_url = find_company_info.extract_company_page(href)
        if user_url and company_url:
            break
    return user_url, company_url


async def _fetch_pages_by_selector(
    url: str, next_page_selector: str | None, max_next_pages: int
) -> List[str]:
    """Return HTML from ``url`` and any following pages."""

    pages: List[str] = []
    current = url
    visited: set[str] = set()
    for _ in range(max_next_pages + 1):
        if current in visited:
            break
        visited.add(current)
        html = await _fetch_and_clean(current)
        if not html:
            break
        pages.append(html)
        if not next_page_selector:
            break
        soup = BeautifulSoup(html, "html.parser")
        next_link = soup.select_one(next_page_selector)
        if not next_link:
            break
        href = next_link.get("href")
        if not href:
            break
        current = urljoin(current, href)

    return pages


async def _generate_js(html: str, instructions: str) -> str:
    """Return JavaScript for ``instructions`` using the page ``html``."""
    if not instructions.strip():
        return ""
    prompt = (
        "Here is the html of the page:\n"
        f"{html}\n\n"
        "Here is what user wants to do:\n"
        f"{instructions}\n\n"
        "Provide only the JavaScript code to execute with Playwright."
    )
    return await asyncio.to_thread(_call_openai, prompt)


async def _apply_actions(page, instructions: str) -> None:
    if not instructions.strip():
        return
    html = await page.content()
    js = await _generate_js(html, instructions)
    if js.strip():  # pragma: no cover - best effort
        try:
            await page.evaluate(js)
            await asyncio.sleep(2)
        except Exception:
            logger.exception("Failed to run generated JavaScript")


async def _fetch_pages_with_actions(
    url: str,
    initial_actions: str,
    page_actions: str,
    pagination_actions: str,
    max_pages: int,
) -> List[str]:
    pages: List[str] = []
    proxy = os.getenv("PROXY_URL")
    async with fetch_html_playwright.browser_ctx(proxy) as ctx:
        page = await ctx.new_page()
        await fetch_html_playwright.apply_stealth(page)
        await page.goto(url, timeout=120_000, wait_until="domcontentloaded")
        await _apply_actions(page, initial_actions)
        for i in range(max_pages):
            await _apply_actions(page, page_actions)
            html = await page.content()
            pages.append(html)
            if i == max_pages - 1:
                break
            await _apply_actions(page, pagination_actions)
            try:
                await page.wait_for_load_state("domcontentloaded", timeout=30_000)
            except Exception:  # pragma: no cover - navigation may fail
                break
    return pages


async def _fetch_pages(
    url: str,
    next_page_selector: str | None,
    max_next_pages: int,
    initial_actions: str = "",
    page_actions: str = "",
    pagination_actions: str = "",
    max_pages: int = 1,
) -> List[str]:
    if any([initial_actions, page_actions, pagination_actions]) or max_pages > 1:
        return await _fetch_pages_with_actions(
            url, initial_actions, page_actions, pagination_actions, max_pages
        )
    return await _fetch_pages_by_selector(url, next_page_selector, max_next_pages)


async def extract_multiple_companies_from_webpage(
    url: str,
    next_page_selector: str | None = None,
    max_next_pages: int = 0,
    *,
    parse_instructions: str = "",
    initial_actions: str = "",
    page_actions: str = "",
    pagination_actions: str = "",
    max_pages: int = 1,
) -> List[Company]:
    pages = await _fetch_pages(
        url,
        next_page_selector,
        max_next_pages,
        initial_actions,
        page_actions,
        pagination_actions,
        max_pages,
    )
    aggregated: list[Company] = []
    for html in pages:
        _user_link, org_link = _extract_linkedin_links(html)
        text = BeautifulSoup(html, "html.parser").get_text("\n", strip=True)
        prompt = (
            "Extract all companies mentioned in the text below.\n"
            f"{parse_instructions}\n"
            f"Return JSON matching this schema:\n{json.dumps(CompanyList.model_json_schema(), indent=2)}\n\n"
            f"Text:\n{text}"
        )
        result, status = await _get_structured_data_internal(prompt, CompanyList)
        if status != "SUCCESS" or result is None:
            continue
        companies = result.companies
        if org_link:
            for c in companies:
                c.organization_linkedin_url = org_link
        aggregated.extend(companies)
    return aggregated


async def extract_comapy_from_webpage(
    url: str,
    next_page_selector: str | None = None,
    max_next_pages: int = 0,
    *,
    parse_instructions: str = "",
    initial_actions: str = "",
    page_actions: str = "",
    pagination_actions: str = "",
    max_pages: int = 1,
) -> Optional[Company]:
    companies = await extract_multiple_companies_from_webpage(
        url,
        next_page_selector,
        max_next_pages,
        parse_instructions=parse_instructions,
        initial_actions=initial_actions,
        page_actions=page_actions,
        pagination_actions=pagination_actions,
        max_pages=max_pages,
    )
    return companies[0] if companies else None


async def extract_multiple_leads_from_webpage(
    url: str,
    next_page_selector: str | None = None,
    max_next_pages: int = 0,
    *,
    parse_instructions: str = "",
    initial_actions: str = "",
    page_actions: str = "",
    pagination_actions: str = "",
    max_pages: int = 1,
) -> List[Lead]:
    pages = await _fetch_pages(
        url,
        next_page_selector,
        max_next_pages,
        initial_actions,
        page_actions,
        pagination_actions,
        max_pages,
    )
    aggregated: list[Lead] = []
    for html in pages:
        user_link, org_link = _extract_linkedin_links(html)
        text = BeautifulSoup(html, "html.parser").get_text("\n", strip=True)
        prompt = (
            "Extract all leads mentioned in the text below.\n"
            f"{parse_instructions}\n"
            f"Return JSON matching this schema:\n{json.dumps(LeadList.model_json_schema(), indent=2)}\n\n"
            f"Text:\n{text}"
        )
        result, status = await _get_structured_data_internal(prompt, LeadList)
        if status != "SUCCESS" or result is None:
            continue
        leads = result.leads
        if user_link or org_link:
            for lead in leads:
                if user_link:
                    lead.user_linkedin_url = user_link
                if org_link:
                    lead.organization_linkedin_url = org_link
        aggregated.extend(leads)
    return aggregated


async def extract_lead_from_webpage(
    url: str,
    next_page_selector: str | None = None,
    max_next_pages: int = 0,
    *,
    parse_instructions: str = "",
    initial_actions: str = "",
    page_actions: str = "",
    pagination_actions: str = "",
    max_pages: int = 1,
) -> Optional[Lead]:
    leads = await extract_multiple_leads_from_webpage(
        url,
        next_page_selector,
        max_next_pages,
        parse_instructions=parse_instructions,
        initial_actions=initial_actions,
        page_actions=page_actions,
        pagination_actions=pagination_actions,
        max_pages=max_pages,
    )
    return leads[0] if leads else None


def _write_companies_csv(companies: List[Company], path: str) -> None:
    import csv

    fieldnames = [
        "organization_name",
        "organization_website",
        "primary_domain_of_organization",
        "link_to_more_information",
        "organization_linkedin_url",
    ]
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for c in companies:
            writer.writerow(json.loads(c.model_dump_json()))


def _write_leads_csv(leads: List[Lead], path: str) -> None:
    import csv

    fieldnames = [
        "first_name",
        "last_name",
        "user_linkedin_url",
        "organization_name",
        "organization_website",
        "primary_domain_of_organization",
        "link_to_more_information",
        "organization_linkedin_url",
        "email",
        "phone",
        "linkedin_follower_count",
    ]
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for l in leads:
            writer.writerow(json.loads(l.model_dump_json()))


async def _run_cli(url: str, args: argparse.Namespace) -> None:
    next_sel = args.next_page_selector
    max_next = args.max_next_pages
    parse_ins = args.parse_instructions or ""
    initial_actions = args.initial_actions or ""
    page_actions = args.page_actions or ""
    pagination_actions = args.pagination_actions or ""
    max_pages = args.max_pages
    if args.lead:
        result = await extract_lead_from_webpage(
            url,
            next_sel,
            max_next,
            parse_instructions=parse_ins,
            initial_actions=initial_actions,
            page_actions=page_actions,
            pagination_actions=pagination_actions,
            max_pages=max_pages,
        )
        if result:
            print(result.model_dump_json(indent=2))
        return
    if args.leads:
        result = await extract_multiple_leads_from_webpage(
            url,
            next_sel,
            max_next,
            parse_instructions=parse_ins,
            initial_actions=initial_actions,
            page_actions=page_actions,
            pagination_actions=pagination_actions,
            max_pages=max_pages,
        )
        if args.output_csv:
            _write_leads_csv(result, args.output_csv)
        else:
            print(
                "[]" if not result else LeadList(leads=result).model_dump_json(indent=2)
            )
        return
    if args.company:
        result = await extract_comapy_from_webpage(
            url,
            next_sel,
            max_next,
            parse_instructions=parse_ins,
            initial_actions=initial_actions,
            page_actions=page_actions,
            pagination_actions=pagination_actions,
            max_pages=max_pages,
        )
        if result:
            print(result.model_dump_json(indent=2))
        return
    if args.companies:
        result = await extract_multiple_companies_from_webpage(
            url,
            next_sel,
            max_next,
            parse_instructions=parse_ins,
            initial_actions=initial_actions,
            page_actions=page_actions,
            pagination_actions=pagination_actions,
            max_pages=max_pages,
        )
        if args.output_csv:
            _write_companies_csv(result, args.output_csv)
        else:
            print(
                "[]"
                if not result
                else CompanyList(companies=result).model_dump_json(indent=2)
            )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract leads or companies from a web page"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--lead", action="store_true", help="Extract one lead")
    group.add_argument("--leads", action="store_true", help="Extract multiple leads")
    group.add_argument("--company", action="store_true", help="Extract one company")
    group.add_argument("--companies", action="store_true", help="Extract multiple companies")
    parser.add_argument("url", help="Website URL")
    parser.add_argument("--next_page_selector", help="CSS selector for next page link")
    parser.add_argument(
        "--max_next_pages",
        type=int,
        default=0,
        help="Number of next pages to parse",
    )
    parser.add_argument("--initial_actions", help="Actions on initial load")
    parser.add_argument("--page_actions", help="Actions on each page load")
    parser.add_argument(
        "--parse_instructions",
        help="Instructions for parsing leads",
    )
    parser.add_argument("--pagination_actions", help="Actions for pagination")
    parser.add_argument(
        "--max_pages",
        type=int,
        default=1,
        help="Max pages to navigate",
    )
    parser.add_argument("--output_csv", help="Output CSV path")
    args = parser.parse_args()
    asyncio.run(_run_cli(args.url, args))


if __name__ == "__main__":
    main()
