import sys
import pathlib
import types

# Make project root importable
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

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
        def __init__(self, *a, **kw):
            pass
        def find_all(self, *a, **kw):
            return []
    bs4.BeautifulSoup = DummySoup
    sys.modules['bs4'] = bs4

if 'openai' not in sys.modules:
    openai = types.ModuleType('openai')
    class DummyClient:
        def __init__(self, api_key=None):
            self.responses = types.SimpleNamespace(create=lambda **kw: types.SimpleNamespace(output_text="dummy"))
    openai.OpenAI = DummyClient
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

import pytest
