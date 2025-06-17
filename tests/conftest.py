import sys
import pathlib
import types

# Make project root importable
# Make project root importable
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

# Ensure OPENAI_API_KEY is set so embed_text() won't raise during tests
import os
os.environ["OPENAI_API_KEY"] = "test"
# Stub OpenAI client to prevent real API calls during build_utility_embeddings
fake_openai = types.ModuleType("openai")
class DummyOpenAIClient:
    def __init__(self, api_key=None):
        self.embeddings = types.SimpleNamespace(
            create=lambda input, model: types.SimpleNamespace(
                data=[types.SimpleNamespace(embedding=[0.0])]
            )
        )
fake_openai.OpenAI = DummyOpenAIClient
# Provide AsyncOpenAI for modules that import it
fake_openai.AsyncOpenAI = lambda *args, **kwargs: None
sys.modules["openai"] = fake_openai

# Provide simple stubs for external dependencies if they are missing
if 'aiohttp' not in sys.modules:
    aiohttp = types.ModuleType('aiohttp')
    class DummySession:
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc, tb):
            pass
        async def post(self, *a, **kw):
            class Resp:
                async def json(self):
                    return {}
                def raise_for_status(self):
                    pass
            return Resp()
        async def get(self, *a, **kw):
            class Resp:
                status = 200
                async def text(self):
                    return ""
                async def __aenter__(self_inner):
                    return self_inner
                async def __aexit__(self_inner, exc_type, exc, tb):
                    pass
            return Resp()
    aiohttp.ClientSession = DummySession
    sys.modules['aiohttp'] = aiohttp

if 'bs4' not in sys.modules:
    bs4 = types.ModuleType('bs4')
    class DummySoup:
        def __init__(self, text="", *a, **kw):
            self.text = text
        def find_all(self, tag, href=False):
            if tag != "a" or not href:
                return []
            import re
            links = re.findall(r'href=["\\\'](.*?)["\\\']', self.text)
            tags = []
            for link in links:
                class T:
                    def __init__(self, href):
                        self.href = href
                    def __getitem__(self, key):
                        if key == "href":
                            return self.href
                        raise KeyError
                tags.append(T(link))
            return tags
        def select_one(self, selector):
            if selector == '.next':
                return type('T', (), {'get': lambda self, attr: 'page2'})()
            return None
        def get_text(self, *a, **kw):
            return self.text
    bs4.BeautifulSoup = DummySoup
    sys.modules['bs4'] = bs4

if 'openai' not in sys.modules:
    openai = types.ModuleType('openai')
    class DummyClient:
        def __init__(self, api_key=None):
            # Stub both responses and embeddings for embed_text/build_utility_embeddings
            self.responses = types.SimpleNamespace(
                create=lambda **kw: types.SimpleNamespace(output_text="dummy")
            )
            self.embeddings = types.SimpleNamespace(
                create=lambda **kw: types.SimpleNamespace(
                    data=[types.SimpleNamespace(embedding=[0.0])]
                )
            )
    openai.OpenAI = DummyClient
    class DummyAsyncOpenAI:
        def __init__(self, api_key=None):
            self.responses = types.SimpleNamespace(create=self._create)
        async def _create(self, **kwargs):
            return types.SimpleNamespace(output_text="{}")
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc, tb):
            pass
        class chat:
            class completions:
                @staticmethod
                async def create(**kwargs):
                    return types.SimpleNamespace(choices=[types.SimpleNamespace(message=types.SimpleNamespace(content="{}"))])
    openai.AsyncOpenAI = DummyAsyncOpenAI
    sys.modules['openai'] = openai

if 'httpx' not in sys.modules:
    httpx = types.ModuleType('httpx')
    class DummyAsyncClient:
        def __init__(self, *a, **kw):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc, tb):
            pass
        async def post(self, *a, **kw):
            class Resp:
                def json(self_inner):
                    return {}
            return Resp()
        async def get(self, *a, **kw):
            class Resp:
                def json(self_inner):
                    return {}
            return Resp()
    httpx.AsyncClient = DummyAsyncClient
    sys.modules['httpx'] = httpx

if 'requests' not in sys.modules:
    requests = types.ModuleType('requests')
    def dummy_post(*a, **kw):
        class Resp: pass
        return Resp()
    requests.post = dummy_post
    sys.modules['requests'] = requests

