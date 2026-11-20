# backend/app/core/scanner.py
"""Walks a cloned repo and builds a manifest of all analysable code files."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Folders to always skip
SKIP_DIRS = {
    ".git",
    ".github",
    ".venv",
    "venv",
    "env",
    ".env",
    "node_modules",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    "dist",
    "build",
    "eggs",
    ".eggs",
    ".tox",
    ".nox",
    "site-packages",
    ".idea",
    ".vscode",
    "migrations",
    "staticfiles",
    "media",
}

# File extensions mapped to language names
LANGUAGE_MAP = {
    ".py": "Python",
    ".js": "JavaScript",
    ".ts": "TypeScript",
    ".jsx": "JavaScript",
    ".tsx": "TypeScript",
    ".java": "Java",
    ".cpp": "C++",
    ".c": "C",
    ".h": "C/C++ Header",
    ".cs": "C#",
    ".go": "Go",
    ".rb": "Ruby",
    ".rs": "Rust",
    ".php": "PHP",
    ".kt": "Kotlin",
    ".swift": "Swift",
    ".scala": "Scala",
    ".r": "R",
    ".sh": "Shell",
    ".yaml": "YAML",
    ".yml": "YAML",
    ".json": "JSON",
    ".md": "Markdown",
    ".html": "HTML",
    ".css": "CSS",
    ".sql": "SQL",
    ".toml": "TOML",
    ".ini": "INI",
    ".cfg": "Config",
}

COMPLEXITY_SUPPORTED = {".py"}


def count_lines(filepath: str) -> int:
    """Counts non-empty lines in a file. Returns 0 on read errors."""
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            return sum(1 for line in f if line.strip())
    except Exception:
        return 0


def should_skip_dir(dirname: str) -> bool:
    """Returns True if this directory should be excluded from scanning."""
    return dirname in SKIP_DIRS or dirname.endswith(".egg-info")


def scan_repo(repo_path: str, max_python_files: int = 2000) -> dict[str, Any]:
    """Recursively walks a repo and builds a file manifest.

    Args:
        repo_path: Local path to the cloned repo.
        max_python_files: Maximum number of Python files to include for complexity analysis.

    Returns:
        dict with:
          - files: list of file dicts
          - total_files: int
          - total_loc: int
          - language_breakdown: dict {language: file_count}
          - python_files: list of paths to .py files (bounded by max_python_files)
          - truncated: bool
          - warning: str | None
    """
    logger.info("[scanner] Scanning %s...", repo_path)

    files = []
    language_counts: dict[str, int] = {}

    for dirpath, dirnames, filenames in os.walk(repo_path):
        dirnames[:] = [d for d in dirnames if not should_skip_dir(d)]

        for filename in filenames:
            ext = Path(filename).suffix.lower()
            if ext not in LANGUAGE_MAP:
                continue

            full_path = os.path.join(dirpath, filename)
            rel_path = os.path.relpath(full_path, repo_path).replace("\\", "/")

            language = LANGUAGE_MAP[ext]
            loc = count_lines(full_path)

            file_entry = {
                "path": full_path,
                "rel_path": rel_path,
                "filename": filename,
                "extension": ext,
                "language": language,
                "loc": loc,
                "can_profile": ext in COMPLEXITY_SUPPORTED,
            }

            files.append(file_entry)
            language_counts[language] = language_counts.get(language, 0) + 1

    # Sort files by LOC descending
    files.sort(key=lambda x: x["loc"], reverse=True)

    total_loc = sum(f["loc"] for f in files)
    all_python_files = [f["path"] for f in files if f["extension"] == ".py"]

    truncated = False
    warning = None
    if len(all_python_files) > max_python_files:
        truncated = True
        warning = f"Repository contains {len(all_python_files)} Python files; analysis was capped at the largest {max_python_files} files."
        logger.warning("[scanner] %s", warning)
        # Cap to largest files by loc
        py_files_sorted = [f["path"] for f in files if f["extension"] == ".py"]
        python_files = py_files_sorted[:max_python_files]
    else:
        python_files = all_python_files

    logger.info(
        "[scanner] ✅ Found %d files | %d LOC | %d Python files",
        len(files),
        total_loc,
        len(python_files),
    )

    return {
        "files": files,
        "total_files": len(files),
        "total_loc": total_loc,
        "language_breakdown": language_counts,
        "python_files": python_files,
        "total_python_files": len(all_python_files),
        "truncated": truncated,
        "warning": warning,
    }
