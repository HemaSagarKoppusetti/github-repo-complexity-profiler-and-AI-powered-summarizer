# test_graph.py
import os
from core.cloner import clone_repo, cleanup_repo
from core.scanner import scan_repo
from core.graph import build_dependency_graph, render_graph_html

# Use a slightly bigger repo to see more interesting graph structure
result = clone_repo("https://github.com/pallets/markupsafe")
assert result["success"], f"Clone failed: {result['error']}"

manifest = scan_repo(result["path"])
graph_data = build_dependency_graph(
    manifest["python_files"],
    result["path"]
)

print("\n--- Graph Stats ---")
stats = graph_data["stats"]
for k, v in stats.items():
    print(f"  {k:<20} {v}")

print("\n--- Hub Modules (most imported) ---")
if graph_data["hub_modules"]:
    for h in graph_data["hub_modules"]:
        print(f"  {h['module']:<45} imported by {h['imported_by']} modules")
else:
    print("  (none — no intra-repo imports detected)")

print("\n--- Circular Dependencies ---")
if graph_data["cycles"]:
    for i, cycle in enumerate(graph_data["cycles"], 1):
        print(f"  Cycle {i}: {' → '.join(cycle)} → {cycle[0]}")
else:
    print("  ✅ No circular dependencies found")

print("\n--- Isolated Modules (no connections) ---")
for mod in graph_data["isolated_modules"]:
    print(f"  {mod}")

print("\n--- External Packages Referenced ---")
print("  " + ", ".join(graph_data["external_packages"][:20]))

print("\n--- All Edges (intra-repo imports) ---")
if graph_data["edges"]:
    for src, dst in graph_data["edges"]:
        print(f"  {src} → {dst}")
else:
    print("  (no intra-repo imports found)")

# Render interactive HTML graph
os.makedirs("reports", exist_ok=True)
render_graph_html(graph_data, "reports/dependency_graph.html")
print("\n  Open reports/dependency_graph.html in your browser to see the graph")

cleanup_repo(result["path"])
print("\n✅ graph.py is working correctly")