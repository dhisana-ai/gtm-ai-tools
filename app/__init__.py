import os
import random
import re
import shlex
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import List
import asyncio
import json
import base64
import random
import datetime
from utils import (apollo_info, call_openai_llm, check_email_zero_bounce,
                   common, extract_from_webpage, find_company_info,
                   find_contact_with_findymail, find_user_by_job_title,
                   find_users_by_name_and_keywords, generate_email,
                   linkedin_search_to_csv, push_lead_to_dhisana_webhook,
                   score_lead, codegen_barbarika_web_parsing)

from utils.common import openai_client_sync

try:
    from flask import (Flask, flash, jsonify, redirect, render_template,
                       request, send_from_directory, session, url_for, Response, stream_with_context)
except Exception:  # pragma: no cover - fallback for test stubs
    from flask import (Flask, flash, jsonify, redirect, render_template,
                       request, send_from_directory, url_for, Response)

    session = {}
import openai
from dotenv import dotenv_values, set_key
try:
    import numpy as np
except Exception:  # pragma: no cover - optional
    np = None
import logging

import faiss
import threading
import queue

logging.basicConfig(level=logging.INFO)

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", "dev")
ENV_FILE = os.path.join(os.path.dirname(__file__), "..", ".env")
UTILS_DIR = os.path.join(os.path.dirname(__file__), "..", "utils")
# FAISS index and codes for utility embeddings (cosine similarity)
# Cache paths for utility embeddings index and codes
# Directory for user-generated utilities: prefer /data mount if available, else use in-repo folder
# Directory for user-generated utilities (create gtm_utility at repo root)
USER_UTIL_DIR = Path(__file__).resolve().parents[1] / "gtm_utility"
USER_UTIL_DIR.mkdir(parents=True, exist_ok=True)

# Data directory for persistent files and FAISS cache; prefer mounted /data in container
ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = Path("/data") if Path("/data").is_dir() else ROOT / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Cache paths for utility embeddings index and codes under the data folder
FAISS_CACHE_DIR = DATA_DIR / "faiss"
EMBED_INDEX_PATH = FAISS_CACHE_DIR / "utility_embeddings.index"
EMBED_CODES_PATH = FAISS_CACHE_DIR / "utility_embeddings.json"

UTILITY_INDEX: faiss.IndexFlatIP | None = None
UTILITY_CODES: list[str] = []

# Preferred column order when displaying CSV data in the grid
DISPLAY_ORDER = [
    "full_name",
    "user_linkedin_url",
    "job_title",
    "email",
]

# Optional nicer titles for utilities when displayed in the UI
UTILITY_TITLES = {
    "call_openai_llm": "OpenAI Tools",
    "linkedin_search_to_csv": "Find Leads with Google Search",
    "apollo_people_search": "Find Leads with Apollo.io",
    "find_a_user_by_name_and_keywords": "Find LinkedIn Profile by Name",
    "find_user_by_job_title": "Find LinkedIn Profile by Job Title",
    "find_users_by_name_and_keywords": "Bulk Find LinkedIn Profiles",
    "apollo_info": "Enrich Lead With Apollo.io",
    "fetch_html_playwright": "Scrape Website HTML (Playwright)",
    "extract_companies_from_image": "Extract Companies from Image",
    "extract_from_webpage": "scrape and extract leads from website",
    "generate_image": "Generate Image",
    "get_website_information": "Get website information",
    "score_lead": "Score Leads",
    "check_email_zero_bounce": "Validate Email",
    "generate_email": "Generate Email",
    "push_lead_to_dhisana_webhook": "Push Leads To Dhisana Webhook",
    "send_email_smtp": "Send Email",
}

# Display order for the utilities list
UTILITY_ORDER = {
    "linkedin_search_to_csv": 0,
    "apollo_people_search": 0,
    "apollo_info": 1,
    "score_lead": 2,
    "check_email_zero_bounce": 3,
    "push_lead_to_dhisana_webhook": 4,
    "generate_email": 5,
    "send_email_smtp": 6,
}

# Tags applied to utilities for filtering in the web UI
UTILITY_TAGS = {
    # Find/Search leads
    "linkedin_search_to_csv": ["find"],
    "apollo_people_search": ["find"],
    "find_a_user_by_name_and_keywords": ["find"],
    "find_user_by_job_title": ["find"],
    "find_users_by_name_and_keywords": ["find"],
    "fetch_html_playwright": ["find"],
    "extract_companies_from_image": ["find"],
    "extract_from_webpage": ["find"],
    # Enrich leads
    "apollo_info": ["enrich"],
    "check_email_zero_bounce": ["enrich"],
    "find_company_info": ["enrich"],
    "find_contact_with_findymail": ["enrich"],
    "call_openai_llm": ["enrich"],
    "generate_email": ["route"],
    "generate_image": ["enrich"],
    # Score leads
    "score_lead": ["score"],
    # Route leads
    "push_lead_to_dhisana_webhook": ["route"],
    "push_company_to_dhisana_webhook": ["route"],
    "push_to_clay_table": ["route"],
    "send_email_smtp": ["route"],
    "send_slack_message": ["route"],
    "hubspot_add_note": ["route"],
    "hubspot_create_contact": ["route"],
    "hubspot_get_contact": ["route"],
    "hubspot_update_contact": ["route"],
    "salesforce_add_note": ["route"],
    "salesforce_create_contact": ["route"],
    "salesforce_get_contact": ["route"],
    "salesforce_update_contact": ["route"],
}

# Utilities that only support CSV upload mode
# Use a list instead of a set so the value can be JSON serialised when passed
# to templates.
UPLOAD_ONLY_UTILS = ["find_users_by_name_and_keywords"]

