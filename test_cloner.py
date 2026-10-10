# test_cloner.py
from core.cloner import clone_repo, cleanup_repo

# We'll use a tiny real repo to keep the test fast
result = clone_repo("https://github.com/pallets/markupsafe")

print("\n--- Result ---")
print(f"Success : {result['success']}")
print(f"Name    : {result['name']}")
print(f"Path    : {result['path']}")
print(f"Error   : {result['error']}")

if result["success"]:
    import os
    files = os.listdir(result["path"])
    print(f"\nFiles in repo root ({len(files)} items):")
    for f in files:
        print(f"  {f}")

    # Clean up after test
    cleanup_repo(result["path"])
    print("\n✅ cloner.py is working correctly")