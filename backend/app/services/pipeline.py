"""Fault-tolerant repository analysis pipeline with progress and persistence."""

from __future__ import annotations

import logging
import threading
import time
from datetime import UTC, datetime
from typing import Any

from app.config import settings
from app.core.churn import analyse_churn
from app.core.cloner import cleanup_repo, clone_repo, parse_repo_name
from app.core.complexity import analyse_all
from app.core.graph import build_dependency_graph
from app.core.hotspots import compute_hotspots
from app.core.pipeline import (
    ChurnData,
    CloneData,
    ComplexityData,
    GraphData,
    HotspotsData,
    ManifestData,
    ReportData,
    StageData,
    StageResult,
    redact_secrets,
    run_stage,
)
from app.core.pipeline import preflight as run_preflight
from app.core.scanner import scan_repo
from app.core.summariser import (
    build_evidence_pack,
    build_fallback_report,
    generate_structured_report,
    render_report_markdown,
)
from app.db.database import SessionLocal
from app.db.models import Analysis
from app.services.events import event_broadcaster
from app.services.llm import get_llm_client

logger = logging.getLogger(__name__)
_concurrency_semaphore = threading.Semaphore(settings.MAX_CONCURRENT_JOBS)


def _log(run_id: str, message: str, level: str = "info") -> None:
    """Write a structured, run-correlated pipeline log record."""
    formatted = "run_id=%s event=%s" % (run_id, message.replace("\n", " "))
    if level == "error":
        logger.error(formatted)
    elif level == "warning":
        logger.warning(formatted)
    else:
        logger.info(formatted)


def update_job_progress(
    job_id: str,
    stage: str,
    percent: int,
    message: str,
    status: str = "running",
    error: str | None = None,
) -> None:
    """Update persisted job status and broadcast an SSE progress event."""
    db = SessionLocal()
    try:
        job = db.query(Analysis).filter(Analysis.id == job_id).first()
        if job:
            job.stage = stage
            job.percent = percent
            job.status = status
            if error:
                job.error = redact_secrets(error)
            db.commit()
    except Exception as exc:
        logger.warning("run_id=%s event=progress_db_update_failed error=%s", job_id, type(exc).__name__)
    finally:
        db.close()
    try:
        event_broadcaster.publish_sync(
            analysis_id=job_id,
            stage=stage,
            percent=percent,
            message=message,
            status=status,
            extra={"error": redact_secrets(error)} if error else None,
        )
    except Exception as exc:
        logger.warning("run_id=%s event=progress_broadcast_failed error=%s", job_id, type(exc).__name__)


def _empty_complexity() -> dict[str, Any]:
    return {
        "results": [],
        "summary": {
            "total_files_analysed": 0,
            "total_python_files_analysed": 0,
            "total_functions": 0,
            "avg_mi_score": 0.0,
            "low_mi_file_count": 0,
            "rank_distribution": {rank: 0 for rank in "ABCDEF"},
            "top_complex_functions": [],
            "least_maintainable": [],
        },
    }


def _empty_graph() -> dict[str, Any]:
    return {
        "nodes": [],
        "edges": [],
        "cycles": [],
        "cycle_components": [],
        "hub_modules": [],
        "module_metrics": [],
        "isolated_modules": [],
        "external_packages": [],
        "stats": {
            "node_count": 0,
            "edge_count": 0,
            "density": 0.0,
            "cycle_count": 0,
            "cycle_components": 0,
            "has_cycles": False,
            "external_deps": 0,
        },
        "graph_elements": {"nodes": [], "edges": []},
    }


def _empty_churn() -> dict[str, Any]:
    return {
        "file_churn": {},
        "most_churned": [],
        "temporal_coupling": [],
        "renames": [],
        "warnings": [],
        "stats": {
            "total_commits": 0,
            "total_authors": 0,
            "repo_age_days": 0,
            "first_commit": "N/A",
            "last_commit": "N/A",
            "history_truncated": False,
            "analysed_window": "No history available",
        },
    }


def _empty_hotspots() -> dict[str, Any]:
    return {
        "hotspots": [],
        "top_hotspots": [],
        "summary": {
            "total_files_scored": 0,
            "critical_count": 0,
            "high_count": 0,
            "medium_count": 0,
            "low_count": 0,
            "top_hotspot": None,
            "top_hotspot_fn": None,
            "critical_files": [],
        },
    }