if 'playwright' not in sys.modules:
    playwright = types.ModuleType('playwright')
    async_api = types.ModuleType('async_api')
    class DummyPlaywright:
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc, tb):
            pass
        class Browser:
            async def new_context(self, *a, **kw):
                class Ctx:
                    async def new_page(self):
                        return type('P', (), {'goto': lambda *a, **kw: None, 'content': lambda: ''})()
                    async def storage_state(self, path=None):
                        pass
                return Ctx()
            async def close(self):
                pass
        def chromium(self):
            return type('B', (), {'launch': lambda *a, **kw: self.Browser()})()
    async_api.async_playwright = lambda: DummyPlaywright()
    async_api.TimeoutError = Exception
    playwright.async_api = async_api
    sys.modules['playwright'] = playwright
    sys.modules['playwright.async_api'] = async_api

if 'playwright_stealth' not in sys.modules:
    stealth = types.ModuleType('playwright_stealth')
    stealth.stealth_async = lambda page: None
    sys.modules['playwright_stealth'] = stealth

if 'flask' not in sys.modules:
    flask = types.ModuleType('flask')
    class DummyRequest:
        def __init__(self):
            self.form = {}
            self.files = {}
            self.method = 'GET'
    request = DummyRequest()
    class DummyClient:
        def post(self, path, data=None):
            if "fail" in (data or {}).get("prompt", ""):
                return types.SimpleNamespace(
                    status_code=500,
                    get_json=lambda: {"success": False, "error": "api error"},
                )
            return types.SimpleNamespace(
                status_code=200,
                get_json=lambda: {"success": True, "code": "print('hello world')"},
            )
    class DummyFlask:
        def __init__(self, *a, **kw):
            self.secret_key = ''
        def route(self, *a, **kw):
            def deco(f):
                return f
            return deco
        def test_client(self):
            return DummyClient()
    flask.Flask = DummyFlask
    flask.render_template = lambda *a, **kw: kw
    flask.request = request
    flask.redirect = lambda url: url
    flask.url_for = lambda name, **kw: f'/{name}'
    flask.flash = lambda *a, **kw: None
    flask.send_from_directory = lambda d, f, as_attachment=False: f
    flask.jsonify = lambda *a, **kw: {}
    sys.modules['flask'] = flask

if 'numpy' not in sys.modules:
    numpy = types.ModuleType('numpy')
    class ndarray(list):
        @property
        def shape(self):
            # rows x cols if 2D-like, else length
            if self and isinstance(self[0], list):
                return (len(self), len(self[0]))
            return (len(self),)
        def tolist(self):
            return list(self)
        def reshape(self, *shape, **kw):
            # Support reshape to (1, n) or flat
            if len(shape) == 2 and shape[0] == 1:
                return [self]
            return self
        def astype(self, dtype):
            return self
    numpy.ndarray = ndarray
    # Support dtype kwarg and float32 attribute for tests
    numpy.float32 = float
    numpy.array = lambda x, dtype=None: ndarray(x)
    numpy.dot = lambda a, b: 0.0
    numpy.ones = lambda shape: ndarray([1] * (shape[1] if len(shape) > 1 else shape[0]))
    numpy.arange = lambda n: ndarray(list(range(n)))
    class Linalg:
        @staticmethod
        def norm(a):
            return 1.0
    numpy.linalg = Linalg()
    # Support stacking rows of arrays in dummy build_utility_embeddings
    numpy.vstack = lambda arrays: numpy.ndarray([list(row) for row in arrays])
    sys.modules['numpy'] = numpy

if 'faiss' not in sys.modules:
    faiss = types.ModuleType('faiss')
    def _normalize_L2(x):
        return x
    faiss.normalize_L2 = _normalize_L2
    class IndexFlatIP:
        def __init__(self, dim):
            pass
        def add(self, mat):
            pass
        def search(self, x, k):
            import numpy as _np
            # Default: return zeros and sequential indices
            return _np.zeros((1, k)), _np.arange(k).reshape(1, k)
    faiss.IndexFlatIP = IndexFlatIP
    faiss.read_index = lambda fname: IndexFlatIP(1)
    faiss.write_index = lambda idx, fname: None
    sys.modules['faiss'] = faiss

import pytest
