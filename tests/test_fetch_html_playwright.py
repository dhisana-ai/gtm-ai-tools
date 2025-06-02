import sys
from types import SimpleNamespace
from utils import fetch_html_playwright as mod

async def dummy_fetch(url, proxy_url=None, captcha_key=None):
    dummy_fetch.called = {
        "url": url,
        "proxy_url": proxy_url,
        "captcha_key": captcha_key,
    }
    return "<html>text</html>"

def test_main_returns_html(monkeypatch, capsys):
    monkeypatch.setenv("PROXY_URL", "http://proxy")
    monkeypatch.setenv("TWO_CAPTCHA_API_KEY", "k")
    monkeypatch.setattr(mod, "fetch_html", dummy_fetch)
    monkeypatch.setattr(sys, "argv", ["fetch_html_playwright.py", "http://e.com"])
    mod.main()
    captured = capsys.readouterr()
    assert "<html>text</html>" in captured.out
    assert dummy_fetch.called["proxy_url"] == "http://proxy"
    assert dummy_fetch.called["captcha_key"] == "k"

def test_main_with_summary(monkeypatch, capsys):
    monkeypatch.setenv("PROXY_URL", "http://proxy")
    monkeypatch.setenv("TWO_CAPTCHA_API_KEY", "k")
    monkeypatch.setenv("OPENAI_API_KEY", "x")
    monkeypatch.setattr(mod, "fetch_html", dummy_fetch)

    class DummyClient:
        def __init__(self):
            self.kwargs = None
            self.responses = SimpleNamespace(create=self.create)
        def create(self, **kwargs):
            self.kwargs = kwargs
            return SimpleNamespace(output_text="summary")

    dummy = DummyClient()
    monkeypatch.setattr(mod, "OpenAI", lambda api_key=None: dummy)
    monkeypatch.setattr(sys, "argv", [
        "fetch_html_playwright.py",
        "http://e.com",
        "--summarize",
        "--instructions",
        "Summ it",
    ])
    mod.main()
    captured = capsys.readouterr()
    assert "summary" in captured.out
    assert "Summ it" in dummy.kwargs["input"]


def test_model_env(monkeypatch):
    monkeypatch.setenv("PROXY_URL", "http://proxy")
    monkeypatch.setenv("TWO_CAPTCHA_API_KEY", "k")
    monkeypatch.setenv("OPENAI_API_KEY", "x")
    monkeypatch.setenv("OPENAI_MODEL_NAME", "gpt-test")
    monkeypatch.setattr(mod, "fetch_html", dummy_fetch)

    class DummyClient:
        def __init__(self):
            self.kwargs = None
            self.responses = SimpleNamespace(create=self.create)

        def create(self, **kwargs):
            self.kwargs = kwargs
            return SimpleNamespace(output_text="summary")

    dummy = DummyClient()
    monkeypatch.setattr(mod, "OpenAI", lambda api_key=None: dummy)
    monkeypatch.setattr(sys, "argv", [
        "fetch_html_playwright.py",
        "http://e.com",
        "--summarize",
    ])
    mod.main()
    assert dummy.kwargs["model"] == "gpt-test"

