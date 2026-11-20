# backend/app/core/hotspots.py
"""Combines complexity (radon) and churn (git) into a per-file risk score.

Risk = 0.50 * churn + 0.30 * complexity + 0.20 * low_maintainability
"""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


def _risk_tier(score: float) -> str:
    """Maps a 0–1 risk score to a human-readable tier."""
    if score >= 0.65:
        return "🔴 Critical"
    elif score >= 0.40:
        return "🟠 High"
    elif score >= 0.20:
        return "🟡 Medium"
    else:
        return "🟢 Low"


def compute_hotspots(
    complexity_data: dict[str, Any],
    churn_data: dict[str, Any],
    repo_path: str,
    top_n: int = 10,
) -> dict[str, Any]:
    """Merges complexity and churn results into a ranked hotspot list.

    Args:
        complexity_data: output from complexity.analyse_all()
        churn_data: output from churn.analyse_churn()
        repo_path: local repo path (for rel_path normalisation)
        top_n: how many hotspots to return in top_hotspots (default 10)

    Returns:
        dict with hotspots, top_hotspots, summary
    """
    logger.info("[hotspots] Computing risk scores...")

    file_churn = churn_data.get("file_churn", {})

    # Build lookup from rel_path -> complexity result
    complexity_lookup = {}
    for result in complexity_data.get("results", []):
        rel = os.path.relpath(result["filepath"], repo_path).replace("\\", "/")
        complexity_lookup[rel] = result

    merged = []
    for rel_path, churn in file_churn.items():
        norm_rel = rel_path.replace("\\", "/")
        cc_data = complexity_lookup.get(norm_rel)
        if cc_data is None:
            # Try alternate slash match
            for k, v in complexity_lookup.items():
                if k.endswith(norm_rel) or norm_rel.endswith(k):
                    cc_data = v
                    break

        if cc_data is None:
            continue

        merged.append({
            "rel_path": norm_rel,
            "commit_count": churn.get("commit_count", 0),
            "churn_rate": churn.get("churn_rate", 0.0),
            "author_count": churn.get("author_count", 0),
            "last_changed": churn.get("last_changed"),
            "mi_score": cc_data.get("mi_score", 100.0),
            "mi_rank": cc_data.get("mi_rank", "A"),
            "avg_cc": cc_data.get("avg_cc", 0.0),
            "max_cc": cc_data.get("max_cc", 0),
            "hotspot_fn": cc_data.get("hotspot_fn"),
            "loc": 0,
        })

    if not merged:
        logger.info("[hotspots] ⚠️ No files to score")
        return {
            "hotspots": [],
            "top_hotspots": [],
            "summary": {
                "total_files_scored": 0,
                "critical_count": 0,
                "high_count": 0,
                "medium_count": 0,
                "low_count": 0,
                "top_hotspot": None,
                "top_hotspot_fn": None,
                "critical_files": [],
            },
        }

    # Normalise dimensions to [0, 1] with safe divide-by-zero guards
    commit_counts = [f["commit_count"] for f in merged]
    max_commits = max(commit_counts) if commit_counts and max(commit_counts) > 0 else 1

    ccs = [f["max_cc"] for f in merged]
    max_cc = max(ccs) if ccs and max(ccs) > 0 else 1

    for f in merged:
        norm_churn = f["commit_count"] / max_commits
        norm_complexity = f["max_cc"] / max_cc

        # Invert MI: low MI (0) = 1.0 risk, high MI (100) = 0.0 risk
        mi_score = max(0.0, min(100.0, float(f["mi_score"])))
        norm_low_mi = 1.0 - (mi_score / 100.0)

        f["risk_score"] = round(
            (0.50 * norm_churn) + (0.30 * norm_complexity) + (0.20 * norm_low_mi),
            4,
        )
        f["risk_tier"] = _risk_tier(f["risk_score"])

    # Sort by risk score descending
    hotspots = sorted(merged, key=lambda x: x["risk_score"], reverse=True)
    top_hotspots = hotspots[:top_n]

    critical = [f for f in hotspots if f["risk_tier"] == "🔴 Critical"]
    high = [f for f in hotspots if f["risk_tier"] == "🟠 High"]
    medium = [f for f in hotspots if f["risk_tier"] == "🟡 Medium"]
    low = [f for f in hotspots if f["risk_tier"] == "🟢 Low"]

    summary = {
        "total_files_scored": len(hotspots),
        "critical_count": len(critical),
        "high_count": len(high),
        "medium_count": len(medium),
        "low_count": len(low),
        "top_hotspot": hotspots[0]["rel_path"] if hotspots else None,
        "top_hotspot_fn": hotspots[0]["hotspot_fn"] if hotspots else None,
        "critical_files": [f["rel_path"] for f in critical],
    }

    logger.info(
        "[hotspots] ✅ %d files scored | 🔴 %d critical | 🟠 %d high | 🟡 %d medium | 🟢 %d low",
        len(hotspots),
        len(critical),
        len(high),
        len(medium),
        len(low),
    )

    return {
        "hotspots": hotspots,
        "top_hotspots": top_hotspots,
        "summary": summary,
    }
