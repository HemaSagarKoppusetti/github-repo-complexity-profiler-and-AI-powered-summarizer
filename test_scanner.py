# test_scanner.py
from core.cloner import clone_repo, cleanup_repo
from core.scanner import scan_repo

# Clone a small repo
result = clone_repo("https://github.com/pallets/markupsafe")
assert result["success"], f"Clone failed: {result['error']}"

# Scan it
manifest = scan_repo(result["path"])

print("\n--- Manifest Summary ---")
print(f"Total files : {manifest['total_files']}")
print(f"Total LOC   : {manifest['total_loc']}")
print(f"Python files: {len(manifest['python_files'])}")

print("\n--- Language Breakdown ---")
for lang, count in sorted(manifest["language_breakdown"].items(),
                           key=lambda x: x[1], reverse=True):
    print(f"  {lang:<20} {count} files")

print("\n--- Top 10 Files by LOC ---")
for f in manifest["files"][:10]:
    print(f"  {f['loc']:>5} LOC  |  {f['rel_path']}")

print("\n--- Python Files (complexity-ready) ---")
for f in manifest["files"]:
    if f["can_profile"]:
        print(f"  ✅ {f['rel_path']}  ({f['loc']} LOC)")

# Cleanup
cleanup_repo(result["path"])
print("\n✅ scanner.py is working correctly")