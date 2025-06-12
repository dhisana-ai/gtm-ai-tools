import sys
from types import SimpleNamespace
from utils import generate_image as mod


class DummyImages:
    def __init__(self):
        self.edit_args = None

    def generate(self, **kwargs):
        raise AssertionError("images.generate should not be called")

    def edit(self, **kwargs):
        self.edit_args = kwargs
        return SimpleNamespace(data=[SimpleNamespace(b64_json="img")])


class DummyResponses:
    def __init__(self):
        self.create_args = None

    def create(self, **kwargs):
        self.create_args = kwargs
        return SimpleNamespace(
            output=[
                SimpleNamespace(
                    type="image_generation_call",
                    result="img",
                )
            ]
        )


class DummyClient:
    def __init__(self):
        self.images = DummyImages()
        self.responses = DummyResponses()


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
    assert dummy.responses.create_args["input"] == "hello"


def test_edit(monkeypatch, capsys):
    dummy = DummyClient()
    monkeypatch.setattr(mod, "OpenAI", lambda api_key=None: dummy)
    monkeypatch.setattr(mod.request, "urlopen", dummy_urlopen)
    monkeypatch.setenv("OPENAI_API_KEY", "x")
    monkeypatch.setattr(sys, "argv", ["generate_image.py", "hi", "--image-url", "http://e.com/a.png"])
    mod.main()
    captured = capsys.readouterr()
    assert "img" in captured.out
    inp = dummy.responses.create_args["input"]
    assert inp[0]["content"][0]["text"] == "hi"
    assert dummy.images.edit_args is None
    assert dummy_urlopen.called == "http://e.com/a.png"
