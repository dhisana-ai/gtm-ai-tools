import os
from utils import get_website_color as mod

def fake_capture_screenshot(url, output_path):
    with open(output_path, "wb") as f:
        f.write(b"fake image data")

def fake_analyze_colors_with_gpt(image_path):
    return "Primary: #FFFFFF, Secondary: #000000"

def test_analyze_colors_with_gpt(monkeypatch, tmp_path):
    class FakeChoice:
        def __init__(self, content):
            self.message = type("msg", (), {"content": content})
    class FakeResponse:
        choices = [FakeChoice("Primary: #FFFFFF, Secondary: #000000")]
    monkeypatch.setattr(mod.openai.chat.completions, "create", lambda *a, **kw: FakeResponse())

    fake_img = tmp_path / "website_screenshot.png"
    fake_img.write_bytes(b"fake")
    result = mod.analyze_colors_with_gpt(str(fake_img))
    assert "Primary" in result and "Secondary" in result

def test_capture_screenshot(monkeypatch):
    class DummyPage:
        def goto(self, *a, **k): self._goto_called = True
        def screenshot(self, path): self._screenshot_called = path
    class DummyBrowser:
        def __init__(self): self._closed = False
        def new_page(self): self.page = DummyPage(); return self.page
        def close(self): self._closed = True
    class DummyPlaywright:
        def __init__(self): self.chromium = self
        def launch(self, *a, **k): self.browser = DummyBrowser(); return self.browser

    monkeypatch.setattr(mod, "sync_playwright", lambda: type("mgr", (), {
        "__enter__": lambda s: DummyPlaywright(),
        "__exit__": lambda s, *a: None
    })())

    mod.capture_screenshot("http://example.com", "dummy.png")
    # If no exception, test passes

def test_main(monkeypatch, tmp_path):
    test_url = "http://example.com"
    img_path = tmp_path / "website_screenshot.png"
    monkeypatch.setattr(mod, "capture_screenshot", lambda url, path: img_path.write_bytes(b"data"))
    monkeypatch.setattr(mod, "analyze_colors_with_gpt", lambda path: "Primary: #FFF, Secondary: #000")
    monkeypatch.setattr(mod.argparse.ArgumentParser, "parse_args", lambda self: type("Args", (), {"url": test_url})())
    monkeypatch.setattr(mod, "print", lambda *a, **k: None)

    os.chdir(tmp_path)
    mod.main()
    assert not img_path.exists()