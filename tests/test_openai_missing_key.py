import asyncio
import pytest
from utils import extract_from_webpage as mod

def test_missing_openai_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(RuntimeError):
        asyncio.run(mod._get_structured_data_internal("prompt", mod.Lead))
