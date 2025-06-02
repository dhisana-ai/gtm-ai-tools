import sys
from types import SimpleNamespace
from utils import generate_image as mod


class DummyImages:
    def __init__(self):
        self.generate_args = None
        self.edit_args = None

    def generate(self, **kwargs):
        self.generate_args = kwargs
        return SimpleNamespace(data=[SimpleNamespace(b64_json="img")])

    def edit(self, **kwargs):
        self.edit_args = kwargs
        return SimpleNamespace(data=[SimpleNamespace(b64_json="img")])


class DummyClient:
    def __init__(self):
        self.images = DummyImages()


class DummyResp:
    def __init__(self, data: bytes):
        self._data = data
    def read(self) -> bytes:
        return self._data
    def __enter__(self):
        return self
    def __exit__(self, exc_type, exc, tb):
        pass

def dummy_urlopen(url):
    dummy_urlopen.called = url
    return DummyResp(b"content")


def test_generate(monkeypatch, capsys):
    dummy = DummyClient()
    monkeypatch.setattr(mod, "OpenAI", lambda api_key=None: dummy)
    monkeypatch.setenv("OPENAI_API_KEY", "x")
    monkeypatch.setattr(sys, "argv", ["generate_image.py", "hello"])
    mod.main()
    captured = capsys.readouterr()
    assert "img" in captured.out
    assert dummy.images.generate_args["prompt"] == "hello"


def test_edit(monkeypatch, capsys):
    dummy = DummyClient()
    monkeypatch.setattr(mod, "OpenAI", lambda api_key=None: dummy)
    monkeypatch.setattr(mod.request, "urlopen", dummy_urlopen)
    monkeypatch.setenv("OPENAI_API_KEY", "x")
    monkeypatch.setattr(sys, "argv", ["generate_image.py", "hi", "--image-url", "http://e.com/a.png"])
    mod.main()
    captured = capsys.readouterr()
    assert "img" in captured.out
    assert dummy.images.edit_args["prompt"] == "hi"
    assert dummy_urlopen.called == "http://e.com/a.png"
