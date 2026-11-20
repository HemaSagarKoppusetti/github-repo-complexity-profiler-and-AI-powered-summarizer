# backend/tests/test_llm_resilience.py
import pytest

from app.services.llm import LLMClientException, MockLLMClient, OpenRouterLLMClient


def test_mock_llm_success():
    client = MockLLMClient(should_fail=False)
    reply = client.generate("test prompt")
    assert "## 1. What This Codebase Does" in reply
    assert "## 2. Architectural Strengths" in reply
    assert "## 3. Top Risk Areas" in reply
    assert "## 4. Refactoring Suggestions" in reply


def test_mock_llm_failure():
    client = MockLLMClient(should_fail=True, error_message="Rate limit 429")
    with pytest.raises(LLMClientException) as excinfo:
        client.generate("test prompt")
    assert "Rate limit 429" in str(excinfo.value)


def test_openrouter_retries_temporary_failures(monkeypatch):
    class Response:
        def __init__(self, status_code, content="ok"):
            self.status_code = status_code
            self.content = content

        def json(self):
            return {"choices": [{"message": {"content": self.content}}]}

    responses = [Response(429), Response(200, '{"headline":"ok"}')]
    calls = []

    def post(*args, **kwargs):
        calls.append(kwargs["json"])
        return responses.pop(0)

    monkeypatch.setattr("app.services.llm.requests.post", post)
    monkeypatch.setattr("app.services.llm.wait_exponential", lambda **kwargs: __import__("tenacity").wait_none())
    client = OpenRouterLLMClient(api_key="test-key", model="primary", max_retries=1)

    assert client.generate("prompt", json_mode=True) == '{"headline":"ok"}'
    assert len(calls) == 2
    assert calls[0]["response_format"] == {"type": "json_object"}


def test_openrouter_falls_back_to_an_alternate_model(monkeypatch):
    class Response:
        def __init__(self, status_code, content="ok"):
            self.status_code = status_code
            self.content = content

        def json(self):
            return {"choices": [{"message": {"content": self.content}}]}

    responses = [Response(400), Response(200, "fallback")]
    calls = []

    def post(url, **kwargs):
        calls.append(kwargs["json"]["model"])
        return responses.pop(0)

    monkeypatch.setattr("app.services.llm.requests.post", post)
    client = OpenRouterLLMClient(
        api_key="test-key",
        model="primary",
        fallback_models=["secondary"],
        max_retries=0,
    )

    assert client.generate("prompt") == "fallback"
    assert calls == ["primary", "secondary"]
