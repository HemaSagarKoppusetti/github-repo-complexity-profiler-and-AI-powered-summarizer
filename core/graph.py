# core/graph.py
# Parses Python imports and builds a module dependency graph.
# Detects circular dependencies and finds hub modules.

import os
import ast
import networkx as nx


def get_module_name(filepath: str, repo_path: str) -> str:
    """
    Converts an absolute file path to a dot-notation module name.
    Example:
      /tmp/repo/src/markupsafe/__init__.py → markupsafe.__init__
      /tmp/repo/utils/helper.py            → utils.helper
    """
    rel = os.path.relpath(filepath, repo_path)
    # Remove .py extension
    rel = rel.replace(".py", "")
    # Normalise path separators to dots
    module = rel.replace(os.sep, ".").replace("/", ".")
    # Strip leading dots
    return module.lstrip(".")


def extract_imports(filepath: str) -> list:
    """
    Parses a Python file and extracts all imported module names.
    Handles both:
      import os
      from pathlib import Path  →  pathlib
      from . import something   →  (relative, skipped)

    Returns a list of top-level module name strings.
    """
    imports = []
    try:
        source = open(filepath, "r", encoding="utf-8", errors="ignore").read()
        tree = ast.parse(source)

        for node in ast.walk(tree):
            # import X, import X as Y
            if isinstance(node, ast.Import):
                for alias in node.names:
                    # Take only the top-level package: os.path → os
                    top = alias.name.split(".")[0]
                    if top:
                        imports.append(top)

            # from X import Y, from X.Y import Z
            elif isinstance(node, ast.ImportFrom):
                if node.module and node.level == 0:  # skip relative imports
                    top = node.module.split(".")[0]
                    if top:
                        imports.append(top)

    except SyntaxError:
        pass  # skip unparseable files silently
    except Exception:
        pass

    return list(set(imports))  # deduplicate


def build_dependency_graph(python_files: list, repo_path: str) -> dict:
    """
    Builds a directed dependency graph from all Python files.
    """
    print(f"  [graph] Building dependency graph for "
          f"{len(python_files)} Python files...")

    # Build module map: full_dotted_name → filepath
    module_map = {}
    for fp in python_files:
        mod_name = get_module_name(fp, repo_path)
        module_map[mod_name] = fp

    # Build an expanded lookup with every dotted segment as a key
    # e.g. "src.markupsafe.__init__" also registers:
    #   "markupsafe.__init__", "__init__", "markupsafe"
    expanded_map = dict(module_map)
    for mod_name in list(module_map.keys()):
        parts = mod_name.split(".")
        for i in range(len(parts)):
            sub = ".".join(parts[i:])
            if sub not in expanded_map:
                expanded_map[sub] = module_map[mod_name]
            # Also register the package name alone (e.g. "markupsafe")
            if i < len(parts) - 1:
                pkg = parts[i]
                if pkg not in expanded_map:
                    expanded_map[pkg] = module_map[mod_name]

    G = nx.DiGraph()

    # Add all repo modules as nodes
    for mod_name in module_map:
        G.add_node(mod_name)

    external_packages = set()

    for fp in python_files:
        src_module = get_module_name(fp, repo_path)
        imported_names = extract_imports(fp)

        for imp in imported_names:
            if imp in expanded_map:
                dst_module = get_module_name(expanded_map[imp], repo_path)
                if src_module != dst_module:  # no self-loops
                    G.add_edge(src_module, dst_module)
            else:
                external_packages.add(imp)

    # ── Cycle detection ───────────────────────────────────────────────────
    try:
        cycles = list(nx.simple_cycles(G))
    except Exception:
        cycles = []

    # ── Hub modules: most imported (highest in-degree) ────────────────────
    in_degrees = sorted(G.in_degree(), key=lambda x: x[1], reverse=True)
    hub_modules = [
        {"module": mod, "imported_by": deg}
        for mod, deg in in_degrees
        if deg > 0
    ][:5]

    # ── Isolated modules: no edges at all ─────────────────────────────────
    isolated = [n for n in G.nodes()
                if G.in_degree(n) == 0 and G.out_degree(n) == 0]

    # ── Graph-level stats ──────────────────────────────────────────────────
    stats = {
        "node_count":    G.number_of_nodes(),
        "edge_count":    G.number_of_edges(),
        "density":       round(nx.density(G), 4),
        "cycle_count":   len(cycles),
        "has_cycles":    len(cycles) > 0,
        "external_deps": len(external_packages),
    }

    print(f"  [graph] ✅ {stats['node_count']} nodes | "
          f"{stats['edge_count']} edges | "
          f"{stats['cycle_count']} cycles | "
          f"density={stats['density']}")

    return {
        "graph":             G,
        "nodes":             list(G.nodes()),
        "edges":             list(G.edges()),
        "cycles":            cycles,
        "hub_modules":       hub_modules,
        "isolated_modules":  isolated,
        "external_packages": sorted(external_packages),
        "stats":             stats,
    }

def render_graph_html(graph_data: dict, output_path: str) -> str:
    """
    Renders the dependency graph as an interactive HTML file using pyvis.
    Node size = in-degree (more imported = bigger node).
    Red nodes = part of a circular dependency.
    Returns the output path.
    """
    from pyvis.network import Network

    G = graph_data["graph"]
    cycles = graph_data["cycles"]

    # Flatten cycle nodes into a set for quick lookup
    cycle_nodes = set()
    for cycle in cycles:
        for node in cycle:
            cycle_nodes.add(node)

    net = Network(height="600px", width="100%",
                  directed=True, bgcolor="#1e1e2e",
                  font_color="white")

    net.barnes_hut(gravity=-8000, central_gravity=0.3,
                   spring_length=150, spring_strength=0.05)

    for node in G.nodes():
        in_deg = G.in_degree(node)
        size   = 15 + (in_deg * 8)
        color  = "#E74C3C" if node in cycle_nodes else "#5B8AF5"
        label  = node.split(".")[-1]  # show only the short name
        net.add_node(node, label=label, size=size,
                     color=color, title=node)

    for src, dst in G.edges():
        net.add_edge(src, dst, color="#666688", arrows="to")

    net.write_html(output_path)
    print(f"  [graph] 📊 Graph saved to {output_path}")
    return output_path