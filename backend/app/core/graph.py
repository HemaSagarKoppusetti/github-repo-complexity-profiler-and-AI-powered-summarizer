"""Package-aware dependency graph construction and bounded cycle analysis."""

from __future__ import annotations

import ast
import logging
import os
from pathlib import Path
from typing import Any

import networkx as nx

logger = logging.getLogger(__name__)

GRAPH_EXTENSIONS = {".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".java"}


def _relative_path(filepath: str, repo_path: str) -> str:
    """Return a normalized repository-relative path."""
    try:
        return Path(filepath).resolve().relative_to(Path(repo_path).resolve()).as_posix()
    except ValueError:
        return Path(filepath).as_posix().replace("\\", "/")


def get_module_name(filepath: str, repo_path: str) -> str:
    """Convert a file path into its package/module name."""
    relative = _relative_path(filepath, repo_path)
    path = Path(relative)
    parts = list(path.with_suffix("").parts)
    if parts and parts[-1] == "__init__":
        parts.pop()
    elif parts and parts[-1] == "index":
        parts.pop()
    return ".".join(parts)


def _python_import_records(filepath: str) -> list[dict[str, Any]]:
    """Extract Python import records when cached scanner data is unavailable."""
    try:
        source = Path(filepath).read_text(encoding="utf-8")
        tree = ast.parse(source)
    except (OSError, UnicodeError, SyntaxError):
        return []

    imports: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend({
                "module": alias.name,
                "level": 0,
                "name": None,
            } for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.extend({
                "module": node.module or "",
                "level": node.level,
                "name": alias.name,
            } for alias in node.names)
    return imports


def extract_imports(filepath: str) -> list[str]:
    """Return imported module names, preserving the legacy helper contract."""
    return sorted({
        str(item["module"]).split(".")[0]
        for item in _python_import_records(filepath)
        if item.get("module")
    })


def _module_index(
    files: list[dict[str, Any]],
    repo_path: str,
) -> tuple[dict[str, str], dict[str, str]]:
    """Build exact module and path indexes without short-name fuzzy aliases."""
    module_to_path: dict[str, str] = {}
    path_to_module: dict[str, str] = {}
    for entry in files:
        relative = str(entry.get("rel_path") or _relative_path(str(entry["path"]), repo_path))
        extension = str(entry.get("extension") or Path(relative).suffix.lower())
        if extension not in GRAPH_EXTENSIONS:
            continue
        module = get_module_name(relative, ".")
        if not module:
            continue
        module_to_path[module] = relative
        path_to_module[relative] = module
        if module.startswith(("src.", "lib.")):
            module_to_path.setdefault(module.split(".", 1)[1], relative)
    return module_to_path, path_to_module


def _resolve_python_import(
    source_module: str,
    import_record: dict[str, Any],
    module_to_path: dict[str, str],
    source_is_package: bool = False,
) -> str | None:
    """Resolve absolute, relative, package, and from-import Python forms."""
    imported_module = str(import_record.get("module") or "")
    imported_name = import_record.get("name")
    level = int(import_record.get("level") or 0)
    if level:
        source_parts = source_module.split(".")
        package_parts = source_parts if source_is_package else source_parts[:-1]
        ascend = max(0, level - 1)
        if ascend:
            package_parts = package_parts[:max(0, len(package_parts) - ascend)]
        base_parts = package_parts + ([part for part in imported_module.split(".") if part] if imported_module else [])
        candidates = [".".join(base_parts + [str(imported_name)])] if imported_name else []
        if base_parts:
            candidates.append(".".join(base_parts))
    else:
        base_parts = [part for part in imported_module.split(".") if part]
        candidates = []
        if imported_name:
            candidates.extend([".".join(base_parts + [str(imported_name)]), ".".join(base_parts)])
        else:
            candidates.append(".".join(base_parts))

    for candidate in candidates:
        if candidate in module_to_path:
            path = module_to_path[candidate]
            return get_module_name(path, ".")
    return None


def _resolve_js_import(source_module: str, import_name: str, module_to_path: dict[str, str]) -> str | None:
    """Resolve relative JS/TS module paths against exact repository module paths."""
    if not import_name.startswith("."):
        return None
    parent = source_module.rpartition(".")[0]
    normalized = os.path.normpath(os.path.join(parent.replace(".", "/"), import_name)).replace("\\", "/")
    base = normalized.replace("/", ".")
    candidates = [base, *(f"{base}{suffix}" for suffix in (".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"))]
    for candidate in candidates:
        for module in module_to_path:
            if module == candidate or module.removesuffix(".__init__") == candidate:
                return get_module_name(module_to_path[module], ".")
    return None


def _representative_cycles(graph: nx.DiGraph, limit: int = 20) -> tuple[list[list[str]], list[list[str]]]:
    """Return cyclic strongly connected components and bounded cycle samples."""
    components = [
        sorted(component)
        for component in nx.strongly_connected_components(graph)
        if len(component) > 1
    ]
    samples: list[list[str]] = []
    for component in components:
        if len(samples) >= limit:
            break
        subgraph = graph.subgraph(component)
        try:
            edge_cycle = nx.find_cycle(subgraph)
            samples.append([edge_cycle[0][0], *[target for _, target in edge_cycle]])
        except nx.NetworkXNoCycle:
            continue
    return components, samples


def _pagerank_scores(graph: nx.DiGraph) -> dict[str, float]:
    """Compute PageRank without requiring NetworkX's optional SciPy backend."""
    nodes = list(graph)
    if not nodes:
        return {}
    damping = 0.85
    score = {node: 1.0 / len(nodes) for node in nodes}
    out_degree = dict(graph.out_degree())
    for _ in range(100):
        dangling_mass = sum(score[node] for node in nodes if out_degree[node] == 0) / len(nodes)
        next_score = {
            node: (1.0 - damping) / len(nodes) + damping * dangling_mass
            for node in nodes
        }
        for source, target in graph.edges():
            if out_degree[source]:
                next_score[target] += damping * score[source] / out_degree[source]
        if sum(abs(next_score[node] - score[node]) for node in nodes) < len(nodes) * 1e-6:
            return next_score
        score = next_score
    return score


def build_dependency_graph(
    python_files: list[str],
    repo_path: str,
    manifest_files: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build a bounded dependency graph while retaining existing result keys."""
    root = Path(repo_path).resolve()
    if manifest_files is None:
        entries = [
            {
                "path": str(path),
                "rel_path": _relative_path(str(path), repo_path),
                "extension": Path(path).suffix.lower(),
                "language": "Python",
                "imports": _python_import_records(str(path)),
            }
            for path in python_files
        ]
    else:
        entries = manifest_files
    module_to_path, path_to_module = _module_index(entries, str(root))
    graph = nx.DiGraph()
    graph.add_nodes_from(sorted(path_to_module.values()))
    external_packages: set[str] = set()

    for entry in entries:
        relative = str(entry.get("rel_path") or _relative_path(str(entry["path"]), str(root)))
        source_module = path_to_module.get(relative)
        if source_module is None:
            continue
        extension = str(entry.get("extension") or Path(relative).suffix.lower())
        is_package = relative.endswith("/__init__.py") or relative == "__init__.py"
        imports = entry.get("imports")
        if not isinstance(imports, list):
            imports = _python_import_records(str(root / relative)) if extension == ".py" else []
        for record in imports:
            if not isinstance(record, dict):
                continue
            imported = str(record.get("module") or "")
            if extension == ".py":
                target = _resolve_python_import(source_module, record, module_to_path, is_package)
            else:
                target = _resolve_js_import(source_module, imported, module_to_path)
                if target is None and imported and extension == ".java":
                    target = get_module_name(module_to_path[imported], ".") if imported in module_to_path else None
            if target and target != source_module:
                graph.add_edge(source_module, target)
            elif imported and not imported.startswith("."):
                external_packages.add(imported.split(".")[0])

    cycle_components, cycles = _representative_cycles(graph)
    cyclic_nodes = {node for component in cycle_components for node in component}
    node_count = graph.number_of_nodes()
    edge_count = graph.number_of_edges()
    if node_count and edge_count:
        pagerank = _pagerank_scores(graph)
        try:
            betweenness = nx.betweenness_centrality(
                graph,
                k=min(100, node_count) if node_count > 500 else None,
                seed=42,
            )
        except (nx.NetworkXException, ValueError):
            betweenness = {node: 0.0 for node in graph}
    else:
        pagerank = {node: 0.0 for node in graph}
        betweenness = {node: 0.0 for node in graph}

    module_metrics = []
    for node in graph:
        fan_in = int(graph.in_degree(node))
        fan_out = int(graph.out_degree(node))
        module_metrics.append({
            "module": node,
            "fan_in": fan_in,
            "fan_out": fan_out,
            "imported_by": fan_in,
            "instability": round(fan_out / (fan_in + fan_out), 4) if fan_in + fan_out else 0.0,
            "pagerank": round(float(pagerank[node]), 6),
            "betweenness": round(float(betweenness[node]), 6),
            "in_cycle": node in cyclic_nodes,
        })
    module_metrics.sort(key=lambda item: (-item["fan_in"], -item["pagerank"], item["module"]))
    hub_modules = [item for item in module_metrics if item["fan_in"] > 0][:10]
    isolated = [node for node in graph if graph.in_degree(node) == 0 and graph.out_degree(node) == 0]
    density = round(float(nx.density(graph)), 4) if node_count > 1 else 0.0
    stats = {
        "node_count": node_count,
        "edge_count": edge_count,
        "density": density,
        "cycle_count": len(cycle_components),
        "cycle_components": len(cycle_components),
        "has_cycles": bool(cycle_components),
        "external_deps": len(external_packages),
    }
    ui_nodes = [{
        "id": item["module"],
        "label": item["module"].split(".")[-1],
        "full_name": item["module"],
        "in_degree": item["fan_in"],
        "out_degree": item["fan_out"],
        "in_cycle": item["in_cycle"],
        "instability": item["instability"],
        "pagerank": item["pagerank"],
        "betweenness": item["betweenness"],
    } for item in module_metrics]
    edges = [[source, target] for source, target in graph.edges()]
    return {
        "nodes": list(graph.nodes()),
        "edges": edges,
        "cycles": cycles,
        "cycle_components": cycle_components,
        "hub_modules": hub_modules,
        "module_metrics": module_metrics,
        "isolated_modules": isolated,
        "external_packages": sorted(external_packages),
        "stats": stats,
        "graph_elements": {
            "nodes": ui_nodes,
            "edges": [{"source": source, "target": target} for source, target in edges],
        },
    }


def render_graph_html(graph_data: dict[str, Any], output_path: str) -> str:
    """Render a graph as interactive HTML using PyVis."""
    from pyvis.network import Network

    cycles = graph_data.get("cycles", [])
    cycle_nodes = {node for cycle in cycles for node in cycle}
    network = Network(height="600px", width="100%", directed=True, bgcolor="#1e1e2e", font_color="white")
    network.barnes_hut(gravity=-8000, central_gravity=0.3, spring_length=150, spring_strength=0.05)
    in_degrees = {node: 0 for node in graph_data.get("nodes", [])}
    for _source, target in graph_data.get("edges", []):
        in_degrees[target] = in_degrees.get(target, 0) + 1
    for node in graph_data.get("nodes", []):
        network.add_node(
            node,
            label=node.split(".")[-1],
            size=15 + in_degrees.get(node, 0) * 8,
            color="#E74C3C" if node in cycle_nodes else "#5B8AF5",
            title=node,
        )
    for source, target in graph_data.get("edges", []):
        network.add_edge(source, target, color="#666688", arrows="to")
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    network.write_html(output_path)
    return output_path
