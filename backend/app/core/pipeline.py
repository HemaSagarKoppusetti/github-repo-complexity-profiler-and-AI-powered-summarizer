"""Validated stage execution primitives for repository analysis."""

from __future__ import annotations

import logging
import re
import shutil
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)


class StageData(BaseModel):
    """Base schema for extensible stage dictionaries."""

    model_config = ConfigDict(extra="allow")


class ManifestData(StageData):
    files: list[dict[str, Any]] = Field(default_factory=list)
    total_files: int = 0
    total_loc: int = 0
    language_breakdown: dict[str, int] = Field(default_factory=dict)
    python_files: list[str] = Field(default_factory=list)


class ComplexityData(StageData):
    results: list[dict[str, Any]] = Field(default_factory=list)
    summary: dict[str, Any] = Field(default_factory=dict)


class GraphData(StageData):
    nodes: list[Any] = Field(default_factory=list)
    edges: list[Any] = Field(default_factory=list)
    cycles: list[list[str]] = Field(default_factory=list)
    stats: dict[str, Any] = Field(default_factory=dict)


class ChurnData(StageData):
    file_churn: dict[str, dict[str, Any]] = Field(default_factory=dict)
    most_churned: list[dict[str, Any]] = Field(default_factory=list)
    stats: dict[str, Any] = Field(default_factory=dict)


class HotspotsData(StageData):
    hotspots: list[dict[str, Any]] = Field(default_factory=list)
    top_hotspots: list[dict[str, Any]] = Field(default_factory=list)
    summary: dict[str, Any] = Field(default_factory=dict)


class ReportData(StageData):
    report_text: str | None = None
    report_json: dict[str, Any] | None = None


class CloneData(StageData):
    success: bool = False
    path: str | None = None
    name: str = "repository"
    url: str = ""
    error: str | None = None


@dataclass
class StageResult:
    """Outcome and quality details for one pipeline stage."""

    stage: str
    status: str
    data: Any
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    duration_s: float = 0.0
    items_processed: int = 0
    items_failed: int = 0

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-ready result record."""
        return asdict(self)


def redact_secrets(message: object) -> str:
    """Remove common credential assignments and configured API keys."""
    text = str(message)
    text = re.sub(
        r"(?i)\b(api[_-]?key|token|password|authorization)\b([=: ]+)([^,\s;]+)",
        r"\1\2[REDACTED]",
        text,
    )
    try:
        from app.config import settings

        if settings.OPENROUTER_API_KEY:
            text = text.replace(settings.OPENROUTER_API_KEY, "[REDACTED]")
    except Exception:
        pass
    return text[:2000]


def run_stage(
    name: str,
    fn: Callable[[], Any],
    timeout_s: float,
    fallback: Any,
    schema: type[StageData] | None = None,
) -> StageResult:
    """Run a stage with a timeout, output validation, and safe fallback data."""
    started = time.monotonic()
    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix=f"stage-{name}")
    future = executor.submit(fn)

    def safe_fallback() -> Any:
        value = fallback() if callable(fallback) else fallback
        if schema is not None:
            return schema.model_validate(value).model_dump()
        return value

    try:
        value = future.result(timeout=max(0.01, timeout_s))
        if schema is not None:
            value = schema.model_validate(value).model_dump()
        processed = len(value) if isinstance(value, (list, dict)) else 0
        return StageResult(
            stage=name,
            status="ok",
            data=value,
            duration_s=round(time.monotonic() - started, 3),
            items_processed=processed,
        )
    except TimeoutError:
        future.cancel()
        message = f"Stage exceeded its {timeout_s:g}s timeout."
        logger.warning("stage=%s status=failed error=%s", name, message)
        return StageResult(
            stage=name,
            status="failed",
            data=safe_fallback(),
            errors=[message],
            duration_s=round(time.monotonic() - started, 3),
        )
    except Exception as exc:
        message = redact_secrets(exc)
        logger.warning("stage=%s status=failed error=%s", name, message)
        return StageResult(
            stage=name,
            status="failed",
            data=safe_fallback(),
            errors=[message],
            duration_s=round(time.monotonic() - started, 3),
        )
    finally:
        executor.shutdown(wait=False, cancel_futures=True)


def preflight(
    github_url: str,
    minimum_free_mb: int = 100,
    llm_key: str | None = None,
) -> dict[str, Any]:
    """Check repository URL, Git availability, disk space, and optional AI config."""
    try:
        parsed = urlsplit(github_url)
        parts = [part for part in parsed.path.strip("/").split("/") if part]
        valid_url = (
            parsed.scheme == "https"
            and parsed.hostname == "github.com"
            and parsed.username is None
            and parsed.password is None
            and parsed.port is None
            and not parsed.query
            and not parsed.fragment
            and len(parts) == 2
            and all(bool(re.fullmatch(r"[A-Za-z0-9_.-]+", part)) for part in parts)
            and all(part not in {".", ".."} for part in parts)
            and parts[1] != ".git"
        )
    except (TypeError, ValueError):
        valid_url = False
    if not valid_url:
        return {
            "ok": False,
            "checks": {"url": False, "git": False, "disk": False, "llm": False},
            "warnings": [],
            "error": "Only https://github.com/<owner>/<repo> repository URLs are supported.",
        }

    git_available = shutil.which("git") is not None
    try:
        disk = shutil.disk_usage(Path(tempfile.gettempdir()))
        available_mb = int(disk.free / (1024 * 1024))
        disk_available = available_mb >= minimum_free_mb
    except OSError:
        available_mb = 0
        disk_available = False

    llm_available = bool((llm_key or "").strip())
    warnings = [] if llm_available else ["AI report skipped: OPENROUTER_API_KEY is not configured."]
    errors = []
    if not git_available:
        errors.append("Git is not installed or is not available on PATH.")
    if not disk_available:
        errors.append(f"Insufficient temporary disk space ({available_mb} MB available).")

    return {
        "ok": not errors,
        "checks": {
            "url": True,
            "git": git_available,
            "disk": disk_available,
            "llm": llm_available,
        },
        "available_disk_mb": available_mb,
        "warnings": warnings,
        "errors": errors,
    }
