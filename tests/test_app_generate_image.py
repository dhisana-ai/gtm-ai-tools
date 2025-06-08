import os
import sys
import types
import base64
import subprocess
import tempfile

# Provide minimal python-dotenv stub if missing
if 'dotenv' not in sys.modules:
    dotenv = types.ModuleType('dotenv')
    dotenv.dotenv_values = lambda *a, **kw: {}
    dotenv.set_key = lambda *a, **kw: None
    sys.modules['dotenv'] = dotenv

# Provide minimal flask stub if not installed
if 'flask' not in sys.modules:
    flask = types.ModuleType('flask')

    class DummyRequest:
        def __init__(self):
            self.form = {}
            self.files = {}
            self.method = 'GET'

    request = DummyRequest()

    def render_template(name, **ctx):
        render_template.context = ctx
        return ctx

    def redirect(url):
        return url

    def url_for(name, **kw):
        return f'/{name}'

    def flash(msg):
        pass

    def send_from_directory(directory, filename, as_attachment=False):
        return os.path.join(directory, filename)

    class DummyFlask:
        def __init__(self, *a, **kw):
            pass
        def route(self, *a, **kw):
            def decorator(f):
                return f
            return decorator

    flask.Flask = DummyFlask
    flask.render_template = render_template
    flask.request = request
    flask.redirect = redirect
    flask.url_for = url_for
    flask.flash = flash
    flask.send_from_directory = send_from_directory
    sys.modules['flask'] = flask

from app import run_utility
from flask import request as flask_request


def test_generate_image_route(monkeypatch):
    b64_data = base64.b64encode(b'img').decode()

    def dummy_run(cmd, capture_output=True, text=True, env=None):
        return types.SimpleNamespace(returncode=0, stdout=b64_data, stderr='')

    paths = []
    real_mkstemp = tempfile.mkstemp

    def dummy_mkstemp(*a, **kw):
        fd, path = real_mkstemp(*a, **kw)
        paths.append(path)
        return fd, path

    monkeypatch.setattr(subprocess, 'run', dummy_run)
    monkeypatch.setattr(tempfile, 'mkstemp', dummy_mkstemp)

    flask_request.method = 'POST'
    flask_request.form = {'util_name': 'generate_image', 'prompt': 'hi'}
    flask_request.files = {}

    ctx = run_utility()
    assert ctx['image_src'].startswith('data:image/png;base64,')
    assert os.path.exists(ctx['download_name'])