# Mapping of utility parameters for the Run a Utility form. Each utility maps
# to a list of dictionaries describing the CLI argument name and display label.
UTILITY_PARAMETERS = {
    "apollo_info": [
        {"name": "--linkedin_url", "label": "LinkedIn URL"},
        {"name": "--email", "label": "Email"},
        {"name": "--full_name", "label": "Full name"},
        {"name": "--company_domain", "label": "Company domain"},
        {"name": "--company_url", "label": "Company URL"},
        {"name": "--primary_domain", "label": "Company domain"},
    ],
    "call_openai_llm": [{"name": "prompt", "label": "Prompt"}],
    "check_email_zero_bounce": [{"name": "email", "label": "E-mail"}],
    "fetch_html_playwright": [
        {"name": "url", "label": "URL"},
        {"name": "--summarize", "label": "Summarize content", "type": "boolean"},
        {"name": "--instructions", "label": "Summarize instructions"},
    ],
    "find_a_user_by_name_and_keywords": [
        {"name": "full_name", "label": "Full name"},
        {"name": "search_keywords", "label": "Search keywords"},
    ],
    "find_company_info": [
        {"name": "--organization_name", "label": "Organization name"},
        {"name": "--organization_linkedin_url", "label": "Organization LinkedIn URL"},
        {"name": "--organization_website", "label": "Organization website"},
        {"name": "--location", "label": "Organization location"},
    ],
    "find_contact_with_findymail": [
        {"name": "full_name", "label": "Full name"},
        {"name": "primary_domain_of_organization", "label": "Company domain"},
        {"name": "--linkedin_url", "label": "LinkedIn URL"},
    ],
    "find_user_by_job_title": [
        {"name": "job_title", "label": "Job title"},
        {"name": "organization_name", "label": "Organization name"},
        {"name": "search_keywords", "label": "Search keywords"},
    ],
    "find_users_by_name_and_keywords": [],
    "hubspot_add_note": [
        {"name": "--id", "label": "Contact ID"},
        {"name": "--note", "label": "Note"},
    ],
    "hubspot_create_contact": [
        {"name": "--email", "label": "Email"},
        {"name": "--linkedin_url", "label": "LinkedIn URL"},
        {"name": "--first_name", "label": "First name"},
        {"name": "--last_name", "label": "Last name"},
        {"name": "--phone", "label": "Phone"},
    ],
    "hubspot_get_contact": [
        {"name": "--id", "label": "Contact ID"},
        {"name": "--email", "label": "Email"},
        {"name": "--linkedin_url", "label": "LinkedIn URL"},
    ],
    "hubspot_update_contact": [
        {"name": "--id", "label": "Contact ID"},
        {"name": "properties", "label": "key=value pairs"},
    ],
    "salesforce_add_note": [
        {"name": "--id", "label": "Contact ID"},
        {"name": "--note", "label": "Note"},
    ],
    "salesforce_create_contact": [
        {"name": "--email", "label": "Email"},
        {"name": "--first_name", "label": "First name"},
        {"name": "--last_name", "label": "Last name"},
        {"name": "--phone", "label": "Phone"},
    ],
    "salesforce_get_contact": [
        {"name": "--id", "label": "Contact ID"},
        {"name": "--email", "label": "Email"},
    ],
    "salesforce_update_contact": [
        {"name": "--id", "label": "Contact ID"},
        {"name": "properties", "label": "key=value pairs"},
    ],
    "linkedin_search_to_csv": [
        {
            "name": "query",
            "label": 'Google query (e.g. site:linkedin.com/in "VP Sales")',
        },
        {"name": "--num", "label": "Number of results"},
    ],
    "apollo_people_search": [
        {"name": "--person_titles", "label": "Job titles"},
        {"name": "--person_locations", "label": "Person locations"},
        {
            "name": "--person_seniorities",
            "label": "Seniority",
            "choices": [
                "owner",
                "founder",
                "c_suite",
                "partner",
                "vp",
                "head",
                "director",
                "manager",
                "senior",
                "entry",
                "intern",
            ],
            "multiple": True,
        },
        {"name": "--organization_locations", "label": "Organization locations"},
        {"name": "--organization_domains", "label": "Organization domains"},
        {
            "name": "--include_similar_titles",
            "label": "Include similar titles",
            "type": "boolean",
        },
        {
            "name": "--contact_email_status",
            "label": "Email status",
            "choices": ["verified", "unverified", "likely to engage", "unavailable"],
        },
        {"name": "--organization_ids", "label": "Organization IDs"},
        {
            "name": "--organization_num_employees_ranges",
            "label": "Employee ranges",
            "choices": [
                "1-10",
                "11-50",
                "51-200",
                "201-500",
                "501-1000",
                "1001-5000",
                "5001-10000",
                "10001+",
            ],
            "multiple": True,
        },
        {"name": "--q_organization_keyword_tags", "label": "Organization keyword tags"},
        {"name": "--q_keywords", "label": "Keyword filter"},
        {"name": "--num_leads", "label": "Number of leads"},
    ],
    "mcp_tool_sample": [{"name": "prompt", "label": "Prompt"}],
    "push_company_to_dhisana_webhook": [
        {"name": "company_name", "label": "Organization name"},
        {"name": "--primary_domain", "label": "Primary domain"},
        {"name": "--linkedin_url", "label": "LinkedIn URL"},
        {"name": "--tags", "label": "Tags"},
        {"name": "--notes", "label": "Notes"},
        {"name": "--webhook_url", "label": "Webhook URL"},
    ],
    "push_lead_to_dhisana_webhook": [
        {"name": "full_name", "label": "Lead name"},
        {"name": "--linkedin_url", "label": "LinkedIn URL"},
        {"name": "--email", "label": "Email"},
        {"name": "--tags", "label": "Tags"},
        {"name": "--notes", "label": "Notes"},
        {"name": "--webhook_url", "label": "Webhook URL"},
    ],
    "extract_companies_from_image": [
        {"name": "image_url", "label": "Image URL"},
    ],
    "generate_image": [
        {"name": "prompt", "label": "Prompt"},
        {"name": "--image-url", "label": "Image URL"},
    ],
    "get_website_information": [
        {"name": "url", "label": "Website URL"},
        {"name": "questions", "label": "Questions (comma-separated) about the website"},
    ],
    "extract_from_webpage": [
        {"name": "url", "label": "Website URL"},
        {"name": "--lead", "label": "Extract One Lead", "type": "boolean"},
        {"name": "--leads", "label": "Extract Multiple Leads", "type": "boolean"},
        {"name": "--company", "label": "Extract One Company", "type": "boolean"},
        {
            "name": "--companies",
            "label": "Extract Multiple Companies",
            "type": "boolean",
        },
        {
            "name": "--initial_actions",
            "label": "Actions to do on Website Load, first time. Like select filters",
        },
        {"name": "--page_actions", "label": "Actions to do When each page loads."},
        {
            "name": "--parse_instructions",
            "label": "Custom instructions on how to extracts leads or company from the webpage that is loaded",
        },
        {
            "name": "--pagination_actions",
            "label": "Instructions on how to move to next page and extract more leads",
        },
        {"name": "--max_pages", "label": "Maximum number of pages to navigate"},
        {
            "name": "--show_ux",
            "label": "Show website UX during parsing",
            "type": "boolean",
        },
    ],
    "generate_email": [
        {
            "name": "--email_generation_instructions",
            "label": "Email generation instructions",
        },
    ],
    "score_lead": [
        {"name": "--instructions", "label": "Instructions"},
    ],
    "send_email_smtp": [
        {"name": "recipient", "label": "Recipient"},
        {"name": "--subject", "label": "Subject"},
        {"name": "--body", "label": "Body"},
        {"name": "--sender_name", "label": "Sender name"},
        {"name": "--sender_email", "label": "Sender email"},
        {"name": "--use_starttls", "label": "Use STARTTLS", "type": "boolean"},
    ],
    "send_slack_message": [
        {"name": "message", "label": "Message"},
        {"name": "--webhook", "label": "Webhook URL"},
    ],
    "push_to_clay_table": [
        {"name": "data", "label": "key=value pairs"},
        {"name": "--webhook_url", "label": "Webhook URL"},
        {"name": "--api_key", "label": "API key"},
    ],
}


def load_custom_parameters() -> None:
    """Load parameter specs from meta files for user utilities."""
    if not USER_UTIL_DIR.is_dir():
        return

    def _parse_args(code: str) -> list[dict[str, str]]:
        pattern = re.compile(r"add_argument\(\s*['\"]([^'\"]+)['\"](.*?)\)")
        help_re = re.compile(r"help\s*=\s*['\"]([^'\"]+)['\"]")
        skip = {
            "output_file",
            "--output_file",
            "input_file",
            "--input_file",
            "csv_file",
            "--csv_file",
        }
        params: list[dict[str, str]] = []
        for m in pattern.finditer(code):
            name = m.group(1)
            if name in skip:
                continue
            rest = m.group(2)
            h = help_re.search(rest)
            label = h.group(1) if h else name.lstrip("-").replace("_", " ").capitalize()
            params.append({"name": name, "label": label})
        return params

    for py_path in USER_UTIL_DIR.glob("*.py"):
        base = py_path.stem
        json_path = py_path.with_suffix(".json")
        params: List[dict[str, str]] | None = None
        if json_path.exists():
            try:
                meta_data = json.loads(json_path.read_text(encoding="utf-8"))
                params = meta_data.get("params") or None
            except Exception:
                params = None
        if params is None:
            try:
                params = _parse_args(py_path.read_text(encoding="utf-8"))
            except Exception:
                params = None
        if params:
            UTILITY_PARAMETERS[base] = params


