"""OpenRouter client with bounded retries, model fallback, and JSON mode."""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from typing import Any

import requests
from tenacity import Retrying, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.config import settings

logger = logging.getLogger(__name__)


class LLMClientException(Exception):
    """Error raised when model generation cannot complete."""


class _TransientLLMError(LLMClientException):
    """Retryable rate-limit, server, timeout, or empty-response error."""


class _JsonModeUnsupported(LLMClientException):
    """Signal that the selected model does not accept a JSON response format."""


class BaseLLMClient(ABC):
    @abstractmethod
    def generate(
        self,
        prompt: str,
        max_tokens: int = 3000,
        system_prompt: str | None = None,
        json_mode: bool = False,
    ) -> str:
        """Generate text from a prompt."""


class OpenRouterLLMClient(BaseLLMClient):
    """OpenRouter client with capped calls and configurable model fallbacks."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        timeout: int = 75,
        max_retries: int = 2,
        fallback_models: list[str] | None = None,
        max_calls: int = 8,
    ) -> None:
        self.api_key = api_key if api_key is not None else settings.OPENROUTER_API_KEY
        self.model = model if model is not None else settings.OPENROUTER_MODEL
        self.base_url = (base_url or settings.OPENROUTER_BASE_URL).rstrip("/")
        self.timeout = timeout
        self.max_retries = max(0, max_retries)
        configured = fallback_models
        if configured is None:
            configured = [
                candidate.strip()
                for candidate in settings.OPENROUTER_FALLBACK_MODELS.split(",")
                if candidate.strip()
            ]
        self.models = list(dict.fromkeys([self.model, *configured]))
        self.max_calls = max_calls
        self.requests_made = 0

    def _request(
        self,
        model: str,
        prompt: str,
        max_tokens: int,
        system_prompt: str | None,
        json_mode: bool,
    ) -> str:
        """Make one OpenRouter request and classify retryable failures."""
        if self.requests_made >= self.max_calls:
            raise LLMClientException("OpenRouter request budget exhausted.")
        self.requests_made += 1
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": 0.2,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key.strip()}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "http://localhost:5173",
                    "X-Title": "GitHub Repo Profiler",
                },
                json=payload,
                timeout=self.timeout,
            )
        except (requests.Timeout, requests.ConnectionError) as exc:
            raise _TransientLLMError(f"OpenRouter request failed ({type(exc).__name__}).") from exc
        if response.status_code in {408, 429} or response.status_code >= 500:
            raise _TransientLLMError(f"OpenRouter temporary error ({response.status_code}).")
        if json_mode and response.status_code in {400, 422}:
            raise _JsonModeUnsupported("The selected model does not support JSON response mode.")
        if response.status_code >= 400:
            raise LLMClientException(f"OpenRouter rejected the request ({response.status_code}).")
        try:
            data = response.json()
            choices = data.get("choices", [])
            content = choices[0].get("message", {}).get("content", "") if choices else ""
            if isinstance(content, list):
                content = "".join(
                    part.get("text", "") for part in content if isinstance(part, dict)
                )
            text = str(content or "").strip()
        except (ValueError, TypeError, IndexError, AttributeError) as exc:
            raise _TransientLLMError("OpenRouter returned an invalid response.") from exc
        if not text:
            raise _TransientLLMError("OpenRouter returned an empty response.")
        return text

    def _retrying_request(
        self,
        model: str,
        prompt: str,
        max_tokens: int,
        system_prompt: str | None,
        json_mode: bool,
    ) -> str:
        """Retry transient failures with tenacity exponential backoff."""
        retrying = Retrying(
            retry=retry_if_exception_type(_TransientLLMError),
            stop=stop_after_attempt(self.max_retries + 1),
            wait=wait_exponential(multiplier=1, min=1, max=8),
            reraise=True,
        )
        return retrying(
            self._request,
            model,
            prompt,
            max_tokens,
            system_prompt,
            json_mode,
        )

    def generate(
        self,
        prompt: str,
        max_tokens: int = 3000,
        system_prompt: str | None = None,
        json_mode: bool = False,
    ) -> str:
        if not self.api_key or not self.api_key.strip():
            raise LLMClientException("OPENROUTER_API_KEY is not configured.")
        last_error: Exception | None = None
        for model in self.models:
            try:
                try:
                    return self._retrying_request(
                        model, prompt, max_tokens, system_prompt, json_mode
                    )
                except _JsonModeUnsupported:
                    return self._retrying_request(
                        model, prompt, max_tokens, system_prompt, False
                    )
            except LLMClientException as exc:
                last_error = exc
                logger.warning("OpenRouter model %s failed (%s).", model, type(exc).__name__)
                if self.requests_made >= self.max_calls:
                    break
        raise LLMClientException(
            f"All configured OpenRouter models failed ({type(last_error).__name__ if last_error else 'unknown error'})."
        ) from last_error


class MockLLMClient(BaseLLMClient):
    """Deterministic mock which retains the legacy report behavior."""

    def __init__(self, should_fail: bool = False, error_message: str = "Mock LLM failure") -> None:
        self.should_fail = should_fail
        self.error_message = error_message

    def generate(
        self,
        prompt: str,
        max_tokens: int = 1500,
        system_prompt: str | None = None,
        json_mode: bool = False,
    ) -> str:
        if self.should_fail:
            raise LLMClientException(self.error_message)
        if json_mode:
            return json.dumps({
                "headline": "Static evidence identifies review priorities.",
                "health": {"rating": "Watch", "rationale": "Only static repository metrics were provided."},
                "purpose": "The repository contains source code evaluated by static analysis.",
                "architecture": {
                    "summary": "Architecture findings are limited to the supplied dependency graph.",
                    "strengths": [],
                    "concerns": [],
                },
                "key_insights": [],
                "risks": [],
                "recommendations": [],
                "quick_wins": [],
                "roadmap": {"days_30": [], "days_60": [], "days_90": []},
                "testing_focus": [],
                "limitations": ["Static analysis does not measure runtime behavior or test coverage."],
            })
        return (
            "## 1. What This Codebase Does\n"
            "Static analysis summarizes source structure, complexity, and repository history.\n\n"
            "## 2. Architectural Strengths\n"
            "- Quantitative analysis is available for the supplied source files.\n\n"
            "## 3. Top Risk Areas\n"
            "- Review the ranked hotspots before high-impact changes.\n\n"
            "## 4. Refactoring Suggestions\n"
            "- Use measured complexity and change history to prioritize review."
        )


def get_llm_client() -> BaseLLMClient:
    """Instantiate the configured model provider."""
    if settings.LLM_PROVIDER.lower() == "mock":
        return MockLLMClient()
    return OpenRouterLLMClient()
