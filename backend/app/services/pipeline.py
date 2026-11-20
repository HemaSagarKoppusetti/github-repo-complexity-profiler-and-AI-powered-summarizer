# backend/app/services/pipeline.py
"""Seven-stage repository analysis pipeline with background execution,

SSE progress emission, 24h caching, and robust error recovery.
"""

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
from app.core.scanner import scan_repo
from app.core.summariser import build_prompt
from app.db.database import SessionLocal
from app.db.models import Analysis
from app.services.events import event_broadcaster
from app.services.llm import LLMClientException, get_llm_client

logger = logging.getLogger(__name__)

# Semaphore to limit concurrent background analysis jobs
_concurrency_semaphore = threading.Semaphore(settings.MAX_CONCURRENT_JOBS)


def _log(job_id: str, msg: str, level: str = "info") -> None:
    formatted = f"[job:{job_id}] {msg}"
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
    """Updates database row and broadcasts SSE event."""
    _log(job_id, f"Stage '{stage}' ({percent}%): {message}")
    db = SessionLocal()
    try:
        job = db.query(Analysis).filter(Analysis.id == job_id).first()
        if job:
            job.stage = stage
            job.percent = percent
            job.status = status
            if error:
                job.error = error
            db.commit()
    except Exception as e:
        _log(job_id, f"Failed updating job status in DB: {e}", "warning")
    finally:
        db.close()

    event_broadcaster.publish_sync(
        analysis_id=job_id,
        stage=stage,
        percent=percent,
        message=message,
        status=status,
        extra={"error": error} if error else None,
    )


