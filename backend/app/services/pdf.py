# backend/app/services/pdf.py
"""PDF report generator using fpdf2."""

from __future__ import annotations

import io
import logging
from typing import Any

from fpdf import FPDF

logger = logging.getLogger(__name__)


def _clean_text(text: str) -> str:
    """Sanitizes text for standard Latin-1 PDF core fonts."""
    if not text:
        return ""
    replacements = {
        "—": "-",
        "–": "-",
        "“": '"',
        "”": '"',
        "’": "'",
        "‘": "'",
        "•": "*",
        "…": "...",
        "🔴": "[Critical]",
        "🟠": "[High]",
        "🟡": "[Medium]",
        "🟢": "[Low]",
        "✅": "[OK]",
        "⚠️": "[Warning]",
        "❌": "[Error]",
        "🔍": "",
        "⚙️": "",
        "📊": "",
        "🔀": "",
        "📈": "",
        "🎯": "",
        "🤖": "",
        "📥": "",
        "🗂️": "",
        "📄": "",
        "🎉": "",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    # Ensure all chars are valid in latin-1
    return text.encode("latin-1", "replace").decode("latin-1")


class ReportPDF(FPDF):
    def __init__(self, repo_name: str) -> None:
        super().__init__(orientation="P", unit="mm", format="A4")
        self.repo_name = _clean_text(repo_name)
        self.set_auto_page_break(auto=True, margin=15)

    def header(self) -> None:
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(120, 120, 120)
        self.cell(0, 8, f"GitHub Complexity Profiler - {self.repo_name}", border=0, align="L")
        self.ln(8)

    def footer(self) -> None:
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 10, f"Page {self.page_no()}", border=0, align="C")


