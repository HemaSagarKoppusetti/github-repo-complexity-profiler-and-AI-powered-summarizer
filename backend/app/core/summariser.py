"""Evidence-first AI summarisation, schema validation, and citation checking."""

from __future__ import annotations

import json
import logging
import re
from collections import defaultdict
from typing import Any, Literal

import requests
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.core.prompts import SYSTEM_PROMPT

logger = logging.getLogger(__name__)


class Health(BaseModel):
    rating: Literal["Healthy", "Watch", "At risk", "Critical"] = "Watch"
    rationale: str = "Insufficient evidence to rate repository health."


class Architecture(BaseModel):
    summary: str = "Architecture could not be determined from available evidence."
    strengths: list[str] = Field(default_factory=list)
    concerns: list[str] = Field(default_factory=list)


class KeyInsight(BaseModel):
    title: str
    evidence: list[str] = Field(default_factory=list)
    so_what: str
    likely_cause: str
    confidence: Literal["High", "Medium", "Low"] = "Low"


class Risk(BaseModel):
    file: str
    severity: str
    why: str
    blast_radius: str
    failure_mode: str


class Recommendation(BaseModel):
    priority: str
    action: str
    target: str
    expected_benefit: str
    effort: Literal["S", "M", "L"]
    confidence: Literal["High", "Medium", "Low"]


class Roadmap(BaseModel):
    days_30: list[str] = Field(default_factory=list)
    days_60: list[str] = Field(default_factory=list)
    days_90: list[str] = Field(default_factory=list)


class TestingFocus(BaseModel):
    file_or_module: str
    reason: str


class AIReport(BaseModel):
    """Validated machine-readable report contract."""

    model_config = ConfigDict(extra="ignore")

    headline: str = "Repository analysis completed with limited evidence."
    health: Health = Field(default_factory=Health)
    purpose: str = "Repository purpose was not inferable from available static evidence."
    architecture: Architecture = Field(default_factory=Architecture)
    key_insights: list[KeyInsight] = Field(default_factory=list)
    risks: list[Risk] = Field(default_factory=list)
    recommendations: list[Recommendation] = Field(default_factory=list)
    quick_wins: list[str] = Field(default_factory=list)
    roadmap: Roadmap = Field(default_factory=Roadmap)
    testing_focus: list[TestingFocus] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


PATH_PATTERN = re.compile(
    r"(?<![\w./-])(?:[\w.-]+/)*[\w.-]+\.(?:py|js|jsx|ts|tsx|java|go|rs|rb|php|c|cc|cpp|h|hpp|cs|md|json|yaml|yml|toml|sql)(?![\w])",
    re.IGNORECASE,
)
FUNCTION_PATTERN = re.compile(r"\b([A-Za-z_][\w.]*)\s*\(\)")
NUMBER_PATTERN = re.compile(r"(?<![\w])\d+(?:\.\d+)?%?")
REPORT_JSON_SCHEMA = AIReport.model_json_schema()


def _normal_path(path: str) -> str:
    return path.replace("\\", "/").lstrip("./")


def _iter_scalars(value: Any):
    if isinstance(value, dict):
        for item in value.values():
            yield from _iter_scalars(item)
    elif isinstance(value, list):
        for item in value:
            yield from _iter_scalars(item)
    else:
        yield value


def _number_key(value: object) -> str:
    try:
        return format(float(str(value).rstrip("%")), ".10g")
    except (TypeError, ValueError):
        return ""


def _known_citations(evidence: dict[str, Any]) -> tuple[set[str], set[str], set[str]]:
    files = {
        _normal_path(str(entry.get("rel_path")))
        for entry in evidence.get("top_hotspots", [])
        if entry.get("rel_path")
    }
    for package in evidence.get("package_aggregates", []):
        files.update(_normal_path(str(path)) for path in package.get("top_files", []))
    function_names = {
        str(function.get("name"))
        for hotspot in evidence.get("top_hotspots", [])
        for function in hotspot.get("function_context", [])
        if function.get("name")
    }
    allowed_numbers = {
        _number_key(value)
        for value in _iter_scalars(evidence)
        if isinstance(value, (int, float)) and not isinstance(value, bool)
    }
    allowed_numbers.update({"0.65", "0.4", "0.2", "30", "60", "90"})
    allowed_numbers.update(
        _number_key(float(value) * 100)
        for value in list(allowed_numbers)
        if value and float(value) <= 1
    )
    return files, function_names, allowed_numbers


