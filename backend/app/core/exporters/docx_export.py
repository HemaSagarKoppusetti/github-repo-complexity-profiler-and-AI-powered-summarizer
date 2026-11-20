"""Microsoft Word DOCX report renderer."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any

from docx import Document
from docx.document import Document as DocumentObject
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

from app.core.exporters.report_model import ChartArtifact, ReportModel, section_content

TIER_COLORS = {
    "Critical": "B91C1C",
    "High": "C2410C",
    "Medium": "A16207",
    "Low": "15803D",
}


def _set_cell_shading(cell: Any, fill: str) -> None:
    """Set a table cell background color."""
    properties = cell._tc.get_or_add_tcPr()
    shading = OxmlElement("w:shd")
    shading.set(qn("w:fill"), fill)
    properties.append(shading)


def _set_cell_text(cell: Any, value: object, bold: bool = False) -> None:
    cell.text = str(value if value is not None else "")
    cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.TOP
    for paragraph in cell.paragraphs:
        for run in paragraph.runs:
            run.bold = bold
            run.font.size = Pt(8)


def _add_table(document: DocumentObject, headers: list[str], rows: list[list[object]]) -> None:
    """Append a readable table with a shaded, repeating header row."""
    table = document.add_table(rows=1, cols=len(headers))
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    header = table.rows[0]
    header._tr.get_or_add_trPr().append(OxmlElement("w:tblHeader"))
    for index, title in enumerate(headers):
        _set_cell_text(header.cells[index], title, bold=True)
        _set_cell_shading(header.cells[index], "DBEAFE")
    for row in rows:
        cells = table.add_row().cells
        for index, value in enumerate(row):
            _set_cell_text(cells[index], value)


def _add_bullets(document: DocumentObject, values: list[str]) -> None:
    for value in values:
        paragraph = document.add_paragraph(style="List Bullet")
        paragraph.add_run(str(value))


def _add_chart(document: DocumentObject, chart: ChartArtifact) -> None:
    """Append a chart and keep its caption next to the image."""
    paragraph = document.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    paragraph.add_run().add_picture(BytesIO(chart.png_bytes), width=Inches(6.2))
    caption = document.add_paragraph()
    caption.paragraph_format.keep_together = True
    caption.add_run(chart.caption).bold = True
    caption.add_run("\n" + chart.how_to_read)


def _add_field(paragraph: Any, instruction: str) -> None:
    """Append a Word field code."""
    run = paragraph.add_run()
    begin = OxmlElement("w:fldChar")
    begin.set(qn("w:fldCharType"), "begin")
    instruction_text = OxmlElement("w:instrText")
    instruction_text.set(qn("xml:space"), "preserve")
    instruction_text.text = instruction
    separate = OxmlElement("w:fldChar")
    separate.set(qn("w:fldCharType"), "separate")
    text = OxmlElement("w:t")
    text.text = "1"
    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    for element in (begin, instruction_text, separate, text, end):
        run._r.append(element)


def render_docx(model: ReportModel, output_path: Path) -> Path:
    """Render the canonical report as an A4 DOCX with editable charts and tables."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    document = Document()
    section = document.sections[0]
    section.page_width = Inches(8.27)
    section.page_height = Inches(11.69)
    section.top_margin = Inches(0.65)
    section.bottom_margin = Inches(0.65)
    section.left_margin = Inches(0.7)
    section.right_margin = Inches(0.7)
    document.core_properties.title = f"{model.repo_name} repository analysis"
    document.core_properties.author = "GitHub Repo Complexity Profiler"
    normal = document.styles["Normal"]
    normal.font.name = "Arial"
    normal.font.size = Pt(9)
    for style_name in ("Heading 1", "Heading 2", "Heading 3"):
        document.styles[style_name].font.name = "Arial"
        document.styles[style_name].font.color.rgb = RGBColor(30, 58, 138)

    header = section.header.paragraphs[0]
    header.text = "GitHub Repo Complexity Profiler"
    header.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    footer = section.footer.paragraphs[0]
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    footer.add_run("Page ")
    _add_field(footer, "PAGE")

    document.add_paragraph("GitHub Repository Analysis", style="Title")
    document.add_heading(model.repo_name, level=1)
    document.add_paragraph(f"Generated: {model.generated_at}")
    document.add_paragraph(f"Analysed commit window: {model.analysed_window}")
    document.add_paragraph(f"Tool version: {model.tool_version}")
    document.add_paragraph(model.headline)
    document.add_page_break()

    document.add_heading("Table of contents", level=1)
    toc_paragraph = document.add_paragraph()
    _add_field(toc_paragraph, 'TOC \\o "1-3" \\h \\z \\u')
    refresh_note = document.add_paragraph("The table of contents refreshes when the user presses F9 in Word.")
    if refresh_note.runs:
        document.add_comment(
            refresh_note.runs,
            "Refresh the generated table of contents by pressing F9 in Word.",
            author="GitHub Repo Profiler",
        )
    document.add_page_break()

    sections = section_content(model)
    document.add_heading("Executive summary", level=1)
    document.add_paragraph(f"Health: {model.health_rating}. {model.health_rationale}")
    document.add_paragraph(sections["executive_summary"]["headline"])
    _add_table(document, ["KPI", "Value"], [[name, value] for name, value in model.kpis.items()])
    document.add_page_break()

    document.add_heading("Key insights", level=1)
    for insight in sections["key_insights"]:
        document.add_heading(insight["title"], level=2)
        _add_bullets(document, insight.get("evidence", []))
        document.add_paragraph(insight.get("so_what", ""))
        document.add_paragraph(
            f"Hypothesis: {insight.get('likely_cause', '')} Confidence: {insight.get('confidence', 'Low')}"
        )
    if not sections["key_insights"]:
        document.add_paragraph("No structured key insights were returned.")
    document.add_page_break()

    document.add_heading("Hotspot quadrant and ranking", level=1)
    for chart in model.charts:
        if chart.name in {"quadrant", "risk_tiers", "hotspot_components"}:
            _add_chart(document, chart)
    hotspot_rows = []
    for item in sections["hotspots"]["rows"]:
        hotspot_rows.append(
            [
                item.get("rel_path", ""),
                item.get("tier", "Low"),
                item.get("quadrant", ""),
                item.get("risk_score", 0),
                item.get("max_cc", 0),
                item.get("mi_score", "N/A") if item.get("mi_available", True) else "N/A",
                item.get("commit_count", 0),
                item.get("loc", 0),
            ]
        )
    _add_table(
        document,
        ["File", "Tier", "Quadrant", "Risk", "CC", "MI", "Churn", "LOC"],
        hotspot_rows or [["No hotspots", "", "", 0, 0, "N/A", 0, 0]],
    )
    for table in document.tables[-1:]:
        for row in table.rows[1:]:
            tier_cell = row.cells[1]
            tier_name = tier_cell.text
            if tier_name in TIER_COLORS:
                for paragraph in tier_cell.paragraphs:
                    for run in paragraph.runs:
                        run.font.color.rgb = RGBColor.from_string(TIER_COLORS[tier_name])
    document.add_page_break()

    document.add_heading("Risks", level=1)
    risk_rows = [
        [item["file"], item["severity"], item["why"], item["blast_radius"], item["failure_mode"]]
        for item in sections["risks"]
    ]
    _add_table(
        document,
        ["File", "Severity", "Why", "Blast radius", "Failure mode"],
        risk_rows or [["", "", "No file-specific risks were returned.", "", ""]],
    )
    document.add_page_break()

    document.add_heading("Recommendations", level=1)
    recommendation_rows = [
        [
            item["priority"],
            item["action"],
            item["target"],
            item["expected_benefit"],
            item["effort"],
            item["confidence"],
        ]
        for item in sections["recommendations"]
    ]
    _add_table(
        document,
        ["Priority", "Action", "Target", "Expected benefit", "Effort", "Confidence"],
        recommendation_rows or [["", "No recommendations were returned.", "", "", "", ""]],
    )
    document.add_heading("Quick wins", level=2)
    _add_bullets(document, model.report.quick_wins)
    document.add_page_break()

    document.add_heading("30/60/90-day roadmap", level=1)
    _add_table(
        document,
        ["Window", "Actions"],
        [
            ["30 days", "; ".join(model.report.roadmap.days_30) or "No evidence-specific item supplied."],
            ["60 days", "; ".join(model.report.roadmap.days_60) or "No evidence-specific item supplied."],
            ["90 days", "; ".join(model.report.roadmap.days_90) or "No evidence-specific item supplied."],
        ],
    )
    document.add_page_break()

    architecture = sections["architecture_and_dependencies"]
    document.add_heading("Architecture and dependency analysis", level=1)
    document.add_paragraph(architecture["architecture"]["summary"])
    _add_bullets(document, architecture["architecture"].get("strengths", []))
    _add_bullets(document, architecture["architecture"].get("concerns", []))
    document.add_paragraph(f"Graph metrics: {architecture['graph_stats']}")
    for chart in model.charts:
        if chart.name == "dependency_graph":
            _add_chart(document, chart)
    _add_table(
        document,
        ["Strongly connected component"],
        [[", ".join(component)] for component in architecture["cycle_components"]]
        or [["No cyclic components detected."]],
    )
    document.add_page_break()

    ownership = sections["ownership_and_churn"]
    document.add_heading("Ownership and churn", level=1)
    document.add_paragraph(f"History statistics: {ownership['stats']}")
    for chart in model.charts:
        if chart.name in {"ownership", "commit_timeline"}:
            _add_chart(document, chart)
    _add_table(
        document,
        ["Files", "Co-change commits"],
        [[", ".join(item["files"]), item["cochange_count"]] for item in ownership["temporal_coupling"]]
        or [["No temporal coupling pairs exceeded threshold.", 0]],
    )
    _add_table(
        document,
        ["File", "Commits", "Added", "Deleted"],
        [
            [
                item.get("rel_path", ""),
                item.get("commit_count", 0),
                item.get("lines_added", 0),
                item.get("lines_deleted", 0),
            ]
            for item in ownership["top_files"]
        ]
        or [["No file history available.", 0, 0, 0]],
    )
    document.add_page_break()

    document.add_heading("Testing focus", level=1)
    _add_table(
        document,
        ["File or module", "Reason"],
        [[item["file_or_module"], item["reason"]] for item in sections["testing_focus"]]
        or [["No testing focus returned.", ""]],
    )
    for chart in model.charts:
        if chart.name in {"cc_ranks", "maintainability", "language_roles"}:
            _add_chart(document, chart)
    document.add_page_break()

    quality = sections["data_quality_and_limitations"]
    document.add_heading("Data quality and limitations", level=1)
    _add_table(
        document,
        ["Severity", "Stage", "File", "Message"],
        [
            [item.get("severity", ""), item.get("stage", ""), item.get("file", ""), item.get("message", "")]
            for item in quality["diagnostics"]
        ]
        or [["info", "analysis", "", "No diagnostics were recorded."]],
    )
    _add_bullets(document, quality["limitations"])
    document.add_page_break()

    appendix = sections["appendix"]
    document.add_heading("Appendix: risk formula and methodology", level=1)
    document.add_paragraph(appendix["risk_formula"])
    document.add_paragraph(f"Weights: {appendix['risk_weights']}")
    document.add_paragraph(f"Tier thresholds: {appendix['tier_thresholds']}")
    document.add_paragraph(appendix["methodology"])
    document.save(str(output_path))
    return output_path
