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


@app.route('/', methods=['GET', 'POST'])
def index():
    preview = None
    workflow = ''
    util_output = None
    download_name = None
    utils_list = _list_utils()
    if request.method == 'POST':
        mode = request.form.get('mode', 'workflow')
        if mode == 'util':
            util_name = request.form.get('util_name', '')
            params = request.form.get('params', '')
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
            if params:
                cmd += shlex.split(params)
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
            args = shlex.split(params)
            for arg in args:
                if arg.endswith('.csv') and (not uploaded or arg != uploaded):
                    path = os.path.abspath(arg)
                    if os.path.exists(path):
                        download_name = path
                        break
        else:
            workflow = request.form.get('workflow', '')
            action = request.form.get('action')
            if action in {'build', 'preview'}:
                preview = workflow
            elif action == 'run':
                flash(f"Running workflow: {workflow}")
    return render_template(
        'index.html',
        workflow=workflow,
        preview=preview,
        utils=utils_list,
        util_output=util_output,
        download_name=download_name,
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


@app.route('/download/<path:filename>')
def download_file(filename: str):
    """Send a file from the temporary directory."""
    return send_from_directory(tempfile.gettempdir(), os.path.basename(filename), as_attachment=True)
