"""Percentile-normalized, multi-signal engineering risk ranking."""

from __future__ import annotations

import logging
import os
from collections.abc import Mapping, Sequence
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_WEIGHTS = {
    "churn": 0.40,
    "complexity": 0.25,
    "low_mi": 0.15,
    "loc": 0.10,
    "bug_fixes": 0.10,
}
TIER_LABELS = {
    "Critical": "🔴 Critical",
    "High": "🟠 High",
    "Medium": "🟡 Medium",
    "Low": "🟢 Low",
}


def _risk_tier(score: float) -> str:
    """Map a 0–1 score to the legacy emoji tier."""
    if score >= 0.65:
        return TIER_LABELS["Critical"]
    if score >= 0.40:
        return TIER_LABELS["High"]
    if score >= 0.20:
        return TIER_LABELS["Medium"]
    return TIER_LABELS["Low"]


def percentile_normalize(values: Sequence[float]) -> list[float]:
    """Return tie-aware percentile ranks scaled to [0, 1]."""
    if len(values) <= 1 or len(set(values)) <= 1:
        return [0.0 for _ in values]
    denominator = len(values) - 1
    result = []
    for value in values:
        lower = sum(candidate < value for candidate in values)
        equal = sum(candidate == value for candidate in values)
        average_rank = lower + (equal - 1) / 2
        result.append(average_rank / denominator)
    return result


def _plain_tier(score: float) -> str:
    """Return the export-safe textual risk tier."""
    if score >= 0.65:
        return "Critical"
    if score >= 0.40:
        return "High"
    if score >= 0.20:
        return "Medium"
    return "Low"


def _risk_quadrant(churn_rank: float, complexity_rank: float, churn: float, complexity: float) -> str:
    """Classify a file by relative churn and complexity."""
    high_churn = churn > 0 and churn_rank >= 0.5
    high_complexity = complexity > 0 and complexity_rank >= 0.5
    if high_churn and high_complexity:
        return "Active danger"
    if high_complexity:
        return "Fragile but stable"
    if high_churn:
        return "Healthy churn"
    return "Healthy"


