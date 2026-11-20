# backend/app/core/graph.py
"""Parses Python imports and builds a module dependency graph.

Detects circular dependencies and finds hub modules. Returns JSON-serialisable
data structures.
"""

from __future__ import annotations

import ast
import logging
import os
from typing import Any

import networkx as nx

logger = logging.getLogger(__name__)


def get_module_name(filepath: str, repo_path: str) -> str:
    """Converts an absolute file path to a dot-notation module name.

    Example:
      repo/src/markupsafe/__init__.py -> src.markupsafe.__init__
      repo/utils/helper.py            -> utils.helper
    """
    rel = os.path.relpath(filepath, repo_path)
    rel = rel.replace(".py", "")
    module = rel.replace(os.sep, ".").replace("/", ".")
    return module.strip(".")


def extract_imports(filepath: str) -> list[str]:
    """Parses a Python file and extracts all imported module names.

    Extracts:
      import os            -> os
      import os.path       -> os
      from pathlib import Path -> pathlib
    """
    imports: list[str] = []
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            source = f.read()

        tree = ast.parse(source)

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top = alias.name.split(".")[0]
                    if top:
                        imports.append(top)
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:  # skip relative imports
                top = node.module.split(".")[0]
                if top:
                    imports.append(top)

    except SyntaxError:
        pass
    except Exception as e:
        logger.debug("Import parsing error in %s: %s", filepath, e)

    return sorted(set(imports))


def build_dependency_graph(python_files: list[str], repo_path: str) -> dict[str, Any]:
    """Builds a directed dependency graph from all Python files.

    Returns JSON-serialisable dictionary.
    """
    logger.info(
        "[graph] Building dependency graph for %d Python files...",
        len(python_files),
    )

    module_map: dict[str, str] = {}
    for fp in python_files:
        mod_name = get_module_name(fp, repo_path)
        module_map[mod_name] = fp

    # Build lookup map for resolving imports to internal modules.
    # Tightened resolver:
    # 1. Full dotted module name (e.g., 'src.markupsafe._native')
    # 2. Package-stripped module name if under 'src.' (e.g. 'markupsafe._native' or 'markupsafe')
    # 3. Top-level package names that correspond to folders with python files
    resolved_lookup: dict[str, str] = dict(module_map)
    for mod_name in list(module_map.keys()):
        parts = mod_name.split(".")
        # Handle src-layout: if module starts with 'src.', allow 'markupsafe' or 'markupsafe.__init__'
        if parts[0] in {"src", "lib"} and len(parts) > 1:
            sub = ".".join(parts[1:])
            resolved_lookup[sub] = module_map[mod_name]
            resolved_lookup[parts[1]] = module_map[mod_name]
        # Also map the top package name (e.g. 'markupsafe') if not already mapped
        top_pkg = parts[0]
        if top_pkg not in resolved_lookup:
            resolved_lookup[top_pkg] = module_map[mod_name]

    G = nx.DiGraph()

    for mod_name in module_map:
        G.add_node(mod_name)

    external_packages: set[str] = set()

    for fp in python_files:
        src_module = get_module_name(fp, repo_path)
        imported_names = extract_imports(fp)

        for imp in imported_names:
            if imp in resolved_lookup:
                dst_module = get_module_name(resolved_lookup[imp], repo_path)
                if src_module != dst_module:
                    G.add_edge(src_module, dst_module)
            else:
                external_packages.add(imp)

    # Detect cycles
    try:
        cycles = list(nx.simple_cycles(G))
    except Exception:
        cycles = []

    cycle_nodes = {node for cycle in cycles for node in cycle}

    # Hub modules (highest in-degree)
    in_degrees = sorted(G.in_degree(), key=lambda x: x[1], reverse=True)
    hub_modules = [
        {"module": mod, "imported_by": deg}
        for mod, deg in in_degrees
        if deg > 0
    ][:10]

    # Isolated modules
    isolated = [
        n for n in G.nodes() if G.in_degree(n) == 0 and G.out_degree(n) == 0
    ]

    density = round(float(nx.density(G)), 4) if len(G.nodes) > 1 else 0.0

    stats = {
        "node_count": G.number_of_nodes(),
        "edge_count": G.number_of_edges(),
        "density": density,
        "cycle_count": len(cycles),
        "has_cycles": len(cycles) > 0,
        "external_deps": len(external_packages),
    }

    # Format nodes and edges with rich UI properties for cytoscape / force-graph
    ui_nodes = []
    for node in G.nodes():
        in_deg = int(G.in_degree(node))
        out_deg = int(G.out_degree(node))
        ui_nodes.append({
            "id": node,
            "label": node.split(".")[-1],
            "full_name": node,
            "in_degree": in_deg,
            "out_degree": out_deg,
            "in_cycle": node in cycle_nodes,
        })

    ui_edges = [
        {"source": src, "target": dst}
        for src, dst in G.edges()
    ]

    logger.info(
        "[graph] ✅ %d nodes | %d edges | %d cycles | density=%s",
        stats["node_count"],
        stats["edge_count"],
        stats["cycle_count"],
        stats["density"],
    )

    return {
        "nodes": list(G.nodes()),
        "edges": [[src, dst] for src, dst in G.edges()],
        "cycles": cycles,
        "hub_modules": hub_modules,
        "isolated_modules": isolated,
        "external_packages": sorted(external_packages),
        "stats": stats,
        "graph_elements": {
            "nodes": ui_nodes,
            "edges": ui_edges,
        },
    }


def render_graph_html(graph_data: dict[str, Any], output_path: str) -> str:
    """Renders the dependency graph as an interactive HTML file using pyvis."""
    from pyvis.network import Network

    cycles = graph_data.get("cycles", [])
    cycle_nodes = {node for cycle in cycles for node in cycle}

    net = Network(
        height="600px",
        width="100%",
        directed=True,
        bgcolor="#1e1e2e",
        font_color="white",
    )

    net.barnes_hut(
        gravity=-8000,
        central_gravity=0.3,
        spring_length=150,
        spring_strength=0.05,
    )

    nodes = graph_data.get("nodes", [])
    edges = graph_data.get("edges", [])

    # Calculate in-degrees
    in_degrees: dict[str, int] = {n: 0 for n in nodes}
    for edge in edges:
        src, dst = edge[0], edge[1]
        in_degrees[dst] = in_degrees.get(dst, 0) + 1

    for node in nodes:
        in_deg = in_degrees.get(node, 0)
        size = 15 + (in_deg * 8)
        color = "#E74C3C" if node in cycle_nodes else "#5B8AF5"
        label = node.split(".")[-1]
        net.add_node(node, label=label, size=size, color=color, title=node)

    for edge in edges:
        src, dst = edge[0], edge[1]
        net.add_edge(src, dst, color="#666688", arrows="to")

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    net.write_html(output_path)
    logger.info("[graph] 📊 Graph saved to %s", output_path)
    return output_path