def load_env():
    return dotenv_values(ENV_FILE)


def get_default_username() -> str:
    """Return the default username for the login form."""
    env = load_env()
    return env.get("APP_USER") or os.environ.get("APP_USER") or "user"


def get_credentials() -> tuple[str, str]:
    """Return (username, password) for the login page."""
    env = load_env()
    username = (
        env.get("APP_USERNAME")
        or os.environ.get("APP_USERNAME")
        or env.get("APP_USER")
        or os.environ.get("APP_USER")
        or "user"
    )
    password = env.get("APP_PASSWORD") or os.environ.get("APP_PASSWORD")
    if not password:
        password = f"user_{random.randint(1000, 9999)}"
        try:
            set_key(ENV_FILE, "APP_PASSWORD", password)
        except Exception:
            pass
    return username, password


def _format_title(name: str) -> str:
    """Return a human friendly title from a module name."""
    return UTILITY_TITLES.get(name, name.replace("_", " ").title())


def _list_utils() -> list[dict[str, str]]:
    """Return available utilities as ``{"name", "title", "desc", "tags"}`` dicts."""
    utils_dir = os.path.join(os.path.dirname(__file__), "..", "utils")
    items: list[dict[str, str]] = []
    for file_name in os.listdir(utils_dir):
        if not file_name.endswith(".py"):
            continue
        base = file_name[:-3]
        if base == "common":
            continue
        desc = base
        try:
            module = __import__(f"utils.{base}", fromlist=["__doc__"])
            if module.__doc__:
                desc = module.__doc__.strip().splitlines()[0]
        except Exception:
            pass
        items.append(
            {
                "name": base,
                "title": _format_title(base),
                "desc": desc,
                "tags": UTILITY_TAGS.get(base, []),
            }
        )

    # Include user generated utilities from gtm_utility folder
    if USER_UTIL_DIR.is_dir():
        for path in USER_UTIL_DIR.glob("*.py"):
            base = path.stem
            meta = path.with_suffix(".json")
            title = _format_title(base)
            desc = base
            if meta.exists():
                try:
                    meta_data = json.loads(meta.read_text(encoding="utf-8"))
                    title = meta_data.get("name", title)
                    desc = meta_data.get("description", desc)
                    params = meta_data.get("params")
                    if params:
                        UTILITY_PARAMETERS[base] = params
                except Exception:
                    pass
            items.append(
                {
                    "name": base,
                    "title": title,
                    "desc": desc,
                    "tags": ["custom"],
                    "custom": True,
                }
            )
    return sorted(
        items,
        key=lambda x: (
            UTILITY_ORDER.get(x["name"], 100),
            x["title"],
        ),
    )


def _load_csv_preview(path: str) -> list[dict[str, str]]:
    """Return up to 1000 rows from a CSV file in display order."""
    rows: list[dict[str, str]] = []
    try:
        with open(path, newline="", encoding="utf-8-sig") as fh:
            reader = csv.DictReader(fh)
            for i, row in enumerate(reader):
                if i >= 1000:
                    break
                ordered: dict[str, str] = {}
                for key in DISPLAY_ORDER:
                    if key in row:
                        ordered[key] = row[key]
                for key, value in row.items():
                    if key not in ordered:
                        ordered[key] = value
                rows.append(ordered)
    except Exception:
        rows = []
    return rows


if hasattr(app, "before_request"):

    @app.before_request
    def require_login():
        endpoint = request.endpoint or ""
        # Allow static files, login, and utility generation without authentication
        if endpoint.startswith("static") or endpoint in ("login", "generate_utility"):
            return
        if not session.get("logged_in"):
            return redirect(url_for("login"))

else:  # pragma: no cover - for tests with DummyFlask

    def require_login():
        return


@app.route("/login", methods=["GET", "POST"])
def login():
    username, password = get_credentials()
    if request.method == "POST":
        if (
            request.form.get("password") == password
            and request.form.get("username") == username
        ):
            session["logged_in"] = True
            return redirect(url_for("run_utility"))
        flash("Invalid credentials.")
    return render_template("login.html", default_username=get_default_username())


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
def index():
    return redirect(url_for("run_utility"))


