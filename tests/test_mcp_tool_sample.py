import sys
from types import SimpleNamespace
from utils import mcp_tool_sample as mod

class DummyClient:
    def __init__(self):
        self.kwargs = None
        self.responses = SimpleNamespace(create=self.create)

    def create(self, **kwargs):
        self.kwargs = kwargs
        return SimpleNamespace(output_text="hello")


def test_mcp_main(monkeypatch, capsys):
    dummy = DummyClient()
    monkeypatch.setattr(mod, "OpenAI", lambda api_key=None: dummy)
    monkeypatch.setenv("OPENAI_API_KEY", "x")
    monkeypatch.setenv("MCP_SERVER_LABEL", "label")
    monkeypatch.setenv("MCP_SERVER_URL", "http://mcp")
    monkeypatch.setenv("MCP_API_KEY_HEADER_NAME", "X-Key")
    monkeypatch.setenv("MCP_API_KEY_HEADER_VALUE", "val")
    monkeypatch.setattr(sys, "argv", ["mcp_tool_sample.py", "hi"])

    mod.main()

    captured = capsys.readouterr()
    assert "hello" in captured.out
    tool = dummy.kwargs["tools"][0]
    assert tool["server_label"] == "label"
    assert tool["server_url"] == "http://mcp"
    assert tool["headers"]["X-Key"] == "val"
