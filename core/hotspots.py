# core/hotspots.py
# Combines complexity (radon) and churn (git) into a per-file risk score.
# risk_score = normalised_complexity × normalised_churn
# Files that are BOTH complex AND frequently changed are the true hotspots.

import os


def compute_hotspots(
    complexity_data: dict,
    churn_data: dict,
    repo_path: str,
    top_n: int = 10
) -> dict:
    """
    Merges complexity and churn results into a ranked hotspot list.

    Args:
        complexity_data : output from complexity.analyse_all()
        churn_data      : output from churn.analyse_churn()
        repo_path       : local repo path (for rel_path normalisation)
        top_n           : how many hotspots to return (default 10)

    Returns a dict with:
      - hotspots      : list of ranked file dicts with risk scores
      - top_hotspots  : top N files by risk score
      - summary       : plain-English interpretation of findings
    """

    print("  [hotspots] Computing risk scores...")

    file_churn = churn_data["file_churn"]

    # ── Build a lookup from rel_path → complexity result ─────────────────
    complexity_lookup = {}
    for result in complexity_data["results"]:
        rel = os.path.relpath(result["filepath"], repo_path)
        complexity_lookup[rel] = result

    # ── Merge complexity + churn per file ─────────────────────────────────
    merged = []
    for rel_path, churn in file_churn.items():
        cc_data = complexity_lookup.get(rel_path, None)

        if cc_data is None:
            continue

        merged.append({
            "rel_path":     rel_path,
            "commit_count": churn["commit_count"],
            "churn_rate":   churn["churn_rate"],
            "author_count": churn["author_count"],
            "last_changed": churn["last_changed"],
            "mi_score":     cc_data["mi_score"],
            "mi_rank":      cc_data["mi_rank"],
            "avg_cc":       cc_data["avg_cc"],
            "max_cc":       cc_data["max_cc"],
            "hotspot_fn":   cc_data["hotspot_fn"],
            "loc":          0,   # filled below
        })

    if not merged:
        print("  [hotspots] ⚠️  No files to score")
        return {"hotspots": [], "top_hotspots": [], "summary": {}}

    # ── Normalise both dimensions to [0, 1] ───────────────────────────────
    max_commits = max(f["commit_count"] for f in merged) or 1
    max_cc      = max(f["max_cc"]       for f in merged) or 1
    min_mi      = min(f["mi_score"]     for f in merged) or 1

    for f in merged:
        norm_churn      = f["commit_count"] / max_commits
        norm_complexity = f["max_cc"]       / max_cc

        # Invert MI: low MI = high risk
        # MI ranges 0–100; we map low MI → high risk score contribution
        norm_low_mi = 1.0 - (f["mi_score"] / 100.0)

        # Risk formula:
        # 50% weight on churn, 30% on cyclomatic complexity, 20% on low MI
        f["risk_score"] = round(
            (0.50 * norm_churn) +
            (0.30 * norm_complexity) +
            (0.20 * norm_low_mi),
            4
        )

        # Human-readable risk tier
        f["risk_tier"] = _risk_tier(f["risk_score"])

    # ── Sort by risk score descending ─────────────────────────────────────
    hotspots = sorted(merged, key=lambda x: x["risk_score"], reverse=True)

    top_hotspots = hotspots[:top_n]

    # ── Plain-English summary ──────────────────────────────────────────────
    critical = [f for f in hotspots if f["risk_tier"] == "🔴 Critical"]
    high     = [f for f in hotspots if f["risk_tier"] == "🟠 High"]
    medium   = [f for f in hotspots if f["risk_tier"] == "🟡 Medium"]
    low      = [f for f in hotspots if f["risk_tier"] == "🟢 Low"]

    summary = {
        "total_files_scored": len(hotspots),
        "critical_count":     len(critical),
        "high_count":         len(high),
        "medium_count":       len(medium),
        "low_count":          len(low),
        "top_hotspot":        hotspots[0]["rel_path"] if hotspots else None,
        "top_hotspot_fn":     hotspots[0]["hotspot_fn"] if hotspots else None,
        "critical_files":     [f["rel_path"] for f in critical],
    }

    print(f"  [hotspots] ✅ {len(hotspots)} files scored | "
          f"🔴 {len(critical)} critical | "
          f"🟠 {len(high)} high | "
          f"🟡 {len(medium)} medium | "
          f"🟢 {len(low)} low")

    return {
        "hotspots":     hotspots,
        "top_hotspots": top_hotspots,
        "summary":      summary,
    }


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