@app.route("/utility", methods=["GET", "POST"])
def run_utility():
    util_output = None
    download_name = None
    image_src = None
    input_rows: list[dict[str, str]] = []
    output_rows: list[dict[str, str]] = []
    input_csv_path: str | None = None
    output_csv_path: str | None = None
    utils_list = _list_utils()
    tags_set = {t for tags in UTILITY_TAGS.values() for t in tags}
    for util in utils_list:
        tags_set.update(util.get("tags", []))
    tag_order = ["find", "enrich", "score", "route", "custom"]
    tags_list = [t for t in tag_order if t in tags_set]
    tags_list.extend(sorted(tags_set - set(tag_order)))
    util_name = request.form.get("util_name", "linkedin_search_to_csv")
    is_custom = any(u.get("custom") and u["name"] == util_name for u in utils_list)
    prev_csv = session.get("prev_csv_path")
    if prev_csv and os.path.exists(prev_csv) and not is_custom:
        input_csv_path = prev_csv
    if request.method == "POST" and request.form.get("action") == "clear_csv":
        session.pop("prev_csv_path", None)
        return redirect(url_for("run_utility"))
    if request.method == "POST":
        file = request.files.get("csv_file")
        uploaded = None
        input_mode = request.form.get("input_mode", "single")
        selected_json = request.form.get("selected_rows", "")
        show_ux_flag = request.form.get("--show_ux")
        if selected_json:
            try:
                rows = json.loads(selected_json)
                if rows:
                    tmp = common.make_temp_csv_filename("selected")
                    with open(tmp, "w", newline="", encoding="utf-8") as fh:
                        writer = csv.DictWriter(fh, fieldnames=rows[0].keys())
                        writer.writeheader()
                        for r in rows:
                            writer.writerow(r)
                    uploaded = tmp
            except Exception:
                uploaded = None
        if not uploaded and file and file.filename:
            tmp_dir = common.get_output_dir()
            filename = os.path.join(tmp_dir, os.path.basename(file.filename))
            file.save(filename)
            uploaded = filename
        if (
            not uploaded
            and input_mode == "previous"
            and prev_csv
            and os.path.exists(prev_csv)
            and not is_custom
        ):
            uploaded = prev_csv
        if (
            not uploaded
            and util_name in UPLOAD_ONLY_UTILS
            and prev_csv
            and os.path.exists(prev_csv)
            and not is_custom
        ):
            uploaded = prev_csv

        if uploaded:
            input_csv_path = uploaded

        def build_cmd(values: dict[str, str]) -> list[str]:
            module_prefix = (
                "gtm_utility"
                if (USER_UTIL_DIR / f"{util_name}.py").exists()
                else "utils"
            )
            cmd = ["python", "-m", f"{module_prefix}.{util_name}"]
            if is_custom and not uploaded:
                nonlocal input_csv_path
                input_csv_path = common.make_temp_csv_filename("automation")
                cmd.append(input_csv_path)
            for spec in UTILITY_PARAMETERS.get(util_name, []):
                name = spec["name"]
                val = (values.get(name) or "").strip()
                if util_name == "extract_from_webpage" and name == "--show_ux":
                    continue
                if (
                    util_name == "linkedin_search_to_csv"
                    and name == "--num"
                    and not val
                ):
                    val = "10"
                if not val:
                    continue
                if spec.get("type") == "boolean":
                    if val.lower() in ("1", "true", "yes", "on"):
                        cmd.append(name)
                elif name.startswith("-"):
                    cmd.extend([name, val])
                else:
                    cmd.append(val)
            if util_name == "linkedin_search_to_csv":
                out_path = common.make_temp_csv_filename(util_name)
                insert_at = len(cmd)
                for i, arg in enumerate(cmd[3:], start=3):
                    if arg.startswith("-"):
                        insert_at = i
                        break
                cmd.insert(insert_at, out_path)
            elif util_name == "extract_from_webpage":
                out_path = common.make_temp_csv_filename(util_name)
                if not any(
                    f in cmd for f in ("--lead", "--leads", "--company", "--companies")
                ):
                    cmd.append("--leads")
                cmd.extend(["--output_csv", out_path])
            elif util_name == "apollo_people_search":
                out_path = common.make_temp_csv_filename(util_name)
                cmd.insert(3, out_path)
            return cmd

        def run_cmd(cmd: list[str], show_ux: bool = False) -> tuple[str, str, str]:
            env = os.environ.copy()
            root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
            env["PYTHONPATH"] = env.get("PYTHONPATH", "") + ":" + root_dir
            if show_ux:
                env["HEADLESS"] = "false"
            proc = subprocess.run(cmd, capture_output=True, text=True, env=env)
            status = "SUCCESS" if proc.returncode == 0 else "FAIL"
            output = (
                proc.stdout
                if proc.returncode == 0
                else (proc.stderr or "Error running command")
            )
            cmd_str = " ".join(shlex.quote(c) for c in cmd)
            return status, cmd_str, output.strip()

        if uploaded:
            if util_name == "linkedin_search_to_csv":
                out_path = common.make_temp_csv_filename(util_name)
                try:
                    linkedin_search_to_csv.linkedin_search_to_csv_from_csv(
                        uploaded, out_path
                    )
                    download_name = out_path
                    output_csv_path = out_path
                    util_output = None
                except Exception as exc:
                    util_output = f"Error: {exc}"
                    download_name = None
                    output_csv_path = None
            elif util_name == "apollo_info":
                out_path = common.make_temp_csv_filename(util_name)
                try:
                    apollo_info.apollo_info_from_csv(uploaded, out_path)
                    download_name = out_path
                    output_csv_path = out_path
                    util_output = None
                except Exception as exc:
                    util_output = f"Error: {exc}"
                    download_name = None
                    output_csv_path = None
            elif util_name == "check_email_zero_bounce":
                out_path = common.make_temp_csv_filename(util_name)
                try:
                    check_email_zero_bounce.check_emails_from_csv(uploaded, out_path)
                    download_name = out_path
                    output_csv_path = out_path
                    util_output = None
                except Exception as exc:
                    util_output = f"Error: {exc}"
                    download_name = None
                    output_csv_path = None
            elif util_name == "score_lead":
                out_path = common.make_temp_csv_filename(util_name)
                instructions = request.form.get("--instructions", "")
                try:
                    score_lead.score_leads_from_csv(uploaded, out_path, instructions)
                    download_name = out_path
                    output_csv_path = out_path
                    util_output = None
                except Exception as exc:
                    util_output = f"Error: {exc}"
                    download_name = None
                    output_csv_path = None
            elif util_name == "generate_email":
                out_path = common.make_temp_csv_filename(util_name)
                email_instructions = request.form.get(
                    "--email_generation_instructions", ""
                )
                try:
                    generate_email.generate_emails_from_csv(
                        uploaded, out_path, email_instructions
                    )
                    download_name = out_path
                    output_csv_path = out_path
                    util_output = None
                except Exception as exc:
                    util_output = f"Error: {exc}"
                    download_name = None
                    output_csv_path = None
            elif util_name == "call_openai_llm":
                out_path = common.make_temp_csv_filename(util_name)
                prompt_text = request.form.get("prompt", "")
                try:
                    call_openai_llm.call_openai_llm_from_csv(
                        uploaded, out_path, prompt_text
                    )
                    download_name = out_path
                    output_csv_path = out_path
                    util_output = None
                except Exception as exc:
                    util_output = f"Error: {exc}"
                    download_name = None
                    output_csv_path = None
            elif util_name == "extract_from_webpage":
                out_path = common.make_temp_csv_filename(util_name)
                mode = "leads"
                if request.form.get("--lead"):
                    mode = "lead"
                elif request.form.get("--company"):
                    mode = "company"
                elif request.form.get("--companies"):
                    mode = "companies"
                try:
                    old_headless = os.environ.get("HEADLESS")
                    if show_ux_flag:
                        os.environ["HEADLESS"] = "false"
                    else:
                        os.environ["HEADLESS"] = "true"
                    extract_from_webpage.extract_from_webpage_from_csv(
                        uploaded,
                        out_path,
                        next_page_selector=request.form.get("--next_page_selector"),
                        max_next_pages=int(request.form.get("--max_next_pages") or 0),
                        parse_instructions=request.form.get("--parse_instructions", ""),
                        initial_actions=request.form.get("--initial_actions", ""),
                        page_actions=request.form.get("--page_actions", ""),
                        pagination_actions=request.form.get("--pagination_actions", ""),
                        max_pages=int(request.form.get("--max_pages") or 1),
                        mode=mode,
                    )
                    if old_headless is None:
                        os.environ.pop("HEADLESS", None)
                    else:
                        os.environ["HEADLESS"] = old_headless
                    download_name = out_path
                    output_csv_path = out_path
                    util_output = None
                except Exception as exc:
                    if old_headless is None:
                        os.environ.pop("HEADLESS", None)
                    else:
                        os.environ["HEADLESS"] = old_headless
                    util_output = f"Error: {exc}"
                    download_name = None
                    output_csv_path = None
            elif util_name == "find_users_by_name_and_keywords":
                out_path = common.make_temp_csv_filename(util_name)
                try:
                    find_users_by_name_and_keywords.find_users(
                        Path(uploaded), Path(out_path)
                    )
                    download_name = out_path
                    output_csv_path = out_path
                    util_output = None
                except Exception as exc:
                    util_output = f"Error: {exc}"
                    download_name = None
                    output_csv_path = None
            elif util_name == "find_user_by_job_title":
                out_path = common.make_temp_csv_filename(util_name)
                try:
                    find_user_by_job_title.find_user_by_job_title_from_csv(
                        uploaded,
                        out_path,
                    )
                    download_name = out_path
                    output_csv_path = out_path
                    util_output = None
                except Exception as exc:
                    util_output = f"Error: {exc}"
                    download_name = None
                    output_csv_path = None
            elif util_name == "find_company_info":
                out_path = common.make_temp_csv_filename(util_name)
                try:
                    find_company_info.find_company_info_from_csv(uploaded, out_path)
                    download_name = out_path
                    output_csv_path = out_path
                    util_output = None
                except Exception as exc:
                    util_output = f"Error: {exc}"
                    download_name = None
                    output_csv_path = None
            elif util_name == "find_contact_with_findymail":
                out_path = common.make_temp_csv_filename(util_name)
                try:
                    find_contact_with_findymail.find_contact_with_findymail_from_csv(
                        uploaded,
                        out_path,
                    )
                    download_name = out_path
                    output_csv_path = out_path
                    util_output = None
                except Exception as exc:
                    util_output = f"Error: {exc}"
                    download_name = None
                    output_csv_path = None
            else:
                import csv

                with open(uploaded, newline="", encoding="utf-8-sig") as fh:
                    reader = csv.DictReader(fh)
                    rows = list(reader)
                    fieldnames = reader.fieldnames or []
                out_path = common.make_temp_csv_filename(util_name)
                with open(out_path, "w", newline="", encoding="utf-8") as out_fh:
                    status_field = (
                        "dhisanaai_webhook_push_status"
                        if util_name == "push_lead_to_dhisana_webhook"
                        else "status"
                    )
                    writer = csv.DictWriter(
                        out_fh,
                        fieldnames=fieldnames + [status_field, "command", "output"],
                    )
                    writer.writeheader()
                    for row in rows:
                        cmd = build_cmd(row)
                        status, cmd_str, out_text = run_cmd(cmd, bool(show_ux_flag))
                        row.update(
                            {
                                status_field: status,
                                "command": cmd_str,
                                "output": out_text,
                            }
                        )
                        writer.writerow(row)
                download_name = out_path
                output_csv_path = out_path
                util_output = None
        else:
            values = {}
            for spec in UTILITY_PARAMETERS.get(util_name, []):
                name = spec["name"]
                if spec.get("multiple"):
                    val = ",".join(request.form.getlist(name))
                else:
                    val = request.form.get(name, "")
                values[name] = val
            cmd = build_cmd(values)
            status, cmd_str, out_text = run_cmd(cmd, bool(show_ux_flag))
            if util_name == "generate_image" and status == "SUCCESS":
                try:
                    img_bytes = base64.b64decode(out_text)
                    fd, out_path = tempfile.mkstemp(
                        suffix=".png", dir=common.get_output_dir()
                    )
                    with os.fdopen(fd, "wb") as fh:
                        fh.write(img_bytes)
                    download_name = out_path
                    image_src = "data:image/png;base64," + out_text
                    util_output = None
                except Exception as exc:
                    util_output = f"Error: {exc}"
            else:
                label = (
                    "dhisanaai_webhook_push_status"
                    if util_name == "push_lead_to_dhisana_webhook"
                    else "status"
                )
                util_output = (
                    f"{label}: {status}\ncommand: {cmd_str}\noutput:\n{out_text}"
                )
                for arg in cmd[3:]:
                    if arg.endswith(".csv"):
                        path = os.path.abspath(arg)
                        if os.path.exists(path):
                            download_name = path
                            output_csv_path = path
                            break
    if output_csv_path and os.path.exists(output_csv_path):
        output_rows = _load_csv_preview(output_csv_path)
    if input_csv_path and os.path.exists(input_csv_path):
        input_rows = _load_csv_preview(input_csv_path)
    if output_csv_path and os.path.exists(output_csv_path) and not is_custom:
        session["prev_csv_path"] = output_csv_path
        prev_csv = output_csv_path
    return render_template(
        "run_utility.html",
        utils=utils_list,
        tags=tags_list,
        util_output=util_output,
        download_name=download_name,
        input_rows=input_rows,
        output_rows=output_rows,
        util_params=UTILITY_PARAMETERS,
        default_util=util_name,
        upload_only=UPLOAD_ONLY_UTILS,
        image_src=image_src,
        prev_csv=prev_csv,
        default_mode="previous" if prev_csv else "single",
    )


