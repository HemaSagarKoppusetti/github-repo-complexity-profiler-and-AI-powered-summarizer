# test_complexity.py
from core.cloner import clone_repo, cleanup_repo
from core.scanner import scan_repo
from core.complexity import analyse_all

# Clone and scan
result = clone_repo("https://github.com/pallets/markupsafe")
assert result["success"], f"Clone failed: {result['error']}"

manifest = scan_repo(result["path"])

# Run complexity analysis
complexity = analyse_all(manifest["python_files"])

summary = complexity["summary"]
results = complexity["results"]

print("\n--- Repo-wide Summary ---")
print(f"Files analysed   : {summary['total_files_analysed']}")
print(f"Total functions  : {summary['total_functions']}")
print(f"Average MI score : {summary['avg_mi_score']} / 100")
print(f"Low MI files (<20): {summary['low_mi_file_count']}")

print("\n--- CC Rank Distribution ---")
for rank, count in summary["rank_distribution"].items():
    bar = "█" * count
    print(f"  Rank {rank}: {bar} ({count})")

print("\n--- Top 5 Most Complex Functions ---")
for fn in summary["top_complex_functions"]:
    import os
    fname = os.path.basename(fn["filepath"])
    print(f"  CC={fn['complexity']} [{fn['rank']}]  {fn['name']}()  in {fname}  (line {fn['lineno']})")

print("\n--- 5 Least Maintainable Files ---")
for r in summary["least_maintainable"]:
    import os
    fname = os.path.basename(r["filepath"])
    print(f"  MI={r['mi_score']:>6} [{r['mi_rank']}]  {fname}")

print("\n--- Per-file Results ---")
for r in results:
    import os
    fname = os.path.basename(r["filepath"])
    if r["error"]:
        print(f"  ❌ {fname} — {r['error']}")
    else:
        print(f"  MI={r['mi_score']:>6} [{r['mi_rank']}]  "
              f"avg_cc={r['avg_cc']}  max_cc={r['max_cc']}  "
              f"hotspot={r['hotspot_fn']}  — {fname}")

cleanup_repo(result["path"])
print("\n✅ complexity.py is working correctly")