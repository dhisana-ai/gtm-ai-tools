import os
import shlex
import subprocess
import tempfile
import csv
import re
import asyncio
from utils import push_lead_to_dhisana_webhook
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    send_from_directory,
)
from dotenv import dotenv_values, set_key

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", "dev")
ENV_FILE = os.path.join(os.path.dirname(__file__), "..", ".env")

# Optional nicer titles for utilities when displayed in the UI
UTILITY_TITLES = {
    "call_openai_llm": "OpenAI Tools",
    "linkedin_search_to_csv": "LinkedIn Search to CSV",
    "find_a_user_by_name_and_keywords": "Find LinkedIn Profile by Name",
    "find_user_by_job_title": "Find LinkedIn Profile by Job Title",
    "find_users_by_name_and_keywords": "Bulk Find LinkedIn Profiles",
    "fetch_html_playwright": "Scrape Website HTML (Playwright)",
}

# Mapping of utility parameters for the Run a Utility form. Each utility maps
# to a list of dictionaries describing the CLI argument name and display label.
UTILITY_PARAMETERS = {
    "apollo_info": [
        {"name": "--linkedin_url", "label": "LinkedIn URL"},
        {"name": "--email", "label": "Email"},
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
        {"name": "company_name", "label": "Company name"},
        {"name": "--location", "label": "Company location"},
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
    "find_users_by_name_and_keywords": [
        {"name": "input_file", "label": "Input CSV"},
        {"name": "output_file", "label": "Output CSV"},
    ],
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
    "extract_from_webpage": [
        {"name": "url", "label": "Website URL"},
        {"name": "--lead", "label": "Fetch lead", "type": "boolean"},
        {"name": "--leads", "label": "Fetch leads", "type": "boolean"},
        {"name": "--company", "label": "Fetch company", "type": "boolean"},
        {"name": "--companies", "label": "Fetch companies", "type": "boolean"},
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
    "push_ph_top_creators": [
        {"name": "--days-back", "label": "Number of days(default: 7) to look back from below date", "type": "number", "default": 7},
        {"name": "--date", "label": "Date (YYYY-MM-DD)", "type": "date", "optional": True},

    ]
}


def load_env():
    return dotenv_values(ENV_FILE)


def _format_title(name: str) -> str:
    """Return a human friendly title from a module name."""
    return UTILITY_TITLES.get(name, name.replace("_", " ").title())


def _list_utils() -> list[dict[str, str]]:
    """Return available utilities as ``{"name", "title", "desc"}`` dicts."""
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
        items.append({"name": base, "title": _format_title(base), "desc": desc})
    return sorted(items, key=lambda x: x["title"])


@app.route('/')
def index():
    return redirect(url_for('run_utility'))


@app.route('/utility', methods=['GET', 'POST'])
def run_utility():
    util_output = None
    download_name = None
    utils_list = _list_utils()
    if request.method == 'POST':
        util_name = request.form.get('util_name', '')
        file = request.files.get('csv_file')
        uploaded = None
        if file and file.filename:
            tmp_dir = tempfile.gettempdir()
            filename = os.path.join(tmp_dir, os.path.basename(file.filename))
            file.save(filename)
            uploaded = filename

        def build_cmd(values: dict[str, str]) -> list[str]:
            cmd = ['python', '-m', f'utils.{util_name}']
            for spec in UTILITY_PARAMETERS.get(util_name, []):
                name = spec['name']
                val = (values.get(name) or '').strip()
                if not val:
                    continue
                if spec.get('type') == 'boolean':
                    if val.lower() in ('1', 'true', 'yes', 'on'):
                        cmd.append(name)
                elif name.startswith('-'):
                    cmd.extend([name, val])
                else:
                    cmd.append(val)
            if util_name == 'linkedin_search_to_csv':
                fd, out_path = tempfile.mkstemp(suffix='.csv', dir=tempfile.gettempdir())
                os.close(fd)
                insert_at = len(cmd)
                for i, arg in enumerate(cmd[3:], start=3):
                    if arg.startswith('-'):
                        insert_at = i
                        break
                cmd.insert(insert_at, out_path)
            return cmd

        def run_cmd(cmd: list[str]) -> tuple[str, str, str]:

            env = os.environ.copy()
            root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
            env['PYTHONPATH'] = env.get('PYTHONPATH', '') + ':' + root_dir
            print(cmd)
            proc = subprocess.run(cmd, capture_output=True, text=True, env=env)
            status = 'SUCCESS' if proc.returncode == 0 else 'FAIL'
            output = proc.stdout if proc.returncode == 0 else (proc.stderr or 'Error running command')
            cmd_str = ' '.join(shlex.quote(c) for c in cmd)
            return status, cmd_str, output.strip()

        if uploaded:
            import csv
            with open(uploaded, newline='', encoding='utf-8') as fh:
                reader = csv.DictReader(fh)
                rows = list(reader)
                fieldnames = reader.fieldnames or []
            out_path = os.path.join(tempfile.gettempdir(), os.path.basename(uploaded) + '.out.csv')
            with open(out_path, 'w', newline='', encoding='utf-8') as out_fh:
                writer = csv.DictWriter(out_fh, fieldnames=fieldnames + ['status', 'command', 'output'])
                writer.writeheader()
                for row in rows:
                    cmd = build_cmd(row)
                    status, cmd_str, out_text = run_cmd(cmd)
                    row.update({'status': status, 'command': cmd_str, 'output': out_text})
                    writer.writerow(row)
            download_name = out_path
            util_output = None
        else:
            values = {spec['name']: request.form.get(spec['name'], '') for spec in UTILITY_PARAMETERS.get(util_name, [])}
            cmd = build_cmd(values)
            status, cmd_str, out_text = run_cmd(cmd)
            util_output = f"status: {status}\ncommand: {cmd_str}\noutput:\n{out_text}"
            for arg in cmd[3:]:
                if arg.endswith('.csv'):
                    path = os.path.abspath(arg)
                    if os.path.exists(path):
                        download_name = path
                        break
    return render_template(
        'run_utility.html',
        utils=utils_list,
        util_output=util_output,
        download_name=download_name,
        util_params=UTILITY_PARAMETERS,
        default_util='linkedin_search_to_csv',
    )



@app.route('/settings', methods=['GET', 'POST'])
def settings():
    env_vars = load_env()
    if request.method == 'POST':
        for key in env_vars:
            value = request.form.get(key, '')
            set_key(ENV_FILE, key, value)
        flash('Settings saved.')
        return redirect(url_for('settings'))
    return render_template('settings.html', env_vars=env_vars)


@app.route('/help')
def help_page():
    """Display simple help information about the app and utilities."""
    utils_list = _list_utils()
    return render_template('help.html', utils=utils_list)


@app.route('/download/<path:filename>')
def download_file(filename: str):
    """Send a file from the temporary directory."""
    return send_from_directory(tempfile.gettempdir(), os.path.basename(filename), as_attachment=True)


@app.route('/push_to_dhisana', methods=['POST'])
def push_to_dhisana():
    csv_path = request.form.get('csv_path', '')
    output_text = request.form.get('output_text', '')
    linkedin_re = re.compile(r'https://www\.linkedin\.com/in/[A-Za-z0-9_-]+')
    urls: set[str] = set()
    if csv_path and os.path.exists(csv_path):
        try:
            with open(csv_path, newline='', encoding='utf-8') as fh:
                reader = csv.reader(fh)
                for row in reader:
                    for cell in row:
                        urls.update(linkedin_re.findall(str(cell)))
        except Exception:
            pass
    urls.update(linkedin_re.findall(output_text or ''))
    if not urls:
        flash('No LinkedIn profile URLs found to push.')
        return redirect(url_for('run_utility'))

    webhook_url = os.getenv('DHISANA_WEBHOOK_URL')
    api_key = os.getenv('DHISANA_API_KEY')
    if not webhook_url or not api_key:
        flash('Please set DHISANA_WEBHOOK_URL and DHISANA_API_KEY in Settings.')
        return redirect(url_for('settings'))

    pushed = 0
    for url in urls:
        try:
            asyncio.run(
                push_lead_to_dhisana_webhook.push_lead_to_dhisana_webhook(
                    '',
                    linkedin_url=url,
                    webhook_url=webhook_url,
                )
            )
            pushed += 1
        except Exception:
            pass
    flash(f'Pushed {pushed} leads to Dhisana.')
    return redirect(url_for('run_utility'))