@app.route("/settings")
def settings():
    """Display environment variables without allowing edits."""
    env_vars = load_env()
    return render_template("settings.html", env_vars=env_vars)


@app.route("/help")
def help_page():
    """Display simple help information about the app and utilities."""
    utils_list = _list_utils()
    return render_template("help.html", utils=utils_list)


@app.route("/history")
def history():
    """Display recent CSV files from the data directory."""
    out_dir = common.get_output_dir()
    files: list[dict[str, str]] = []
    if out_dir.is_dir():
        csv_paths = [p for p in out_dir.iterdir() if p.suffix.lower() == ".csv"]
        csv_paths.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        for p in csv_paths[:50]:
            files.append(
                {
                    "name": p.name,
                    "mtime": datetime.datetime.fromtimestamp(
                        p.stat().st_mtime
                    ).strftime("%Y-%m-%d %H:%M:%S"),
                }
            )
    return render_template("history.html", csv_files=files)


@app.route("/download/<path:filename>")
def download_file(filename: str):
    """Send a file from the output directory."""
    return send_from_directory(
        common.get_output_dir(), os.path.basename(filename), as_attachment=True
    )


@app.route("/download_selected", methods=["POST"])
def download_selected():
    csv_path = request.form.get("csv_path", "")
    selected_json = request.form.get("selected_rows", "")
    if selected_json:
        try:
            rows = json.loads(selected_json)
            if rows:
                tmp = common.make_temp_csv_filename("download")
                with open(tmp, "w", newline="", encoding="utf-8") as fh:
                    writer = csv.DictWriter(fh, fieldnames=rows[0].keys())
                    writer.writeheader()
                    for r in rows:
                        writer.writerow(r)
                csv_path = tmp
        except Exception:
            pass
    if not csv_path or not os.path.exists(csv_path):
        flash("No CSV found to download.")
        return redirect(url_for("run_utility"))
    return send_from_directory(
        common.get_output_dir(), os.path.basename(csv_path), as_attachment=True
    )


@app.route("/push_to_dhisana", methods=["POST"])
def push_to_dhisana():
    csv_path = request.form.get("csv_path", "")
    selected_json = request.form.get("selected_rows", "")
    output_text = request.form.get("output_text", "")
    if selected_json:
        try:
            rows = json.loads(selected_json)
            if rows:
                tmp = common.make_temp_csv_filename("push")
                with open(tmp, "w", newline="", encoding="utf-8") as fh:
                    writer = csv.DictWriter(fh, fieldnames=rows[0].keys())
                    writer.writeheader()
                    for r in rows:
                        writer.writerow(r)
                csv_path = tmp
        except Exception:
            pass
    linkedin_re = re.compile(r"https://www\.linkedin\.com/in/[A-Za-z0-9_-]+")
    urls: set[str] = set()
    if csv_path and os.path.exists(csv_path):
        try:
            with open(csv_path, newline="", encoding="utf-8-sig") as fh:
                reader = csv.reader(fh)
                for row in reader:
                    for cell in row:
                        urls.update(linkedin_re.findall(str(cell)))
        except Exception:
            pass
    urls.update(linkedin_re.findall(output_text or ""))
    if not urls:
        flash("No LinkedIn profile URLs found to push.")
        return redirect(url_for("run_utility"))

    webhook_url = os.getenv("DHISANA_WEBHOOK_URL")
    api_key = os.getenv("DHISANA_API_KEY")
    if not webhook_url or not api_key:
        flash("Please set DHISANA_WEBHOOK_URL and DHISANA_API_KEY in Settings.")
        return redirect(url_for("settings"))

    pushed = 0
    for url in urls:
        try:
            asyncio.run(
                push_lead_to_dhisana_webhook.push_lead_to_dhisana_webhook(
                    "",
                    linkedin_url=url,
                    webhook_url=webhook_url,
                )
            )
            pushed += 1
        except Exception:
            pass
    flash(f"Pushed {pushed} leads to Dhisana.")
    return redirect(url_for("run_utility"))


