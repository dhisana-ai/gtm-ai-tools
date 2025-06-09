"""This script is designed to scrape top apps and user information from Product Hunt and process the data for
integration with the Dhisana API webhook """
import argparse
import asyncio
import datetime
import json
import logging
import re
from typing import List, Dict, Optional, Any

import os
import aiohttp

from bs4 import BeautifulSoup

from utils.fetch_html_playwright import fetch_html

BASE_URL = "https://www.producthunt.com"

logging.basicConfig(level=logging.INFO)
async def fetch_and_clean(url: str) -> str:
    """
    Fetch HTML content from a URL and clean it by removing unwanted tags.

    Args:
        url (str): The URL to fetch HTML content from.

    Returns:
        str: Cleaned HTML content as a string.

    Example:
        cleaned_html = await fetch_and_clean('https://example.com')
    """
    html = await fetch_html(url)
    soup = BeautifulSoup(html or "", "html.parser")
    for tag in soup(["script", "style", "meta", "code", "svg"]):
        tag.decompose()
    return str(soup)


async def extract_leader_dashboard_apps(dashboard_link: str) -> List[Dict]:
    """
    Extract leaderboard apps data from the Product Hunt leaderboard page URL.

    Args:
        dashboard_link (str): URL of the Product Hunt leaderboard daily page.
        ex: "https://www.producthunt.com/leaderboard/daily/2024/06/30"


    Returns:
        List[Dict]: List of apps with keys 'name', 'about', 'company_categories', and 'product_hunt_link'.
        sample output:
        [
            {
                'name': 'RepoSecGo',
                'about': 'Get instant security insights for GitHub repositories using OpenSSF Scorecard metrics. Analyze code review practices, maintenance status, security policies, and more before integrating dependencies into your projects.',
                'company_categories': ['GitHub', 'Developer Tools'],
                'product_hunt_link': 'https://www.producthunt.com/products/reposecgo',
                'company_name': 'RepoSecGo', 'company_website': 'https://reposecgo.com/?ref=producthunt',
                'company_domain': 'reposecgo.com'
            },...
        ]

    Example:
        apps = await extract_leader_dashboard_apps("https://www.producthunt.com/leaderboard/daily/2024/06/30")
    """
    html = await fetch_and_clean(dashboard_link)
    soup = BeautifulSoup(html, 'html.parser')
    apps = []
    app_sections = soup.find_all(
        "section",
        attrs={"data-sentry-component": "Card", "data-test": re.compile(r'post-item-\d+')},
    )

    for section in app_sections:
        name_link = section.find("a", attrs={"data-test": re.compile(r'post-name-\d+')})
        if not name_link:
            continue
        name = name_link.get_text(strip=True)
        product_hunt_link = name_link.get("href", "")

        about_link = section.find("a", class_="text-16 font-normal text-dark-gray text-secondary")
        about = about_link.get_text(strip=True) if about_link else ""

        categories = []
        tags_parent = section.find("div", attrs={"data-sentry-component": "TagList"})
        if tags_parent:
            categories = [a.get_text(strip=True) for a in tags_parent.find_all("a")]

        apps.append({
            "name": name,
            "about": about,
            "company_categories": categories,
            "product_hunt_link": BASE_URL + product_hunt_link,
        })
    return apps


