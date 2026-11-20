# backend/app/api/health.py
"""Health check and configuration inspection endpoint."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.config import settings

router = APIRouter(tags=["Health"])


class LLMHealth(BaseModel):
    provider: str
    model: str
    configured: bool


class HealthResponse(BaseModel):
    status: str
    version: str
    environment: str
    llm: LLMHealth


@router.get("/health", response_model=HealthResponse)
def get_health() -> HealthResponse:
    """Returns application status and checks whether the LLM API key is configured."""
    has_key = bool(settings.OPENROUTER_API_KEY and settings.OPENROUTER_API_KEY.strip())
    # If mock provider, it is always considered configured
    is_configured = has_key or settings.LLM_PROVIDER.lower() == "mock"

    return HealthResponse(
        status="healthy",
        version="1.0.0",
        environment=settings.ENVIRONMENT,
        llm=LLMHealth(
            provider=settings.LLM_PROVIDER,
            model=settings.OPENROUTER_MODEL,
            configured=is_configured,
        ),
    )