def _save_structured_failure(
    job_id: str,
    repo_name: str,
    message: str,
    diagnostics: list[dict[str, Any]],
    stages: list[dict[str, Any]],
    github_url: str,
) -> None:
    """Persist a structured failure without exposing traceback or credentials."""
    db = SessionLocal()
    try:
        job = db.query(Analysis).filter(Analysis.id == job_id).first()
        if job:
            job.repo_name = repo_name
            job.status = "failed"
            job.stage = "failed"
            job.percent = 100
            job.error = redact_secrets(message)
            job.completed_at = datetime.now(UTC)
            job.set_result({
                "repo_name": repo_name,
                "github_url": github_url,
                "error": {"code": "ANALYSIS_FAILED", "message": redact_secrets(message)},
                "diagnostics": diagnostics,
                "stages": stages,
            })
            db.commit()
    finally:
        db.close()


def _stage(
    run_id: str,
    name: str,
    fn: Any,
    timeout_s: float,
    fallback: Any,
    schema: type[StageData],
    stages: list[dict[str, Any]],
    diagnostics: list[dict[str, Any]],
) -> dict[str, Any]:
    """Execute, validate, and record a pipeline stage."""
    result = run_stage(name, fn, timeout_s, fallback, schema)
    data = result.data
    if result.status == "failed":
        for error in result.errors:
            diagnostics.append({
                "stage": name,
                "file": "",
                "severity": "error",
                "message": error,
            })
    if isinstance(data, dict):
        for diagnostic in data.get("diagnostics", []):
            if isinstance(diagnostic, dict):
                diagnostics.append(diagnostic)
    if name == "scan":
        result.items_processed = int(data.get("total_files", 0))
        result.items_failed = int(data.get("analysis_errors", 0))
    elif name == "complexity":
        result.items_processed = len(data.get("results", []))
        result.items_failed = sum(item.get("error") is not None for item in data.get("results", []))
    elif name == "graph":
        result.items_processed = int(data.get("stats", {}).get("node_count", 0))
    elif name == "churn":
        result.items_processed = int(data.get("stats", {}).get("total_commits", 0))
    elif name == "hotspots":
        result.items_processed = len(data.get("hotspots", []))
    if result.status == "ok" and (result.items_failed or result.errors):
        result.status = "partial"
    stages.append(result.as_dict())
    _log(run_id, f"stage={name} status={result.status} duration_s={result.duration_s:.3f}")
    return data


