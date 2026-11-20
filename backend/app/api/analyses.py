# backend/app/api/analyses.py
"""API endpoints for managing and querying repository analyses."""

from __future__ import annotations

import json
import logging
import threading
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Query,
    Response,
    status,
)
from fastapi.responses import StreamingResponse
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.config import settings
from app.core.cloner import parse_repo_name
from app.db.database import get_db
from app.db.models import Analysis
from app.schemas.analysis import (
    AnalysisCreate,
    AnalysisDetail,
    AnalysisKeyMetrics,
    AnalysisSummary,
    PaginatedResponse,
)
from app.services.events import event_broadcaster
from app.services.pdf import generate_pdf_report
from app.services.pipeline import regenerate_llm_report, run_analysis

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analyses", tags=["Analyses"])


def _extract_key_metrics(analysis: Analysis) -> AnalysisKeyMetrics | None:
    """Helper to extract top-level KPI metrics from result JSON."""
    result = analysis.get_result()
    if not result:
        return None

    manifest = result.get("manifest", {})
    churn_stats = result.get("churn", {}).get("stats", {})
    comp_sum = result.get("complexity", {}).get("summary", {})
    graph_stats = result.get("graph", {}).get("stats", {})
    hotspots_sum = result.get("hotspots", {}).get("summary", {})

    return AnalysisKeyMetrics(
        total_files=manifest.get("total_files", 0),
        total_loc=manifest.get("total_loc", 0),
        total_commits=churn_stats.get("total_commits", 0),
        total_authors=churn_stats.get("total_authors", 0),
        repo_age_days=churn_stats.get("repo_age_days", 0),
        avg_mi_score=comp_sum.get("avg_mi_score", 0.0),
        circular_deps=graph_stats.get("cycle_count", 0),
        critical_hotspots=hotspots_sum.get("critical_count", 0),
        high_hotspots=hotspots_sum.get("high_count", 0),
    )