async def extract_app_company_info(app_link: str) -> Dict[str, Optional[str]]:
    """
    Extract detailed company information from a Product Hunt app page URL.

    Args:
        app_link (str): URL of the Product Hunt app page. ex: https://www.producthunt.com/products/lettre-app/

    Returns:
        Dict[str, Optional[str]]: Dictionary containing keys such as 'name', 'about', 'company_name',
            'company_website', 'company_domain', 'company_categories'.
        sample output:
        {
            'name': 'RepoSecGo',
            'about': 'Get instant security insights for GitHub repositories using OpenSSF Scorecard metrics. Analyze code review practices, maintenance status, security policies, and more before integrating dependencies into your projects.',
            'company_categories': ['GitHub', 'Developer Tools'],
            'company_name': 'RepoSecGo',
            'company_website': 'https://reposecgo.com/?ref=producthunt',
            'company_domain': 'reposecgo.com'
        }

    Example:
        info = await extract_app_company_info("https://www.producthunt.com/posts/example-app")
    """
    logging.info("Extracting company info from app link: %s", app_link)
    html = await fetch_and_clean(app_link)
    soup = BeautifulSoup(html, "html.parser")

    result = {}
    h1 = soup.find('h1', class_=re.compile(r'text-24.+'))
    if h1:
        result["name"] = h1.get_text(strip=True)
    else:
        title = soup.find('title')
        if title:
            result["name"] = title.get_text(strip=True).split(':')[0]
        else:
            result["name"] = ""

    about = ""
    desc_block = soup.find('div', {'data-sentry-component': "Description"})
    if desc_block:
        p = desc_block.find('p')
        if p:
            about = p.get_text(strip=True)

    if not about:
        for comment in soup.select('div[data-sentry-component="RichText"]'):
            maker_badge = comment.parent.find_previous_sibling(
                lambda tag: tag.name == "div" and "Maker" in tag.get_text()
            )
            if maker_badge:
                about = comment.get_text(separator=' ', strip=True)
                break

    if not about:
        meta = soup.find('meta', attrs={'name': 'description'})
        if meta:
            about = meta['content']
    result["about"] = about

    company_name = ""
    info_blocks = soup.find_all('div', class_=re.compile(r'font-semibold.*'))
    for b in info_blocks:
        if "Info" in b.get_text() and b.find_parent('div'):
            parent = b.find_parent('div')
            sibling = parent.find('span', class_=re.compile(r'font-semibold'))
            if sibling:
                company_name = sibling.get_text(strip=True)
            else:
                company_name = result.get("name", "")
            break
    if not company_name:
        company_name = result.get("name", "")
    result["company_name"] = company_name

    company_website = None
    sidebar_a = soup.find("div", string=re.compile("Company Info"))
    if sidebar_a:
        a = sidebar_a.find_next("a", href=re.compile(r'^https?'))
        if a:
            company_website = a['href']
    if not company_website:
        website_btn = soup.find("a", {"data-test": "visit-website-button"}, href=True)
        if website_btn:
            company_website = website_btn['href']
    result["company_website"] = company_website

    def get_domain(url: Optional[str]) -> str:
        if not url:
            return ""
        return re.sub(r"https?://|/$", "", url).split("/")[0].replace("www.", "")

    result["company_domain"] = get_domain(company_website)

    categories = set()
    cats_section = soup.find('div', {'data-sentry-component': "Categories"})
    if cats_section:
        for a in cats_section.find_all('a', href=True):
            txt = a.get_text(strip=True)
            if txt:
                categories.add(txt)

    for taglist in soup.find_all('div', {'data-sentry-component': "TagList"}):
        tag_title = taglist.find(string=re.compile(r'Launch tags:', re.I))
        if tag_title:
            for a in taglist.find_all('a', href=True):
                txt = a.get_text(strip=True)
                if txt:
                    categories.add(txt)

    result["company_categories"] = list(categories)

    return result


