import networkx as nx

from app.core.graph import _representative_cycles, build_dependency_graph


def _entry(path, imports, extension=".py", language="Python"):
    return {
        "path": path,
        "rel_path": path,
        "extension": extension,
        "language": language,
        "imports": imports,
    }


def test_python_relative_imports_resolve_with_src_layout():
    files = [
        _entry("src/pkg/__init__.py", [{"module": "", "level": 1, "name": "a"}]),
        _entry("src/pkg/a.py", [{"module": "", "level": 1, "name": "b"}]),
        _entry("src/pkg/b.py", [{"module": "", "level": 1, "name": "a"}]),
    ]

    graph = build_dependency_graph(
        ["src/pkg/__init__.py", "src/pkg/a.py", "src/pkg/b.py"],
        ".",
        files,
    )

    assert ["src.pkg.a", "src.pkg.b"] in graph["edges"]
    assert ["src.pkg.b", "src.pkg.a"] in graph["edges"]
    assert graph["stats"]["cycle_count"] == 1
    assert graph["cycles"]


def test_javascript_relative_import_resolves_to_file():
    files = [
        _entry("src/app.ts", [{"module": "./components/button", "level": 0, "name": None}], ".ts", "TypeScript"),
        _entry("src/components/button.ts", [], ".ts", "TypeScript"),
    ]

    graph = build_dependency_graph([], ".", files)

    assert ["src.app", "src.components.button"] in graph["edges"]


def test_large_graph_cycle_detection_uses_scc_and_caps_samples():
    graph = nx.DiGraph()
    graph.add_edges_from((f"m{index}", f"m{index + 1}") for index in range(1500))
    graph.add_edge("m1500", "m0")
    graph.add_nodes_from(f"isolated{index}" for index in range(1500))

    components, samples = _representative_cycles(graph)

    assert len(components) == 1
    assert len(components[0]) == 1501
    assert len(samples) == 1
    assert samples[0][0] == samples[0][-1]
