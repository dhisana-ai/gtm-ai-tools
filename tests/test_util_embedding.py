import os
import numpy as np
import types

import pytest

from app import embed_text, UTILITY_EMBEDDINGS, get_top_k_utilities


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
    # Prepare two dummy utilities with known embeddings
    UTILITY_EMBEDDINGS.clear()
    UTILITY_EMBEDDINGS.extend([
        {"filename": "a.py", "code": "code A", "embedding": np.array([1.0, 0.0])},
        {"filename": "b.py", "code": "code B", "embedding": np.array([0.0, 1.0])},
    ])

    # Stub embed_text to return a vector closer to the first utility
    monkeypatch.setattr("app.embed_text", lambda prompt: np.array([1.0, 0.0]))

    top = get_top_k_utilities("prompt", k=2)
    assert top == ["code A", "code B"]

    # If k=1, only the closest utility is returned
    top1 = get_top_k_utilities("prompt", k=1)
    assert top1 == ["code A"]