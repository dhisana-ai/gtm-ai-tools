import types
from utils import send_slack_message as mod

class DummyReq:
    def __init__(self):
        self.calls = []
    def post(self, url, json=None, timeout=None):
        self.calls.append((url, json, timeout))
        class Resp: pass
        return Resp()

def test_send_with_env(monkeypatch):
    dummy = DummyReq()
    monkeypatch.setattr(mod, "requests", types.SimpleNamespace(post=dummy.post))
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "http://env-hook")
    mod.send_slack_message("hello")
    assert dummy.calls[0][0] == "http://env-hook"
    assert dummy.calls[0][1] == {"text": "hello"}


def test_skip_without_webhook(monkeypatch):
    dummy = DummyReq()
    monkeypatch.setattr(mod, "requests", types.SimpleNamespace(post=dummy.post))
    monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)
    mod.send_slack_message("hi")
    assert dummy.calls == []
