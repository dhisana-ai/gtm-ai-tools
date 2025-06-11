import sys
import os
import pytest
from types import SimpleNamespace
from utils import get_website_color as mod

# Dummy async context manager for playwright_browser
class DummyAsyncContext:
    async def __aenter__(self):
        return self
    async def __aexit__(self, exc_type, exc, tb):
        pass
    async def new_page(self):
        return DummyPage()
    async def close(self):
        pass

class DummyPage:
    async def goto(self, url, wait_until=None, timeout=None):
        DummyPage.called_url = url
    async def screenshot(self, path=None, full_page=None):
        DummyPage.screenshot_path = path
        # Ensure directory exists before writing file
        import os
        os.makedirs(os.path.dirname(path), exist_ok=True)
        # Simulate file creation
        with open(path, "wb") as f:
            f.write(b"fake image data")
    async def close(self):
        pass

def dummy_analyze_colors_with_gpt(image_path):
    dummy_analyze_colors_with_gpt.called = image_path
    return "Primary: #123456, Secondary: #abcdef"

def test_main_prints_color_result(monkeypatch, capsys, tmp_path):
    test_url = "http://example.com"
    # Patch playwright_browser to use dummy async context
    monkeypatch.setattr(mod, "playwright_browser", lambda: DummyAsyncContext())
    monkeypatch.setattr(mod, "analyze_colors_with_gpt", dummy_analyze_colors_with_gpt)
    monkeypatch.setattr(sys, "argv", ["get_website_color.py", test_url])
    monkeypatch.setattr(mod.os.path, "exists", lambda p: True)
    monkeypatch.setattr(mod.os, "remove", lambda p: None)
    # Patch uuid to return a fixed value for deterministic filename
    monkeypatch.setattr(mod.uuid, "uuid4", lambda: "testuuid12345678")
    mod.main()
    captured = capsys.readouterr()
    assert "Color Analysis Result" in captured.out
    assert "#123456" in captured.out
    assert DummyPage.called_url == test_url
    assert dummy_analyze_colors_with_gpt.called.endswith("testuuid12_screenshot.png")

def test_main_prompts_for_url(monkeypatch, capsys, tmp_path):
    test_url = "http://input.com"
    monkeypatch.setattr(mod, "playwright_browser", lambda: DummyAsyncContext())
    monkeypatch.setattr(mod, "analyze_colors_with_gpt", dummy_analyze_colors_with_gpt)
    monkeypatch.setattr(sys, "argv", ["get_website_color.py"])  # No URL
    monkeypatch.setattr("builtins.input", lambda _: test_url)
    monkeypatch.setattr(mod.os.path, "exists", lambda p: True)
    monkeypatch.setattr(mod.os, "remove", lambda p: None)
    monkeypatch.setattr(mod.uuid, "uuid4", lambda: "testuuid12345678")
    mod.main()
    captured = capsys.readouterr()
    assert "Color Analysis Result" in captured.out
    assert "#123456" in captured.out
    assert DummyPage.called_url == test_url
    assert dummy_analyze_colors_with_gpt.called.endswith("testuuid12_screenshot.png")

def test_analyze_colors_with_gpt_reads_file(monkeypatch, tmp_path):
    image_path = tmp_path / "img.png"
    with open(image_path, "wb") as f:
        f.write(b"fake image data")
    # Create dummy openai.chat.completions.create structure
    class DummyCompletions:
        @staticmethod
        def create(**kwargs):
            class DummyResponse:
                class Choice:
                    class Message:
                        content = "Primary: Red, Secondary: Blue"
                    message = Message()
                choices = [Choice()]
            return DummyResponse()
    class DummyChat:
        completions = DummyCompletions()
    class DummyOpenAI:
        chat = DummyChat()
    monkeypatch.setattr(mod, "openai", DummyOpenAI())
    result = mod.analyze_colors_with_gpt(str(image_path))
    assert "Primary: Red" in result