def validate_citations(report: AIReport, evidence: dict[str, Any]) -> tuple[AIReport, list[dict[str, str]]]:
    """Remove unverified file/function/metric citations from a validated report."""
    known_files, known_functions, known_numbers = _known_citations(evidence)
    diagnostics: list[dict[str, str]] = []

    def clean_text(text: str, field_name: str) -> str:
        def clean_path(match: re.Match[str]) -> str:
            path = _normal_path(match.group(0))
            if path in known_files:
                return path
            diagnostics.append({
                "stage": "report", "file": path, "severity": "warning",
                "message": f"Removed citation to a file absent from the evidence pack ({field_name}).",
            })
            return "[unverified file omitted]"

        text = PATH_PATTERN.sub(clean_path, text)

        def clean_function(match: re.Match[str]) -> str:
            name = match.group(1).split(".")[-1]
            if name in known_functions:
                return match.group(0)
            diagnostics.append({
                "stage": "report", "file": "", "severity": "warning",
                "message": f"Removed citation to an unverified function ({field_name}).",
            })
            return "an unverified function"

        text = FUNCTION_PATTERN.sub(clean_function, text)
        if field_name not in {"priority"}:
            def clean_number(match: re.Match[str]) -> str:
                token = match.group(0)
                base = token.rstrip("%")
                if _number_key(base) in known_numbers:
                    return token
                diagnostics.append({
                    "stage": "report", "file": "", "severity": "warning",
                    "message": f"Replaced an unsupported numeric claim ({field_name}).",
                })
                return "[unverified]"

            text = NUMBER_PATTERN.sub(clean_number, text)
        return text

    def clean_value(value: Any, field_name: str = "") -> Any:
        if isinstance(value, str):
            return clean_text(value, field_name)
        if isinstance(value, list):
            return [clean_value(item, field_name) for item in value]
        if isinstance(value, dict):
            return {key: clean_value(item, key) for key, item in value.items()}
        return value

    data = report.model_dump()
    risks: list[dict[str, Any]] = []
    for risk in data["risks"]:
        file_path = _normal_path(risk["file"])
        if file_path not in known_files:
            diagnostics.append({
                "stage": "report", "file": file_path, "severity": "warning",
                "message": "Dropped risk whose file is absent from the evidence pack.",
            })
            continue
        risk["file"] = file_path
        risks.append(risk)
    data["risks"] = risks
    cleaned = clean_value(data)
    return AIReport.model_validate(cleaned), diagnostics


def _safe_default_report(evidence: dict[str, Any], reason: str | None = None) -> AIReport:
    """Construct an evidence-only report when AI generation is unavailable."""
    hotspots = evidence.get("top_hotspots", [])
    recommendations = []
    risks = []
    testing_focus = []
    for index, hotspot in enumerate(hotspots[:3]):
        path = str(hotspot["rel_path"])
        metrics = (
            f"risk {hotspot.get('risk_score', 0)}, complexity {hotspot.get('max_cc', 0)}, "
            f"and {hotspot.get('commit_count', 0)} commits"
        )
        risks.append(Risk(
            file=path,
            severity=str(hotspot.get("tier", "Low")),
            why=f"The measured {metrics} place this file among the highest-ranked hotspots.",
            blast_radius="Static dependency impact is not established by this file-level score.",
            failure_mode="A change could regress behavior in this hotspot; runtime effects were not measured.",
        ))
        recommendations.append(Recommendation(
            priority=f"P{index + 1}",
            action="Review the highest-ranked risk components and add a focused regression check before changing this file.",
            target=path,
            expected_benefit=f"Reduce change risk associated with the measured {metrics}.",
            effort="S",
            confidence="Medium",
        ))
        testing_focus.append(TestingFocus(
            file_or_module=path,
            reason=f"Prioritize this file because its measured {metrics}.",
        ))
    limitations = [
        "Static analysis cannot establish runtime behavior, production failures, or test coverage.",
        "Maintainability index is available only for Python files.",
    ]
    if evidence.get("repo", {}).get("history_truncated"):
        limitations.append("Git history is shallow or capped; lifetime churn may be incomplete.")
    if reason:
        limitations.append(reason)
    report = AIReport(
        headline=f"{evidence.get('repo', {}).get('name', 'Repository')} has measurable static risk signals that need engineering review.",
        health=Health(rating="Watch", rationale="The assessment is based on static metrics and available Git history only."),
        purpose=f"Automated analysis of {evidence.get('repo', {}).get('name', 'the repository')} identified code structure, complexity, and change-history metrics.",
        architecture=Architecture(
            summary="The available evidence describes file-level metrics and dependencies; it does not establish runtime architecture.",
            strengths=[],
            concerns=["Review high-risk files in context before making structural changes."],
        ),
        risks=risks,
        recommendations=recommendations,
        quick_wins=[item.action for item in recommendations[:3]],
        testing_focus=testing_focus,
        limitations=limitations,
    )
    return validate_citations(report, evidence)[0]


