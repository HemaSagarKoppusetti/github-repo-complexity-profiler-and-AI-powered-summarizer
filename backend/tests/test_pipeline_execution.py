import subprocess

import pytest

from app.config import settings
from app.db.database import SessionLocal, init_db
from app.db.models import Analysis
from app.services import pipeline


def _tracked_repo(path):
    path.mkdir()
    subprocess.run(["git", "init", str(path)], check=True, capture_output=True, timeout=10)
    subprocess.run(["git", "-C", str(path), "config", "user.email", "test@example.com"], check=True, timeout=10)
    subprocess.run(["git", "-C", str(path), "config", "user.name", "Test"], check=True, timeout=10)
    (path / "module.py").write_text("def run(value):\n    return value\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(path), "add", "."], check=True, timeout=10)


def _create_job(job_id):
    init_db()
    db = SessionLocal()
    db.query(Analysis).filter(Analysis.id == job_id).delete()
    db.add(Analysis(
        id=job_id,
        github_url="https://github.com/pallets/markupsafe",
        repo_name="markupsafe",
        status="queued",
        stage="queued",
        percent=0,
    ))
    db.commit()
    db.close()


@pytest.mark.parametrize(
    ("stage_name", "patch_name"),
    [
        ("scan", "scan_repo"),
        ("complexity", "analyse_all"),
        ("graph", "build_dependency_graph"),
        ("churn", "analyse_churn"),
        ("hotspots", "compute_hotspots"),
    ],
)
def test_pipeline_stage_exceptions_degrade_to_diagnostics(
    tmp_path, monkeypatch, stage_name, patch_name
):
    job_id = f"stage-failure-{stage_name}"
    _create_job(job_id)
    repo = tmp_path / "repo"
    _tracked_repo(repo)
    monkeypatch.setattr(settings, "LLM_PROVIDER", "mock")
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", "")
    monkeypatch.setattr(
        pipeline,
        "clone_repo",
        lambda **kwargs: {"success": True, "path": str(repo), "name": "repo", "url": "https://github.com/pallets/markupsafe"},
    )
    monkeypatch.setattr(pipeline, "cleanup_repo", lambda path: None)

    def fail(*args, **kwargs):
        raise RuntimeError(f"injected {stage_name} error")

    monkeypatch.setattr(pipeline, patch_name, fail)
    pipeline.run_analysis(job_id, "https://github.com/pallets/markupsafe")

    db = SessionLocal()
    try:
        job = db.query(Analysis).filter(Analysis.id == job_id).first()
        result = job.get_result()
        assert job.status == "completed"
        assert any(item["stage"] == stage_name for item in result["diagnostics"])
        assert all("Traceback" not in item["message"] for item in result["diagnostics"])
        assert result["report_json"] is not None
    finally:
        db.query(Analysis).filter(Analysis.id == job_id).delete()
        db.commit()
        db.close()


def test_clone_failure_persists_structured_error_without_traceback(tmp_path, monkeypatch):
    job_id = "clone-failure-structured"
    _create_job(job_id)
    monkeypatch.setattr(settings, "LLM_PROVIDER", "mock")
    monkeypatch.setattr(pipeline, "clone_repo", lambda **kwargs: {
        "success": False,
        "path": None,
        "name": "markupsafe",
        "url": "https://github.com/pallets/markupsafe",
        "error": "Repository unavailable",
    })

    pipeline.run_analysis(job_id, "https://github.com/pallets/markupsafe")

    db = SessionLocal()
    try:
        job = db.query(Analysis).filter(Analysis.id == job_id).first()
        result = job.get_result()
        assert job.status == "failed"
        assert result["error"]["message"] == "Repository unavailable"
        assert "Traceback" not in job.error
    finally:
        db.query(Analysis).filter(Analysis.id == job_id).delete()
        db.commit()
        db.close()
