"""Extract today's top Product Hunt apps and founders, and send to Dhisana webhook."""

import asyncio
import datetime
import json
import logging
import re
from typing import List, Dict, Optional


import os
import aiohttp


from bs4 import BeautifulSoup
from utils.fetch_html_playwright import fetch_html, browser_ctx, apply_stealth
BASE_URL = "https://www.producthunt.com"
DHISANA_API_KEY = os.getenv("DHISANA_API_KEY")
DHISANA_WEBHOOK_URL = os.getenv("DHISANA_COMPANY_INPUT_URL")
if not DHISANA_API_KEY:
    raise RuntimeError("DHISANA_API_KEY environment variable is not set")

if not DHISANA_WEBHOOK_URL:
    raise RuntimeError("DHISANA_COMPANY_INPUT_URL environment variable is not set")

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


async def extract_leader_dashboard_apps(dashboard_link: str, max_num_app: int = 10) -> List[Dict]:
    """
    Extract leaderboard apps data from the Product Hunt leaderboard page URL.

    Args:
        dashboard_link (str): URL of the Product Hunt leaderboard daily page.
        max_num_app (int, optional): Maximum number of apps to extract. Defaults to 10.

    Returns:
        List[Dict]: List of apps with keys 'name', 'about', 'company_categories', and 'product_hunt_link'.

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
        app_link (str): URL of the Product Hunt app page.

    Returns:
        Dict[str, Optional[str]]: Dictionary containing keys such as 'name', 'about', 'company_name',
            'company_website', 'company_domain', 'company_categories'.

    Example:
        info = await extract_app_company_info("https://www.producthunt.com/posts/example-app")
    """
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

    Example:
        lead = await lead_parser_from_profile_link("https://www.producthunt.com/@username")
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

    lead = {
        "name": name,
        "title": title,
        "about": about,
        "first_name": first_name,
        "last_name": last_name,
        "organization_name": organization_name,
        "link_to_more_information": user_url,
        "follower_count": follower_count
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

    Example:
        members = await extract_team_members("https://www.producthunt.com/posts/example-app/makers")
    """
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


async def scrape_producthunt_top_apps(max_num_app: int = 10) -> List[Dict]:
    """
    Scrape the Product Hunt daily leaderboard for top apps, extract detailed info and founders,
    and push founder lead data to a configured Dhisana webhook.

    Args:
        max_num_app (int, optional): Maximum number of apps to scrape. Defaults to 10.

    Returns:
        List[Dict]: List of apps with enriched information including company info and founders.

    Side Effects:
        Pushes founder lead data with relevant details to DHISANA webhook URL via HTTP POST.

    Example:
        apps = await scrape_producthunt_top_apps(max_num_app=10)
    """
    async with browser_ctx(proxy_url=None) as ctx:
        page = await ctx.new_page()
        await apply_stealth(page)

        today = datetime.datetime.now().strftime("%Y/%m/%d")
        leader_dashboard_url = f"https://www.producthunt.com/leaderboard/daily/{today}"

        apps = await extract_leader_dashboard_apps(leader_dashboard_url, max_num_app)
        for app in apps:
            app["company_info"] = await extract_app_company_info(app["product_hunt_link"])
            team_members = await extract_team_members(app["product_hunt_link"] + "/makers")
            app["founders"] = [member for member in team_members if "founder" in member["title"].lower()]

            if not app["founders"]:
                logging.info(f"Skipping app '{app['name']}' since no founders found.")
                continue

            if not DHISANA_API_KEY:
                logging.error("DHISANA_API_KEY environment variable is not set. Skipping push to Dhisana.")
                continue

            headers = {"X-API-Key": DHISANA_API_KEY, "Content-Type": "application/json"}
            async with aiohttp.ClientSession() as session:
                for founder in app["founders"]:
                    full_name = founder.get("name", "")
                    first_name = full_name.split()[0] if full_name else ""
                    last_name = full_name.split()[-1] if full_name else ""
                    user_linkedin_url = founder.get("profile_link", "")

                    primary_domain_of_organization = app.get("company_info", {}).get("company_domain", "")
                    job_title = founder.get("title", "")
                    headline = job_title
                    organization_name = app.get("company_info", {}).get("company_name", "")
                    payload = [
                        {
                            "full_name": full_name,
                            "first_name": first_name,
                            "last_name": last_name,
                            "user_linkedin_url": user_linkedin_url,
                            "primary_domain_of_organization": primary_domain_of_organization,
                            "job_title": job_title,
                            "headline": headline,
                            "organization_name": organization_name,
                        }
                    ]

                    try:
                        async with session.post(DHISANA_WEBHOOK_URL, headers=headers, json=payload) as resp:
                            resp.raise_for_status()
                            logging.info(f"Pushed founder lead '{full_name}' for app '{app['name']}' to Dhisana webhook.")
                    except Exception as e:
                        logging.error(f"Failed to push founder lead '{full_name}' for app '{app['name']}': {e}")

        logging.info(json.dumps(apps, indent=2))
        return apps


async def main():
    apps = await scrape_producthunt_top_apps(max_num_app=20)
    print(json.dumps(apps, indent=2))


if __name__ == '__main__':
    asyncio.run(main())