def embed_text(text: str) -> np.ndarray:
    """Return the LLM embedding for the given text."""
    client = openai_client_sync()
    response = client.embeddings.create(
        input=text,
        model="text-embedding-ada-002",
    )
    return np.array(response.data[0].embedding)


def build_utility_embeddings() -> None:
    """Load or build utility embeddings and FAISS index cache."""
    global UTILITY_INDEX, UTILITY_CODES
    # Try loading from cache
    if EMBED_INDEX_PATH.exists() and EMBED_CODES_PATH.exists():
        try:
            UTILITY_INDEX = faiss.read_index(str(EMBED_INDEX_PATH))
            with open(EMBED_CODES_PATH, "r", encoding="utf-8") as f:
                UTILITY_CODES = json.load(f)
            return
        except Exception:
            # fallback to rebuild
            pass

    codes: list[str] = []
    embeds: list[np.ndarray] = []
    for fname in os.listdir(UTILS_DIR):
        if not fname.endswith(".py") or fname in ['common.py', "codegen_barbarika_web_parsing.py"]:
            continue
        path = os.path.join(UTILS_DIR, fname)
        with open(path, "r", encoding="utf-8") as f:
            code = f.read()
        embeds.append(embed_text(code[:2000]).astype(np.float32))
        codes.append(code)
    # Also scan user-generated utilities on Desktop
    if USER_UTIL_DIR.is_dir():
        for user_path in USER_UTIL_DIR.glob("*.py"):
            try:
                code = user_path.read_text(encoding="utf-8")
            except Exception:
                continue
            embeds.append(embed_text(code[:2000]).astype(np.float32))
            codes.append(code)

    if embeds:
        mat = np.vstack(embeds)
        faiss.normalize_L2(mat)
        index = faiss.IndexFlatIP(mat.shape[1])
        index.add(mat)
    else:
        index = faiss.IndexFlatIP(1)

    UTILITY_INDEX = index
    UTILITY_CODES = codes

    # Persist cache
    try:
        EMBED_INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
        faiss.write_index(UTILITY_INDEX, str(EMBED_INDEX_PATH))
        with open(EMBED_CODES_PATH, "w", encoding="utf-8") as f:
            json.dump(UTILITY_CODES, f)
    except Exception:
        pass


build_utility_embeddings()
load_custom_parameters()


def get_top_k_utilities(prompt: str, k: int) -> list[str]:
    """Return the top-k utility code snippets for the given prompt."""
    query_vec = embed_text(prompt).astype(np.float32)
    faiss.normalize_L2(query_vec.reshape(1, -1))
    distances, indices = UTILITY_INDEX.search(query_vec.reshape(1, -1), k)
    return [UTILITY_CODES[i] for i in indices[0]]


@app.route("/generate_utility", methods=["POST"])
def generate_utility():
    user_prompt = request.form["prompt"]
    top_examples = get_top_k_utilities(user_prompt, k=5)
    prompt_lines = []
    prompt_lines.append(
        "# User wants to build a new GTM utility with the following details:"
    )
    prompt_lines.append(f"# {user_prompt}")
    prompt_lines.append(
        "# The utility should accept command line arguments and also provide a *_from_csv* function that reads the same parameters from a CSV file."
    )
    prompt_lines.append(
        "# The input CSV columns should match the argument names without leading dashes."
    )
    prompt_lines.append(
        "# Do NOT create a 'mode' argument or any sub-commands. main() should simply parse \"output_file\" as the first positional argument followed by optional parameters."
    )
    prompt_lines.append(
        "# Provide a <utility_name>_from_csv(input_file, output_file, **kwargs) helper that reads the same parameters from a CSV file."
    )
    prompt_lines.append(
        "# The input CSV headers must match the argument names (without leading dashes) except for output_file."
    )
    prompt_lines.append(
        "# The output CSV must keep all original columns and append any new columns produced by the utility."
    )
    prompt_lines.append(
        "# Please output only the Python code for this utility below, without any markdown fences or additional text"
    )
    prompt_lines.append(
        "# Get fully functional, compiling standalone python script with all the required imports."
    )
    prompt_lines.append(
        "# Generate e2e functional script will all required functions, dont take any dependency on content in utils directory or custom modules. Use the code in the prompt just as examples not as dependency. You can use only the standard python libraries  and following as dependencies when generating code.\n"
        "httpx\n"
        "openai\n"
        "pydantic>=2.0\n"
        "playwright==1.52.0\n"
        "playwright-stealth>=2.0.0\n"
        "aiohttp\n"
        "beautifulsoup4\n"
        "aiosmtplib\n"
        "requests\n"
        "simple_salesforce\n"
        "numpy\n"
        "greenlet>=2.0.2,\n"
        "pandas"
    )
    prompt_lines.append(
        "# arguments to mail will be like in example below, output_file is always a parameter. input arguments like --person_title etc are custom parameters that can be passed as input the to script\n"
        "def main() -> None:\n"
        '    parser = argparse.ArgumentParser(description="Search people in Apollo.io")\n'
        '    parser.add_argument("output_file", help="CSV file to create")\n'
        '    parser.add_argument("--person_titles", default="", help="Comma separated job titles")\n'
        '    parser.add_argument("--person_locations", default="", help="Comma separated locations")'
    )
    prompt_lines.append(
        "# Use standard names for lead and company properties in output like full_name, first_name, last_name, user_linkedin_url, email, organization_linkedin_url, website, job_tiltle, lead_location, primary_domain_of_organization"
    )
    prompt_lines.append(
        "# Use user_linkedin_url property to represent ursers linked in url"
    )
    prompt_lines.append(
        '# Always write the output to the csv in the output_file specific like below converting the json to csv format. \nfieldnames: List[str] = []\n    for row in results:\n        for key in row:\n            if key not in fieldnames:\n                fieldnames.append(key)\n\n    with out_path.open("w", newline="", encoding="utf-8") as fh:\n        writer = csv.DictWriter(fh, fieldnames=fieldnames)\n        writer.writeheader()\n        for row in results:\n            writer.writerow(row)\n'
    )
    prompt_lines.append(
        "# The app passes the output_path implicitly using the tool name and current date_time; do not ask the user for this value."
    )
    prompt_lines.append(
        "# Use following as examples which can help you generate the code required for above GTM utility.",
    )
    for idx, example in enumerate(top_examples, start=1):
        prompt_lines.append(f"# Example {idx}:")
        for line in example.splitlines():
            prompt_lines.append(f"# {line}")
    prompt_lines.append(
        "# Helo generate a fully functional python utility code that user wants.",
    )
    codex_prompt = "\n".join(prompt_lines) + "\n"
    logging.info("OpenAI prompt being sent:\n%s", codex_prompt)

    try:
        client = openai_client_sync()
        model_name = os.getenv("MODEL_TO_GENERATE_UTILITY", "o3")
        response = client.responses.create(model=model_name, input=codex_prompt)
        prev_response_id = getattr(response, "id", None)
        # Only handle the new format: response.output is a list of ResponseOutputMessage
        code = None
        if (
            hasattr(response, "output")
            and isinstance(response.output, list)
            and len(response.output) > 0
        ):
            for msg in response.output:
                if hasattr(msg, "content") and isinstance(msg.content, list):
                    for c in msg.content:
                        if (
                            hasattr(c, "text")
                            and isinstance(c.text, str)
                            and c.text.strip()
                        ):
                            code = c.text.strip()
                            break
                    if code:
                        break
        if not code:
            raise ValueError(f"Unexpected OpenAI response format: {response!r}")
    except Exception as e:
        logging.error("OpenAI API error: %s", str(e))
        return jsonify({"success": False, "error": str(e)}), 500

    # Validate generated code by attempting to compile; if syntax errors occur,
    # ask the LLM to correct up to 10 retries.
    for attempt in range(10):
        try:
            compile(code, "<generated>", "exec")
            break
        except Exception as compile_err:
            logging.warning(
                "Generated code failed to compile (attempt %d): %s",
                attempt + 1,
                compile_err,
            )
            commented_code = "\n".join(f"# {line}" for line in code.splitlines())
            correction_prompt = (
                codex_prompt
                + f"# The previous generated code failed to compile on attempt {attempt+1}: {compile_err}\n"
                + f"{commented_code}\n"
                + "# Please provide the full corrected utility code below:\n"
            )
            response = client.responses.create(
                model=model_name,
                input=correction_prompt,
                previous_response_id=prev_response_id,
            )
            prev_response_id = getattr(response, "id", prev_response_id)
            # Extract corrected code same as before
            new_code = None
            if hasattr(response, "output") and isinstance(response.output, list):
                for msg in response.output:
                    if hasattr(msg, "content") and isinstance(msg.content, list):
                        for c in msg.content:
                            if (
                                hasattr(c, "text")
                                and isinstance(c.text, str)
                                and c.text.strip()
                            ):
                                new_code = c.text.strip()
                                break
                        if new_code:
                            break
            if not new_code:
                continue
            code = new_code
    else:
        # Exhausted retries without valid code
        err_msg = f"Code failed to compile after {attempt+1} attempts: {compile_err}"
        logging.error(err_msg)
        return jsonify({"success": False, "error": err_msg}), 500

    return jsonify({"success": True, "code": code})


