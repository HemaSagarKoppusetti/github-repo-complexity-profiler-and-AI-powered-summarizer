"""Shared report exports in PDF, HTML, and DOCX formats."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable

from app.core.exporters.docx_export import render_docx
from app.core.exporters.html_export import render_html
from app.core.exporters.pdf_export import render_pdf
from app.core.exporters.report_model import ReportModel, build_report_model

RENDERERS = {
    "pdf": render_pdf,
    "html": render_html,
    "docx": render_docx,
}


def _render(model: ReportModel, fmt: str, out_dir: str | Path) -> Path:
    format_name = fmt.lower().lstrip(".")
    if format_name not in RENDERERS:
        raise ValueError(f"Unsupported report format: {fmt}")
    output_directory = Path(out_dir)
    output_directory.mkdir(parents=True, exist_ok=True)
    safe_repo_name = re.sub(r"[^A-Za-z0-9._-]+", "_", model.repo_name).strip("._")
    filename = f"{safe_repo_name or 'repository'}_report.{format_name}"
    return RENDERERS[format_name](model, output_directory / filename)


def export_report(analysis: dict[str, Any], fmt: str, out_dir: str | Path) -> Path:
    """Export a repository analysis in one supported format."""
    model = build_report_model(analysis)
    return _render(model, fmt, out_dir)


def export_all(
    analysis: dict[str, Any],
    formats: Iterable[str] = ("pdf", "html", "docx"),
    out_dir: str | Path = "reports",
) -> dict[str, Path]:
    """Build the report model once and export each requested format."""
    model = build_report_model(analysis)
    return {fmt.lower().lstrip("."): _render(model, fmt, out_dir) for fmt in formats}


__all__ = ["ReportModel", "build_report_model", "export_all", "export_report"]
