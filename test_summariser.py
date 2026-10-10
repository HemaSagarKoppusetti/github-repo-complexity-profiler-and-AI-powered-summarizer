# test_summariser.py
import os
from core.cloner import clone_repo, cleanup_repo
from core.scanner import scan_repo
from core.complexity import analyse_all
from core.churn import analyse_churn
from core.graph import build_dependency_graph
from core.hotspots import compute_hotspots
from core.summariser import generate_report

# Run full pipeline
result = clone_repo("https://github.com/pallets/markupsafe")
assert result["success"], f"Clone failed: {result['error']}"

repo_path = result["path"]
repo_name = result["name"]

manifest   = scan_repo(repo_path)
complexity = analyse_all(manifest["python_files"])
churn      = analyse_churn(repo_path, manifest["python_files"])
graph      = build_dependency_graph(manifest["python_files"], repo_path)
hotspots   = compute_hotspots(complexity, churn, repo_path)

# Generate LLM report
report = generate_report(
    repo_name  = repo_name,
    scan       = manifest,
    complexity = complexity,
    churn      = churn,
    graph      = graph,
    hotspots   = hotspots,
)

print("\n" + "═" * 60)
print("  GENERATED REPORT")
print("═" * 60)

if report["error"]:
    print(f"❌ Error: {report['error']}")
else:
    print(report["report_text"])

    # Save to file
    os.makedirs("reports", exist_ok=True)
    out_path = f"reports/{repo_name}_report.md"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(report["report_text"])
    print(f"\n  📄 Report saved to {out_path}")

cleanup_repo(repo_path)
print("\n✅ summariser.py is working correctly")