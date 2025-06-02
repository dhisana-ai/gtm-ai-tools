import sys
from types import SimpleNamespace
from utils import call_openai_llm as mod

class DummyClient:
    def __init__(self, api_key=None):
        self.kwargs = None
        self.responses = SimpleNamespace(create=self.create)

    def create(self, **kwargs):
        self.kwargs = kwargs
        return SimpleNamespace(output_text="hi")

def test_openai_main(monkeypatch, capsys):
    monkeypatch.setattr(mod, "OpenAI", lambda api_key=None: DummyClient())
    monkeypatch.setenv("OPENAI_API_KEY", "x")
    monkeypatch.setattr(sys, "argv", ["call_openai_llm.py", "hello"])
    mod.main()
    captured = capsys.readouterr()
    assert "hi" in captured.out


def test_model_env(monkeypatch):
    dummy = DummyClient()
    monkeypatch.setattr(mod, "OpenAI", lambda api_key=None: dummy)
    monkeypatch.setenv("OPENAI_API_KEY", "x")
    monkeypatch.setenv("OPENAI_MODEL_NAME", "gpt-test")
    monkeypatch.setattr(sys, "argv", ["call_openai_llm.py", "hi"])
    mod.main()
    assert dummy.kwargs["model"] == "gpt-test"

