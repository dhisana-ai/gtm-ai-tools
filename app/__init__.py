import os
from flask import Flask, render_template, request, redirect, url_for, flash
from dotenv import dotenv_values, set_key

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", "dev")
ENV_FILE = os.path.join(os.path.dirname(__file__), "..", ".env")


def load_env():
    return dotenv_values(ENV_FILE)


@app.route('/', methods=['GET', 'POST'])
def index():
    preview = None
    workflow = ''
    if request.method == 'POST':
        workflow = request.form.get('workflow', '')
        action = request.form.get('action')
        if action in {'build', 'preview'}:
            preview = workflow
        elif action == 'run':
            flash(f"Running workflow: {workflow}")
    return render_template('index.html', workflow=workflow, preview=preview)


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
