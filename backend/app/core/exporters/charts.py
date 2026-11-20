"""Headless, self-contained PNG chart generation for analysis reports."""

from __future__ import annotations

import io
import logging
import threading
from collections import Counter
from typing import Any, Callable

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import networkx as nx

from app.core.exporters.report_model import ChartArtifact, ReportModel

logger = logging.getLogger(__name__)
_MATPLOTLIB_LOCK = threading.RLock()
PALETTE = {
    "Critical": "#b91c1c",
    "High": "#ea580c",
    "Medium": "#d97706",
    "Low": "#15803d",
    "blue": "#2563eb",
    "teal": "#0f766e",
    "purple": "#7c3aed",
    "slate": "#475569",
}


def _png(figure: Any) -> bytes:
    """Serialize a Matplotlib figure as an A4-readable PNG."""
    buffer = io.BytesIO()
    figure.savefig(buffer, format="png", dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(figure)
    return buffer.getvalue()


def _base_axes(title: str, width: float = 8.0, height: float = 4.5) -> tuple[Any, Any]:
    """Create a consistently styled figure."""
    figure, axis = plt.subplots(figsize=(width, height))
    axis.set_title(title, fontsize=14, fontweight="bold", pad=14)
    axis.grid(axis="y", alpha=0.2)
    return figure, axis


def _chart(
    model: ReportModel,
    name: str,
    title: str,
    caption: str,
    how_to_read: str,
    builder: Callable[[], bytes | None],
) -> ChartArtifact | None:
    """Build one chart without allowing visualization errors to fail an export."""
    try:
        image = builder()
        if image is None:
            model.diagnostics.append(
                {
                    "stage": "export",
                    "file": "",
                    "severity": "info",
                    "message": f"Skipped chart '{title}': no data was available.",
                }
            )
            return None
        return ChartArtifact(name, title, image, caption, how_to_read)
    except Exception as exc:
        logger.warning("Chart %s failed (%s).", name, type(exc).__name__)
        model.diagnostics.append(
            {
                "stage": "export",
                "file": "",
                "severity": "warning",
                "message": f"Chart '{title}' could not be rendered ({type(exc).__name__}).",
            }
        )
        return None


def _tier_distribution(model: ReportModel) -> bytes | None:
    rows = model.hotspots.get("hotspots", [])
    if not rows:
        return None
    counts = Counter(item.get("tier", "Low") for item in rows)
    labels = [tier for tier in ("Critical", "High", "Medium", "Low") if counts[tier]]
    figure, axis = plt.subplots(figsize=(6, 4.5))
    axis.pie(
        [counts[label] for label in labels],
        labels=labels,
        colors=[PALETTE[label] for label in labels],
        autopct="%1.0f%%",
        startangle=90,
        wedgeprops={"width": 0.42, "edgecolor": "white"},
        textprops={"fontsize": 9},
    )
    axis.set_title("Risk tier distribution", fontsize=14, fontweight="bold")
    axis.axis("equal")
    return _png(figure)


def _hotspot_components(model: ReportModel) -> bytes | None:
    rows = model.hotspots.get("top_hotspots", [])[:10]
    if not rows:
        return None
    labels = [str(item.get("rel_path", "")) for item in reversed(rows)]
    components = ["churn", "complexity", "low_mi", "loc", "bug_fixes"]
    colors = [PALETTE["blue"], PALETTE["purple"], PALETTE["High"], PALETTE["teal"], PALETTE["slate"]]
    figure, axis = _base_axes("Top hotspot risk components", 9.0, max(4.5, len(rows) * 0.42))
    left = [0.0] * len(rows)
    for component, color in zip(components, colors, strict=True):
        values = [float(item.get("risk_components", {}).get(component, 0.0)) for item in reversed(rows)]
        axis.barh(labels, values, left=left, label=component.replace("_", " ").title(), color=color)
        left = [previous + value for previous, value in zip(left, values, strict=True)]
    axis.set_xlabel("Weighted percentile risk components")
    axis.legend(loc="lower right", fontsize=8)
    return _png(figure)


def _quadrant_scatter(model: ReportModel) -> bytes | None:
    rows = model.hotspots.get("hotspots", [])
    if not rows:
        return None
    x_values = [float(item.get("commits_last_90_days") or item.get("commit_count", 0)) for item in rows]
    y_values = [float(item.get("max_cc", 0)) for item in rows]
    loc_values = [max(1.0, float(item.get("loc", 1))) for item in rows]
    colors = [PALETTE.get(item.get("tier", "Low"), PALETTE["Low"]) for item in rows]
    figure, axis = _base_axes("Complexity vs. churn risk quadrants", 9.0, 6.0)
    axis.scatter(
        x_values,
        y_values,
        s=[min(700, 30 + value * 2) for value in loc_values],
        c=colors,
        alpha=0.65,
        edgecolors="white",
    )
    churn_median = sorted(x_values)[len(x_values) // 2]
    complexity_median = sorted(y_values)[len(y_values) // 2]
    axis.axvline(churn_median, color="#64748b", linestyle="--", linewidth=1)
    axis.axhline(complexity_median, color="#64748b", linestyle="--", linewidth=1)
    axis.set_xlabel("Commits in last 90 days (fallback: lifetime commits)")
    axis.set_ylabel("Maximum cyclomatic complexity")
    axis.text(
        0.98,
        0.98,
        "Active danger",
        transform=axis.transAxes,
        ha="right",
        va="top",
        fontsize=9,
        color=PALETTE["Critical"],
    )
    axis.text(
        0.02,
        0.98,
        "Fragile but stable",
        transform=axis.transAxes,
        ha="left",
        va="top",
        fontsize=9,
        color=PALETTE["High"],
    )
    axis.text(
        0.98,
        0.02,
        "Healthy churn",
        transform=axis.transAxes,
        ha="right",
        va="bottom",
        fontsize=9,
        color=PALETTE["teal"],
    )
    axis.text(
        0.02, 0.02, "Healthy", transform=axis.transAxes, ha="left", va="bottom", fontsize=9, color=PALETTE["slate"]
    )
    for item in sorted(rows, key=lambda row: row.get("risk_score", 0), reverse=True)[:8]:
        axis.annotate(
            str(item.get("rel_path", "")),
            (
                float(item.get("commits_last_90_days") or item.get("commit_count", 0)),
                float(item.get("max_cc", 0)),
            ),
            fontsize=7,
            xytext=(4, 4),
            textcoords="offset points",
        )
    return _png(figure)


def _cc_ranks(model: ReportModel) -> bytes | None:
    rank_counts = model.complexity.get("summary", {}).get("rank_distribution", {})
    if not rank_counts or not sum(rank_counts.values()):
        return None
    figure, axis = _base_axes("Cyclomatic-complexity rank distribution")
    labels = list("ABCDEF")
    values = [rank_counts.get(label, 0) for label in labels]
    axis.bar(
        labels,
        values,
        color=[PALETTE["teal"], PALETTE["blue"], PALETTE["Medium"], PALETTE["High"], PALETTE["Critical"], "#7f1d1d"],
    )
    axis.set_xlabel("Radon complexity rank")
    axis.set_ylabel("Function count")
    return _png(figure)


def _mi_histogram(model: ReportModel) -> bytes | None:
    results = [
        item
        for item in model.complexity.get("results", [])
        if item.get("mi_available", item.get("language", "Python") == "Python") and item.get("error") is None
    ]
    scores = [float(item.get("mi_score", 0)) for item in results]
    if not scores:
        return None
    figure, axis = _base_axes("Python maintainability index distribution")
    axis.hist(scores, bins=10, range=(0, 100), color=PALETTE["blue"], alpha=0.8, edgecolor="white")
    axis.axvline(20, color=PALETTE["Critical"], linestyle="--", label="MI 20 threshold")
    axis.axvline(65, color=PALETTE["teal"], linestyle="--", label="MI 65 threshold")
    axis.set_xlabel("Maintainability index (0–100)")
    axis.set_ylabel("Python file count")
    axis.legend(fontsize=8)
    return _png(figure)


def _commit_timeline(model: ReportModel) -> bytes | None:
    rows = model.churn.get("commits_by_month", [])
    if not rows:
        return None
    figure, axis = _base_axes("Commits per month (last 36 months)")
    labels = [item["month"] for item in rows[-36:]]
    values = [item["commits"] for item in rows[-36:]]
    axis.plot(labels, values, color=PALETTE["blue"], marker="o", linewidth=2)
    axis.set_xlabel("Month")
    axis.set_ylabel("Commits")
    axis.tick_params(axis="x", labelrotation=55, labelsize=7)
    return _png(figure)


def _dependency_graph(model: ReportModel) -> bytes | None:
    nodes = model.graph.get("nodes", [])
    edges = model.graph.get("edges", [])
    if not nodes:
        return None
    graph = nx.DiGraph()
    graph.add_nodes_from(nodes)
    graph.add_edges_from((edge[0], edge[1]) for edge in edges)
    all_nodes = sorted(graph, key=lambda node: graph.degree(node), reverse=True)
    capped = all_nodes[:80]
    graph = graph.subgraph(capped).copy()
    positions = nx.spring_layout(graph, seed=42, iterations=25)
    cycle_nodes = {node for component in model.graph.get("cycle_components", []) for node in component}
    fan_in = dict(graph.in_degree())
    node_colors = [PALETTE["Critical"] if node in cycle_nodes else PALETTE["blue"] for node in graph]
    node_sizes = [220 + fan_in.get(node, 0) * 110 for node in graph]
    figure, axis = plt.subplots(figsize=(9, 7))
    nx.draw_networkx_edges(graph, positions, ax=axis, arrows=True, alpha=0.25, width=0.7, arrowsize=8)
    nx.draw_networkx_nodes(graph, positions, ax=axis, node_color=node_colors, node_size=node_sizes, alpha=0.85)
    hubs = {item.get("module") for item in model.graph.get("hub_modules", [])[:10]}
    labels = {node: node.split(".")[-1] for node in graph if node in hubs}
    nx.draw_networkx_labels(graph, positions, labels=labels, ax=axis, font_size=7)
    axis.set_title("Dependency graph (top 80 nodes by degree)", fontsize=14, fontweight="bold")
    axis.axis("off")
    return _png(figure)


def _ownership(model: ReportModel) -> bytes | None:
    rows = model.hotspots.get("hotspots", [])
    rows = sorted(rows, key=lambda item: item.get("top_author_share", 0), reverse=True)[:10]
    if not rows:
        return None
    labels = [str(item.get("rel_path", "")) for item in reversed(rows)]
    shares = [float(item.get("top_author_share", 0)) * 100 for item in reversed(rows)]
    factors = [int(item.get("bus_factor", 0)) for item in reversed(rows)]
    figure, axis = _base_axes("Ownership concentration and bus factor", 9.0, max(4.5, len(rows) * 0.42))
    bars = axis.barh(labels, shares, color=PALETTE["purple"], alpha=0.8)
    axis.set_xlabel("Largest author's share of file commits (%)")
    axis.set_xlim(0, 100)
    for bar, factor in zip(bars, factors, strict=True):
        axis.text(
            min(bar.get_width() + 1, 96),
            bar.get_y() + bar.get_height() / 2,
            f"bus factor {factor}",
            va="center",
            fontsize=7,
        )
    return _png(figure)


def _language_role_breakdown(model: ReportModel) -> bytes | None:
    languages = model.manifest.get("language_breakdown", {})
    roles = model.manifest.get("role_breakdown", {})
    entries = [(f"Language: {key}", value) for key, value in languages.items()]
    entries.extend((f"Role: {key}", value) for key, value in roles.items())
    if not entries:
        return None
    entries.sort(key=lambda item: item[1])
    labels = [item[0] for item in entries]
    values = [item[1] for item in entries]
    figure, axis = _base_axes("Language and file-role breakdown", 8.0, max(4.5, len(entries) * 0.32))
    axis.barh(
        labels, values, color=[PALETTE["blue"] if label.startswith("Language") else PALETTE["teal"] for label in labels]
    )
    axis.set_xlabel("File count")
    return _png(figure)


def generate_charts(model: ReportModel) -> list[ChartArtifact]:
    """Create all available report charts and record skips as diagnostics."""
    chart_definitions: list[tuple[str, str, str, str, Callable[[], bytes | None]]] = [
        (
            "risk_tiers",
            "Risk tier distribution",
            "Files are grouped by their evidence-based risk tier.",
            "The slices show the share of scored files in each tier.",
            lambda: _tier_distribution(model),
        ),
        (
            "hotspot_components",
            "Top hotspot risk components",
            "The highest-ranked hotspots are decomposed into their normalized risk signals.",
            "Compare component lengths to see which signals drive each file's score.",
            lambda: _hotspot_components(model),
        ),
        (
            "quadrant",
            "Complexity vs. churn quadrants",
            "Files with both high change activity and complexity are the active-danger candidates.",
            "Files above and right of the median lines combine higher complexity with more recent churn.",
            lambda: _quadrant_scatter(model),
        ),
        (
            "cc_ranks",
            "Cyclomatic-complexity ranks",
            "Function counts are grouped by Radon rank from A through F.",
            "Ranks C through F indicate increasingly complex functions.",
            lambda: _cc_ranks(model),
        ),
        (
            "maintainability",
            "Maintainability index",
            "The histogram shows Python MI scores with thresholds at 20 and 65.",
            "Scores below 20 are difficult to maintain; higher values indicate better maintainability.",
            lambda: _mi_histogram(model),
        ),
        (
            "commit_timeline",
            "Commit timeline",
            "Monthly commit activity is shown for the latest 36-month window.",
            "Gaps or bursts indicate changes in repository activity, not code quality.",
            lambda: _commit_timeline(model),
        ),
        (
            "dependency_graph",
            "Dependency graph",
            "Internal import edges and cyclic components are shown for up to 80 modules.",
            "Red nodes participate in a dependency cycle; larger nodes have greater fan-in.",
            lambda: _dependency_graph(model),
        ),
        (
            "ownership",
            "Ownership and bus factor",
            "The chart compares the top author's share with each hotspot's bus factor.",
            "High concentration with a low bus factor signals knowledge concentration.",
            lambda: _ownership(model),
        ),
        (
            "language_roles",
            "Language and file roles",
            "Repository files are grouped by language and role.",
            "Compare the file mix to understand which parts of the repository dominate analysis.",
            lambda: _language_role_breakdown(model),
        ),
    ]
    charts: list[ChartArtifact] = []
    with _MATPLOTLIB_LOCK:
        for name, title, caption, how_to_read, builder in chart_definitions:
            chart = _chart(model, name, title, caption, how_to_read, builder)
            if chart:
                charts.append(chart)
    return charts