@router.post("", status_code=status.HTTP_201_CREATED)
def create_analysis(
    payload: AnalysisCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Creates a new repository analysis job or returns cached results."""
    github_url = payload.github_url
    repo_name = parse_repo_name(github_url)

    # 24-hour cache check
    if not payload.force:
        cutoff = datetime.now(UTC) - timedelta(hours=settings.CACHE_TTL_HOURS)
        cached = (
            db.query(Analysis)
            .filter(
                Analysis.github_url == github_url,
                Analysis.status == "completed",
                Analysis.created_at >= cutoff,
            )
            .order_by(desc(Analysis.created_at))
            .first()
        )
        if cached:
            logger.info("Returning cached analysis for %s (id: %s)", github_url, cached.id)
            return {
                "id": cached.id,
                "status": cached.status,
                "repo_name": cached.repo_name,
                "cached": True,
            }

    # Create new analysis row
    new_job = Analysis(
        github_url=github_url,
        repo_name=repo_name,
        status="queued",
        stage="queued",
        percent=0,
        report_status="pending",
    )
    db.add(new_job)
    db.commit()
    db.refresh(new_job)

    # Launch background worker
    worker_thread = threading.Thread(
        target=run_analysis,
        args=(new_job.id, github_url, payload.top_n),
        daemon=True,
    )
    worker_thread.start()

    return {
        "id": new_job.id,
        "status": new_job.status,
        "repo_name": repo_name,
        "cached": False,
    }


@router.get("", response_model=PaginatedResponse[AnalysisSummary])
def list_analyses(
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    search: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
) -> PaginatedResponse[AnalysisSummary]:
    """Returns a paginated list of past repository analyses."""
    query = db.query(Analysis)

    if search:
        search_pattern = f"%{search.strip()}%"
        query = query.filter(
            (Analysis.repo_name.ilike(search_pattern))
            | (Analysis.github_url.ilike(search_pattern))
        )

    if status_filter:
        query = query.filter(Analysis.status == status_filter)

    total = query.count()
    offset = (page - 1) * size
    items = query.order_by(desc(Analysis.created_at)).offset(offset).limit(size).all()

    summary_items = []
    for item in items:
        summary_items.append(
            AnalysisSummary(
                id=item.id,
                github_url=item.github_url,
                repo_name=item.repo_name,
                status=item.status,
                stage=item.stage,
                percent=item.percent,
                error=item.error,
                report_status=item.report_status,
                created_at=item.created_at,
                completed_at=item.completed_at,
                duration_seconds=item.duration_seconds,
                key_metrics=_extract_key_metrics(item),
            )
        )

    pages = (total + size - 1) // size if total > 0 else 1
    return PaginatedResponse(
        items=summary_items,
        total=total,
        page=page,
        size=size,
        pages=pages,
    )


@router.get("/{analysis_id}", response_model=AnalysisDetail)
def get_analysis(
    analysis_id: str,
    db: Session = Depends(get_db),
) -> AnalysisDetail:
    """Retrieves full analysis results and report text by ID."""
    item = db.query(Analysis).filter(Analysis.id == analysis_id).first()
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": f"Analysis '{analysis_id}' not found"},
        )

    return AnalysisDetail(
        id=item.id,
        github_url=item.github_url,
        repo_name=item.repo_name,
        status=item.status,
        stage=item.stage,
        percent=item.percent,
        error=item.error,
        report_status=item.report_status,
        report_text=item.report_text,
        created_at=item.created_at,
        completed_at=item.completed_at,
        duration_seconds=item.duration_seconds,
        result=item.get_result(),
    )


@router.get("/{analysis_id}/events")
async def stream_analysis_events(
    analysis_id: str,
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """Streams real-time stage progress over Server-Sent Events (SSE)."""
    item = db.query(Analysis).filter(Analysis.id == analysis_id).first()
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": f"Analysis '{analysis_id}' not found"},
        )

    return StreamingResponse(
        event_broadcaster.subscribe(analysis_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/{analysis_id}/report.md")
def download_markdown_report(
    analysis_id: str,
    db: Session = Depends(get_db),
) -> Response:
    """Downloads the generated AI report as a Markdown (.md) document."""
    item = db.query(Analysis).filter(Analysis.id == analysis_id).first()
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": f"Analysis '{analysis_id}' not found"},
        )

    if not item.report_text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "REPORT_NOT_AVAILABLE", "message": "Report text has not been generated for this analysis"},
        )

    filename = f"{item.repo_name}_report.md"
    return Response(
        content=item.report_text,
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{analysis_id}/report.pdf")
def download_pdf_report(
    analysis_id: str,
    db: Session = Depends(get_db),
) -> Response:
    """Downloads an executive summary and analysis report as a formatted PDF."""
    item = db.query(Analysis).filter(Analysis.id == analysis_id).first()
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": f"Analysis '{analysis_id}' not found"},
        )

    result_data = item.get_result()
    if not result_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "DATA_NOT_AVAILABLE", "message": "Analysis data is not yet available"},
        )

    pdf_bytes = generate_pdf_report(
        analysis_data=result_data,
        repo_name=item.repo_name,
        report_text=item.report_text,
    )

    filename = f"{item.repo_name}_report.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{analysis_id}/export.json")
def download_raw_json(
    analysis_id: str,
    db: Session = Depends(get_db),
) -> Response:
    """Downloads the complete raw analysis metrics as a JSON file."""
    item = db.query(Analysis).filter(Analysis.id == analysis_id).first()
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": f"Analysis '{analysis_id}' not found"},
        )

    result_data = item.get_result() or {}
    export_payload = {
        "id": item.id,
        "github_url": item.github_url,
        "repo_name": item.repo_name,
        "status": item.status,
        "created_at": item.created_at.isoformat(),
        "completed_at": item.completed_at.isoformat() if item.completed_at else None,
        "duration_seconds": item.duration_seconds,
        "report_status": item.report_status,
        "report_text": item.report_text,
        "data": result_data,
    }

    filename = f"{item.repo_name}_export.json"
    return Response(
        content=json.dumps(export_payload, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.delete("/{analysis_id}", status_code=status.HTTP_200_OK)
def delete_analysis(
    analysis_id: str,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Deletes an analysis record from the database."""
    item = db.query(Analysis).filter(Analysis.id == analysis_id).first()
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": f"Analysis '{analysis_id}' not found"},
        )

    db.delete(item)
    db.commit()
    return {"success": True, "message": f"Analysis '{analysis_id}' deleted successfully"}


@router.post("/{analysis_id}/rerun-report")
def rerun_report_endpoint(
    analysis_id: str,
) -> dict[str, Any]:
    """Regenerates the AI report from existing stored metrics without recloning."""
    try:
        result = regenerate_llm_report(analysis_id)
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_STATE", "message": str(e)},
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "LLM_ERROR", "message": str(e)},
        )
