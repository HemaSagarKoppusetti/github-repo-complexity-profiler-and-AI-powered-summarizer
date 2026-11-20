from app.core.summariser import (
    AIReport,
    _fit_evidence_budget,
    build_evidence_pack,
    generate_structured_report,
    repair_json_response,
    validate_citations,
)
from app.services.llm import MockLLMClient


def _evidence():
    return {
        "repo": {"name": "sample", "analysed_window": "2026-01-01 to 2026-02-01", "history_truncated": False},
        "data_quality": {"diagnostics_count": 0, "flags": [], "stages_with_gaps": []},
        "kpis": {"total_files": 2, "commits": 3, "average_mi": 60.0},
        "top_hotspots": [{
            "rel_path": "src/module.py",
            "risk_score": 0.8,
            "tier": "Critical",
            "commit_count": 3,
            "max_cc": 12,
            "function_context": [{"name": "run", "signature": "run(value)", "docstring": "Execute the operation."}],
        }],
        "package_aggregates": [{"package": "src", "top_files": ["src/module.py"]}],
    }


def test_json_repair_extracts_fenced_object_and_trailing_commas():
    parsed = repair_json_response('answer:\n```json\n{"headline":"ok", "items":[1,2,],}\n```')
    assert parsed == {"headline": "ok", "items": [1, 2]}


def test_citation_validation_removes_unverified_file_and_function():
    report = AIReport.model_validate({
        "headline": "Review src/module.py and other.py after run() and invented().",
        "health": {"rating": "Watch", "rationale": "Evidence shows 3 commits."},
        "purpose": "Inspect the supplied module.",
        "risks": [{
            "file": "other.py",
            "severity": "High",
            "why": "Unknown file",
            "blast_radius": "Unknown",
            "failure_mode": "Unknown",
        }],
        "recommendations": [{
            "priority": "P1",
            "action": "Inspect run().",
            "target": "src/module.py",
            "expected_benefit": "Grounded in 12 complexity.",
            "effort": "S",
            "confidence": "Medium",
        }],
    })

    cleaned, diagnostics = validate_citations(report, _evidence())
    encoded = cleaned.model_dump_json()
    assert "other.py" not in encoded
    assert "invented()" not in encoded
    assert "[unverified file omitted]" in encoded
    assert len(diagnostics) >= 2
    assert cleaned.recommendations[0].effort == "S"
    assert cleaned.recommendations[0].confidence == "Medium"


def test_evidence_pack_contains_hotspots_cycles_ownership_and_quality():
    evidence = build_evidence_pack(
        "sample",
        {"total_files": 1, "total_loc": 10, "language_breakdown": {"Python": 1}, "role_breakdown": {"source": 1}},
        {"summary": {"total_python_files_analysed": 1, "total_functions": 1, "avg_mi_score": 75}},
        {"stats": {"total_commits": 2, "analysed_window": "window"}, "temporal_coupling": []},
        {"stats": {"cycle_count": 1}, "cycle_components": [["pkg.a", "pkg.b"]]},
        {"hotspots": [{
            "rel_path": "pkg/a.py", "risk_score": 0.7, "max_cc": 9,
            "bus_factor": 1, "top_author_share": 1.0, "function_context": [],
        }]},
        [{"stage": "scan", "message": "One file was skipped."}],
    )

    assert evidence["scc_cycles"] == [["pkg.a", "pkg.b"]]
    assert evidence["ownership_outliers"][0]["bus_factor"] == 1
    assert evidence["diagnostics"][0]["message"] == "One file was skipped."


def test_evidence_budget_truncates_low_priority_tail():
    evidence = _evidence()
    evidence["diagnostics"] = [{"message": "tail " * 5000}]

    packed, truncated = _fit_evidence_budget(evidence, 100, "openrouter/free")

    assert truncated
    assert "top_hotspots" in packed
    assert "diagnostics" not in packed


def test_mock_structured_report_validates_and_renders():
    report, diagnostics = generate_structured_report(_evidence(), MockLLMClient())

    assert report.headline
    assert isinstance(report, AIReport)
    assert diagnostics == []