@app.route("/save_utility", methods=["POST"])
def save_utility():
    try:
        data = request.get_json(force=True)
        code = data.get("code")
        if not code:
            return jsonify({"success": False, "error": "No code to save"}), 400
        name = data.get("name", "").strip()
        desc = data.get("description", "").strip()
        prompt = data.get("prompt", "").strip()

        if not name:
            return jsonify({"success": False, "error": "Name required"}), 400

        # Sanitize name and build unique base
        safe = re.sub(r"\s+", "_", name)
        safe = re.sub(r"[^A-Za-z0-9_-]", "", safe)
        safe = safe[:30]
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        base = f"{safe}_{timestamp}"

        target_dir = USER_UTIL_DIR
        logging.info("save_utility: target folder=%s", target_dir)

        file_path = target_dir / f"{base}.py"
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(code)

        param_pattern = re.compile(r"add_argument\(\s*['\"]([^'\"]+)['\"](.*?)\)")
        help_pattern = re.compile(r"help\s*=\s*['\"]([^'\"]+)['\"]")
        params: list[dict[str, str]] = []
        skip_args = {
            "output_file",
            "--output_file",
            "input_file",
            "--input_file",
            "csv_file",
            "--csv_file",
        }
        for match in param_pattern.finditer(code):
            arg_name = match.group(1)
            if arg_name in skip_args:
                continue
            rest = match.group(2)
            help_match = help_pattern.search(rest)
            label = (
                help_match.group(1)
                if help_match
                else arg_name.lstrip("-").replace("_", " ").capitalize()
            )
            params.append({"name": arg_name, "label": label})

        meta = {"name": name, "description": desc, "prompt": prompt, "params": params}
        with open(target_dir / f"{base}.json", "w", encoding="utf-8") as f:
            json.dump(meta, f)

        if params:
            UTILITY_PARAMETERS[base] = params
            load_custom_parameters()

        logging.info("save_utility: wrote file %s", file_path)
        return jsonify({"success": True, "file_path": str(file_path)})
    except Exception as e:
        logging.error("Error saving utility to file: %s", e)
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/web_parse_utility', methods=['GET', 'POST'])
def web_parse_utility():
    if request.method == 'GET':
        # If it's a GET request with parameters, treat it as a POST
        if request.args:
            def generate():
                # Set up logging at the start
                logging.basicConfig(level=logging.INFO)
                logger = logging.getLogger(__name__)
                try:
                    url = request.args.get('url')
                    fields = request.args.get('fields', '').split(',')
                    max_depth = int(request.args.get('max_depth', 3))
                    pagination = request.args.get('pagination', 'false').lower() == 'true'
                    instructions = request.args.get('instructions', '')
                    if not url:
                        return json.dumps({'error': 'URL is required'})
                    requirement = codegen_barbarika_web_parsing.UserRequirement(
                        target_url=url,
                        data_to_extract=fields,
                        max_depth=max_depth,
                        pagination=pagination,
                        additional_instructions=instructions
                    )

                    def tree_update_callback(tree_json):
                        tree_update_queue.put({'type': 'tree_update', 'tree': tree_json})

                    def log_update_callback(msg):
                        tree_update_queue.put({'type': 'log', 'message': f"{datetime.datetime.now().strftime('%H:%M:%S')}:{msg}"})
                    parser = codegen_barbarika_web_parsing.WebParser(requirement,
                                                                     log_update_callback,
                                                                     tree_update_callback)
                    tree_update_queue = queue.Queue()



                    def run_crawl():
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        try:
                            tree_update_queue.put({'type': 'log', 'message': 'Analyzing requirements...'})
                            plan = loop.run_until_complete(parser.analyze_requirement())
                            tree_update_queue.put({'type': 'plan', 'plan': plan})
                            parser.plan = plan
                            loop.run_until_complete(parser.build_page_tree(tree_update_callback=tree_update_callback, log_update_callback=log_update_callback))
                            tree_update_queue.put({'type': 'log', 'message': 'Generating extraction code...'})
                            loop.run_until_complete(parser.generate_extraction_code())
                            tree_update_queue.put({'type': 'log', 'message': 'Executing generated code...'})
                            result = loop.run_until_complete(parser.execute_generated_code(url))
                            # Defensive assignment and logging
                            if not parser.generated_code and 'code' in result:
                                parser.generated_code = result['code']
                            if (not result.get('extracted_data') or len(result.get('extracted_data', [])) == 0) and 'data' in result:
                                result['extracted_data'] = result['data']
                            logger.info(f"[web_parse_utility] Final generated_code length: {len(parser.generated_code) if parser.generated_code else 0}")
                            logger.info(f"[web_parse_utility] Final extracted_data length: {len(result.get('extracted_data', [])) if result.get('extracted_data') else 0}")
                            completion_data = {
                                'type': 'complete',
                                'code': parser.generated_code,
                                'result': result,
                                'extracted_data': result.get('extracted_data', []),
                                'total_items': result.get('total_items', 0),
                                'execution_success': result.get('execution_success', False),
                                'csv_file': result.get('csv_file', ''),
                                'message': result.get('message', ''),
                                'extra_info': getattr(parser, 'extra_info', {}),
                                'plan': getattr(parser, 'plan', None)
                            }
                            tree_update_queue.put(completion_data)
                        except Exception as e:
                            error_msg = f"Error: {str(e)}"
                            logger.error(error_msg)
                            tree_update_queue.put({'type': 'error', 'error': error_msg})
                        finally:
                            loop.close()

                    crawl_thread = threading.Thread(target=run_crawl, daemon=True)
                    crawl_thread.start()
                    while True:
                        try:
                            update = tree_update_queue.get(timeout=0.2)
                            if isinstance(update, dict) and update.get('type') == 'complete':
                                yield f"data: {json.dumps(update)}\n\n"
                                break
                            elif isinstance(update, dict) and update.get('type') == 'error':
                                yield f"data: {json.dumps(update)}\n\n"
                                break
                            elif isinstance(update, dict) and update.get('type') == 'log':
                                yield f"data: {json.dumps(update)}\n\n"
                            elif isinstance(update, dict) and update.get('type') == 'plan':
                                yield f"data: {json.dumps(update)}\n\n"
                            elif isinstance(update, dict) and update.get('type') == 'tree_update':
                                yield f"data: {json.dumps(update)}\n\n"
                            else:
                                # fallback for any other dict
                                yield f"data: {json.dumps({'type': 'tree_update', 'tree': update})}\n\n"
                        except queue.Empty:
                            if not crawl_thread.is_alive():
                                break
                            continue
                except Exception as e:
                    error_msg = f"Error: {str(e)}"
                    logger.error(error_msg)
                    yield f"data: {json.dumps({'type': 'error', 'error': error_msg})}\n\n"
            return Response(
                stream_with_context(generate()),
                mimetype='text/event-stream',
                headers={
                    'Cache-Control': 'no-cache',
                    'Connection': 'keep-alive',
                    'X-Accel-Buffering': 'no',
                    'Content-Type': 'text/event-stream'
                }
            )
        # If it's a GET request without parameters, render the template
        return render_template('web_parse_utility.html')
    # Handle POST request
    def generate():
        # Set up logging at the start
        logging.basicConfig(level=logging.INFO)
        logger = logging.getLogger(__name__)
        try:
            data = request.get_json()
            url = data.get('url')
            fields = data.get('fields', '').split(',')
            max_depth = int(data.get('max_depth', 3))
            pagination = data.get('pagination', 'false').lower() == 'true'
            instructions = data.get('instructions', '')
            if not url:
                return json.dumps({'error': 'URL is required'})
            requirement = codegen_barbarika_web_parsing.UserRequirement(
                target_url=url,
                data_to_extract=fields,
                max_depth=max_depth,
                pagination=pagination,
                additional_instructions=instructions
            )
            parser = codegen_barbarika_web_parsing.WebParser(requirement)
            tree_update_queue = queue.Queue()

            def tree_update_callback(tree_json):
                tree_update_queue.put({'type': 'tree_update', 'tree': tree_json})

            def run_crawl():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    tree_update_queue.put({'type': 'log', 'message': 'Analyzing requirements...'})
                    plan = loop.run_until_complete(parser.analyze_requirement())
                    tree_update_queue.put({'type': 'plan', 'plan': plan})
                    parser.plan = plan
                    loop.run_until_complete(parser.build_page_tree(tree_update_callback=tree_update_callback))
                    tree_update_queue.put({'type': 'log', 'message': 'Generating extraction code...'})
                    loop.run_until_complete(parser.generate_extraction_code())
                    tree_update_queue.put({'type': 'log', 'message': 'Executing generated code...'})
                    result = loop.run_until_complete(parser.execute_generated_code(url))
                    # Defensive assignment and logging
                    if not parser.generated_code and 'code' in result:
                        parser.generated_code = result['code']
                    if (not result.get('extracted_data') or len(result.get('extracted_data', [])) == 0) and 'data' in result:
                        result['extracted_data'] = result['data']
                    logger.info(f"[web_parse_utility] Final generated_code length: {len(parser.generated_code) if parser.generated_code else 0}")
                    logger.info(f"[web_parse_utility] Final extracted_data length: {len(result.get('extracted_data', [])) if result.get('extracted_data') else 0}")
                    completion_data = {
                        'type': 'complete',
                        'code': parser.generated_code,
                        'result': result,
                        'extracted_data': result.get('extracted_data', []),
                        'total_items': result.get('total_items', 0),
                        'execution_success': result.get('execution_success', False),
                        'csv_file': result.get('csv_file', ''),
                        'message': result.get('message', ''),
                        'extra_info': getattr(parser, 'extra_info', {}),
                        'plan': getattr(parser, 'plan', None)
                    }
                    tree_update_queue.put(completion_data)
                except Exception as e:
                    error_msg = f"Error: {str(e)}"
                    logger.error(error_msg)
                    tree_update_queue.put({'type': 'error', 'error': error_msg})
                finally:
                    loop.close()
            crawl_thread = threading.Thread(target=run_crawl, daemon=True)
            crawl_thread.start()
            while True:
                try:
                    update = tree_update_queue.get(timeout=0.2)
                    if isinstance(update, dict) and update.get('type') == 'complete':
                        yield f"data: {json.dumps(update)}\n\n"
                        break
                    elif isinstance(update, dict) and update.get('type') == 'error':
                        yield f"data: {json.dumps(update)}\n\n"
                        break
                    elif isinstance(update, dict) and update.get('type') == 'log':
                        yield f"data: {json.dumps(update)}\n\n"
                    elif isinstance(update, dict) and update.get('type') == 'plan':
                        yield f"data: {json.dumps(update)}\n\n"
                    elif isinstance(update, dict) and update.get('type') == 'tree_update':
                        yield f"data: {json.dumps(update)}\n\n"
                    else:
                        yield f"data: {json.dumps({'type': 'tree_update', 'tree': update})}\n\n"
                except queue.Empty:
                    if not crawl_thread.is_alive():
                        break
                    continue
        except Exception as e:
            error_msg = f"Error: {str(e)}"
            logger.error(error_msg)
            yield f"data: {json.dumps({'type': 'error', 'error': error_msg})}\n\n"
    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no',
            'Content-Type': 'text/event-stream'
        }
    )