def run_analysis(
    job_id: str,
    github_url: str,
    top_n: int = 10,
) -> None:
    """Executes the 7 analysis stages sequentially inside a background worker."""
    acquired = _concurrency_semaphore.acquire(blocking=True, timeout=120)
    if not acquired:
        update_job_progress(
            job_id,
            stage="queued",
            percent=0,
            message="Server is busy processing other repositories. Please retry shortly.",
            status="failed",
            error="Concurrency limit reached",
        )
        return

    start_time = time.time()
    repo_path: str | None = None
    repo_name = parse_repo_name(github_url)

    update_job_progress(
        job_id,
        stage="starting",
        percent=2,
        message=f"Starting analysis for {repo_name}...",
        status="running",
    )

    try:
        # ── STAGE 1: CLONE (Weight: 15% -> 15%) ──────────────────────────────
        update_job_progress(
            job_id,
            stage="clone",
            percent=5,
            message=f"📥 Cloning repository '{repo_name}' from GitHub...",
        )
        clone_result = clone_repo(
            github_url=github_url,
            timeout=settings.CLONE_TIMEOUT_SECONDS,
            max_size_mb=settings.MAX_REPO_SIZE_MB,
        )

        if not clone_result["success"]:
            err_msg = clone_result["error"] or "Unknown clone failure"
            update_job_progress(
                job_id,
                stage="clone",
                percent=15,
                message=f"❌ Clone failed: {err_msg}",
                status="failed",
                error=err_msg,
            )
            return

        repo_path = clone_result["path"]
        repo_name = clone_result["name"]
        update_job_progress(
            job_id,
            stage="clone",
            percent=15,
            message=f"✅ Repository cloned successfully ({clone_result.get('size_mb', 0)} MB)",
        )

        # ── STAGE 2: SCAN (Weight: 5% -> 20%) ────────────────────────────────
        update_job_progress(
            job_id,
            stage="scan",
            percent=17,
            message="🗂️ Scanning repository file tree...",
        )
        manifest = scan_repo(
            repo_path=repo_path,
            max_python_files=settings.MAX_PYTHON_FILES,
        )
        py_files_count = len(manifest["python_files"])
        scan_msg = (
            f"✅ Manifest built: {manifest['total_files']} files, "
            f"{manifest['total_loc']:,} LOC, {py_files_count} Python files"
        )
        if manifest.get("warning"):
            scan_msg += f" ({manifest['warning']})"

        update_job_progress(
            job_id,
            stage="scan",
            percent=20,
            message=scan_msg,
        )

        # Check for zero Python files
        has_python_files = py_files_count > 0

        # ── STAGE 3: COMPLEXITY (Weight: 15% -> 35%) ─────────────────────────
        update_job_progress(
            job_id,
            stage="complexity",
            percent=25,
            message="📊 Analysing code cyclomatic complexity and maintainability...",
        )
        if has_python_files:
            complexity = analyse_all(manifest["python_files"])
            c_sum = complexity["summary"]
            c_msg = (
                f"✅ Analysed {c_sum['total_functions']} functions | "
                f"avg MI: {c_sum['avg_mi_score']}/100"
            )
        else:
            complexity = {
                "results": [],
                "summary": {
                    "total_files_analysed": 0,
                    "total_functions": 0,
                    "avg_mi_score": 0.0,
                    "low_mi_file_count": 0,
                    "rank_distribution": {"A": 0, "B": 0, "C": 0, "D": 0, "E": 0, "F": 0},
                    "top_complex_functions": [],
                    "least_maintainable": [],
                },
            }
            c_msg = "ℹ️ No Python files found for complexity analysis"

        update_job_progress(
            job_id,
            stage="complexity",
            percent=35,
            message=c_msg,
        )

        # ── STAGE 4: GRAPH (Weight: 15% -> 50%) ──────────────────────────────
        update_job_progress(
            job_id,
            stage="graph",
            percent=40,
            message="🔀 Constructing AST dependency graph and cycle detection...",
        )
        if has_python_files:
            graph = build_dependency_graph(manifest["python_files"], repo_path)
            g_stats = graph["stats"]
            g_msg = (
                f"✅ Graph constructed: {g_stats['node_count']} nodes, "
                f"{g_stats['edge_count']} edges, {g_stats['cycle_count']} cycles"
            )
        else:
            graph = {
                "nodes": [],
                "edges": [],
                "cycles": [],
                "hub_modules": [],
                "isolated_modules": [],
                "external_packages": [],
                "stats": {
                    "node_count": 0,
                    "edge_count": 0,
                    "density": 0.0,
                    "cycle_count": 0,
                    "has_cycles": False,
                    "external_deps": 0,
                },
                "graph_elements": {"nodes": [], "edges": []},
            }
            g_msg = "ℹ️ Dependency graph skipped (zero Python files)"

        update_job_progress(
            job_id,
            stage="graph",
            percent=50,
            message=g_msg,
        )

        # ── STAGE 5: CHURN (Weight: 20% -> 70%) ──────────────────────────────
        update_job_progress(
            job_id,
            stage="churn",
            percent=55,
            message="📈 Mining git log for file change frequency and authorship...",
        )
        churn = analyse_churn(repo_path, manifest["python_files"])
        ch_stats = churn["stats"]
        update_job_progress(
            job_id,
            stage="churn",
            percent=70,
            message=(
                f"✅ Git history parsed: {ch_stats['total_commits']} commits, "
                f"{ch_stats['total_authors']} authors, {ch_stats['repo_age_days']} days old"
            ),
        )

        # ── STAGE 6: HOTSPOTS (Weight: 5% -> 75%) ────────────────────────────
        update_job_progress(
            job_id,
            stage="hotspots",
            percent=72,
            message="🎯 Computing multi-factor risk scores and ranking hotspots...",
        )
        hotspots = compute_hotspots(complexity, churn, repo_path, top_n)
        h_sum = hotspots["summary"]
        update_job_progress(
            job_id,
            stage="hotspots",
            percent=75,
            message=(
                f"✅ Hotspots computed: 🔴 {h_sum['critical_count']} Critical | "
                f"🟠 {h_sum['high_count']} High | 🟡 {h_sum['medium_count']} Medium | "
                f"🟢 {h_sum['low_count']} Low"
            ),
        )

        # ── STAGE 7: LLM REPORT (Weight: 25% -> 100%) ────────────────────────
        update_job_progress(
            job_id,
            stage="report",
            percent=80,
            message="🤖 Synthesising AI code architecture and risk assessment report...",
        )

        report_text: str | None = None
        report_status = "pending"
        report_error: str | None = None

        if not has_python_files:
            report_text = (
                f"# Repository Analysis: {repo_name}\n\n"
                "## 1. What This Codebase Does\n"
                f"This repository contains {manifest['total_files']} files ({manifest['total_loc']} LOC), "
                f"predominantly composed of: {', '.join(f'{k} ({v})' for k, v in manifest['language_breakdown'].items())}.\n\n"
                "## 2. Architectural Strengths\n"
                "- Clean file manifest structure.\n\n"
                "## 3. Top Risk Areas\n"
                "- Zero Python files were detected; Python static complexity profiling was not applicable.\n\n"
                "## 4. Refactoring Suggestions\n"
                "- Refer to repository specific guidelines for non-Python file reviews."
            )
            report_status = "completed"
        else:
            try:
                prompt = build_prompt(
                    repo_name=repo_name,
                    scan=manifest,
                    complexity=complexity,
                    churn=churn,
                    graph=graph,
                    hotspots=hotspots,
                )
                llm_client = get_llm_client()
                report_text = llm_client.generate(prompt)
                report_status = "completed"
                _log(job_id, "AI report generated successfully")
            except (LLMClientException, Exception) as e:
                report_status = "failed"
                report_error = str(e)
                _log(job_id, f"AI report generation failed: {e}", "warning")

        # Compile final results package
        duration = round(time.time() - start_time, 2)
        full_result = {
            "repo_name": repo_name,
            "github_url": github_url,
            "manifest": manifest,
            "complexity": complexity,
            "graph": graph,
            "churn": churn,
            "hotspots": hotspots,
            "duration_seconds": duration,
        }

        # Save to database
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
                if report_error:
                    job.error = f"Report generation warning: {report_error}"
                job.set_result(full_result)
                db.commit()
        finally:
            db.close()

        update_job_progress(
            job_id,
            stage="completed",
            percent=100,
            message="🎉 Repository analysis complete!",
            status="completed",
        )

    except Exception as e:
        err_msg = f"Unexpected pipeline failure: {e}"
        _log(job_id, err_msg, "error")
        update_job_progress(
            job_id,
            stage="failed",
            percent=100,
            message=err_msg,
            status="failed",
            error=err_msg,
        )

    finally:
        # Guaranteed cleanup in finally block
        if repo_path:
            cleanup_repo(repo_path)
        _concurrency_semaphore.release()


def regenerate_llm_report(analysis_id: str) -> dict[str, Any]:
    """Regenerates the LLM report from stored analysis results without recloning."""
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

        prompt = build_prompt(
            repo_name=job.repo_name,
            scan=result_data["manifest"],
            complexity=result_data["complexity"],
            churn=result_data["churn"],
            graph=result_data["graph"],
            hotspots=result_data["hotspots"],
        )

        llm_client = get_llm_client()
        report_text = llm_client.generate(prompt)

        job.report_text = report_text
        job.report_status = "completed"
        db.commit()

        return {
            "id": job.id,
            "report_status": "completed",
            "report_text": report_text,
        }
    finally:
        db.close()
