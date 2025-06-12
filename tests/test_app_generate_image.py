# --- imports ---
import os
import sys
import types
import base64
import subprocess
import tempfile

# Record any existing flask module to restore later
_original_flask = sys.modules.get('flask')

# Provide minimal python-dotenv stub if missing
if 'dotenv' not in sys.modules:
    dotenv = types.ModuleType('dotenv')
    dotenv.dotenv_values = lambda *a, **kw: {}
    dotenv.set_key = lambda *a, **kw: None
    sys.modules['dotenv'] = dotenv

# Provide minimal flask stub if not installed, and restore original after app import
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

    def jsonify(*args, **kwargs):
        # Return a dict for testing purposes
        if args and not kwargs:
            return args[0] if len(args) == 1 else list(args)
        return kwargs

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
    flask.jsonify = jsonify
    sys.modules['flask'] = flask


# Override openai.OpenAI in pytest conftest stub for build_utility_embeddings
class DummyEmbeddings:
    def create(self, **kwargs):
        class DummyData:
            def __init__(self):
                self.data = [type('obj', (object,), {'embedding': [0.0] * 1536})()]
        return DummyData()

class DummyClient:
    def __init__(self, api_key=None):
        self.embeddings = DummyEmbeddings()

# Use pytest conftest stub, overriding only OpenAI for this test
_openai = sys.modules.get('openai')
if _openai is None:
    import openai as _openai
_openai.OpenAI = lambda api_key=None: DummyClient(api_key)

# --- third-party & application imports ---
from flask import request as flask_request
from app import run_utility


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

# Restore real flask module so stub does not leak to other tests
if _original_flask is not None:
    sys.modules['flask'] = _original_flask
else:
    sys.modules.pop('flask', None)
    # Re-import real Flask package
    import importlib
    sys.modules['flask'] = importlib.import_module('flask')
# Remove stub-loaded app module so it will be re-imported under real flask
sys.modules.pop('app', None)