def run_analysis(job_id: str, github_url: str, top_n: int = 10) -> None:
    """Run all stages with validated fallbacks and persist quality diagnostics."""
    acquired = _concurrency_semaphore.acquire(blocking=True, timeout=120)
    repo_name = parse_repo_name(github_url)
    if not acquired:
        _save_structured_failure(
            job_id,
            repo_name,
            "Concurrency limit reached; retry the analysis later.",
            [{"stage": "queue", "file": "", "severity": "error", "message": "Concurrency limit reached."}],
            [],
            github_url,
        )
        return

    started = time.monotonic()
    repo_path: str | None = None
    diagnostics: list[dict[str, Any]] = []
    stages: list[dict[str, Any]] = []
    report_text: str | None = None
    report_json: dict[str, Any] | None = None
    report_status = "pending"
    try:
        try:
            update_job_progress(job_id, "starting", 2, f"Starting analysis for {repo_name}...")
        except Exception as exc:
            diagnostics.append({
                "stage": "progress", "file": "", "severity": "warning",
                "message": f"Progress notification failed ({type(exc).__name__}).",
            })

        llm_key = settings.OPENROUTER_API_KEY
        if settings.LLM_PROVIDER.lower() == "mock":
            llm_key = "mock"
        preflight_data = _stage(
            job_id,
            "preflight",
            lambda: run_preflight(github_url, settings.MIN_FREE_DISK_MB, llm_key),
            10,
            {"ok": False, "errors": ["Preflight could not be completed."]},
            StageData,
            stages,
            diagnostics,
        )
        diagnostics.extend({
            "stage": "preflight",
            "file": "",
            "severity": "warning",
            "message": redact_secrets(warning),
        } for warning in preflight_data.get("warnings", []))
        if not preflight_data.get("ok"):
            message = "; ".join(preflight_data.get("errors", [])) or preflight_data.get("error", "Preflight failed.")
            diagnostics.append({
                "stage": "preflight", "file": "", "severity": "error",
                "message": redact_secrets(message),
            })
            _save_structured_failure(job_id, repo_name, message, diagnostics, stages, github_url)
            try:
                update_job_progress(job_id, "failed", 100, "Repository preflight failed.", "failed", message)
            except Exception:
                pass
            return

        clone_data = _stage(
            job_id,
            "clone",
            lambda: clone_repo(
                github_url=github_url,
                timeout=settings.CLONE_TIMEOUT_SECONDS,
                max_size_mb=settings.MAX_REPO_SIZE_MB,
                depth=settings.MAX_HISTORY_COMMITS,
            ),
            settings.CLONE_TIMEOUT_SECONDS + 2,
            {"success": False, "path": None, "name": repo_name, "url": "", "error": "Clone failed."},
            CloneData,
            stages,
            diagnostics,
        )
        if not clone_data.get("success") or not clone_data.get("path"):
            message = redact_secrets(clone_data.get("error") or "Repository clone failed.")
            diagnostics.append({
                "stage": "clone", "file": "", "severity": "error", "message": message,
            })
            _save_structured_failure(job_id, repo_name, message, diagnostics, stages, github_url)
            try:
                update_job_progress(job_id, "failed", 100, "Repository clone failed.", "failed", message)
            except Exception:
                pass
            return
        repo_path = str(clone_data["path"])
        repo_name = str(clone_data.get("name") or repo_name)
        try:
            update_job_progress(job_id, "scan", 15, f"Scanning {repo_name}...")
        except Exception:
            pass

        manifest = _stage(
            job_id,
            "scan",
            lambda: scan_repo(
                repo_path,
                max_python_files=settings.MAX_PYTHON_FILES,
                max_files=settings.MAX_ANALYSIS_FILES,
                max_analysis_time_seconds=settings.MAX_ANALYSIS_TIME_SECONDS,
            ),
            min(settings.MAX_ANALYSIS_TIME_SECONDS, 240),
            {
                "files": [], "total_files": 0, "total_loc": 0,
                "language_breakdown": {}, "role_breakdown": {},
                "python_files": [], "total_python_files": 0,
                "diagnostics": [], "truncated": False, "warning": "Scanner failed.",
            },
            ManifestData,
            stages,
            diagnostics,
        )
        python_paths = set(manifest.get("python_files", []))
        analysis_entries = [
            item for item in manifest.get("files", [])
            if item.get("language") != "Python" or item.get("path") in python_paths
        ]
        complexity = _stage(
            job_id,
            "complexity",
            lambda: analyse_all(
                manifest.get("python_files", []),
                file_entries=analysis_entries,
            ),
            180,
            _empty_complexity,
            ComplexityData,
            stages,
            diagnostics,
        )
        graph = _stage(
            job_id,
            "graph",
            lambda: build_dependency_graph(
                manifest.get("python_files", []),
                repo_path,
                analysis_entries,
            ),
            180,
            _empty_graph,
            GraphData,
            stages,
            diagnostics,
        )
        churn = _stage(
            job_id,
            "churn",
            lambda: analyse_churn(
                repo_path,
                manifest.get("python_files", []),
                manifest_files=manifest.get("files", []),
                max_commits=settings.MAX_HISTORY_COMMITS,
            ),
            120,
            _empty_churn,
            ChurnData,
            stages,
            diagnostics,
        )
        hotspots = _stage(
            job_id,
            "hotspots",
            lambda: compute_hotspots(
                complexity,
                churn,
                repo_path,
                top_n,
                manifest_files=analysis_entries,
            ),
            30,
            _empty_hotspots,
            HotspotsData,
            stages,
            diagnostics,
        )
        evidence = build_evidence_pack(
            repo_name,
            manifest,
            complexity,
            churn,
            graph,
            hotspots,
            diagnostics,
        )

        if not preflight_data.get("checks", {}).get("llm"):
            from app.core.summariser import build_fallback_report

            structured_report = build_fallback_report(
                evidence,
                "AI synthesis was skipped because OPENROUTER_API_KEY is not configured.",
            )
            report_text = render_report_markdown(structured_report)
            report_json = structured_report.model_dump()
            report_status = "skipped"
            report_stage = StageResult(
                stage="report",
                status="skipped",
                data={"report_text": report_text, "report_json": report_json},
                warnings=["AI report skipped because no LLM key is configured."],
            )
        else:
            try:
                update_job_progress(job_id, "report", 80, "Generating an evidence-grounded report...")
            except Exception:
                pass
            report_started = time.monotonic()
            structured_report, report_diagnostics = generate_structured_report(
                evidence,
                get_llm_client(),
                settings.OPENROUTER_MODEL,
                settings.OPENROUTER_BASE_URL,
            )
            diagnostics.extend(report_diagnostics)
            report_json = structured_report.model_dump()
            report_text = render_report_markdown(structured_report)
            failed_ai = any("generation failed" in item.get("message", "").lower() for item in report_diagnostics)
            report_status = "failed" if failed_ai else "completed"
            report_stage = StageResult(
                stage="report",
                status="partial" if report_diagnostics else "ok",
                data={"report_text": report_text, "report_json": report_json},
                warnings=[item["message"] for item in report_diagnostics],
                duration_s=round(time.monotonic() - report_started, 3),
            )
        # Validate the final report stage's output contract as well.
        report_stage_data = ReportData.model_validate(report_stage.data).model_dump()
        report_stage.data = report_stage_data
        stages.append(report_stage.as_dict())

        try:
            cleanup_repo(repo_path)
            repo_path = None
        except Exception as exc:
            diagnostics.append({
                "stage": "cleanup", "file": "", "severity": "warning",
                "message": f"Temporary repository cleanup failed ({type(exc).__name__}).",
            })

        duration = round(time.monotonic() - started, 2)
        full_result = {
            "repo_name": repo_name,
            "github_url": github_url,
            "manifest": manifest,
            "complexity": complexity,
            "graph": graph,
            "churn": churn,
            "hotspots": hotspots,
            "report_json": report_json,
            "diagnostics": diagnostics,
            "stages": stages,
            "metadata": {
                "history_truncated": churn.get("stats", {}).get("history_truncated", False),
                "analysed_window": churn.get("stats", {}).get("analysed_window", "No history available"),
                "clone_depth": settings.MAX_HISTORY_COMMITS,
            },
            "duration_seconds": duration,
        }
        db = SessionLocal()
        try:
            job = db.query(Analysis).filter(Analysis.id == job_id).first()
            if job:
                job.repo_name = repo_name
                job.status = "completed"
                job.stage = "completed"
                job.percent = 100
                job.completed_at = datetime.now(UTC)
                job.duration_seconds = duration
                job.report_text = report_text
                job.report_status = report_status
                if report_status == "failed":
                    job.error = "AI report generation failed; evidence-only fallback is available."
                job.set_result(full_result)
                db.commit()
        finally:
            db.close()
        try:
            update_job_progress(job_id, "completed", 100, "Repository analysis complete.", "completed")
        except Exception:
            pass
    except Exception as exc:
        message = redact_secrets(f"Analysis pipeline failed ({type(exc).__name__}).")
        diagnostics.append({
            "stage": "pipeline", "file": "", "severity": "error", "message": message,
        })
        _log(job_id, message, "error")
        _save_structured_failure(job_id, repo_name, message, diagnostics, stages, github_url)
        try:
            update_job_progress(job_id, "failed", 100, message, "failed", message)
        except Exception:
            pass
    finally:
        if repo_path:
            try:
                cleanup_repo(repo_path)
            except Exception as exc:
                _log(job_id, f"stage=cleanup status=partial error={type(exc).__name__}", "warning")
        _concurrency_semaphore.release()