@app.route('/save_web_parse_utility', methods=['POST'])
def save_web_parse_utility():
    """Save web parsing utility as a new utility."""
    try:
        data = request.get_json()
        if not data or not all(k in data for k in ['code', 'name', 'description', 'prompt']):
            return jsonify({'error': 'Missing required fields'}), 400

        # Save the utility using the existing save_utility function
        try:
            # Create a temporary request context with the data
            with app.test_request_context(json=data):
                # Call save_utility which will get the data from request.get_json()
                response = save_utility()
                return response
        except Exception as e:
            logging.error('Error in save_utility: %s', str(e))
            return jsonify({'success': False, 'error': str(e)}), 500

    except Exception as e:
        logging.error('Error in save_web_parse_utility: %s', str(e))
        return jsonify({'error': str(e)}), 500


@app.route('/download_web_parse_csv')
def download_web_parse_csv():
    """Download the CSV file from the latest web parsing session."""
    csv_file = session.get('web_parse_csv_file')
    if not csv_file or not os.path.exists(csv_file):
        flash("No CSV file found from web parsing session.")
        return redirect(url_for("run_utility"))

    filename = os.path.basename(csv_file)
    return send_from_directory(
        os.path.dirname(csv_file),
        filename,
        as_attachment=True,
        download_name='extracted_data.csv'
    )
