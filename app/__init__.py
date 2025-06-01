import os
import shlex
import subprocess
import tempfile
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
        {"name": "--proxy_url", "label": "Proxy URL"},
        {"name": "--captcha_key", "label": "2Captcha key"},
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
    "linkedin_search_to_csv": [
        {"name": "query", "label": "Google query"},
        {"name": "output_file", "label": "Output CSV"},
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
}


def load_env():
    return dotenv_values(ENV_FILE)


def _list_utils() -> list[tuple[str, str]]:
    """Return available utilities as ``(name, description)`` tuples."""
    utils_dir = os.path.join(os.path.dirname(__file__), "..", "utils")
    items: list[tuple[str, str]] = []
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
        items.append((base, desc))
    return sorted(items, key=lambda x: x[0])


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
        cmd = [
            'python',
            '-m',
            f'utils.{util_name}',
        ]
        for spec in UTILITY_PARAMETERS.get(util_name, []):
            name = spec['name']
            value = request.form.get(name, '').strip()
            if not value:
                continue
            if spec.get('type') == 'boolean':
                cmd.append(name)
            elif name.startswith('-'):
                cmd.extend([name, value])
            else:
                cmd.append(value)
        if uploaded:
            cmd.append(uploaded)
        env = os.environ.copy()
        root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        env['PYTHONPATH'] = env.get('PYTHONPATH', '') + ':' + root_dir
        proc = subprocess.run(cmd, capture_output=True, text=True, env=env)
        if proc.returncode != 0:
            util_output = proc.stderr or 'Error running command'
        else:
            util_output = proc.stdout
        for arg in cmd[3:]:
            if arg.endswith('.csv') and (not uploaded or arg != uploaded):
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
