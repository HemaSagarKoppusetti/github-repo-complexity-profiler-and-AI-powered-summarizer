import json
import re
import zipfile
from pathlib import Path

from docx import Document
from pypdf import PdfReader

from app.core.exporters import export_all
from app.core.exporters.__main__ import main


def _analysis_fixture():
    hotspots = [
        {
            "rel_path": "src/example.py",
            "tier": "High",
            "quadrant": "Active danger",
            "risk_score": 0.7,
            "risk_components": {
                "churn": 0.2,
                "complexity": 0.2,
                "low_mi": 0.1,
                "loc": 0.1,
                "bug_fixes": 0.1,
            },
            "max_cc": 12,
            "mi_score": 48.0,
            "mi_available": True,
            "commit_count": 8,
            "commits_last_90_days": 4,
            "loc": 120,
            "bug_fix_count": 2,
            "top_author_share": 0.75,
            "bus_factor": 1,
            "function_context": [],
        }
    ]
    report = {
        "headline": "The example repository needs focused risk reduction.",
        "health": {"rating": "Watch", "rationale": "One active hotspot has concentrated ownership."},
        "purpose": "A fixture repository used to verify exports.",
        "architecture": {
            "summary": "Two modules form a small cyclic dependency.",
            "strengths": ["The repository has a compact source tree."],
            "concerns": ["The example modules import each other."],
        },
        "key_insights": [
            {
                "title": "A changing module is difficult to maintain.",
                "evidence": ["src/example.py has 8 commits and a maintainability score of 48."],
                "so_what": "Changes may carry elevated regression risk.",
                "likely_cause": "The module may combine several responsibilities.",
                "confidence": "Medium",
            }
        ],
        "risks": [
            {
                "file": "src/example.py",
                "severity": "High",
                "why": "The file combines recent churn and high complexity.",
                "blast_radius": "Callers of the example module.",
                "failure_mode": "A change may introduce regressions.",
            }
        ],
        "recommendations": [
            {
                "priority": "1",
                "action": "Add focused tests around the changing behavior.",
                "target": "src/example.py",
                "expected_benefit": "Reduce regression risk.",
                "effort": "S",
                "confidence": "Medium",
            }
        ],
        "quick_wins": ["Add tests for the active hotspot."],
        "roadmap": {
            "days_30": ["Cover the active hotspot."],
            "days_60": ["Separate import responsibilities."],
            "days_90": ["Review ownership concentration."],
        },
        "testing_focus": [
            {
                "file_or_module": "src/example.py",
                "reason": "It has the highest combined churn and complexity in this fixture.",
            }
        ],
        "limitations": [
            "The fixture contains no runtime telemetry.",
            "Reference https://example.com is not part of this offline report.",
        ],
    }
    return {
        "repo_name": "example-repository",
        "data": {
            "report_json": report,
            "manifest": {
                "total_files": 2,
                "total_loc": 160,
                "language_breakdown": {"Python": 2},
                "role_breakdown": {"source": 2},
                "diagnostics": [],
            },
            "complexity": {
                "summary": {
                    "avg_mi_score": 48,
                    "rank_distribution": {"A": 4, "B": 2, "C": 1},
                },
                "results": [
                    {
                        "rel_path": "src/example.py",
                        "language": "Python",
                        "mi_available": True,
                        "mi_score": 48,
                        "error": None,
                    }
                ],
            },
            "graph": {
                "nodes": ["src.example", "src.helper"],
                "edges": [["src.example", "src.helper"], ["src.helper", "src.example"]],
                "cycle_components": [["src.example", "src.helper"]],
                "hub_modules": [{"module": "src.example", "fan_in": 1, "fan_out": 1, "instability": 0.5}],
                "stats": {"cycle_count": 1, "node_count": 2, "edge_count": 2},
            },
            "churn": {
                "stats": {"total_commits": 8, "total_authors": 2, "analysed_window": "8 commits"},
                "commits_by_month": [{"month": "2026-01", "commits": 4}],
                "most_churned": [
                    {
                        "rel_path": "src/example.py",
                        "commit_count": 8,
                        "lines_added": 40,
                        "lines_deleted": 10,
                    }
                ],
                "temporal_coupling": [
                    {
                        "files": ["src/example.py", "src/helper.py"],
                        "cochange_count": 4,
                    }
                ],
            },
            "hotspots": {
                "hotspots": hotspots,
                "top_hotspots": hotspots,
                "summary": {
                    "quadrant_counts": {"Active danger": 1},
                    "risk_weights": {"churn": 0.5, "complexity": 0.3, "low_mi": 0.2},
                },
            },
            "diagnostics": [
                {
                    "stage": "scan",
                    "file": "src/example.py",
                    "severity": "info",
                    "message": "Fixture diagnostic.",
                }
            ],
        },
    }


def test_export_all_generates_searchable_pdf_html_and_docx(tmp_path: Path):
    files = export_all(_analysis_fixture(), out_dir=tmp_path)

    assert set(files) == {"pdf", "html", "docx"}
    assert all(path.is_file() for path in files.values())

    pdf = PdfReader(str(files["pdf"]))
    pdf_text = "\n".join(page.extract_text() or "" for page in pdf.pages)
    assert len(pdf.pages) >= 4
    assert "example-repository" in pdf_text
    assert "Executive summary" in pdf_text

    html = files["html"].read_text(encoding="utf-8")
    assert html.count("data:image/png;base64,") >= 6
    assert not re.search(r"https?://", html, re.IGNORECASE)
    assert "[external URL omitted]" in html

    document = Document(files["docx"])
    paragraphs = "\n".join(paragraph.text for paragraph in document.paragraphs)
    assert len(document.inline_shapes) >= 6
    assert "Executive summary" in paragraphs
    assert "Data quality and limitations" in paragraphs
    assert "Appendix: risk formula and methodology" in paragraphs

    with zipfile.ZipFile(files["docx"]) as archive:
        assert "word/comments.xml" in archive.namelist()


def test_export_cli_writes_selected_format(tmp_path: Path):
    source = tmp_path / "analysis.json"
    source.write_text(json.dumps(_analysis_fixture()), encoding="utf-8")
    output_directory = tmp_path / "reports"

    assert (
        main(
            [
                str(source),
                "--formats",
                "html",
                "--out",
                str(output_directory),
            ]
        )
        == 0
    )
    assert (output_directory / "example-repository_report.html").is_file()
