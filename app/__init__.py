import os
import shlex
import shutil
import subprocess
import tempfile
import csv
import re
import asyncio
import json
import base64
import random
import datetime
from utils import (
    push_lead_to_dhisana_webhook,
    linkedin_search_to_csv,
    apollo_info,
    check_email_zero_bounce,
    find_users_by_name_and_keywords,
    find_user_by_job_title,
    find_company_info,
    call_openai_llm,
    score_lead,
    generate_email,
    extract_from_webpage,
    common,
)
from pathlib import Path

try:
    from flask import (
        Flask,
        render_template,
        request,
        redirect,
        url_for,
        flash,
        send_from_directory,
        session,
        jsonify,
    )
except Exception:  # pragma: no cover - fallback for test stubs
    from flask import (
        Flask,
        render_template,
        request,
        redirect,
        url_for,
        flash,
        send_from_directory,
        jsonify,
    )

    session = {}
from dotenv import dotenv_values, set_key
import openai
try:
    import numpy as np
except Exception:  # pragma: no cover - optional
    np = None
import logging
import faiss

logging.basicConfig(level=logging.INFO)

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", "dev")
ENV_FILE = os.path.join(os.path.dirname(__file__), "..", ".env")
UTILS_DIR = os.path.join(os.path.dirname(__file__), "..", "utils")
# FAISS index and codes for utility embeddings (cosine similarity)
# Cache paths for utility embeddings index and codes
# Directory for user-generated utilities: prefer /data mount if available, else use in-repo folder
# Directory for user-generated utilities (create gtm_utility at repo root)
USER_UTIL_DIR = Path(__file__).resolve().parents[1] / 'gtm_utility'
USER_UTIL_DIR.mkdir(parents=True, exist_ok=True)

# Data directory for persistent files and FAISS cache; prefer mounted /data in container
ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = Path('/data') if Path('/data').is_dir() else ROOT / 'data'
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Cache paths for utility embeddings index and codes under the data folder
FAISS_CACHE_DIR = DATA_DIR / 'faiss'
EMBED_INDEX_PATH = FAISS_CACHE_DIR / 'utility_embeddings.index'
EMBED_CODES_PATH = FAISS_CACHE_DIR / 'utility_embeddings.json'

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
    "find_a_user_by_name_and_keywords": "Find LinkedIn Profile by Name",
    "find_user_by_job_title": "Find LinkedIn Profile by Job Title",
    "find_users_by_name_and_keywords": "Bulk Find LinkedIn Profiles",
    "apollo_info": "Enrich Lead With Apollo.io",
    "fetch_html_playwright": "Scrape Website HTML (Playwright)",
    "extract_companies_from_image": "Extract Companies from Image",
    "extract_from_webpage": "Extract Leads From Website",
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
        {"name": "company_domain", "label": "Company domain"},
    ],
    "find_user_by_job_title": [
        {"name": "job_title", "label": "Job title"},
        {"name": "company_name", "label": "Company name"},
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
        {"name": "--companies", "label": "Extract Multiple Companies", "type": "boolean"},
        {"name": "--initial_actions", "label": "Actions to do on Website Load, first time. Like select filters"},
        {"name": "--page_actions", "label": "Actions to do When each page loads."},
        {"name": "--parse_instructions", "label": "Custom instructions on how to extracts leads or company from the webpage that is loaded"},
        {"name": "--pagination_actions", "label": "Instructions on how to move to next page and extract more leads"},
        {"name": "--max_pages", "label": "Maximum number of pages to navigate"},
        {"name": "--show_ux", "label": "Show website UX during parsing", "type": "boolean"},
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
    tag_order = ["find", "enrich", "score", "route"]
    tags_list = [t for t in tag_order if t in tags_set]
    tags_list.extend(sorted(tags_set - set(tag_order)))
    util_name = request.form.get("util_name", "linkedin_search_to_csv")
    prev_csv = session.get("prev_csv_path")
    if prev_csv and os.path.exists(prev_csv):
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
        ):
            uploaded = prev_csv
        if (
            not uploaded
            and util_name in UPLOAD_ONLY_UTILS
            and prev_csv
            and os.path.exists(prev_csv)
        ):
            uploaded = prev_csv

        if uploaded:
            input_csv_path = uploaded

        def build_cmd(values: dict[str, str]) -> list[str]:
            cmd = ["python", "-m", f"utils.{util_name}"]
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
                    f in cmd
                    for f in ("--lead", "--leads", "--company", "--companies")
                ):
                    cmd.append("--leads")
                cmd.extend(["--output_csv", out_path])
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
                        job_title=request.form.get("job_title", ""),
                        search_keywords=request.form.get("search_keywords", ""),
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
            values = {
                spec["name"]: request.form.get(spec["name"], "")
                for spec in UTILITY_PARAMETERS.get(util_name, [])
            }
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
    if output_csv_path and os.path.exists(output_csv_path):
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


