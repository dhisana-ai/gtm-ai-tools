import os
import numpy as np
import types

import pytest

from app import embed_text, UTILITY_INDEX, UTILITY_CODES, get_top_k_utilities


def test_embed_text(monkeypatch):
    # Stub OpenAI embeddings response
    dummy_vector = [0.1, 0.2, 0.3]
    class DummyClient:
        def __init__(self, api_key=None):
            self.embeddings = types.SimpleNamespace(
                create=lambda input, model: types.SimpleNamespace(
                    data=[types.SimpleNamespace(embedding=dummy_vector)]
                )
            )

    monkeypatch.setenv("OPENAI_API_KEY", "test_key")
    monkeypatch.setattr("app.openai.OpenAI", lambda api_key=None: DummyClient(api_key))

    arr = embed_text("dummy text")
    assert isinstance(arr, np.ndarray)
    assert arr.tolist() == dummy_vector


def test_get_top_k_utilities(monkeypatch):
    # Prepare a fake FAISS index and codes list for two dummy utilities
    UTILITY_CODES.clear()
    UTILITY_CODES.extend(["code A", "code B"])
    class DummyIndex:
        def search(self, query, k):
            # Return top k indices [0..k-1] with dummy scores
            import numpy as _np
            return _np.ones((1, k)), _np.arange(k).reshape(1, k)
    # Override the index and embed_text to control results
    monkeypatch.setattr("app.UTILITY_INDEX", DummyIndex())
    monkeypatch.setattr("app.embed_text", lambda prompt: np.array([1.0, 0.0], dtype=np.float32))

    top = get_top_k_utilities("prompt", k=2)
    assert top == ["code A", "code B"]

    # If k=1, only the first code is returned
    top1 = get_top_k_utilities("prompt", k=1)
    assert top1 == ["code A"]