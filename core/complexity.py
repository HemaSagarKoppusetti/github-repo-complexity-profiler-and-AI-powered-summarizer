# core/complexity.py
# Runs radon over Python files to extract cyclomatic complexity and
# maintainability index. Only works on .py files.

from radon.complexity import cc_visit, cc_rank
from radon.metrics import mi_visit, mi_rank


# CC rank meanings (from radon docs):
# A (1–5)   → simple, low risk
# B (6–10)  → slightly complex
# C (11–15) → complex — worth refactoring
# D (16–20) → more complex
# E (21–25) → very complex, high risk
# F (26+)   → extremely complex, untestable

# MI score meanings:
# 100 → perfectly maintainable
# 20+ → maintainable
# 10–20 → moderate difficulty
# <10  → very hard to maintain


def analyse_file_complexity(filepath: str) -> dict:
    """
    Runs CC and MI analysis on a single Python file.

    Returns a dict with:
      - filepath     : str
      - mi_score     : float  (0–100, higher is better)
      - mi_rank      : str    ('A','B','C')
      - functions    : list of function-level CC results
      - avg_cc       : float  average CC across all functions
      - max_cc       : int    highest CC in the file
      - hotspot_fn   : str    name of the most complex function
      - error        : str or None
    """
    try:
        source = open(filepath, "r", encoding="utf-8", errors="ignore").read()

        if not source.strip():
            return _empty_result(filepath)

        # ── Maintainability Index ─────────────────────────────────────────
        mi_score = mi_visit(source, multi=True)
        mi_score = round(mi_score, 2)
        rank_mi  = mi_rank(mi_score)

        # ── Cyclomatic Complexity per function/method ─────────────────────
        cc_results = cc_visit(source)

        functions = []
        for block in cc_results:
            functions.append({
                "name":       block.name,
                "type":       type(block).__name__,  # Function or Class
                "complexity": block.complexity,
                "rank":       cc_rank(block.complexity),
                "lineno":     block.lineno,
            })

        # Sort functions by complexity descending
        functions.sort(key=lambda x: x["complexity"], reverse=True)

        avg_cc     = round(sum(f["complexity"] for f in functions) / len(functions), 2) if functions else 0.0
        max_cc     = functions[0]["complexity"] if functions else 0
        hotspot_fn = functions[0]["name"] if functions else None

        return {
            "filepath":   filepath,
            "mi_score":   mi_score,
            "mi_rank":    rank_mi,
            "functions":  functions,
            "avg_cc":     avg_cc,
            "max_cc":     max_cc,
            "hotspot_fn": hotspot_fn,
            "error":      None,
        }

    except Exception as e:
        return {
            "filepath":   filepath,
            "mi_score":   0.0,
            "mi_rank":    "?",
            "functions":  [],
            "avg_cc":     0.0,
            "max_cc":     0,
            "hotspot_fn": None,
            "error":      str(e),
        }


def _empty_result(filepath: str) -> dict:
    """Returns a zeroed result for empty files."""
    return {
        "filepath":   filepath,
        "mi_score":   100.0,
        "mi_rank":    "A",
        "functions":  [],
        "avg_cc":     0.0,
        "max_cc":     0,
        "hotspot_fn": None,
        "error":      None,
    }


def analyse_all(python_files: list) -> dict:
    """
    Runs complexity analysis across all Python files in the manifest.

    Args:
        python_files : list of absolute file paths (from scanner manifest)

    Returns a dict with:
      - results      : list of per-file dicts (from analyse_file_complexity)
      - summary      : aggregated stats across the whole repo
    """
    print(f"  [complexity] Analysing {len(python_files)} Python files...")

    results = []
    for filepath in python_files:
        result = analyse_file_complexity(filepath)
        results.append(result)

    # ── Build repo-wide summary ───────────────────────────────────────────
    valid = [r for r in results if r["error"] is None]

    all_functions = []
    for r in valid:
        for fn in r["functions"]:
            all_functions.append({**fn, "filepath": r["filepath"]})

    # Rank distribution across all functions
    rank_counts = {"A": 0, "B": 0, "C": 0, "D": 0, "E": 0, "F": 0}
    for fn in all_functions:
        rank = fn.get("rank", "A")
        if rank in rank_counts:
            rank_counts[rank] += 1

    # Files with MI below 20 are considered unmaintainable
    low_mi_files = [r for r in valid if r["mi_score"] < 20]

    # Top 5 most complex functions across entire repo
    top_complex = sorted(all_functions,
                         key=lambda x: x["complexity"],
                         reverse=True)[:5]

    # Top 5 least maintainable files
    low_mi = sorted(valid, key=lambda x: x["mi_score"])[:5]

    avg_mi = round(sum(r["mi_score"] for r in valid) / len(valid), 2) if valid else 0

    summary = {
        "total_files_analysed": len(results),
        "total_functions":      len(all_functions),
        "avg_mi_score":         avg_mi,
        "low_mi_file_count":    len(low_mi_files),
        "rank_distribution":    rank_counts,
        "top_complex_functions":top_complex,
        "least_maintainable":   low_mi,
    }

    print(f"  [complexity] ✅ Done | "
          f"{len(all_functions)} functions | "
          f"avg MI: {avg_mi} | "
          f"complex (C+): {rank_counts['C'] + rank_counts['D'] + rank_counts['E'] + rank_counts['F']}")

    return {
        "results": results,
        "summary": summary,
    }