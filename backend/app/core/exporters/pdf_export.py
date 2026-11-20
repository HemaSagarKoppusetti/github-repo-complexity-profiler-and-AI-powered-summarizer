"""Accessible ReportLab Platypus PDF renderer."""

from __future__ import annotations

import io
import os
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Flowable,
    Frame,
    Image,
    KeepTogether,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus.tableofcontents import TableOfContents

from app.core.exporters.report_model import ChartArtifact, ReportModel, section_content

TIER_COLORS = {
    "Critical": "#b91c1c",
    "High": "#c2410c",
    "Medium": "#a16207",
    "Low": "#15803d",
}


def _register_font() -> bool:
    """Register a system sans font if one is available on Windows."""
    candidates = [
        Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts" / "arial.ttf",
        Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts" / "segoeui.ttf",
    ]
    for candidate in candidates:
        if candidate.exists():
            pdfmetrics.registerFont(TTFont("ProfilerSans", str(candidate)))
            return True
    return False


def _text(value: object, supports_unicode: bool) -> str:
    """Escape XML-sensitive text and sanitize glyphs when no Unicode font exists."""
    text = str(value if value is not None else "")
    if not supports_unicode:
        text = text.encode("ascii", errors="replace").decode("ascii")
    return escape(text).replace("\n", "<br/>")


def _paragraph(value: object, style: ParagraphStyle, supports_unicode: bool) -> Paragraph:
    return Paragraph(_text(value, supports_unicode), style)


def _table(
    rows: list[list[Any]],
    widths: list[float],
    style: ParagraphStyle,
    supports_unicode: bool,
) -> Table:
    """Create a repeating-header, wrapped-text report table."""
    data = [
        [_paragraph(cell, style, supports_unicode) if not isinstance(cell, Flowable) else cell for cell in row]
        for row in rows
    ]
    table = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#cbd5e1")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return table


class _ReportDocTemplate(BaseDocTemplate):
    """PDF document template with a generated table of contents and page numbers."""

    def __init__(self, path: Path, toc: TableOfContents) -> None:
        self.toc = toc
        super().__init__(
            str(path),
            pagesize=A4,
            leftMargin=18 * mm,
            rightMargin=18 * mm,
            topMargin=20 * mm,
            bottomMargin=18 * mm,
            title="Repository analysis report",
            author="GitHub Repo Complexity Profiler",
        )
        frame = Frame(self.leftMargin, self.bottomMargin, self.width, self.height, id="body")
        self.addPageTemplates(PageTemplate(id="report", frames=frame, onPage=self._draw_page_chrome))

    def _draw_page_chrome(self, canvas: Any, document: Any) -> None:
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#cbd5e1"))
        canvas.line(self.leftMargin, 14 * mm, A4[0] - self.rightMargin, 14 * mm)
        canvas.setFont("ProfilerSans" if "ProfilerSans" in pdfmetrics.getRegisteredFontNames() else "Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#475569"))
        canvas.drawString(self.leftMargin, 10 * mm, "GitHub Repo Complexity Profiler")
        canvas.drawRightString(A4[0] - self.rightMargin, 10 * mm, f"Page {document.page}")
        canvas.restoreState()

    def afterFlowable(self, flowable: Flowable) -> None:
        if isinstance(flowable, Paragraph) and flowable.style.name == "Heading1Custom":
            title = flowable.getPlainText()
            self.notify("TOCEntry", (0, title, self.page))


def _add_heading(story: list[Flowable], title: str, styles: Any, unicode: bool) -> None:
    story.append(Paragraph(_text(title, unicode), styles["Heading1Custom"]))
    story.append(Spacer(1, 3 * mm))


def _add_bullets(story: list[Flowable], values: list[str], styles: Any, unicode: bool) -> None:
    for value in values:
        story.append(Paragraph(f"&bull; {_text(value, unicode)}", styles["BodyTextCustom"]))
        story.append(Spacer(1, 1.5 * mm))


def _chart_flowables(chart: ChartArtifact, width: float, styles: Any, unicode: bool) -> KeepTogether:
    image = Image(io.BytesIO(chart.png_bytes))
    image.drawWidth = width
    image.drawHeight = min(250 * mm, width * image.imageHeight / image.imageWidth)
    caption = Paragraph(
        f"<b>{_text(chart.caption, unicode)}</b><br/>{_text(chart.how_to_read, unicode)}",
        styles["Small"],
    )
    return KeepTogether([image, Spacer(1, 2 * mm), caption])


