# core/summariser.py
# Feeds structured repo metrics into an LLM and generates a plain-English
# report with four sections: purpose, strengths, risks, and suggestions.

import os
import requests
from dotenv import load_dotenv

load_dotenv()


def _call_llm(prompt: str, max_tokens: int = 1500) -> str:
    """Calls OpenRouter API and returns the response text."""
    key   = os.getenv("OPENROUTER_API_KEY")
    model = os.getenv("OPENROUTER_MODEL")

    response = requests.post(
        url="https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization":  f"Bearer {key}",
            "Content-Type":   "application/json",
            "HTTP-Referer":   "http://localhost:8501",
            "X-Title":        "GitHub Repo Profiler",
        },
        json={
            "model":    model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
        },
        timeout=60
    )

    data = response.json()

    if "error" in data:
        raise Exception(f"LLM error: {data['error']}")

    return data["choices"][0]["message"]["content"].strip()


def _build_prompt(
    repo_name:       str,
    scan:            dict,
    complexity:      dict,
    churn:           dict,
    graph:           dict,
    hotspots:        dict,
) -> str:
    """Assembles a structured prompt from all metric dicts."""

    c_summary  = complexity["summary"]
    ch_stats   = churn["stats"]
    g_stats    = graph["stats"]
    h_summary  = hotspots["summary"]
    top_h      = hotspots["top_hotspots"][:5]

    # Format top hotspots as a readable table
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
    for fn in c_summary["top_complex_functions"]:
        fn_lines.append(
            f"  - {fn['name']}() CC={fn['complexity']} [{fn['rank']}] "
            f"line {fn['lineno']}"
        )
    fn_block = "\n".join(fn_lines) if fn_lines else "  None"

    # Format least maintainable files
    mi_lines = []
    for r in c_summary["least_maintainable"]:
        mi_lines.append(
            f"  - {os.path.basename(r['filepath'])} "
            f"MI={r['mi_score']} [{r['mi_rank']}]"
        )
    mi_block = "\n".join(mi_lines) if mi_lines else "  None"

    # Format cycles
    if graph["cycles"]:
        cycle_block = "\n".join(
            "  - " + " → ".join(c) + f" → {c[0]}"
            for c in graph["cycles"]
        )
    else:
        cycle_block = "  None detected ✅"

    # Format hub modules
    hub_lines = [
        f"  - {h['module']} (imported by {h['imported_by']} modules)"
        for h in graph["hub_modules"]
    ] if graph["hub_modules"] else ["  None"]
    hub_block = "\n".join(hub_lines)

    # Language breakdown
    lang_block = ", ".join(
        f"{lang}: {count} files"
        for lang, count in sorted(
            scan["language_breakdown"].items(),
            key=lambda x: x[1], reverse=True
        )
    )

    prompt = f"""You are a senior software architect reviewing a codebase called "{repo_name}".

Here is the complete static analysis report. Use ONLY this data — do not invent facts.

═══ OVERVIEW ═══
Repo name        : {repo_name}
Total files      : {scan['total_files']}
Total LOC        : {scan['total_loc']}
Languages        : {lang_block}

═══ COMPLEXITY ═══
Python files     : {c_summary['total_files_analysed']}
Total functions  : {c_summary['total_functions']}
Average MI score : {c_summary['avg_mi_score']} / 100  (higher = more maintainable)
Low MI files     : {c_summary['low_mi_file_count']}  (MI < 20 = unmaintainable)
CC rank dist     : {c_summary['rank_distribution']}

Top complex functions:
{fn_block}

Least maintainable files:
{mi_block}

═══ GIT HISTORY ═══
Total commits    : {ch_stats['total_commits']}
Total authors    : {ch_stats['total_authors']}
Repo age         : {ch_stats['repo_age_days']} days
First commit     : {ch_stats['first_commit']}
Last commit      : {ch_stats['last_commit']}

═══ DEPENDENCY GRAPH ═══
Nodes (modules)  : {g_stats['node_count']}
Edges (imports)  : {g_stats['edge_count']}
Graph density    : {g_stats['density']}
Circular deps    : {g_stats['cycle_count']}
External deps    : {g_stats['external_deps']}

Circular dependency cycles:
{cycle_block}

Hub modules (most imported):
{hub_block}

═══ HOTSPOT RISK RANKING ═══
Risk formula: 50% churn + 30% complexity + 20% low-maintainability
{h_summary['critical_count']} Critical | {h_summary['high_count']} High | \
{h_summary['medium_count']} Medium | {h_summary['low_count']} Low

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
3 bullet points. Each must name a specific file, explain why it's risky using
the metrics, and describe what could go wrong if it's changed carelessly.

## 4. Refactoring Suggestions
3 bullet points ordered by impact (highest first). Each must name the specific
file or function to change and describe the concrete action to take.
"""
    return prompt


def generate_report(
    repo_name:  str,
    scan:       dict,
    complexity: dict,
    churn:      dict,
    graph:      dict,
    hotspots:   dict,
) -> dict:
    """
    Generates the full LLM report from all analysis modules.

    Returns a dict with:
      - report_text : the full markdown report string
      - prompt      : the prompt sent (useful for debugging)
      - error       : None or error string
    """

    print("  [summariser] Building prompt...")
    prompt = _build_prompt(repo_name, scan, complexity, churn, graph, hotspots)

    print("  [summariser] Calling LLM (this may take 15–30 seconds)...")
    try:
        report_text = _call_llm(prompt, max_tokens=1500)
        print("  [summariser] ✅ Report generated")
        return {
            "report_text": report_text,
            "prompt":      prompt,
            "error":       None,
        }
    except Exception as e:
        print(f"  [summariser] ❌ Error: {e}")
        return {
            "report_text": None,
            "prompt":      prompt,
            "error":       str(e),
        }