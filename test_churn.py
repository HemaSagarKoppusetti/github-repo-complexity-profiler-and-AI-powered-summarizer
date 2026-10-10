# test_churn.py
from core.cloner import clone_repo, cleanup_repo
from core.scanner import scan_repo
from core.churn import analyse_churn

result = clone_repo("https://github.com/pallets/markupsafe")
assert result["success"], f"Clone failed: {result['error']}"

manifest = scan_repo(result["path"])
churn_data = analyse_churn(result["path"], manifest["python_files"])

stats = churn_data["stats"]
print("\n--- Repo Git Stats ---")
print(f"  Total commits  : {stats['total_commits']}")
print(f"  Total authors  : {stats['total_authors']}")
print(f"  Repo age       : {stats['repo_age_days']} days")
print(f"  First commit   : {stats['first_commit']}")
print(f"  Last commit    : {stats['last_commit']}")

print("\n--- Top 5 Most Churned Files ---")
for f in churn_data["most_churned"]:
    print(f"  {f['commit_count']:>4} commits  |  "
          f"rate={f['churn_rate']:>5}/mo  |  "
          f"{f['author_count']} author(s)  |  "
          f"{f['rel_path']}")

print("\n--- All Python File Churn ---")
for rel_path, data in churn_data["file_churn"].items():
    print(f"  {data['commit_count']:>4} commits  |  "
          f"{data['last_changed'] or 'never':>12}  |  "
          f"{rel_path}")

cleanup_repo(result["path"])
print("\n✅ churn.py is working correctly")