def render_pdf(model: ReportModel, output_path: Path) -> Path:
    """Render the canonical report as a multi-page, searchable PDF."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    unicode_font = _register_font()
    font_name = "ProfilerSans" if unicode_font else "Helvetica"
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="Heading1Custom",
            parent=styles["Heading1"],
            fontName=font_name,
            fontSize=16,
            leading=20,
            textColor=colors.HexColor("#1e3a8a"),
            spaceBefore=5 * mm,
            spaceAfter=2 * mm,
            keepWithNext=True,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Heading2Custom",
            parent=styles["Heading2"],
            fontName=font_name,
            fontSize=11,
            leading=14,
            textColor=colors.HexColor("#334155"),
            spaceBefore=3 * mm,
            spaceAfter=1.5 * mm,
            keepWithNext=True,
        )
    )
    styles.add(
        ParagraphStyle(
            name="BodyTextCustom",
            parent=styles["BodyText"],
            fontName=font_name,
            fontSize=8.5,
            leading=12,
            alignment=TA_LEFT,
            spaceAfter=2 * mm,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Small",
            parent=styles["BodyTextCustom"],
            fontName=font_name,
            fontSize=7.5,
            leading=10,
            textColor=colors.HexColor("#475569"),
        )
    )
    styles.add(
        ParagraphStyle(
            name="CoverTitle",
            parent=styles["Title"],
            fontName=font_name,
            fontSize=25,
            leading=31,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#1e3a8a"),
            spaceAfter=12 * mm,
        )
    )
    sections = section_content(model)
    story: list[Flowable] = []
    story.extend(
        [
            Spacer(1, 35 * mm),
            Paragraph(_text("GitHub Repository Analysis", unicode_font), styles["CoverTitle"]),
            Paragraph(_text(model.repo_name, unicode_font), styles["Heading2Custom"]),
            Paragraph(_text(f"Generated: {model.generated_at}", unicode_font), styles["BodyTextCustom"]),
            Paragraph(
                _text(f"Analysed commit window: {model.analysed_window}", unicode_font), styles["BodyTextCustom"]
            ),
            Paragraph(_text(f"Tool version: {model.tool_version}", unicode_font), styles["BodyTextCustom"]),
            Spacer(1, 15 * mm),
            Paragraph(_text(model.headline, unicode_font), styles["BodyTextCustom"]),
            PageBreak(),
        ]
    )
    toc = TableOfContents()
    toc.levelStyles = [
        ParagraphStyle(
            name="TOCHeading",
            fontName=font_name,
            fontSize=9,
            leftIndent=12,
            firstLineIndent=-12,
            spaceBefore=3,
        ),
    ]
    _add_heading(story, "Table of contents", styles, unicode_font)
    story.append(toc)
    story.append(PageBreak())

    _add_heading(story, "Executive summary", styles, unicode_font)
    story.append(
        Paragraph(
            f"<b>Health: {_text(model.health_rating, unicode_font)}</b> — {_text(model.health_rationale, unicode_font)}",
            styles["BodyTextCustom"],
        )
    )
    story.append(Paragraph(_text(sections["executive_summary"]["headline"], unicode_font), styles["BodyTextCustom"]))
    story.append(
        _table(
            [["KPI", "Value"], *[[key, value] for key, value in model.kpis.items()]],
            [65 * mm, 95 * mm],
            styles["BodyTextCustom"],
            unicode_font,
        )
    )
    story.append(PageBreak())

    _add_heading(story, "Key insights", styles, unicode_font)
    for insight in sections["key_insights"]:
        story.append(Paragraph(f"<b>{_text(insight['title'], unicode_font)}</b>", styles["Heading2Custom"]))
        _add_bullets(story, insight.get("evidence", []), styles, unicode_font)
        story.append(Paragraph(_text(insight.get("so_what", ""), unicode_font), styles["BodyTextCustom"]))
        story.append(
            Paragraph(
                f"Hypothesis: {_text(insight.get('likely_cause', ''), unicode_font)} "
                f"Confidence: {_text(insight.get('confidence', 'Low'), unicode_font)}",
                styles["BodyTextCustom"],
            )
        )
    if not sections["key_insights"]:
        story.append(Paragraph("No structured key insights were returned.", styles["BodyTextCustom"]))
    story.append(PageBreak())

    _add_heading(story, "Hotspot quadrant and ranking", styles, unicode_font)
    for chart in model.charts:
        if chart.name in {"quadrant", "risk_tiers", "hotspot_components"}:
            story.append(_chart_flowables(chart, 165 * mm, styles, unicode_font))
            story.append(Spacer(1, 3 * mm))
    hotspot_rows = [
        [
            "File",
            "Tier",
            "Quadrant",
            "Risk",
            "CC",
            "MI",
            "Churn",
            "LOC",
        ]
    ]
    for item in sections["hotspots"]["rows"]:
        tier = _text(item.get("tier", "Low"), unicode_font)
        tier_cell = Paragraph(
            f'<font color="{TIER_COLORS.get(item.get("tier"), TIER_COLORS["Low"])}"><b>{tier}</b></font>',
            styles["BodyTextCustom"],
        )
        hotspot_rows.append(
            [
                item.get("rel_path", ""),
                tier_cell,
                item.get("quadrant", ""),
                item.get("risk_score", 0),
                item.get("max_cc", 0),
                item.get("mi_score", "N/A") if item.get("mi_available", True) else "N/A",
                item.get("commit_count", 0),
                item.get("loc", 0),
            ]
        )
    story.append(
        _table(
            hotspot_rows,
            [43 * mm, 16 * mm, 23 * mm, 13 * mm, 11 * mm, 12 * mm, 14 * mm, 12 * mm],
            styles["Small"],
            unicode_font,
        )
    )
    story.append(PageBreak())

    _add_heading(story, "Risks", styles, unicode_font)
    risk_rows = [["File", "Severity", "Why", "Blast radius", "Failure mode"]]
    for item in sections["risks"]:
        risk_rows.append([item["file"], item["severity"], item["why"], item["blast_radius"], item["failure_mode"]])
    if len(risk_rows) == 1:
        risk_rows.append(["No file-specific risks were returned.", "", "", "", ""])
    story.append(_table(risk_rows, [26 * mm, 17 * mm, 48 * mm, 35 * mm, 34 * mm], styles["Small"], unicode_font))
    story.append(PageBreak())

    _add_heading(story, "Recommendations", styles, unicode_font)
    recommendation_rows = [["Priority", "Action", "Target", "Expected benefit", "Effort", "Confidence"]]
    for item in sections["recommendations"]:
        recommendation_rows.append(
            [
                item["priority"],
                item["action"],
                item["target"],
                item["expected_benefit"],
                item["effort"],
                item["confidence"],
            ]
        )
    if len(recommendation_rows) == 1:
        recommendation_rows.append(["", "No recommendations were returned.", "", "", "", ""])
    story.append(
        _table(
            recommendation_rows, [15 * mm, 48 * mm, 27 * mm, 48 * mm, 12 * mm, 15 * mm], styles["Small"], unicode_font
        )
    )
    _add_heading(story, "Quick wins", styles, unicode_font)
    _add_bullets(story, model.report.quick_wins, styles, unicode_font)
    story.append(PageBreak())

    _add_heading(story, "30/60/90-day roadmap", styles, unicode_font)
    roadmap_rows = [["Window", "Actions"]]
    for label, actions in (
        ("30 days", model.report.roadmap.days_30),
        ("60 days", model.report.roadmap.days_60),
        ("90 days", model.report.roadmap.days_90),
    ):
        roadmap_rows.append([label, "\n".join(actions) if actions else "No evidence-specific item supplied."])
    story.append(_table(roadmap_rows, [30 * mm, 135 * mm], styles["BodyTextCustom"], unicode_font))
    story.append(PageBreak())

    architecture = sections["architecture_and_dependencies"]
    _add_heading(story, "Architecture and dependency analysis", styles, unicode_font)
    story.append(Paragraph(_text(architecture["architecture"]["summary"], unicode_font), styles["BodyTextCustom"]))
    _add_bullets(story, architecture["architecture"].get("strengths", []), styles, unicode_font)
    _add_bullets(story, architecture["architecture"].get("concerns", []), styles, unicode_font)
    story.append(
        Paragraph(_text(f"Graph metrics: {architecture['graph_stats']}", unicode_font), styles["BodyTextCustom"])
    )
    for chart in model.charts:
        if chart.name == "dependency_graph":
            story.append(_chart_flowables(chart, 165 * mm, styles, unicode_font))
    cycle_rows = [
        ["Strongly connected component"],
        *[[", ".join(component)] for component in architecture["cycle_components"]],
    ]
    if len(cycle_rows) == 1:
        cycle_rows.append(["No cyclic components detected."])
    story.append(_table(cycle_rows, [165 * mm], styles["BodyTextCustom"], unicode_font))
    story.append(PageBreak())

    ownership = sections["ownership_and_churn"]
    _add_heading(story, "Ownership and churn", styles, unicode_font)
    story.append(Paragraph(_text(f"History statistics: {ownership['stats']}", unicode_font), styles["BodyTextCustom"]))
    for chart in model.charts:
        if chart.name in {"ownership", "commit_timeline"}:
            story.append(_chart_flowables(chart, 165 * mm, styles, unicode_font))
    coupling_rows: list[list[Any]] = [["Files", "Co-change commits"]]
    coupling_rows.extend(
        [[", ".join(item["files"]), item["cochange_count"]] for item in ownership["temporal_coupling"]]
    )
    if len(coupling_rows) == 1:
        coupling_rows.append(["No temporal coupling pairs exceeded threshold.", 0])
    story.append(_table(coupling_rows, [135 * mm, 30 * mm], styles["BodyTextCustom"], unicode_font))
    churn_rows: list[list[Any]] = [["File", "Commits", "Added", "Deleted"]]
    churn_rows.extend(
        [
            [
                item.get("rel_path", ""),
                item.get("commit_count", 0),
                item.get("lines_added", 0),
                item.get("lines_deleted", 0),
            ]
            for item in ownership["top_files"]
        ]
    )
    if len(churn_rows) == 1:
        churn_rows.append(["No file-level history was available.", 0, 0, 0])
    story.append(_table(churn_rows, [85 * mm, 25 * mm, 25 * mm, 25 * mm], styles["Small"], unicode_font))
    story.append(PageBreak())

    _add_heading(story, "Testing focus", styles, unicode_font)
    focus_rows = [["File or module", "Reason"]]
    focus_rows.extend([[item["file_or_module"], item["reason"]] for item in sections["testing_focus"]])
    if len(focus_rows) == 1:
        focus_rows.append(["No testing focus returned.", ""])
    story.append(_table(focus_rows, [55 * mm, 110 * mm], styles["BodyTextCustom"], unicode_font))
    for chart in model.charts:
        if chart.name in {"cc_ranks", "maintainability", "language_roles"}:
            story.append(_chart_flowables(chart, 165 * mm, styles, unicode_font))
    story.append(PageBreak())

    quality = sections["data_quality_and_limitations"]
    _add_heading(story, "Data quality and limitations", styles, unicode_font)
    quality_rows = [["Severity", "Stage", "File", "Message"]]
    quality_rows.extend(
        [
            [item.get("severity", ""), item.get("stage", ""), item.get("file", ""), item.get("message", "")]
            for item in quality["diagnostics"]
        ]
    )
    if len(quality_rows) == 1:
        quality_rows.append(["info", "analysis", "", "No diagnostics were recorded."])
    story.append(_table(quality_rows, [19 * mm, 25 * mm, 48 * mm, 73 * mm], styles["Small"], unicode_font))
    _add_bullets(story, quality["limitations"], styles, unicode_font)
    story.append(PageBreak())

    appendix = sections["appendix"]
    _add_heading(story, "Appendix: risk formula and methodology", styles, unicode_font)
    story.append(Paragraph(_text(appendix["risk_formula"], unicode_font), styles["BodyTextCustom"]))
    story.append(Paragraph(_text(f"Weights: {appendix['risk_weights']}", unicode_font), styles["BodyTextCustom"]))
    story.append(
        Paragraph(_text(f"Tier thresholds: {appendix['tier_thresholds']}", unicode_font), styles["BodyTextCustom"])
    )
    story.append(Paragraph(_text(appendix["methodology"], unicode_font), styles["BodyTextCustom"]))

    document = _ReportDocTemplate(output_path, toc)
    document.multiBuild(story)
    return output_path
