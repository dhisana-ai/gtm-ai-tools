import os
import sys
import types
import datetime

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