def regenerate_llm_report(analysis_id: str) -> dict[str, Any]:
    """Regenerate the structured report from persisted metrics without recloning."""
    db = SessionLocal()
    try:
        job = db.query(Analysis).filter(Analysis.id == analysis_id).first()
        if not job:
            raise ValueError(f"Analysis '{analysis_id}' not found")
        if job.status != "completed":
            raise ValueError("Cannot regenerate report for an incomplete analysis")
        result_data = job.get_result()
        if not result_data:
            raise ValueError("No analysis result data stored")
        evidence = build_evidence_pack(
            job.repo_name,
            result_data.get("manifest", {}),
            result_data.get("complexity", {}),
            result_data.get("churn", {}),
            result_data.get("graph", {}),
            result_data.get("hotspots", {}),
            result_data.get("diagnostics", []),
        )
        if settings.OPENROUTER_API_KEY.strip() or settings.LLM_PROVIDER.lower() == "mock":
            report, diagnostics = generate_structured_report(
                evidence, get_llm_client(), settings.OPENROUTER_MODEL, settings.OPENROUTER_BASE_URL
            )
            report_status = "failed" if any("generation failed" in item.get("message", "").lower() for item in diagnostics) else "completed"
        else:
            report = build_fallback_report(evidence, "AI synthesis was skipped because OPENROUTER_API_KEY is not configured.")
            diagnostics = []
            report_status = "skipped"
        report_text = render_report_markdown(report)
        result_data["report_json"] = report.model_dump()
        result_data["diagnostics"] = [*result_data.get("diagnostics", []), *diagnostics]
        result_data["stages"] = [
            *[stage for stage in result_data.get("stages", []) if stage.get("stage") != "report"],
            StageResult("report", report_status, {"report_json": report.model_dump()}).as_dict(),
        ]
        job.report_text = report_text
        job.report_status = report_status
        job.set_result(result_data)
        db.commit()
        return {
            "id": job.id,
            "report_status": report_status,
            "report_text": report_text,
            "report_json": report.model_dump(),
            "diagnostics": diagnostics,
        }
    finally:
        db.close()
