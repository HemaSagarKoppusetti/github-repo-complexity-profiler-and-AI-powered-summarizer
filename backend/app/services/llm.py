# backend/app/services/llm.py
"""LLM client interface and providers with retry and backoff."""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from typing import Any

import requests

from app.config import settings

logger = logging.getLogger(__name__)


class LLMClientException(Exception):
    """Custom exception raised when LLM generation fails."""


class BaseLLMClient(ABC):
    @abstractmethod
    def generate(self, prompt: str, max_tokens: int = 3000) -> str:
        """Generates text from the given prompt."""


class OpenRouterLLMClient(BaseLLMClient):
    """OpenRouter API client with retries and exponential backoff."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        timeout: int = 75,
        max_retries: int = 2,
    ) -> None:
        self.api_key = api_key if api_key is not None else settings.OPENROUTER_API_KEY
        self.model = model if model is not None else settings.OPENROUTER_MODEL
        self.base_url = (base_url or settings.OPENROUTER_BASE_URL).rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries

    def generate(self, prompt: str, max_tokens: int = 3000) -> str:
        if not self.api_key or not self.api_key.strip():
            raise LLMClientException(
                "OPENROUTER_API_KEY is not configured. Please provide an API key in .env"
            )

        headers = {
            "Authorization": f"Bearer {self.api_key.strip()}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost:5173",
            "X-Title": "GitHub Repo Profiler",
        }

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
        }

        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                logger.info(
                    "[llm] Calling OpenRouter (attempt %d/%d, model=%s)...",
                    attempt + 1,
                    self.max_retries + 1,
                    self.model,
                )
                response = requests.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=self.timeout,
                )

                if response.status_code == 429:
                    raise LLMClientException(
                        f"OpenRouter Rate Limited (429): {response.text}"
                    )

                if response.status_code >= 500:
                    raise LLMClientException(
                        f"OpenRouter Server Error ({response.status_code}): {response.text}"
                    )

                data = response.json()
                if "error" in data:
                    err = data["error"]
                    err_msg = err.get("message", str(err)) if isinstance(err, dict) else str(err)
                    raise LLMClientException(f"OpenRouter error: {err_msg}")

                choices = data.get("choices")
                if not choices:
                    raise LLMClientException("OpenRouter returned empty choices array")

                msg = choices[0].get("message", {})
                content = (msg.get("content") or "").strip()

                # Fallback for reasoning models that hit token limit in reasoning
                if not content and msg.get("reasoning"):
                    content = msg["reasoning"].strip()

                if not content:
                    raise LLMClientException("OpenRouter returned empty content and reasoning")

                logger.info("[llm] ✅ Successfully received %d chars from OpenRouter", len(content))
                return content

            except Exception as e:
                last_error = e
                logger.warning(
                    "[llm] Attempt %d failed: %s", attempt + 1, e
                )
                if attempt < self.max_retries:
                    backoff = 2 ** (attempt + 1)
                    logger.info("[llm] Retrying in %d seconds...", backoff)
                    time.sleep(backoff)

        raise LLMClientException(f"All LLM retries failed. Last error: {last_error}")


class MockLLMClient(BaseLLMClient):
    """Predictable mock client for unit and integration testing."""

    def __init__(self, should_fail: bool = False, error_message: str = "Mock LLM failure") -> None:
        self.should_fail = should_fail
        self.error_message = error_message

    def generate(self, prompt: str, max_tokens: int = 1500) -> str:
        if self.should_fail:
            raise LLMClientException(self.error_message)

        return (
            "## 1. What This Codebase Does\n"
            "This repository provides a specialized Python utility for efficient text and data transformations. "
            "Its module layout emphasizes clean encapsulation and minimal overhead.\n\n"
            "## 2. Architectural Strengths\n"
            "- Low coupling across foundational modules with no circular dependencies.\n"
            "- High test coverage and maintainability scores across primary components.\n\n"
            "## 3. Top Risk Areas\n"
            "- High churn and complexity in the core initialization module increase regression risk.\n"
            "- Multiple concurrent contributors to hotspot files could lead to merge conflicts.\n"
            "- Core dispatch routines require careful profiling before refactoring.\n\n"
            "## 4. Refactoring Suggestions\n"
            "- Modularize the primary entry point into smaller single-responsibility submodules.\n"
            "- Decompose functions with cyclomatic complexity exceeding 15.\n"
            "- Establish dedicated regression integration benchmarks."
        )


def get_llm_client() -> BaseLLMClient:
    """Factory that instantiates the configured LLM client."""
    provider = settings.LLM_PROVIDER.lower()
    if provider == "mock":
        return MockLLMClient()
    return OpenRouterLLMClient()