async def lead_parser_from_profile_link(profile_link: str) -> Dict[str, Optional[str]]:
    """
    Parse a Product Hunt user profile page to extract lead information.

    Args:
        profile_link (str): URL of the Product Hunt user profile.
    Returns:
        Dict[str, Optional[str]]: Dictionary with keys 'name', 'title', 'about', 'first_name',
            'last_name', 'organization_name', 'link_to_more_information', 'follower_count'.
        sample output:
        {
          "name": "Surya",
          "title": "Co-founder & CTO @Hyring",
          "about": "I love building products that solve real problems.",
          "first_name": "Surya",
          "last_name": "Surya",
          "organization_name": "",
          "link_to_more_information": "https://www.producthunt.com/@surya_nagarajan1",
          "follower_count": 17,
          "linkedin_profile_url": "https://www.linkedin.com/in/surya-nagarajan09/",
          "badges": ["Top 5 Launch","Tastemaker", "Tastemaker 10", "Tastemaker 5"]
        }

    Example:
        lead = await lead_parser_from_profile_link("https://www.producthunt.com/@surya_nagarajan1")
    """
    html = await fetch_and_clean(profile_link)
    soup = BeautifulSoup(html, "html.parser")

    name_tag = soup.find("h1", class_="text-24 font-semibold text-dark-gray mb-1")
    name = name_tag.text.strip() if name_tag else ""

    title_tag = soup.find("div", class_="text-18 font-light text-light-gray mb-1")
    title = title_tag.text.strip() if title_tag else ""

    about = ""
    for h2 in soup.find_all("h2"):
        if h2.text.strip().lower() == "about":
            p = h2.find_next_sibling("p")
            if p:
                about = p.text.strip()
                break

    if name:
        split_name = name.split(" ")
        first_name = split_name[0]
        last_name = split_name[-1]
    else:
        first_name, last_name = "", ""

    org_tag = soup.find("a", href=re.compile(r"/products/"))
    organization_name = org_tag.text.strip() if org_tag else ""

    follower_count = 0
    followers_tag = soup.find("a", href=re.compile("/@[^/]+/followers"))
    if followers_tag:
        m = re.search(r"(\d+)", followers_tag.text)
        if m:
            follower_count = int(m.group(1))

    user_url = ""
    canonical = soup.find("link", rel="canonical")
    if canonical and canonical.get("href"):
        user_url = canonical["href"]
    else:
        username_a = soup.find("a", href=re.compile('^/@[^/]+$'))
        if username_a:
            username = username_a['href'].split('/')[1]
            user_url = f"https://www.producthunt.com/{username}"
    linkedin_a = soup.find('a', href=re.compile(r'^https://www\.linkedin\.com/'))
    linkedin_profile_url = linkedin_a['href'] if linkedin_a else ''

    badges = []
    badge_divs = soup.find_all('div', attrs={"data-sentry-component": "BadgeItem"})
    for badge_div in badge_divs:
        badge_title = badge_div.find('div', class_='text-14')
        if badge_title:
            badges.append(badge_title.get_text(strip=True))

    lead = {
        "name": name,
        "title": title,
        "about": about,
        "first_name": first_name,
        "last_name": last_name,
        "organization_name": organization_name,
        "link_to_more_information": user_url,
        "follower_count": follower_count,
        "linkedin_profile_url": linkedin_profile_url,
        "badges": badges,
    }

    logging.debug("Lead parser output: %s", lead)
    return lead


async def extract_team_members(makers_link: str) -> List[Dict[str, str]]:
    """
    Extract team members information from a Product Hunt makers page URL.

    Args:
        makers_link (str): URL of the Product Hunt makers page for a product.

    Returns:
        List[Dict[str, str]]: List of team members with keys 'name', 'title', 'profile_link'.
        sample output:
        [
            {
                'name': 'Shaer Reaz',
                'title': 'Co-Founder, Product Manager, PR/Comms',
                'profile_link': 'https://www.producthunt.com/@shaer_reaz'
            },...
        ]
    Example:
        members = await extract_team_members("https://www.producthunt.com/posts/example-app/makers")
    """
    logging.info("Extracting team members from makers link: %s", makers_link)
    html = await fetch_and_clean(makers_link)
    soup = BeautifulSoup(html, 'html.parser')

    result = []
    for maker_section in soup.select("section[data-test^='maker-card']"):
        name_a = maker_section.select_one("a.text-16.font-semibold")
        profile_link = ""
        name = ""
        if name_a:
            name = name_a.get_text(strip=True)
            profile_link = name_a.get("href", "")
            if profile_link and not profile_link.startswith("http"):
                profile_link = f"https://www.producthunt.com{profile_link}"
        title_a = maker_section.select_one("a.text-14.font-normal")
        title = title_a.get_text(strip=True) if title_a else ""
        result.append({
            "name": name,
            "title": title,
            "profile_link": profile_link,
        })
    return result


