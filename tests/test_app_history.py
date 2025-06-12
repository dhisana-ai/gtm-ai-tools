import os
import sys
import types
import datetime

# Record any existing flask module to restore later
_original_flask = sys.modules.get('flask')

# Provide minimal python-dotenv stub if missing
if 'dotenv' not in sys.modules:
    dotenv = types.ModuleType('dotenv')
    dotenv.dotenv_values = lambda *a, **kw: {}
    dotenv.set_key = lambda *a, **kw: None
    sys.modules['dotenv'] = dotenv

# Provide minimal flask stub for testing history view
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

# Stub session object
session = {}

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
flask.session = session
sys.modules['flask'] = flask
# Ensure app is re-imported under the stubbed flask module
sys.modules.pop('app', None)
from app import history
from utils import common


def test_history(monkeypatch, tmp_path):
    d = tmp_path
    f1 = d / 'a.csv'
    f2 = d / 'b.csv'
    f1.write_text('a')
    f2.write_text('b')
    old = (datetime.datetime.now() - datetime.timedelta(seconds=10)).timestamp()
    os.utime(f1, (old, old))
    monkeypatch.setattr(common, 'get_output_dir', lambda: d)
    ctx = history()
    files = [item['name'] for item in ctx['csv_files']]
    assert files == ['b.csv', 'a.csv']

# Restore real flask module so stub does not leak to other tests
if _original_flask is not None:
    sys.modules['flask'] = _original_flask
else:
    sys.modules.pop('flask', None)
    import importlib
    sys.modules['flask'] = importlib.import_module('flask')
# Remove stub-loaded app module so it will be re-imported under real flask
sys.modules.pop('app', None)