def build_fallback_report(evidence: dict[str, Any], reason: str | None = None) -> AIReport:
    """Build a citation-checked report without contacting an LLM."""
    return _safe_default_report(evidence, reason)


def render_report_markdown(report: AIReport) -> str:
    """Render the validated structured report as Markdown."""
    data = report.model_dump()
    sections = [
        f"# {data['headline']}",
        f"## Health: {data['health']['rating']}\n\n{data['health']['rationale']}",
        f"## Purpose\n\n{data['purpose']}",
        f"## Architecture\n\n{data['architecture']['summary']}",
    ]
    for heading, items in (
        ("Architectural strengths", data["architecture"]["strengths"]),
        ("Architectural concerns", data["architecture"]["concerns"]),
        ("Key insights", data["key_insights"]),
        ("Risks", data["risks"]),
        ("Recommendations", data["recommendations"]),
        ("Quick wins", data["quick_wins"]),
        ("Testing focus", data["testing_focus"]),
        ("Limitations", data["limitations"]),
    ):
        if not items:
            continue
        rendered = []
        for item in items:
            if isinstance(item, str):
                rendered.append(f"- {item}")
            elif isinstance(item, dict):
                rendered.append("- " + "; ".join(f"{key}: {value}" for key, value in item.items() if value))
        sections.append(f"## {heading}\n\n" + "\n".join(rendered))
    roadmap = data["roadmap"]
    sections.append(
        "## Roadmap\n\n"
        + "\n".join(
            f"- **{days} days:** " + ("; ".join(actions) if actions else "No evidence-specific item.")
            for days, actions in ((30, roadmap["days_30"]), (60, roadmap["days_60"]), (90, roadmap["days_90"]))
        )
    )
    return "\n\n".join(sections)


def repair_json_response(raw: str) -> dict[str, Any]:
    """Extract a JSON object and repair common trailing-comma/fence issues."""
    text = raw.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.IGNORECASE | re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    start = text.find("{")
    if start < 0:
        raise ValueError("No JSON object found in model response.")
    depth = 0
    in_string = False
    escaped = False
    end = -1
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
        elif char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                end = index + 1
                break
    if end < 0:
        raise ValueError("Model response contains incomplete JSON.")
    candidate = re.sub(r",\s*([}\]])", r"\1", text[start:end])
    parsed = json.loads(candidate)
    if not isinstance(parsed, dict):
        raise ValueError("Model response JSON must be an object.")
    return parsed


def _markdown_fallback(raw: str) -> dict[str, Any]:
    """Convert markdown headings into a minimal valid report object."""
    sections: dict[str, str] = {}
    current = "headline"
    for line in raw.splitlines():
        if line.startswith("#"):
            current = line.lstrip("# ").strip().lower()
            sections.setdefault(current, "")
        else:
            sections[current] = (sections.get(current, "") + " " + line.strip()).strip()
    return {
        "headline": sections.get("headline", "Repository analysis returned non-JSON output."),
        "health": {"rating": "Watch", "rationale": "The model returned markdown rather than validated JSON."},
        "purpose": sections.get("purpose", "Purpose could not be parsed from the model response."),
        "architecture": {
            "summary": sections.get("architecture", "Architecture could not be parsed from the model response."),
            "strengths": [],
            "concerns": [],
        },
        "limitations": ["The model response was repaired from markdown; confidence is reduced."],
    }