def convert_to_dhisana_leads_payload(producthunt_apps: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """
    Convert Product Hunt apps data into a payload suitable for Dhisana leads.

    Args:
        producthunt_apps (List[Dict[str, Any]]): List of apps with enriched information.
        sample input:
        [
            {
                'name': 'FuseBase /formerly Nimbus/',
                'about': 'Scattered tools and clunky collaboration cost you time and money. FuseBase unifies internal and external teamwork—powered by AI agents that automate admin work, so you focus on what matters most.\nIt’s like Notion, but purpose-built for internal teams and external collaboration. Turbo-charged with always-on AI Agents that live inside your FuseBase workspaces, inside every portal, inside a lightning-fast browser extension, and inside our Zapier-style Automation Hub',
                'company_categories': ['Project management software', 'Productivity', 'Artificial Intelligence', 'Chrome Extensions', 'Team collaboration software', 'No-code platforms'],
                'product_hunt_link': 'https://www.producthunt.com/products/fusebase',
                'company_name': 'FuseBase /formerly Nimbus/',
                'company_website': 'http://thefusebase.com/?ref=producthunt',
                'company_domain': 'thefusebase.com',
                'founders': [{'name': 'Paul Sher', 'title': 'Founder of FuseBase', 'profile_link': 'https://www.producthunt.com/@pavel_sher'}]
            }
        }

    Returns:
        List[Dict[str, str]]: List of dictionaries formatted for Dhisana leads.
        sample output:
        [
            {
                "full_name": "John Doe",
                "first_name": "John",
                "last_name": "Doe",
                "user_linkedin_url": "https://linkedin.com/in/johndoe",
                "primary_domain_of_organization": "example.com",
                "job_title": "Founder & CEO",
                "headline": "Founder & CEO at Example Inc.",
                "organization_name": "Example Inc."
            },....
        ]

    Example:
        payload = convert_to_dhisana_leads_payload(apps)
    """
    payload = []
    for app in producthunt_apps:
        if not app["founders"]:
            logging.info(f"Skipping app '{app['name']}' since no founders found.")
            continue
        for founder in app["founders"]:
            full_name = founder.get("name", "")
            first_name = full_name.split()[0] if full_name else ""
            last_name = full_name.split()[-1] if full_name else ""
            user_linkedin_url = founder.get("linkedin_profile_url", "")
            if not user_linkedin_url:
                user_linkedin_url = founder.get("profile_link", "")
            primary_domain_of_organization = app.get("company_info", {}).get("company_domain", "")
            job_title = founder.get("title", "")
            headline = job_title
            organization_name = app.get("company_info", {}).get("company_name", "")

            payload.append({
                "full_name": full_name,
                "first_name": first_name,
                "last_name": last_name,
                "user_linkedin_url": user_linkedin_url,
                "primary_domain_of_organization": primary_domain_of_organization,
                "job_title": job_title,
                "headline": headline,
                "organization_name": organization_name,
            })
    return payload


async def push_leads_to_dhisana_webhook(payload: List[Dict[str, str]]) -> bool:
    """
    Push leads data to the Dhisana webhook.
    Args:
        payload (List[Dict[str, str]]): List of leads data to send.
        sample payload:
        [
            {
                "full_name": "John Doe",
                "first_name": "John",
                "last_name": "Doe",
                "user_linkedin_url": "https://linkedin.com/in/johndoe",
                "primary_domain_of_organization": "example.com",
                "job_title": "Founder & CEO",
                "headline": "Founder & CEO at Example Inc.",
                "organization_name": "Example Inc."
            }
        ]
    Returns:
        bool: True if the request was successful, False otherwise.

    """
    DHISANA_API_KEY = os.getenv("DHISANA_API_KEY")
    DHISANA_WEBHOOK_URL = os.getenv("DHISANA_COMPANY_INPUT_URL")
    if not DHISANA_API_KEY:
        raise RuntimeError("DHISANA_API_KEY environment variable is not set")

    if not DHISANA_WEBHOOK_URL:
        raise RuntimeError("DHISANA_COMPANY_INPUT_URL environment variable is not set")
    headers = {"X-API-Key": DHISANA_API_KEY, "Content-Type": "application/json"}
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(DHISANA_WEBHOOK_URL, headers=headers, json=payload) as resp:
                resp.raise_for_status()
        except Exception as e:
            logging.error("Failed to push leads to Dhisana webhook: %s", e)


async def scrape_producthunt_top_apps_for_period(days_back: int = 7, date: Optional[str] = None) -> List[Dict]:
    """
    Scrape top Product Hunt apps for a specific date or a range ending at that date.

    Args:
        days_back (int): Number of days to look back from the given date (inclusive).
        date (str | None): The end date in 'YYYY/MM/DD' format. Defaults to today's date if None.

    Returns:
        List[Dict]: List of scraped apps with their details.
    """
    all_apps = []

    # Default to today if date is not provided
    if date is None:
        end_date = datetime.datetime.now()
    else:
        end_date = datetime.datetime.strptime(date, "%Y/%m/%d")

    for i in range(days_back):
        current_date = (end_date - datetime.timedelta(days=i)).strftime("%Y/%m/%d")
        logging.info(f"Processing date: {current_date}")
        apps = await scrape_single_day(current_date)
        logging.info(f"Found {len(apps)} apps for date {current_date}")
        all_apps.extend(apps)

    logging.info(f"Total apps found: {len(all_apps)}")
    # Enrich each app with company information
    for app in all_apps:
        app_info = await extract_app_company_info(app["product_hunt_link"])
        app.update(app_info)
    # Extract founders from each app's makers page
    for app in all_apps:
        founders = []
        makers_link = app["product_hunt_link"] + "/makers"
        team_members = await extract_team_members(makers_link)
        for member in team_members:
            if "founder" in member["title"].lower():
                founder_info = await lead_parser_from_profile_link(member["profile_link"])
                member.update(founder_info)
                founders.append(member)
        app["founders"] = founders
        # Enrich each founder with their profile information
        logging.info(f"Found {len(app['founders'])} founders for app '{app['name']}'")
    return all_apps


async def scrape_single_day(date: str) -> List[Dict]:
    """
    Scrape top Product Hunt apps for a single day.

    Args:
        date (str): The date to scrape in YYYY/MM/DD format.
    Returns:
        List[Dict]: List of scraped apps with their details.
        sample output:
        [
            {
                'name': 'FuseBase AI Agents',
                'about': 'AI agents for smarter internal & external collaboration',
                'company_categories': ['Chrome Extensions', 'Productivity', 'Artificial Intelligence'],
                'product_hunt_link': 'https://www.producthunt.com/products/fusebase'
            },...
        ]
    """
    dashboard_link = f"{BASE_URL}/leaderboard/daily/{date}"
    print(f"dashboard_link: {dashboard_link}")
    apps = await extract_leader_dashboard_apps(dashboard_link)

    return apps


async def push_ph_top_creators_to_dhisana_webhook(days_back: int = 1, date: str | None = None, ) -> bool:
    """
    Push top Product Hunt creators to Dhisana webhook for a specific date or period.

    Args:
        days_back (int | None): Number of days to look back from today. If provided, overrides date parameter.
        date (str | None): The date to process in YYYY/MM/DD format. If None and days_back is None, uses today's date.

    Returns:
        bool: True if successful, False otherwise.
    """
    apps = await scrape_producthunt_top_apps_for_period(days_back, date)
    payload = convert_to_dhisana_leads_payload(apps)
    await push_leads_to_dhisana_webhook(payload)
    print(json.dumps(payload, indent=2))


async def main() -> None:
    """Main function to run the script."""
    parser = argparse.ArgumentParser(description="Push Product Hunt top creators to Dhisana webhook")
    parser.add_argument(
        "--days-back",
        type=int,
        default=1,
        help="Number of days to look back from the given --date (or today if --date is not provided). "
             "Defaults to 1."
    )
    parser.add_argument(
        "--date",
        type=str,
        help="End date in YYYY/MM/DD format. If not provided, defaults to today. "
             "Used as the reference point for --days-back."
    )
    args = parser.parse_args()

    # If date is provided, use it; otherwise use days_back
    await push_ph_top_creators_to_dhisana_webhook(
        days_back=args.days_back,
        date=args.date
    )



if __name__ == "__main__":
    asyncio.run(main())
