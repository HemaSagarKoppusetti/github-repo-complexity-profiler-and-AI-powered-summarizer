# backend/app/core/complexity.py
"""Runs radon over Python files to extract cyclomatic complexity and maintainability index."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from radon.complexity import cc_rank, cc_visit
from radon.metrics import mi_rank, mi_visit

logger = logging.getLogger(__name__)


def _empty_result(filepath: str) -> dict[str, Any]:
    """Returns a zeroed result for empty or unparseable files."""
    return {
        "filepath": filepath,
        "mi_score": 100.0,
        "mi_rank": "A",
        "functions": [],
        "avg_cc": 0.0,
        "max_cc": 0,
        "hotspot_fn": None,
        "error": None,
    }


def analyse_file_complexity(filepath: str) -> dict[str, Any]:
    """Runs CC and MI analysis on a single Python file."""
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            source = f.read()

        if not source.strip():
            return _empty_result(filepath)

        # Maintainability Index
        mi_score = mi_visit(source, multi=True)
        mi_score = round(float(mi_score), 2)
        rank_mi = mi_rank(mi_score)

        # Cyclomatic Complexity per function/method
        cc_results = cc_visit(source)

        functions = []
        for block in cc_results:
            functions.append({
                "name": block.name,
                "type": type(block).__name__,
                "complexity": block.complexity,
                "rank": cc_rank(block.complexity),
                "lineno": block.lineno,
            })

        functions.sort(key=lambda x: x["complexity"], reverse=True)

        avg_cc = (
            round(sum(f["complexity"] for f in functions) / len(functions), 2)
            if functions
            else 0.0
        )
        max_cc = functions[0]["complexity"] if functions else 0
        hotspot_fn = functions[0]["name"] if functions else None

        return {
            "filepath": filepath,
            "mi_score": mi_score,
            "mi_rank": rank_mi,
            "functions": functions,
            "avg_cc": avg_cc,
            "max_cc": max_cc,
            "hotspot_fn": hotspot_fn,
            "error": None,
        }

    except Exception as e:
        logger.debug("Complexity error on %s: %s", filepath, e)
        return {
            "filepath": filepath,
            "mi_score": 0.0,
            "mi_rank": "?",
            "functions": [],
            "avg_cc": 0.0,
            "max_cc": 0,
            "hotspot_fn": None,
            "error": str(e),
        }


def analyse_all(
    python_files: list[str],
    progress_cb: Callable[[int, int, str], None] | None = None,
) -> dict[str, Any]:
    """Runs complexity analysis across all Python files in the manifest.

    Args:
        python_files: list of absolute file paths
        progress_cb: optional callback(current, total, filename)

    Returns:
        dict with results and summary
    """
    total = len(python_files)
    logger.info("[complexity] Analysing %d Python files...", total)

    results = []
    for idx, filepath in enumerate(python_files, 1):
        result = analyse_file_complexity(filepath)
        results.append(result)
        if progress_cb and (idx % 25 == 0 or idx == total):
            progress_cb(idx, total, filepath)

    # Build repo-wide summary
    valid = [r for r in results if r["error"] is None]

    all_functions = []
    for r in valid:
        for fn in r["functions"]:
            all_functions.append({**fn, "filepath": r["filepath"]})

    rank_counts = {"A": 0, "B": 0, "C": 0, "D": 0, "E": 0, "F": 0}
    for fn in all_functions:
        rank = fn.get("rank", "A")
        if rank in rank_counts:
            rank_counts[rank] += 1

    low_mi_files = [r for r in valid if r["mi_score"] < 20]

    top_complex = sorted(
        all_functions, key=lambda x: x["complexity"], reverse=True
    )[:5]

    low_mi = sorted(valid, key=lambda x: x["mi_score"])[:5]

    avg_mi = (
        round(sum(r["mi_score"] for r in valid) / len(valid), 2)
        if valid
        else 0.0
    )

    summary = {
        "total_files_analysed": len(results),
        "total_functions": len(all_functions),
        "avg_mi_score": avg_mi,
        "low_mi_file_count": len(low_mi_files),
        "rank_distribution": rank_counts,
        "top_complex_functions": top_complex,
        "least_maintainable": low_mi,
    }

    logger.info(
        "[complexity] ✅ Done | %d functions | avg MI: %s",
        len(all_functions),
        avg_mi,
    )

    return {
        "results": results,
        "summary": summary,
    }
