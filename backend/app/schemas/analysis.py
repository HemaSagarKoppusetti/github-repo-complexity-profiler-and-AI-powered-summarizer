# backend/app/schemas/analysis.py
"""Pydantic v2 schemas for API requests, responses, and validation."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator

GITHUB_URL_PATTERN = re.compile(
    r"^https://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?/?$"
)


def validate_github_repo_url(url: str) -> str:
    """Strictly validates a GitHub repository URL.

    Only https://github.com/<owner>/<repo> allowed. Rejects shell characters,
    file://, ssh, non-github hosts.
    """
    clean_url = url.strip()
    if not clean_url:
        raise ValueError("GitHub URL cannot be empty")

    if any(ch in clean_url for ch in [";", "&", "|", "`", "$", "<", ">", "\n", "\r", " "]):
        raise ValueError("Invalid characters detected in URL")

    match = GITHUB_URL_PATTERN.match(clean_url)
    if not match:
        raise ValueError(
            "Invalid GitHub URL. Must be in format: https://github.com/<owner>/<repo>"
        )

    owner, repo = match.group(1), match.group(2)
    if not owner or not repo or owner == "." or repo == ".":
        raise ValueError("Owner and repository name must be non-empty")

    # Canonicalize URL without trailing slash or .git
    return f"https://github.com/{owner}/{repo}"


class AnalysisCreate(BaseModel):
    github_url: str = Field(
        ...,
        description="Public GitHub repository URL",
        examples=["https://github.com/pallets/markupsafe"],
    )
    top_n: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Number of hotspot files to compute in top ranking",
    )
    force: bool = Field(
        default=False,
        description="If True, bypasses 24-hour cache and re-analyzes",
    )

    @field_validator("github_url")
    @classmethod
    def check_github_url(cls, v: str) -> str:
        return validate_github_repo_url(v)


class AnalysisKeyMetrics(BaseModel):
    total_files: int = 0
    total_loc: int = 0
    total_commits: int = 0
    total_authors: int = 0
    repo_age_days: int = 0
    avg_mi_score: float = 0.0
    circular_deps: int = 0
    critical_hotspots: int = 0
    high_hotspots: int = 0


class AnalysisSummary(BaseModel):
    id: str
    github_url: str
    repo_name: str
    status: str
    stage: str | None = None
    percent: int = 0
    error: str | None = None
    report_status: str = "pending"
    created_at: datetime
    completed_at: datetime | None = None
    duration_seconds: float | None = None
    key_metrics: AnalysisKeyMetrics | None = None

    model_config = ConfigDict(from_attributes=True)


class AnalysisDetail(BaseModel):
    id: str
    github_url: str
    repo_name: str
    status: str
    stage: str | None = None
    percent: int = 0
    error: str | None = None
    report_status: str
    report_text: str | None = None
    created_at: datetime
    completed_at: datetime | None = None
    duration_seconds: float | None = None
    result: dict[str, Any] | None = None

    model_config = ConfigDict(from_attributes=True)


class AnalysisEvent(BaseModel):
    stage: str
    percent: int
    message: str
    status: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetail


T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    size: int
    pages: int
