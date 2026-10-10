# core/cloner.py
# Clones a GitHub repo into a local temp folder and returns the path.

import os
import stat
import shutil
import tempfile
from git import Repo, GitCommandError


def _force_delete(action, name, exc):
    """
    Windows-safe deletion callback.
    Strips read-only flag from .git files then retries.
    """
    os.chmod(name, stat.S_IWRITE)
    action(name)


def parse_repo_name(github_url: str) -> str:
    """
    Extracts the repo name from a GitHub URL.
    Example: https://github.com/pallets/flask → flask
    """
    url = github_url.rstrip("/").removesuffix(".git")
    return url.split("/")[-1]


def clone_repo(github_url: str, target_dir: str = None) -> dict:
    """
    Clones a GitHub repo into a local directory.

    Args:
        github_url : Full GitHub URL e.g. https://github.com/pallets/flask
        target_dir : Optional custom path. If None, uses a system temp folder.

    Returns:
        A dict with:
          - success (bool)
          - path    (str)  : local path to the cloned repo
          - name    (str)  : repo name
          - url     (str)  : original URL
          - error   (str)  : error message if success is False
    """

    repo_name = parse_repo_name(github_url)

    if target_dir is None:
        base = tempfile.gettempdir()
        target_dir = os.path.join(base, "repo_profiler", repo_name)

    # If already cloned before, delete and re-clone fresh (Windows-safe)
    if os.path.exists(target_dir):
        print(f"  [cloner] Found existing copy at {target_dir}, removing...")
        shutil.rmtree(target_dir, onexc=_force_delete)

    os.makedirs(target_dir, exist_ok=True)

    print(f"  [cloner] Cloning '{repo_name}' from {github_url}...")

    try:
        Repo.clone_from(github_url, target_dir)
        print(f"  [cloner] ✅ Done — saved to {target_dir}")
        return {
            "success": True,
            "path": target_dir,
            "name": repo_name,
            "url": github_url,
            "error": None
        }

    except GitCommandError as e:
        error_msg = str(e)
        print(f"  [cloner] ❌ Git error: {error_msg}")
        return {
            "success": False,
            "path": None,
            "name": repo_name,
            "url": github_url,
            "error": error_msg
        }

    except Exception as e:
        print(f"  [cloner] ❌ Unexpected error: {e}")
        return {
            "success": False,
            "path": None,
            "name": repo_name,
            "url": github_url,
            "error": str(e)
        }


def cleanup_repo(path: str):
    """
    Deletes the cloned repo from disk.
    Windows-safe: handles read-only .git files by forcing permissions first.
    """
    if path and os.path.exists(path):
        shutil.rmtree(path, onexc=_force_delete)
        print(f"  [cloner] 🗑️  Cleaned up {path}")