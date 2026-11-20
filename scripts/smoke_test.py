#!/usr/bin/env python3
"""End-to-End Smoke Test Script.

Analyses https://github.com/pallets/markupsafe end-to-end and asserts that
'src/markupsafe/__init__.py' is identified as a Critical or High risk hotspot.
"""

from __future__ import annotations

import os
import sys
import time
import uuid

# Add backend directory to sys.path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
BACKEND_DIR = os.path.join(PROJECT_ROOT, "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.db.database import SessionLocal, init_db  # noqa: E402
from app.db.models import Analysis  # noqa: E402
from app.services.pipeline import run_analysis  # noqa: E402


def run_smoke_test() -> None:
    print("=" * 70)
    print("🚀 [SMOKE TEST] End-to-End Pipeline Verification")
    print("=" * 70)

    target_repo = "https://github.com/pallets/markupsafe"
    print(f"Target repository: {target_repo}")

    init_db()
    db = SessionLocal()

    job_id = str(uuid.uuid4())
    job = Analysis(
        id=job_id,
        github_url=target_repo,
        repo_name="markupsafe",
        status="queued",
        stage="queued",
        percent=0,
    )
    db.add(job)
    db.commit()
    db.close()

    print(f"Created smoke test job ID: {job_id}")
    print("Executing 7-stage pipeline (clone, scan, complexity, graph, churn, hotspots, report)...")

    start_time = time.time()
    run_analysis(job_id=job_id, github_url=target_repo, top_n=10)
    elapsed = time.time() - start_time

    print(f"Pipeline completed in {elapsed:.2f} seconds.")

    # Retrieve and verify results
    db = SessionLocal()
    completed_job = db.query(Analysis).filter(Analysis.id == job_id).first()

    assert completed_job is not None, "Job record not found in database!"
    assert completed_job.status == "completed", f"Job failed with status '{completed_job.status}': {completed_job.error}"
    assert completed_job.percent == 100, f"Job percent is {completed_job.percent}, expected 100"

    result = completed_job.get_result()
    assert result is not None, "Analysis result_json is empty!"

    hotspots = result.get("hotspots", {}).get("hotspots", [])
    print(f"\nDiscovered {len(hotspots)} hotspot files.")

    target_file = "src/markupsafe/__init__.py"
    target_hotspot = next(
        (h for h in hotspots if h["rel_path"].replace("\\", "/") == target_file),
        None,
    )

    assert target_hotspot is not None, f"Expected hotspot '{target_file}' not found in results! Found: {[h['rel_path'] for h in hotspots]}"

    tier = target_hotspot.get("risk_tier", "")
    score = target_hotspot.get("risk_score", 0.0)
    commits = target_hotspot.get("commit_count", 0)
    max_cc = target_hotspot.get("max_cc", 0)
    mi_score = target_hotspot.get("mi_score", 0.0)

    print(f"\nTarget File: {target_file}")
    print(f"Risk Tier  : {tier}")
    print(f"Risk Score : {score}")
    print(f"Commits    : {commits}")
    print(f"Max CC     : {max_cc}")
    print(f"MI Score   : {mi_score}")

    assert "Critical" in tier or "High" in tier, (
        f"Assertion failed: '{target_file}' tier was expected to be Critical or High, but got '{tier}' (score: {score})"
    )

    print("\n" + "=" * 70)
    print("✅ SMOKE TEST PASSED: All acceptance assertions satisfied!")
    print("=" * 70)
    db.close()


if __name__ == "__main__":
    try:
        run_smoke_test()
    except Exception as e:
        print(f"\n❌ SMOKE TEST FAILED: {e}", file=sys.stderr)
        sys.exit(1)
