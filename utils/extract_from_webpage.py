"""Extract companies and leads from any web page.

This module scrapes a page with Playwright and then asks an LLM to return
structured company or lead data."""

from __future__ import annotations

import os
import logging
import argparse
import asyncio
import json
import sys
import typing
from typing import List, Optional, Tuple, Type, TextIO
from dataclasses import dataclass
from urllib.parse import urljoin
from pathlib import Path

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


@dataclass
class PageData:
    html: str
    js_output: Optional[str] = None


async def _get_structured_data_internal(
    prompt: str, model: Type[BaseModel]
) -> Tuple[Optional[BaseModel], str]:
    """Send ``prompt`` to OpenAI and parse the response as ``model``."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY environment variable is not set")

    try:
        async with AsyncOpenAI(api_key=api_key) as client:
            response = await client.responses.create(
                model=common.get_openai_model(),
                input=prompt,
            )
        text = getattr(response, "output_text", "") or ""
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
    logger.debug("Found LinkedIn user: %s, company: %s", user_url, company_url)
    return user_url, company_url


async def _fetch_pages_by_selector(
    url: str,
    next_page_selector: str | None,
    max_next_pages: int,
    run_js_on_page: str = "",
) -> List[PageData]:
    """Return HTML (and optional JS output) from ``url`` and following pages."""

    if not run_js_on_page.strip():
        pages: List[PageData] = []
        current = url
        visited: set[str] = set()
        for _ in range(max_next_pages + 1):
            logger.info("Fetching page %s", current)
            if current in visited:
                break
            visited.add(current)
            html = await _fetch_and_clean(current)
            if not html:
                break
            pages.append(PageData(html))
            if not next_page_selector:
                break
            soup = BeautifulSoup(html, "html.parser")
            next_link = soup.select_one(next_page_selector)
            if not next_link:
                logger.debug("No next link found with selector %s", next_page_selector)
                break
            href = next_link.get("href")
            if not href:
                logger.debug("Next link missing href attribute")
                break
            logger.info("Navigating to next page: %s", href)
            current = urljoin(current, href)
        return pages

    pages: List[PageData] = []
    proxy = os.getenv("PROXY_URL")
    async with fetch_html_playwright.browser_ctx(proxy) as ctx:
        page = await ctx.new_page()
        await fetch_html_playwright.apply_stealth(page)
        current = url
        visited: set[str] = set()
        for _ in range(max_next_pages + 1):
            logger.info("Navigating to %s", current)
            if current in visited:
                break
            visited.add(current)
            await page.goto(current, timeout=120_000, wait_until="domcontentloaded")
            html = await page.content()
            soup = BeautifulSoup(html or "", "html.parser")
            for tag in soup(["script", "style", "meta", "code", "svg"]):
                tag.decompose()
            js_out: Optional[str] = None
            try:
                js_out = await page.evaluate(run_js_on_page)
                logger.info("JavaScript output: %s", js_out)
            except Exception:
                logger.exception("Failed to run provided JavaScript")
            pages.append(PageData(str(soup), js_out))
            if not next_page_selector:
                break
            next_link = soup.select_one(next_page_selector)
            if not next_link:
                logger.debug("No next link found with selector %s", next_page_selector)
                break
            href = next_link.get("href")
            if not href:
                logger.debug("Next link missing href attribute")
                break
            logger.info("Navigating to next page: %s", href)
            current = urljoin(current, href)
    return pages


async def _generate_js(html: str, instructions: str) -> str:
    """Return JavaScript for ``instructions`` using the page ``html``."""
    if not instructions.strip():
        logger.debug("No instructions provided, skipping JavaScript generation")
        return ""
    prompt = (
        "Here is the html of the page:\n"
        f"{html}\n\n"
        "Here is what user wants to do:\n"
        f"{instructions}\n\n"
        "Provide only the JavaScript code to execute with Playwright."
    )
    js = await asyncio.to_thread(_call_openai, prompt)
    logger.debug("Generated JavaScript:\n%s", js)
    return js


async def _apply_actions(page, instructions: str) -> None:
    if not instructions.strip():
        logger.debug("No actions to apply")
        return
    html = await page.content()
    js = await _generate_js(html, instructions)
    if js.strip():  # pragma: no cover - best effort
        try:
            logger.info("Executing JavaScript:\n%s", js)
            await page.evaluate(js)
            await asyncio.sleep(2)
        except Exception:
            logger.exception("Failed to run generated JavaScript")
    else:
        logger.debug("No JavaScript generated for actions")


async def _fetch_pages_with_actions(
    url: str,
    initial_actions: str,
    page_actions: str,
    pagination_actions: str,
    max_pages: int,
    run_js_on_page: str = "",
) -> List[PageData]:
    pages: List[PageData] = []
    proxy = os.getenv("PROXY_URL")
    async with fetch_html_playwright.browser_ctx(proxy) as ctx:
        page = await ctx.new_page()
        await fetch_html_playwright.apply_stealth(page)
        logger.info("Navigating to %s", url)
        await page.goto(url, timeout=120_000, wait_until="domcontentloaded")
        logger.info("Applying initial actions")
        await _apply_actions(page, initial_actions)
        for i in range(max_pages):
            logger.info("Processing page %s", i + 1)
            await _apply_actions(page, page_actions)
            html = await page.content()
            js_out: Optional[str] = None
            if run_js_on_page.strip():
                try:
                    js_out = await page.evaluate(run_js_on_page)
                    logger.info("JavaScript output: %s", js_out)
                except Exception:
                    logger.exception("Failed to run provided JavaScript")
            pages.append(PageData(html, js_out))
            if i == max_pages - 1:
                break
            logger.info("Applying pagination actions")
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
    run_js_on_page: str = "",
) -> List[PageData]:
    if any([initial_actions, page_actions, pagination_actions]) or max_pages > 1:
        logger.info("Using action-based navigation")
        return await _fetch_pages_with_actions(
            url,
            initial_actions,
            page_actions,
            pagination_actions,
            max_pages,
            run_js_on_page,
        )
    logger.info("Using selector-based pagination")
    return await _fetch_pages_by_selector(
        url, next_page_selector, max_next_pages, run_js_on_page
    )


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
    run_js_on_page: str = "",
) -> List[Company]:
    pages = await _fetch_pages(
        url,
        next_page_selector,
        max_next_pages,
        initial_actions,
        page_actions,
        pagination_actions,
        max_pages,
        run_js_on_page,
    )
    aggregated: list[Company] = []
    for page in pages:
        html = page.html
        js_text = page.js_output
        logger.debug("Parsing page for companies")
        _user_link, org_link = _extract_linkedin_links(html)
        if js_text is not None:
            text = str(js_text)
        else:
            text = BeautifulSoup(html, "html.parser").get_text("\n", strip=True)
        prompt = (
            "Extract all companies mentioned in the text below.\n"
            f"{parse_instructions}\n"
            f"Return JSON matching this schema:\n{json.dumps(CompanyList.model_json_schema(), indent=2)}\n\n"
            f"Text:\n{text}"
        )
        result, status = await _get_structured_data_internal(prompt, CompanyList)
        if status != "SUCCESS" or result is None:
            logger.debug("Company extraction failed: %s", status)
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
    run_js_on_page: str = "",
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
        run_js_on_page=run_js_on_page,
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
    run_js_on_page: str = "",
) -> List[Lead]:
    pages = await _fetch_pages(
        url,
        next_page_selector,
        max_next_pages,
        initial_actions,
        page_actions,
        pagination_actions,
        max_pages,
        run_js_on_page,
    )
    aggregated: list[Lead] = []
    for page in pages:
        html = page.html
        js_text = page.js_output
        logger.debug("Parsing page for leads")
        user_link, org_link = _extract_linkedin_links(html)
        if js_text is not None:
            text = str(js_text)
        else:
            text = BeautifulSoup(html, "html.parser").get_text("\n", strip=True)
        prompt = (
            "Extract all leads mentioned in the text below.\n"
            f"{parse_instructions}\n"
            f"Return JSON matching this schema:\n{json.dumps(LeadList.model_json_schema(), indent=2)}\n\n"
            f"Text:\n{text}"
        )
        result, status = await _get_structured_data_internal(prompt, LeadList)
        if status != "SUCCESS" or result is None:
            logger.debug("Lead extraction failed: %s", status)
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


def extract_from_webpage_from_csv(
    input_file: str | Path,
    output_file: str | Path,
    *,
    next_page_selector: str | None = None,
    max_next_pages: int = 0,
    parse_instructions: str = "",
    initial_actions: str = "",
    page_actions: str = "",
    pagination_actions: str = "",
    max_pages: int = 1,
    run_js_on_page: str = "",
    mode: str = "leads",
) -> None:
    """Process ``input_file`` and aggregate results to ``output_file``."""

    import csv

    in_path = Path(input_file)
    out_path = Path(output_file)

    with in_path.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        fieldnames = reader.fieldnames or []
        if "website_url" not in fieldnames:
            raise ValueError("upload csv with website_url column")
        rows = list(reader)

    agg_leads: list[Lead] = []
    agg_companies: list[Company] = []

    for row in rows:
        url = (row.get("website_url") or "").strip()
        if not url:
            continue
        if mode == "lead":
            result = asyncio.run(
                extract_lead_from_webpage(
                    url,
                    next_page_selector,
                    max_next_pages,
                    parse_instructions=parse_instructions,
                    initial_actions=initial_actions,
                    page_actions=page_actions,
                    pagination_actions=pagination_actions,
                    max_pages=max_pages,
                    run_js_on_page=run_js_on_page,
                )
            )
            if result:
                agg_leads.append(result)
        elif mode == "leads":
            results = asyncio.run(
                extract_multiple_leads_from_webpage(
                    url,
                    next_page_selector,
                    max_next_pages,
                    parse_instructions=parse_instructions,
                    initial_actions=initial_actions,
                    page_actions=page_actions,
                    pagination_actions=pagination_actions,
                    max_pages=max_pages,
                    run_js_on_page=run_js_on_page,
                )
            )
            agg_leads.extend(results)
        elif mode == "company":
            result = asyncio.run(
                extract_comapy_from_webpage(
                    url,
                    next_page_selector,
                    max_next_pages,
                    parse_instructions=parse_instructions,
                    initial_actions=initial_actions,
                    page_actions=page_actions,
                    pagination_actions=pagination_actions,
                    max_pages=max_pages,
                    run_js_on_page=run_js_on_page,
                )
            )
            if result:
                agg_companies.append(result)
        else:  # companies
            results = asyncio.run(
                extract_multiple_companies_from_webpage(
                    url,
                    next_page_selector,
                    max_next_pages,
                    parse_instructions=parse_instructions,
                    initial_actions=initial_actions,
                    page_actions=page_actions,
                    pagination_actions=pagination_actions,
                    max_pages=max_pages,
                    run_js_on_page=run_js_on_page,
                )
            )
            agg_companies.extend(results)

    if mode in {"lead", "leads"}:
        # Deduplicate leads by company and by user identifier
        deduped: list[Lead] = []
        seen_companies: set[str] = set()
        seen_users: set[str] = set()
        for lead in agg_leads:
            comp_key = (lead.organization_name or "").strip().lower()
            user_key = (lead.user_linkedin_url or lead.email or "").strip().lower()
            if comp_key and comp_key in seen_companies:
                continue
            if user_key and user_key in seen_users:
                continue
            if comp_key:
                seen_companies.add(comp_key)
            if user_key:
                seen_users.add(user_key)
            deduped.append(lead)
        _write_leads_csv(deduped, str(out_path))
    else:
        # Deduplicate companies by organization name
        deduped: list[Company] = []
        seen: set[str] = set()
        for comp in agg_companies:
            key = (comp.organization_name or "").strip().lower()
            if key and key in seen:
                continue
            if key:
                seen.add(key)
            deduped.append(comp)
        _write_companies_csv(deduped, str(out_path))


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
    run_js_on_page: str = "",
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
        run_js_on_page=run_js_on_page,
    )
    return leads[0] if leads else None


def _write_companies_csv(
    companies: List[Company], dest: typing.Union[str, typing.TextIO]
) -> None:
    import csv

    fieldnames = [
        "organization_name",
        "organization_website",
        "primary_domain_of_organization",
        "link_to_more_information",
        "organization_linkedin_url",
    ]
    should_close = False
    if isinstance(dest, str):
        fh = open(dest, "w", newline="", encoding="utf-8")
        should_close = True
    else:
        fh = dest
    writer = csv.DictWriter(fh, fieldnames=fieldnames)
    writer.writeheader()
    for c in companies:
        writer.writerow(json.loads(c.model_dump_json()))
    if should_close:
        fh.close()


def _write_leads_csv(leads: List[Lead], dest: typing.Union[str, typing.TextIO]) -> None:
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
    should_close = False
    if isinstance(dest, str):
        fh = open(dest, "w", newline="", encoding="utf-8")
        should_close = True
    else:
        fh = dest
    writer = csv.DictWriter(fh, fieldnames=fieldnames)
    writer.writeheader()
    for l in leads:
        writer.writerow(json.loads(l.model_dump_json()))
    if should_close:
        fh.close()


async def _run_cli(url: str, args: argparse.Namespace) -> None:
    next_sel = args.next_page_selector
    max_next = args.max_next_pages
    parse_ins = args.parse_instructions or ""
    initial_actions = args.initial_actions or ""
    page_actions = args.page_actions or ""
    pagination_actions = args.pagination_actions or ""
    max_pages = args.max_pages
    run_js = args.run_js_on_page or ""
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
            run_js_on_page=run_js,
        )
        if result:
            dest = args.output_csv or sys.stdout
            _write_leads_csv([result], dest)
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
            run_js_on_page=run_js,
        )
        dest = args.output_csv or sys.stdout
        _write_leads_csv(result, dest)
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
            run_js_on_page=run_js,
        )
        if result:
            dest = args.output_csv or sys.stdout
            _write_companies_csv([result], dest)
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
            run_js_on_page=run_js,
        )
        dest = args.output_csv or sys.stdout
        _write_companies_csv(result, dest)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract leads or companies from a web page"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--lead", action="store_true", help="Extract one lead")
    group.add_argument("--leads", action="store_true", help="Extract multiple leads")
    group.add_argument("--company", action="store_true", help="Extract one company")
    group.add_argument(
        "--companies", action="store_true", help="Extract multiple companies"
    )
    parser.add_argument("url", nargs="?", help="Website URL")
    parser.add_argument("--csv", help="Input CSV file with website_url column")
    parser.add_argument("--next_page_selector", help="CSS selector for next page link")
    parser.add_argument(
        "--max_next_pages",
        type=int,
        default=0,
        help="Number of next pages to parse",
    )
    parser.add_argument("--initial_actions", help="Actions on initial load")
    parser.add_argument("--page_actions", help="Actions on each page load")
    parser.add_argument("--run_js_on_page", help="JavaScript to run on each page")
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
    parser.add_argument(
        "--show_ux",
        action="store_true",
        help="Show the website in a browser window while parsing",
    )
    parser.add_argument("--output_csv", help="Output CSV path")
    args = parser.parse_args()

    if args.show_ux:
        os.environ["HEADLESS"] = "false"

    if bool(args.csv) == bool(args.url):
        parser.error("Provide either a URL or --csv")

    if args.csv:
        if not args.output_csv:
            raise ValueError("--output_csv is required when using --csv")
        mode = "leads"
        if args.lead:
            mode = "lead"
        elif args.company:
            mode = "company"
        elif args.companies:
            mode = "companies"
        extract_from_webpage_from_csv(
            args.csv,
            args.output_csv,
            next_page_selector=args.next_page_selector,
            max_next_pages=args.max_next_pages,
            parse_instructions=args.parse_instructions or "",
            initial_actions=args.initial_actions or "",
            page_actions=args.page_actions or "",
            pagination_actions=args.pagination_actions or "",
            max_pages=args.max_pages,
            run_js_on_page=args.run_js_on_page or "",
            mode=mode,
        )
    else:
        asyncio.run(_run_cli(args.url, args))


if __name__ == "__main__":
    main()
