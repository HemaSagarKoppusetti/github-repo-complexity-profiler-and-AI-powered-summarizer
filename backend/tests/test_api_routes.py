# backend/tests/test_api_routes.py
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.db.database import SessionLocal, init_db
from app.db.models import Analysis
from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_db():
    init_db()
    db = SessionLocal()
    db.query(Analysis).delete()
    db.commit()
    db.close()
    yield


def test_health_route():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "llm" in data
    assert "version" in data


def test_create_analysis_validation_failure():
    # Bad URL (not https or bad domain)
    response = client.post("/api/analyses", json={"github_url": "http://invalidsite.com/foo/bar"})
    assert response.status_code == 422
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "VALIDATION_ERROR"


def test_list_analyses_empty():
    response = client.get("/api/analyses")
    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["total"] == 0
    assert data["page"] == 1


def test_get_analysis_not_found():
    response = client.get("/api/analyses/non-existent-id")
    assert response.status_code == 404
    data = response.json()
    assert data["error"]["code"] == "NOT_FOUND"


def test_get_analysis_detail_and_exports():
    # Seed a completed record into DB
    db = SessionLocal()
    sample_analysis = Analysis(
        id="test-job-uuid",
        github_url="https://github.com/pallets/markupsafe",
        repo_name="markupsafe",
        status="completed",
        stage="completed",
        percent=100,
        report_status="completed",
        report_text="# Test Report Content\n## 1. What This Codebase Does\nTest summary.",
        created_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
        duration_seconds=12.5,
    )
    sample_analysis.set_result({
        "manifest": {"total_files": 10, "total_loc": 500, "python_files": ["src/markupsafe/__init__.py"]},
        "complexity": {
            "summary": {"total_files_analysed": 1, "total_functions": 5, "avg_mi_score": 75.0, "top_complex_functions": []}
        },
        "churn": {
            "stats": {"total_commits": 100, "total_authors": 5, "repo_age_days": 300}
        },
        "graph": {
            "stats": {"node_count": 2, "edge_count": 1, "cycle_count": 0}
        },
        "hotspots": {
            "hotspots": [
                {
                    "rel_path": "src/markupsafe/__init__.py",
                    "risk_tier": "🔴 Critical",
                    "risk_score": 0.85,
                    "commit_count": 50,
                    "max_cc": 15,
                    "mi_score": 45.0,
                    "author_count": 3,
                }
            ],
            "top_hotspots": [],
            "summary": {"critical_count": 1, "high_count": 0, "medium_count": 0, "low_count": 0}
        }
    })
    db.add(sample_analysis)
    db.commit()
    db.close()

    # GET detail
    res_detail = client.get("/api/analyses/test-job-uuid")
    assert res_detail.status_code == 200
    detail_data = res_detail.json()
    assert detail_data["id"] == "test-job-uuid"
    assert detail_data["repo_name"] == "markupsafe"
    assert detail_data["result"] is not None

    # GET export.json
    res_export = client.get("/api/analyses/test-job-uuid/export.json")
    assert res_export.status_code == 200
    assert "application/json" in res_export.headers["content-type"]
    exported = res_export.json()
    assert exported["id"] == "test-job-uuid"
    assert "data" in exported

    # GET report.md
    res_md = client.get("/api/analyses/test-job-uuid/report.md")
    assert res_md.status_code == 200
    assert "text/markdown" in res_md.headers["content-type"]
    assert "Test Report Content" in res_md.text

    # GET report.pdf
    res_pdf = client.get("/api/analyses/test-job-uuid/report.pdf")
    assert res_pdf.status_code == 200
    assert "application/pdf" in res_pdf.headers["content-type"]
    assert res_pdf.content[:4] == b"%PDF"

    # DELETE
    res_del = client.get("/api/analyses/test-job-uuid")
    assert res_del.status_code == 200
    res_delete = client.delete("/api/analyses/test-job-uuid")
    assert res_delete.status_code == 200

    # Ensure deleted
    res_after = client.get("/api/analyses/test-job-uuid")
    assert res_after.status_code == 404