def generate_pdf_report(analysis_data: dict[str, Any], repo_name: str, report_text: str | None) -> bytes:
    """Generates an executive PDF report containing KPIs, Hotspots, Complex Functions, and AI Summary."""
    pdf = ReportPDF(repo_name=repo_name)
    pdf.add_page()

    # Title Banner
    pdf.set_font("Helvetica", "B", 20)
    pdf.set_text_color(30, 41, 59)
    pdf.cell(0, 12, _clean_text(f"Repository Analysis: {repo_name}"), ln=True)

    github_url = analysis_data.get("github_url", "")
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(100, 116, 139)
    pdf.cell(0, 6, _clean_text(f"URL: {github_url}"), ln=True)
    pdf.ln(4)

    # 1. Executive Summary & KPIs
    pdf.set_font("Helvetica", "B", 13)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(0, 8, "1. Executive Summary & Key Metrics", ln=True)
    pdf.ln(2)

    manifest = analysis_data.get("manifest", {})
    churn_stats = analysis_data.get("churn", {}).get("stats", {})
    comp_sum = analysis_data.get("complexity", {}).get("summary", {})
    graph_stats = analysis_data.get("graph", {}).get("stats", {})
    h_sum = analysis_data.get("hotspots", {}).get("summary", {})

    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(51, 65, 85)

    kpis = [
        ("Total Files", str(manifest.get("total_files", 0))),
        ("Total LOC", f"{manifest.get('total_loc', 0):,}"),
        ("Total Commits", str(churn_stats.get("total_commits", 0))),
        ("Contributors", str(churn_stats.get("total_authors", 0))),
        ("Repo Age", f"{churn_stats.get('repo_age_days', 0)} days"),
        ("Avg Maintainability", f"{comp_sum.get('avg_mi_score', 0)} / 100"),
        ("Circular Dependencies", str(graph_stats.get("cycle_count", 0))),
        ("Critical Hotspots", str(h_sum.get("critical_count", 0))),
    ]

    # Render KPI grid (2 columns)
    row_height = 6
    for i in range(0, len(kpis), 2):
        k1, v1 = kpis[i]
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(40, row_height, k1 + ":", border=1)
        pdf.set_font("Helvetica", "", 9)
        pdf.cell(45, row_height, "  " + v1, border=1)

        if i + 1 < len(kpis):
            k2, v2 = kpis[i + 1]
            pdf.cell(10, row_height, "")  # gap
            pdf.set_font("Helvetica", "B", 9)
            pdf.cell(40, row_height, k2 + ":", border=1)
            pdf.set_font("Helvetica", "", 9)
            pdf.cell(45, row_height, "  " + v2, border=1)
        pdf.ln(row_height)

    pdf.ln(6)

    # 2. Hotspots Ranking Table
    pdf.set_font("Helvetica", "B", 13)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(0, 8, "2. Ranked Hotspot Risk Files", ln=True)
    pdf.ln(2)

    hotspots = analysis_data.get("hotspots", {}).get("hotspots", [])[:10]
    if hotspots:
        # Table Header
        pdf.set_font("Helvetica", "B", 8)
        pdf.set_fill_color(241, 245, 249)
        pdf.cell(20, 6, "Tier", border=1, fill=True)
        pdf.cell(85, 6, "File", border=1, fill=True)
        pdf.cell(20, 6, "Risk Score", border=1, fill=True, align="R")
        pdf.cell(18, 6, "Commits", border=1, fill=True, align="R")
        pdf.cell(18, 6, "Max CC", border=1, fill=True, align="R")
        pdf.cell(18, 6, "MI Score", border=1, fill=True, align="R")
        pdf.ln(6)

        pdf.set_font("Helvetica", "", 8)
        for h in hotspots:
            tier = h.get("risk_tier", "").replace("🔴", "").replace("🟠", "").replace("🟡", "").replace("🟢", "").strip()
            rel_path = h.get("rel_path", "")
            if len(rel_path) > 48:
                rel_path = "..." + rel_path[-45:]

            pdf.cell(20, 6, tier, border=1)
            pdf.cell(85, 6, rel_path, border=1)
            pdf.cell(20, 6, f"{h.get('risk_score', 0):.4f}", border=1, align="R")
            pdf.cell(18, 6, str(h.get("commit_count", 0)), border=1, align="R")
            pdf.cell(18, 6, str(h.get("max_cc", 0)), border=1, align="R")
            pdf.cell(18, 6, str(h.get("mi_score", 0)), border=1, align="R")
            pdf.ln(6)
    else:
        pdf.set_font("Helvetica", "I", 9)
        pdf.cell(0, 6, "No hotspot files detected.", ln=True)

    pdf.ln(6)

    # 3. Top Complex Functions
    pdf.set_font("Helvetica", "B", 13)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(0, 8, "3. Top Complex Functions (Radon)", ln=True)
    pdf.ln(2)

    top_fns = comp_sum.get("top_complex_functions", [])
    if top_fns:
        pdf.set_font("Helvetica", "B", 8)
        pdf.set_fill_color(241, 245, 249)
        pdf.cell(60, 6, "Function Name", border=1, fill=True)
        pdf.cell(80, 6, "File", border=1, fill=True)
        pdf.cell(20, 6, "CC", border=1, fill=True, align="R")
        pdf.cell(20, 6, "Line", border=1, fill=True, align="R")
        pdf.ln(6)

        pdf.set_font("Helvetica", "", 8)
        for fn in top_fns:
            fp = fn.get("filepath", "")
            fname = fp.split("\\")[-1].split("/")[-1]
            pdf.cell(60, 6, f"{fn.get('name', '')}()", border=1)
            pdf.cell(80, 6, fname, border=1)
            pdf.cell(20, 6, str(fn.get("complexity", 0)), border=1, align="R")
            pdf.cell(20, 6, str(fn.get("lineno", 0)), border=1, align="R")
            pdf.ln(6)
    else:
        pdf.set_font("Helvetica", "I", 9)
        pdf.cell(0, 6, "No complex functions found.", ln=True)

    pdf.ln(6)

    # 4. AI Architectural Review Report
    if report_text:
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 13)
        pdf.set_text_color(15, 23, 42)
        pdf.cell(0, 8, "4. AI Code Architecture & Risk Review", ln=True)
        pdf.ln(3)

        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(51, 65, 85)

        for line in report_text.splitlines():
            clean_line = _clean_text(line.strip())
            if not clean_line:
                pdf.ln(3)
                continue

            if clean_line.startswith("## "):
                pdf.ln(2)
                pdf.set_font("Helvetica", "B", 11)
                pdf.set_text_color(30, 41, 59)
                pdf.cell(0, 6, clean_line[3:], ln=True)
                pdf.set_font("Helvetica", "", 9)
                pdf.set_text_color(51, 65, 85)
            elif clean_line.startswith("# "):
                pdf.set_font("Helvetica", "B", 12)
                pdf.cell(0, 7, clean_line[2:], ln=True)
                pdf.set_font("Helvetica", "", 9)
            elif clean_line.startswith("- "):
                pdf.multi_cell(0, 5, "  * " + clean_line[2:])
            else:
                pdf.multi_cell(0, 5, clean_line)

    buffer = io.BytesIO()
    pdf.output(buffer)
    return buffer.getvalue()
