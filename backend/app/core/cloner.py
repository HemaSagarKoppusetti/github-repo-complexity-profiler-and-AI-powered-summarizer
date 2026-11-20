# backend/app/core/cloner.py
"""Clones a GitHub repo into a local temp folder and returns the path.

Contains Windows-safe read-only deletion logic and friendly error handling.
"""

from __future__ import annotations

import logging
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from collections.abc import Callable
from typing import Any
from urllib.parse import urlsplit

from app.schemas.analysis import validate_github_repo_url

logger = logging.getLogger(__name__)


def _force_delete(action: Callable[..., Any], name: str, exc: Any) -> None:
    """Windows-safe deletion callback.

    Strips read-only flag from .git files then retries deletion. Compatible
    with both shutil.rmtree's onexc (Python 3.12+) and onerror (Python < 3.12).
    """
    try:
        os.chmod(name, stat.S_IWRITE)
    except Exception:
        pass
    try:
        action(name)
    except Exception as e:
        logger.debug("Failed retry deleting %s: %s", name, e)


def _safe_rmtree(path: str) -> None:
    """Safely removes a directory tree handling Windows file locks and read-only attributes."""
    if not os.path.exists(path):
        return

    # In Python 3.12+, onexc is preferred. In Python 3.11, onerror is used.
    if sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=_force_delete)
    else:
        shutil.rmtree(path, onerror=_force_delete)


def parse_repo_name(github_url: str) -> str:
    """Extracts the repo name from a GitHub URL.

    Example: https://github.com/pallets/flask -> flask
    """
    parts = [part for part in urlsplit(github_url).path.strip("/").split("/") if part]
    return parts[-1].removesuffix(".git") if len(parts) == 2 else "repository"


def get_dir_size_mb(path: str) -> float:
    """Calculates total size of directory in megabytes."""
    total_bytes = 0
    for dirpath, _, filenames in os.walk(path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            try:
                total_bytes += os.path.getsize(fp)
            except OSError:
                pass
    return round(total_bytes / (1024 * 1024), 2)


def clone_repo(
    github_url: str,
    target_dir: str | None = None,
    timeout: int = 180,
    max_size_mb: int = 300,
    depth: int = 2000,
) -> dict[str, Any]:
    """Clones a GitHub repo into a local directory with timeout and size guards.

    Args:
        github_url: Full GitHub URL e.g. https://github.com/pallets/flask
        target_dir: Optional custom path. If None, uses a system temp folder.
        timeout: Clone timeout in seconds (default 180).
        max_size_mb: Maximum allowed repo size in MB (default 300).

    Returns:
        dict with success (bool), path (str | None), name (str), url (str), error (str | None)
    """
    repo_name = parse_repo_name(github_url)
    try:
        canonical_url = validate_github_repo_url(github_url)
    except ValueError as exc:
        return {
            "success": False,
            "path": None,
            "name": repo_name,
            "url": "",
            "error": str(exc),
        }

    if target_dir is None:
        base = tempfile.gettempdir()
        target_dir = os.path.join(base, "repo_profiler", repo_name)

    # Clean existing directory if present
    if os.path.exists(target_dir):
        logger.info("[cloner] Found existing copy at %s, removing...", target_dir)
        _safe_rmtree(target_dir)

    os.makedirs(target_dir, exist_ok=True)
    logger.info("[cloner] Cloning '%s'...", repo_name)

    try:
        subprocess.run(
            [
                "git", "clone", "--depth", str(max(1, depth)),
                "--single-branch", "--no-tags", "--", canonical_url, target_dir,
            ],
            capture_output=True,
            check=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )

        size_mb = get_dir_size_mb(target_dir)
        if size_mb > max_size_mb:
            _safe_rmtree(target_dir)
            msg = f"Repository size ({size_mb} MB) exceeds maximum allowed limit ({max_size_mb} MB)."
            logger.warning("[cloner] ❌ %s", msg)
            return {
                "success": False,
                "path": None,
                "name": repo_name,
                "url": github_url,
                "error": msg,
            }

        logger.info("[cloner] ✅ Done (%s MB) — saved to %s", size_mb, target_dir)
        return {
            "success": True,
            "path": target_dir,
            "name": repo_name,
            "url": canonical_url,
            "error": None,
            "size_mb": size_mb,
            "depth": max(1, depth),
        }
    except subprocess.TimeoutExpired:
        _safe_rmtree(target_dir)
        error_msg = f"Git clone exceeded its {timeout}s timeout."
        logger.error("[cloner] %s", error_msg)
        return {
            "success": False,
            "path": None,
            "name": repo_name,
            "url": canonical_url,
            "error": error_msg,
        }
    except subprocess.CalledProcessError as e:
        error_msg = (e.stderr or "").strip()
        if "Authentication failed" in error_msg or "Repository not found" in error_msg or "not found" in error_msg.lower():
            friendly_err = "Repository not found or private. Please ensure the repository URL is correct and public."
        else:
            friendly_err = f"Git clone failed ({e.returncode})."
        _safe_rmtree(target_dir)
        logger.error("[cloner] ❌ Git error: %s", friendly_err)
        return {
            "success": False,
            "path": None,
            "name": repo_name,
            "url": canonical_url,
            "error": friendly_err,
        }

    except Exception as e:
        _safe_rmtree(target_dir)
        logger.error("[cloner] ❌ Unexpected clone error: %s", e)
        return {
            "success": False,
            "path": None,
            "name": repo_name,
            "url": canonical_url,
            "error": f"Clone failed ({type(e).__name__}).",
        }


def cleanup_repo(path: str | None) -> None:
    """Deletes the cloned repo from disk.

    Windows-safe: handles read-only .git files by forcing permissions first.
    """
    if path and os.path.exists(path):
        _safe_rmtree(path)
        logger.info("[cloner] 🗑️ Cleaned up %s", path)