def compute_hotspots(
    complexity_data: dict[str, Any],
    churn_data: dict[str, Any],
    repo_path: str,
    top_n: int = 10,
    manifest_files: list[dict[str, Any]] | None = None,
    risk_weights: Mapping[str, float] | None = None,
    include_non_source: bool = False,
) -> dict[str, Any]:
    """Merge complexity and churn metrics into backward-compatible hotspots."""
    logger.info("[hotspots] Computing risk scores...")
    file_churn = churn_data.get("file_churn", {})
    entries = {
        str(entry.get("rel_path", "")).replace("\\", "/"): entry
        for entry in manifest_files or []
    }
    weights = dict(DEFAULT_WEIGHTS)
    if risk_weights:
        weights.update({key: max(0.0, float(value)) for key, value in risk_weights.items() if key in weights})
    weight_total = sum(weights.values())
    if weight_total == 0:
        weights = dict(DEFAULT_WEIGHTS)
        weight_total = sum(weights.values())
    weights = {key: value / weight_total for key, value in weights.items()}

    merged: list[dict[str, Any]] = []
    for result in complexity_data.get("results", []):
        relative = str(result.get("rel_path") or os.path.relpath(result["filepath"], repo_path)).replace("\\", "/")
        entry = entries.get(relative, {})
        role = str(result.get("role") or entry.get("role") or "source")
        if role in {"config", "docs", "generated"} and not include_non_source:
            continue
        churn = file_churn.get(relative, {})
        mi_available = bool(result.get("mi_available", result.get("language", "Python") == "Python"))
        mi_score = float(result.get("mi_score", 100.0)) if mi_available else 100.0
        file_context = entry.get("functions", [])
        complex_functions = sorted(
            result.get("functions", []),
            key=lambda function: function.get("complexity", 0),
            reverse=True,
        )[:3]
        context_by_name = {
            (item.get("name"), item.get("lineno")): item for item in file_context
        }
        function_context = []
        for function in complex_functions:
            source_context = context_by_name.get((function.get("name"), function.get("lineno")), {})
            function_context.append({
                "name": function.get("name", ""),
                "signature": source_context.get("signature", f"{function.get('name', '')}()"),
                "docstring": source_context.get("docstring", ""),
                "complexity": function.get("complexity", 0),
                "lineno": function.get("lineno", 0),
            })

        merged.append({
            "rel_path": relative,
            "language": result.get("language", entry.get("language", "Python")),
            "role": role,
            "commit_count": int(churn.get("commit_count", 0)),
            "lines_added": int(churn.get("lines_added", 0)),
            "lines_deleted": int(churn.get("lines_deleted", 0)),
            "churn_rate": float(churn.get("churn_rate", 0.0)),
            "commits_last_90_days": int(churn.get("commits_last_90_days", 0)),
            "bug_fix_count": int(churn.get("bug_fix_count", 0)),
            "author_count": int(churn.get("author_count", 0)),
            "top_author_share": float(churn.get("top_author_share", 0.0)),
            "bus_factor": int(churn.get("bus_factor", 0)),
            "last_changed": churn.get("last_changed"),
            "mi_score": round(max(0.0, min(100.0, mi_score)), 2),
            "mi_rank": result.get("mi_rank", "N/A"),
            "mi_available": mi_available,
            "avg_cc": float(result.get("avg_cc", 0.0)),
            "max_cc": int(result.get("max_cc", 0)),
            "hotspot_fn": result.get("hotspot_fn"),
            "loc": int(result.get("loc", entry.get("loc", 0))),
            "function_context": function_context,
        })

    if not merged:
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
                "risk_weights": weights,
            },
        }

    churn_values = [float(item["commits_last_90_days"] or item["commit_count"]) for item in merged]
    complexity_values = [float(item["max_cc"]) for item in merged]
    low_mi_values = [100.0 - item["mi_score"] if item["mi_available"] else 0.0 for item in merged]
    loc_values = [float(item["loc"]) for item in merged]
    bug_fix_values = [float(item["bug_fix_count"]) for item in merged]
    churn_ranks = percentile_normalize(churn_values)
    complexity_ranks = percentile_normalize(complexity_values)
    low_mi_ranks = percentile_normalize(low_mi_values)
    loc_ranks = percentile_normalize(loc_values)
    bug_fix_ranks = percentile_normalize(bug_fix_values)

    for index, file_data in enumerate(merged):
        components = {
            "churn": churn_ranks[index],
            "complexity": complexity_ranks[index],
            "low_mi": low_mi_ranks[index],
            "loc": loc_ranks[index],
            "bug_fixes": bug_fix_ranks[index],
        }
        role_factor = {"test": 0.6, "config": 0.35, "docs": 0.2}.get(file_data["role"], 1.0)
        score = sum(weights[key] * components[key] for key in weights) * role_factor
        score = round(max(0.0, min(1.0, score)), 4)
        tier = _plain_tier(score)
        file_data.update({
            "risk_components": components,
            "risk_score": score,
            "risk_tier": TIER_LABELS[tier],
            "tier": tier,
            "quadrant": _risk_quadrant(
                churn_ranks[index],
                complexity_ranks[index],
                churn_values[index],
                complexity_values[index],
            ),
        })

    ranked = sorted(merged, key=lambda item: (-item["risk_score"], item["rel_path"]))
    top_hotspots = ranked[:max(0, top_n)]
    top_paths = {item["rel_path"] for item in ranked[:15]}
    for item in ranked:
        if item["rel_path"] not in top_paths:
            item.pop("function_context", None)
    tiers = {tier: [item for item in ranked if item["tier"] == tier] for tier in TIER_LABELS}
    quadrants = {
        label: sum(item["quadrant"] == label for item in ranked)
        for label in ("Active danger", "Fragile but stable", "Healthy churn", "Healthy")
    }
    summary = {
        "total_files_scored": len(ranked),
        "critical_count": len(tiers["Critical"]),
        "high_count": len(tiers["High"]),
        "medium_count": len(tiers["Medium"]),
        "low_count": len(tiers["Low"]),
        "top_hotspot": ranked[0]["rel_path"],
        "top_hotspot_fn": ranked[0]["hotspot_fn"],
        "critical_files": [item["rel_path"] for item in tiers["Critical"]],
        "quadrant_counts": quadrants,
        "risk_weights": weights,
        "risk_formula": "Percentile ranks: "
        + ", ".join(f"{key}={value:.0%}" for key, value in weights.items())
        + "; tests/config/docs are down-weighted.",
    }
    return {"hotspots": ranked, "top_hotspots": top_hotspots, "summary": summary}
