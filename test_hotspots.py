# test_hotspots.py
from core.cloner import clone_repo, cleanup_repo
from core.scanner import scan_repo
from core.complexity import analyse_all
from core.churn import analyse_churn
from core.hotspots import compute_hotspots

result = clone_repo("https://github.com/pallets/markupsafe")
assert result["success"], f"Clone failed: {result['error']}"

manifest    = scan_repo(result["path"])
complexity  = analyse_all(manifest["python_files"])
churn       = analyse_churn(result["path"], manifest["python_files"])
hotspots    = compute_hotspots(complexity, churn, result["path"])

summary = hotspots["summary"]
print("\n--- Hotspot Summary ---")
print(f"  Files scored   : {summary['total_files_scored']}")
print(f"  🔴 Critical    : {summary['critical_count']}")
print(f"  🟠 High        : {summary['high_count']}")
print(f"  🟡 Medium      : {summary['medium_count']}")
print(f"  🟢 Low         : {summary['low_count']}")
print(f"  Top hotspot    : {summary['top_hotspot']}")
print(f"  Riskiest fn    : {summary['top_hotspot_fn']}()")

print("\n--- Full Hotspot Ranking ---")
print(f"  {'RISK':>6}  {'TIER':<15}  {'CC':>4}  {'MI':>6}  "
      f"{'COMMITS':>7}  {'FILE'}")
print("  " + "-" * 75)
for f in hotspots["hotspots"]:
    print(f"  {f['risk_score']:>6.4f}  {f['risk_tier']:<15}  "
          f"{f['max_cc']:>4}  {f['mi_score']:>6}  "
          f"{f['commit_count']:>7}  {f['rel_path']}")

cleanup_repo(result["path"])
print("\n✅ hotspots.py is working correctly")