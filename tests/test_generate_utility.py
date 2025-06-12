import types

import pytest

from app import app


class DummyResponseSuccess:
    def __init__(self, **kwargs):
        self.output = [
            types.SimpleNamespace(
                content=[types.SimpleNamespace(text="print('hello world')")]
            )
        ]


class DummyClientSuccess:
    def __init__(self, api_key=None):
        pass

    @property
    def responses(self):
        return types.SimpleNamespace(create=lambda **kwargs: DummyResponseSuccess())


class DummyClientFailure:
    def __init__(self, api_key=None):
        pass

    @property
    def responses(self):
        return types.SimpleNamespace(create=lambda **kwargs: (_ for _ in ()).throw(RuntimeError("api error")))


@pytest.fixture(autouse=True)
def monkey_openai(monkeypatch):
    # Ensure OPENAI_API_KEY is set for the test
    monkeypatch.setenv("OPENAI_API_KEY", "test_key")
    yield


def test_generate_utility_success(monkeypatch):
    # Skip embedding lookup and stub openai.OpenAI to use our successful dummy client
    monkeypatch.setattr("app.get_top_k_utilities", lambda prompt, k: [])
    monkeypatch.setattr("app.openai.OpenAI", lambda api_key=None: DummyClientSuccess(api_key))

    client = app.test_client()
    response = client.post("/generate_utility", data={"prompt": "make code"})

    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert "print('hello world')" in data["code"]


def test_generate_utility_api_error(monkeypatch):
    # Skip embedding lookup and stub openai.OpenAI to raise an error
    monkeypatch.setattr("app.get_top_k_utilities", lambda prompt, k: [])
    monkeypatch.setattr("app.openai.OpenAI", lambda api_key=None: DummyClientFailure(api_key))

    client = app.test_client()
    response = client.post("/generate_utility", data={"prompt": "fail code"})

    assert response.status_code == 500
    data = response.get_json()
    assert data["success"] is False
    assert "api error" in data["error"]