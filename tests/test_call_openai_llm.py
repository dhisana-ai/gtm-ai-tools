import sys
from types import SimpleNamespace
from utils import openai_sample as mod

class DummyClient:
    def __init__(self, api_key=None):
        self.responses = SimpleNamespace(create=lambda **kw: SimpleNamespace(output_text="hi"))

def test_openai_main(monkeypatch, capsys):
    monkeypatch.setattr(mod, "OpenAI", lambda api_key=None: DummyClient())
    monkeypatch.setenv("OPENAI_API_KEY", "x")
    monkeypatch.setattr(sys, "argv", ["openai_sample.py", "hello"])
    mod.main()
    captured = capsys.readouterr()
    assert "hi" in captured.out

