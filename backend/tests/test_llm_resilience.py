# backend/tests/test_llm_resilience.py
import pytest

from app.services.llm import LLMClientException, MockLLMClient


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