@app.route("/settings", methods=["GET", "POST"])
def settings():
    env_vars = load_env()
    if request.method == "POST":
        for key in env_vars:
            value = request.form.get(key, "")
            set_key(ENV_FILE, key, value)
        flash("Settings saved.")
        return redirect(url_for("settings"))
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
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY environment variable is not set")
    client = openai.OpenAI(api_key=api_key)
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
            with open(EMBED_CODES_PATH, 'r', encoding='utf-8') as f:
                UTILITY_CODES = json.load(f)
            return
        except Exception:
            # fallback to rebuild
            pass

    codes: list[str] = []
    embeds: list[np.ndarray] = []
    for fname in os.listdir(UTILS_DIR):
        if not fname.endswith('.py') or fname == 'common.py':
            continue
        path = os.path.join(UTILS_DIR, fname)
        with open(path, 'r', encoding='utf-8') as f:
            code = f.read()
        embeds.append(embed_text(code[:2000]).astype(np.float32))
        codes.append(code)
    # Also scan user-generated utilities on Desktop
    if USER_UTIL_DIR.is_dir():
        for user_path in USER_UTIL_DIR.glob('*.py'):
            try:
                code = user_path.read_text(encoding='utf-8')
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
        with open(EMBED_CODES_PATH, 'w', encoding='utf-8') as f:
            json.dump(UTILITY_CODES, f)
    except Exception:
        pass

build_utility_embeddings()

def get_top_k_utilities(prompt: str, k: int) -> list[str]:
    """Return the top-k utility code snippets for the given prompt."""
    query_vec = embed_text(prompt).astype(np.float32)
    faiss.normalize_L2(query_vec.reshape(1, -1))
    distances, indices = UTILITY_INDEX.search(query_vec.reshape(1, -1), k)
    return [UTILITY_CODES[i] for i in indices[0]]


@app.route("/generate_utility", methods=["POST"])
def generate_utility():
    user_prompt = request.form["prompt"]
    top_examples = get_top_k_utilities(user_prompt, k=3)
    prompt_lines = [
        "# The following are Python utilities for GTM automation, lead generation, enrichment, outreach, or sales/marketing workflows.",
    ]
    for idx, example in enumerate(top_examples, start=1):
        prompt_lines.append(f"# Example {idx}:")
        for line in example.splitlines():
            prompt_lines.append(f"# {line}")
    prompt_lines.append("# User wants a new GTM utility:")
    prompt_lines.append(f"# {user_prompt}")
    prompt_lines.append(
        "# Please output only the Python code for this utility below, without any markdown fences or additional text"
    )
    codex_prompt = "\n".join(prompt_lines) + "\n"
    logging.info("OpenAI prompt being sent:\n%s", codex_prompt)

    try:
        client = openai.OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        response = client.responses.create(
            model="gpt-4o-mini",
            input=codex_prompt
        )
        prev_response_id = getattr(response, 'id', None)
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
            compile(code, '<generated>', 'exec')
            break
        except Exception as compile_err:
            logging.warning("Generated code failed to compile (attempt %d): %s",
                            attempt + 1, compile_err)
            commented_code = "\n".join(f"# {line}" for line in code.splitlines())
            correction_prompt = (
                codex_prompt
                + f"# The previous generated code failed to compile on attempt {attempt+1}: {compile_err}\n"
                + f"{commented_code}\n"
                + "# Please provide the full corrected utility code below:\n"
            )
            response = client.responses.create(
                model="gpt-4o-mini",
                input=correction_prompt,
                previous_response_id=prev_response_id,
            )
            prev_response_id = getattr(response, 'id', prev_response_id)
            # Extract corrected code same as before
            new_code = None
            if hasattr(response, "output") and isinstance(response.output, list):
                for msg in response.output:
                    if hasattr(msg, "content") and isinstance(msg.content, list):
                        for c in msg.content:
                            if hasattr(c, "text") and isinstance(c.text, str) and c.text.strip():
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

    return jsonify({
        "success": True,
        "code": code
    })


@app.route('/save_utility', methods=['POST'])
def save_utility():
    try:
        data = request.get_json(force=True)
        code = data.get('code')
        if not code:
            return jsonify({'success': False, 'error': 'No code to save'}), 400
        prompt = data.get('prompt', '').strip()

        # Build filename from prompt or fallback to timestamped utility name
        if prompt:
            # Sanitize prompt to safe file prefix
            safe = re.sub(r'\s+', '_', prompt)
            safe = re.sub(r'[^A-Za-z0-9_-]', '', safe)
            safe = safe[:30]
            timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{safe}_{timestamp}.py"
        else:
            timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'utility_{timestamp}.py'

        target_dir = USER_UTIL_DIR
        logging.info("save_utility: target folder=%s", target_dir)

        file_path = target_dir / filename
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(code)
        logging.info("save_utility: wrote file %s", file_path)
        return jsonify({'success': True, 'file_path': str(file_path)})
    except Exception as e:
        logging.error('Error saving utility to file: %s', e)
        return jsonify({'success': False, 'error': str(e)}), 500