def _estimate_tokens(value: Any, model: str) -> int:
    """Estimate prompt tokens with tiktoken when installed, otherwise chars/4."""
    text = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    try:
        import tiktoken

        try:
            encoder = tiktoken.encoding_for_model(model)
        except KeyError:
            encoder = tiktoken.get_encoding("cl100k_base")
        return len(encoder.encode(text))
    except ImportError:
        return max(1, (len(text) + 3) // 4)


def _get_model_context_length(model: str, base_url: str) -> int:
    """Fetch OpenRouter's model context length, with a conservative fallback."""
    if not model or model == "openrouter/free":
        return 24_000
    try:
        response = requests.get(f"{base_url.rstrip('/')}/models", timeout=8)
        if response.status_code != 200:
            return 24_000
        for item in response.json().get("data", []):
            if item.get("id") == model and isinstance(item.get("context_length"), int):
                return item["context_length"]
    except (requests.RequestException, ValueError, TypeError, AttributeError):
        logger.info("Model context lookup unavailable; using conservative token budget.")
    return 24_000


def build_evidence_pack(
    repo_name: str,
    scan: dict[str, Any],
    complexity: dict[str, Any],
    churn: dict[str, Any],
    graph: dict[str, Any],
    hotspots: dict[str, Any],
    diagnostics: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Collect high-priority, path-verifiable evidence from every analysis stage."""
    hotspot_rows = hotspots.get("hotspots", [])[:15]
    repo_stats = churn.get("stats", {})
    scan_diagnostics = scan.get("diagnostics", [])
    quality = list(diagnostics or []) + list(scan_diagnostics)
    quality.extend({
        "stage": "churn", "file": "", "severity": "warning", "message": warning,
    } for warning in churn.get("warnings", []))
    if not complexity.get("summary", {}).get("total_python_files_analysed", complexity.get("summary", {}).get("total_files_analysed", 0)):
        quality.append({
            "stage": "complexity", "file": "", "severity": "info",
            "message": "No Python maintainability index measurements are available.",
        })

    packages: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for hotspot in hotspots.get("hotspots", []):
        path = str(hotspot.get("rel_path", ""))
        package = path.split("/", 1)[0] if "/" in path else "(repository root)"
        packages[package].append(hotspot)
    package_aggregates = []
    for name, items in packages.items():
        package_aggregates.append({
            "package": name,
            "file_count": len(items),
            "average_risk": round(sum(item.get("risk_score", 0.0) for item in items) / len(items), 4),
            "average_complexity": round(sum(item.get("max_cc", 0) for item in items) / len(items), 2),
            "top_files": [item.get("rel_path") for item in sorted(items, key=lambda row: row.get("risk_score", 0), reverse=True)[:5]],
        })
    package_aggregates.sort(key=lambda item: (-item["average_risk"], item["package"]))
    ownership = sorted(
        hotspot_rows,
        key=lambda item: (item.get("bus_factor", 0) or 10**6, -item.get("top_author_share", 0)),
    )[:10]
    summary = complexity.get("summary", {})
    return {
        "repo": {
            "name": repo_name,
            "analysed_window": repo_stats.get("analysed_window", "No history window available"),
            "history_truncated": bool(repo_stats.get("history_truncated", False)),
            "analysis_truncated": bool(scan.get("truncated", False)),
        },
        "data_quality": {
            "diagnostics_count": len(quality),
            "flags": [item.get("message", "") for item in quality[:30]],
            "stages_with_gaps": sorted({item.get("stage", "unknown") for item in quality}),
        },
        "kpis": {
            "total_files": scan.get("total_files", 0),
            "total_loc": scan.get("total_loc", 0),
            "languages": scan.get("language_breakdown", {}),
            "roles": scan.get("role_breakdown", {}),
            "python_files": summary.get("total_python_files_analysed", summary.get("total_files_analysed", 0)),
            "functions": summary.get("total_functions", 0),
            "average_mi": summary.get("avg_mi_score", 0.0),
            "commits": repo_stats.get("total_commits", 0),
            "authors": repo_stats.get("total_authors", 0),
            "cycle_count": graph.get("stats", {}).get("cycle_count", 0),
            "critical_hotspots": hotspots.get("summary", {}).get("critical_count", 0),
            "risk_weights": hotspots.get("summary", {}).get("risk_weights", {}),
        },
        "top_hotspots": hotspot_rows,
        "scc_cycles": graph.get("cycle_components", [])[:20],
        "cycle_examples": graph.get("cycles", [])[:20],
        "hub_modules": graph.get("hub_modules", [])[:15],
        "ownership_outliers": ownership,
        "temporal_coupling": churn.get("temporal_coupling", [])[:10],
        "package_aggregates": package_aggregates[:30],
        "language_and_role_breakdown": {
            "languages": scan.get("language_breakdown", {}),
            "roles": scan.get("role_breakdown", {}),
        },
        "diagnostics": quality[:30],
    }


def _fit_evidence_budget(evidence: dict[str, Any], budget_tokens: int, model: str) -> tuple[dict[str, Any], bool]:
    """Keep the highest priority evidence until the input token budget is reached."""
    result = {
        key: evidence[key]
        for key in ("repo", "data_quality", "kpis")
    }
    if _estimate_tokens(result, model) >= budget_tokens:
        return result, True
    truncated = False
    for section in (
        "top_hotspots", "scc_cycles", "cycle_examples", "hub_modules",
        "ownership_outliers", "temporal_coupling", "package_aggregates",
        "language_and_role_breakdown", "diagnostics",
    ):
        if section == "language_and_role_breakdown":
            trial = {**result, section: evidence.get(section, {})}
            if _estimate_tokens(trial, model) > budget_tokens:
                truncated = True
                break
            result = trial
            continue
        result[section] = []
        for item in evidence.get(section, []):
            trial = dict(result)
            trial[section] = [*result[section], item] if isinstance(result[section], list) else item
            if _estimate_tokens(trial, model) > budget_tokens:
                truncated = True
                break
            result = trial
        if truncated:
            break
    return result, truncated


def _parse_ai_report(raw: str) -> AIReport:
    """Parse JSON or repair a markdown response into the report schema."""
    try:
        value = repair_json_response(raw)
    except (ValueError, json.JSONDecodeError):
        value = _markdown_fallback(raw)
    try:
        return AIReport.model_validate(value)
    except ValidationError:
        return AIReport.model_validate(_markdown_fallback(raw))


def _prompt_for(evidence: dict[str, Any]) -> str:
    """Create the user prompt with the machine-readable output schema."""
    return (
        "EVIDENCE PACK (JSON):\n"
        + json.dumps(evidence, ensure_ascii=False, separators=(",", ":"))
        + "\n\nOUTPUT SCHEMA (JSON Schema):\n"
        + json.dumps(REPORT_JSON_SCHEMA, ensure_ascii=False, separators=(",", ":"))
    )


def generate_structured_report(
    evidence: dict[str, Any],
    llm_client: Any,
    model: str = "openrouter/free",
    base_url: str = "https://openrouter.ai/api/v1",
) -> tuple[AIReport, list[dict[str, str]]]:
    """Generate a schema-valid report using direct or bounded map-reduce calls."""
    context_length = _get_model_context_length(model, base_url)
    output_reserve = min(4000, max(1000, context_length // 6))
    input_budget = max(1000, int(context_length * 0.60) - output_reserve)
    fitted, truncated = _fit_evidence_budget(evidence, input_budget, model)
    diagnostics: list[dict[str, str]] = []
    try:
        if not truncated:
            raw = llm_client.generate(
                _prompt_for(fitted),
                max_tokens=output_reserve,
                system_prompt=SYSTEM_PROMPT,
                json_mode=True,
            )
        else:
            package_outputs = []
            packages = evidence.get("package_aggregates", [])[:7]
            global_paths = {
                item.get("rel_path") for item in evidence.get("top_hotspots", [])
            }
            for package in packages:
                package_name = package.get("package")
                package_paths = set(package.get("top_files", []))
                package_evidence = {
                    "repo": evidence.get("repo", {}),
                    "package": package,
                    "files": [
                        item for item in evidence.get("top_hotspots", [])
                        if item.get("rel_path") in package_paths
                    ],
                    "global_hotspot_paths": sorted(global_paths),
                }
                raw_map = llm_client.generate(
                    _prompt_for(package_evidence),
                    max_tokens=min(1000, output_reserve),
                    system_prompt=SYSTEM_PROMPT,
                    json_mode=True,
                )
                package_outputs.append({
                    "package": package_name,
                    "report": _parse_ai_report(raw_map).model_dump(),
                })
            reduce_evidence = {
                "global_kpis": evidence.get("kpis", {}),
                "top_hotspots": evidence.get("top_hotspots", [])[:15],
                "map_findings": package_outputs,
                "data_quality": evidence.get("data_quality", {}),
            }
            raw = llm_client.generate(
                _prompt_for(reduce_evidence),
                max_tokens=output_reserve,
                system_prompt=SYSTEM_PROMPT,
                json_mode=True,
            )
    except Exception as exc:
        diagnostics.append({
            "stage": "report", "file": "", "severity": "warning",
            "message": f"AI report generation failed ({type(exc).__name__}); generated evidence-only fallback.",
        })
        return _safe_default_report(evidence, "AI synthesis was unavailable; deterministic evidence-only findings are shown."), diagnostics

    report = _parse_ai_report(raw)
    report, citation_diagnostics = validate_citations(report, evidence)
    diagnostics.extend(citation_diagnostics)
    if truncated:
        diagnostics.append({
            "stage": "report", "file": "", "severity": "info",
            "message": "Evidence exceeded the direct prompt budget and was summarized by package.",
        })
    return report, diagnostics


def build_prompt(
    repo_name: str,
    scan: dict[str, Any],
    complexity: dict[str, Any],
    churn: dict[str, Any],
    graph: dict[str, Any],
    hotspots: dict[str, Any],
) -> str:
    """Preserve the legacy prompt helper while supplying structured evidence."""
    evidence = build_evidence_pack(repo_name, scan, complexity, churn, graph, hotspots)
    return _prompt_for(evidence)
