"""Shared report model used by every export renderer."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from pydantic import ValidationError

from app.core.summariser import AIReport


@dataclass
class ChartArtifact:
    """A rendered chart and its explanatory text."""

    name: str
    title: str
    png_bytes: bytes
    caption: str
    how_to_read: str


@dataclass
class ReportModel:
    """Normalized content for PDF, HTML, and DOCX exports."""

    repo_name: str
    generated_at: str
    analysed_window: str
    tool_version: str
    headline: str
    health_rating: str
    health_rationale: str
    kpis: dict[str, Any]
    report: AIReport
    manifest: dict[str, Any]
    complexity: dict[str, Any]
    graph: dict[str, Any]
    churn: dict[str, Any]
    hotspots: dict[str, Any]
    diagnostics: list[dict[str, Any]] = field(default_factory=list)
    charts: list[ChartArtifact] = field(default_factory=list)


def build_report_model(
    analysis: dict[str, Any],
    report_json: dict[str, Any] | None = None,
    include_charts: bool = True,
) -> ReportModel:
    """Build the canonical report content and optionally render charts."""
    data = analysis.get("data", analysis)
    if not isinstance(data, dict):
        data = {}
    manifest = data.get("manifest", {})
    complexity = data.get("complexity", {})
    graph = data.get("graph", {})
    churn = data.get("churn", {})
    hotspots = data.get("hotspots", {})
    raw_report = report_json or data.get("report_json") or analysis.get("report_json") or {}
    diagnostics = list(data.get("diagnostics", []))
    try:
        report = AIReport.model_validate(raw_report)
    except (ValidationError, TypeError):
        diagnostics.append(
            {
                "stage": "export",
                "file": "",
                "severity": "warning",
                "message": "Structured AI report was unavailable; rendered a safe default.",
            }
        )
        report = AIReport(
            headline=f"{analysis.get('repo_name', data.get('repo_name', 'Repository'))} analysis",
            purpose="Static repository metrics are available; the AI report is not.",
            limitations=["A complete structured AI report was not available at export time."],
        )
    churn_stats = churn.get("stats", {})
    summary = complexity.get("summary", {})
    graph_stats = graph.get("stats", {})
    kpis = {
        "Files": manifest.get("total_files", 0),
        "LOC": manifest.get("total_loc", 0),
        "Commits": churn_stats.get("total_commits", 0),
        "Average MI": summary.get("avg_mi_score", 0),
        "Cycles": graph_stats.get("cycle_count", 0),
    }
    for item in manifest.get("diagnostics", []):
        if item not in diagnostics:
            diagnostics.append(item)
    if not diagnostics:
        diagnostics.append(
            {
                "stage": "analysis",
                "file": "",
                "severity": "info",
                "message": "No stage-level diagnostics were recorded.",
            }
        )
    model = ReportModel(
        repo_name=str(analysis.get("repo_name", data.get("repo_name", "Repository"))),
        generated_at=datetime.now(UTC).strftime("%Y-%m-%d"),
        analysed_window=str(
            data.get("metadata", {}).get(
                "analysed_window",
                churn_stats.get("analysed_window", "No Git history available"),
            )
        ),
        tool_version="2.0",
        headline=report.headline,
        health_rating=report.health.rating,
        health_rationale=report.health.rationale,
        kpis=kpis,
        report=report,
        manifest=manifest,
        complexity=complexity,
        graph=graph,
        churn=churn,
        hotspots=hotspots,
        diagnostics=diagnostics,
    )
    if include_charts:
        from app.core.exporters.charts import generate_charts

        model.charts = generate_charts(model)
    return model


def section_content(model: ReportModel) -> dict[str, Any]:
    """Return identical structured section content for every renderer."""
    report = model.report.model_dump()
    hotspot_rows = model.hotspots.get("hotspots", [])
    churn_stats = model.churn.get("stats", {})
    graph_stats = model.graph.get("stats", {})
    risk_weights = model.hotspots.get("summary", {}).get("risk_weights", {})
    return {
        "executive_summary": {
            "headline": report["headline"],
            "health_rating": report["health"]["rating"],
            "health_rationale": report["health"]["rationale"],
            "kpis": model.kpis,
        },
        "key_insights": report["key_insights"],
        "hotspots": {
            "quadrant_counts": model.hotspots.get("summary", {}).get("quadrant_counts", {}),
            "rows": hotspot_rows[:15],
        },
        "risks": report["risks"],
        "recommendations": report["recommendations"],
        "roadmap": report["roadmap"],
        "architecture_and_dependencies": {
            "architecture": report["architecture"],
            "graph_stats": graph_stats,
            "cycle_components": model.graph.get("cycle_components", []),
            "hub_modules": model.graph.get("hub_modules", []),
        },
        "ownership_and_churn": {
            "stats": churn_stats,
            "top_files": model.churn.get("most_churned", [])[:10],
            "temporal_coupling": model.churn.get("temporal_coupling", [])[:10],
        },
        "testing_focus": report["testing_focus"],
        "data_quality_and_limitations": {
            "diagnostics": model.diagnostics,
            "limitations": report["limitations"],
        },
        "appendix": {
            "risk_formula": model.hotspots.get("summary", {}).get(
                "risk_formula",
                "Risk score combines percentile-normalized churn, complexity, low MI, LOC, and bug-fix counts.",
            ),
            "risk_weights": risk_weights,
            "tier_thresholds": {
                "Critical": "score >= 0.65",
                "High": "score >= 0.40",
                "Medium": "score >= 0.20",
                "Low": "score < 0.20",
            },
            "methodology": "Static source analysis, bounded Git history, AST import resolution, and percentile-ranked risk signals.",
        },
    }
