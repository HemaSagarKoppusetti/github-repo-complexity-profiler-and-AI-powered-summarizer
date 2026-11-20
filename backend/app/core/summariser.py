# backend/app/core/summariser.py
"""Feeds structured repo metrics into an LLM and generates a plain-English

report with four sections: purpose, strengths, risks, and suggestions.
"""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


def build_prompt(
    repo_name: str,
    scan: dict[str, Any],
    complexity: dict[str, Any],
    churn: dict[str, Any],
    graph: dict[str, Any],
    hotspots: dict[str, Any],
) -> str:
    """Assembles a structured prompt from all metric dicts.

    Strictly instructs the model to only use the provided data.
    """
    c_summary = complexity.get("summary", {})
    ch_stats = churn.get("stats", {})
    g_stats = graph.get("stats", {})
    h_summary = hotspots.get("summary", {})
    top_h = hotspots.get("top_hotspots", [])[:5]

    # Format top hotspots
    hotspot_lines = []
    for f in top_h:
        hotspot_lines.append(
            f"  - {f['rel_path']} "
            f"(risk={f['risk_score']}, tier={f['risk_tier']}, "
            f"CC={f['max_cc']}, MI={f['mi_score']}, "
            f"commits={f['commit_count']})"
        )
    hotspot_block = "\n".join(hotspot_lines) if hotspot_lines else "  None"

    # Format top complex functions
    fn_lines = []
    for fn in c_summary.get("top_complex_functions", []):
        fn_lines.append(
            f"  - {fn['name']}() CC={fn['complexity']} [{fn['rank']}] "
            f"line {fn['lineno']}"
        )
    fn_block = "\n".join(fn_lines) if fn_lines else "  None"

    # Format least maintainable files
    mi_lines = []
    for r in c_summary.get("least_maintainable", []):
        mi_lines.append(
            f"  - {os.path.basename(r['filepath'])} "
            f"MI={r['mi_score']} [{r['mi_rank']}]"
        )
    mi_block = "\n".join(mi_lines) if mi_lines else "  None"

    # Format cycles
    cycles = graph.get("cycles", [])
    if cycles:
        cycle_block = "\n".join(
            "  - " + " → ".join(c) + f" → {c[0]}" for c in cycles
        )
    else:
        cycle_block = "  None detected ✅"

    # Format hub modules
    hub_lines = [
        f"  - {h['module']} (imported by {h['imported_by']} modules)"
        for h in graph.get("hub_modules", [])
    ]
    hub_block = "\n".join(hub_lines) if hub_lines else "  None"

    # Language breakdown
    lang_breakdown = scan.get("language_breakdown", {})
    lang_block = ", ".join(
        f"{lang}: {count} files"
        for lang, count in sorted(
            lang_breakdown.items(), key=lambda x: x[1], reverse=True
        )
    ) or "None"

    prompt = f"""You are a senior software architect reviewing a codebase called "{repo_name}".

CRITICAL INSTRUCTION: You must base your findings and text STRICTLY and ONLY on the empirical metrics and facts supplied below. Do NOT hallucinate dependencies, frameworks, files, or numbers not present in this prompt.

═══ OVERVIEW ═══
Repo name        : {repo_name}
Total files      : {scan.get('total_files', 0)}
Total LOC        : {scan.get('total_loc', 0)}
Languages        : {lang_block}

═══ COMPLEXITY ═══
Python files     : {c_summary.get('total_files_analysed', 0)}
Total functions  : {c_summary.get('total_functions', 0)}
Average MI score : {c_summary.get('avg_mi_score', 0)} / 100  (higher = more maintainable)
Low MI files     : {c_summary.get('low_mi_file_count', 0)}  (MI < 20 = unmaintainable)
CC rank dist     : {c_summary.get('rank_distribution', {})}

Top complex functions:
{fn_block}

Least maintainable files:
{mi_block}

═══ GIT HISTORY ═══
Total commits    : {ch_stats.get('total_commits', 0)}
Total authors    : {ch_stats.get('total_authors', 0)}
Repo age         : {ch_stats.get('repo_age_days', 0)} days
First commit     : {ch_stats.get('first_commit', 'N/A')}
Last commit      : {ch_stats.get('last_commit', 'N/A')}

═══ DEPENDENCY GRAPH ═══
Nodes (modules)  : {g_stats.get('node_count', 0)}
Edges (imports)  : {g_stats.get('edge_count', 0)}
Graph density    : {g_stats.get('density', 0.0)}
Circular deps    : {g_stats.get('cycle_count', 0)}
External deps    : {g_stats.get('external_deps', 0)}

Circular dependency cycles:
{cycle_block}

Hub modules (most imported):
{hub_block}

═══ HOTSPOT RISK RANKING ═══
Risk formula: 50% churn + 30% complexity + 20% low-maintainability
{h_summary.get('critical_count', 0)} Critical | {h_summary.get('high_count', 0)} High | {h_summary.get('medium_count', 0)} Medium | {h_summary.get('low_count', 0)} Low

Top risk files:
{hotspot_block}

═══ YOUR TASK ═══
Write a professional code review report with EXACTLY these four sections.
Be specific — use file names, function names, and numbers from the data above.
Do NOT give generic advice. Every recommendation must cite a specific file or metric.

## 1. What This Codebase Does
2–3 sentences. Infer the purpose from the repo name, file names, and module structure.

## 2. Architectural Strengths
2–3 bullet points. What is this codebase doing well based on the metrics?

## 3. Top Risk Areas
3 bullet points. Each must name a specific file, explain why it's risky using the metrics, and describe what could go wrong if it's changed carelessly.

## 4. Refactoring Suggestions
3 bullet points ordered by impact (highest first). Each must name the specific file or function to change and describe the concrete action to take.
"""
    return prompt
