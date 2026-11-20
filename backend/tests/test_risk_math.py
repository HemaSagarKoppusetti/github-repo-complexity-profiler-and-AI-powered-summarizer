# backend/tests/test_risk_math.py
import pytest

from app.core.hotspots import _risk_tier, compute_hotspots


def test_risk_tier_mapping():
    assert _risk_tier(0.85) == "🔴 Critical"
    assert _risk_tier(0.65) == "🔴 Critical"
    assert _risk_tier(0.50) == "🟠 High"
    assert _risk_tier(0.40) == "🟠 High"
    assert _risk_tier(0.30) == "🟡 Medium"
    assert _risk_tier(0.20) == "🟡 Medium"
    assert _risk_tier(0.15) == "🟢 Low"
    assert _risk_tier(0.0) == "🟢 Low"


def test_hotspot_math_and_normalization():
    complexity_data = {
        "results": [
            {
                "filepath": "repo/app/core.py",
                "mi_score": 50.0,
                "mi_rank": "B",
                "avg_cc": 10.0,
                "max_cc": 20,
                "hotspot_fn": "run",
                "error": None,
            },
            {
                "filepath": "repo/app/util.py",
                "mi_score": 100.0,
                "mi_rank": "A",
                "avg_cc": 2.0,
                "max_cc": 2,
                "hotspot_fn": "helper",
                "error": None,
            },
        ]
    }

    churn_data = {
        "file_churn": {
            "app/core.py": {
                "commit_count": 100,
                "churn_rate": 10.0,
                "author_count": 5,
                "last_changed": "2026-06-01",
            },
            "app/util.py": {
                "commit_count": 10,
                "churn_rate": 1.0,
                "author_count": 1,
                "last_changed": "2026-05-01",
            },
        }
    }

    result = compute_hotspots(complexity_data, churn_data, repo_path="repo")
    hotspots = result["hotspots"]
    assert len(hotspots) == 2

    # app/core.py has max commits (100 -> norm 1.0), max CC (20 -> norm 1.0), MI 50 (norm low MI = 0.5)
    # Risk score = 0.50 * 1.0 + 0.30 * 1.0 + 0.20 * 0.5 = 0.50 + 0.30 + 0.10 = 0.90 -> Critical
    core_hotspot = next(h for h in hotspots if "core.py" in h["rel_path"])
    assert core_hotspot["risk_score"] == pytest.approx(0.90, abs=0.01)
    assert core_hotspot["risk_tier"] == "🔴 Critical"

    summary = result["summary"]
    assert summary["total_files_scored"] == 2
    assert summary["critical_count"] == 1


def test_hotspot_zero_division_guard():
    # Test case where all commits and CC are zero
    complexity_data = {
        "results": [
            {
                "filepath": "repo/empty.py",
                "mi_score": 100.0,
                "mi_rank": "A",
                "avg_cc": 0.0,
                "max_cc": 0,
                "hotspot_fn": None,
                "error": None,
            }
        ]
    }
    churn_data = {
        "file_churn": {
            "empty.py": {
                "commit_count": 0,
                "churn_rate": 0.0,
                "author_count": 0,
                "last_changed": None,
            }
        }
    }

    result = compute_hotspots(complexity_data, churn_data, repo_path="repo")
    assert len(result["hotspots"]) == 1
    # 0 commits (norm 0), 0 cc (norm 0), 100 MI (norm 0) -> risk 0.0
    assert result["hotspots"][0]["risk_score"] == 0.0
    assert result["hotspots"][0]["risk_tier"] == "🟢 Low"


def test_hotspot_empty_manifest():
    result = compute_hotspots({"results": []}, {"file_churn": {}}, repo_path="repo")
    assert result["hotspots"] == []
    assert result["top_hotspots"] == []
    assert result["summary"]["total_files_scored"] == 0
