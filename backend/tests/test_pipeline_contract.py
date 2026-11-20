import time

from app.core.pipeline import ManifestData, preflight, run_stage


def test_run_stage_validates_and_returns_schema_defaults():
    result = run_stage("scan", lambda: {"total_files": 2}, 1, {}, ManifestData)

    assert result.status == "ok"
    assert result.data["total_files"] == 2
    assert result.data["python_files"] == []


def test_run_stage_malformed_output_uses_schema_valid_fallback():
    result = run_stage(
        "scan",
        lambda: {"total_files": "not-an-integer"},
        1,
        {"files": [], "total_files": 0, "total_loc": 0, "python_files": []},
        ManifestData,
    )

    assert result.status == "failed"
    assert result.data["total_files"] == 0
    assert result.errors


def test_run_stage_exception_and_timeout_are_recorded():
    failed = run_stage("graph", lambda: 1 / 0, 1, {"nodes": []})
    timed_out = run_stage(
        "churn", lambda: time.sleep(0.2), 0.01, {"file_churn": {}}
    )

    assert failed.status == "failed"
    assert failed.data == {"nodes": []}
    assert timed_out.status == "failed"
    assert timed_out.data == {"file_churn": {}}
    assert timed_out.errors


def test_preflight_validates_url_and_warns_when_ai_is_not_configured():
    invalid = preflight("https://example.com/owner/repo", llm_key="")
    valid = preflight("https://github.com/pallets/markupsafe", llm_key="")

    assert invalid["ok"] is False
    assert valid["checks"]["url"] is True
    assert valid["checks"]["llm"] is False
    assert any("AI report skipped" in warning for warning in valid["warnings"])
