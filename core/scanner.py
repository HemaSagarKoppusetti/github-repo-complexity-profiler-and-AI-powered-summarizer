# core/scanner.py
# Walks a cloned repo and builds a manifest of all analysable code files.

import os
from pathlib import Path

# ── Folders to always skip ───────────────────────────────────────────────────
SKIP_DIRS = {
    ".git", ".github", ".venv", "venv", "env", ".env",
    "node_modules", "__pycache__", ".mypy_cache", ".pytest_cache",
    "dist", "build", "eggs", ".eggs", "*.egg-info",
    ".tox", ".nox", "site-packages", ".idea", ".vscode",
    "migrations", "staticfiles", "media"
}

# ── File extensions we care about, mapped to language names ──────────────────
LANGUAGE_MAP = {
    ".py":   "Python",
    ".js":   "JavaScript",
    ".ts":   "TypeScript",
    ".jsx":  "JavaScript",
    ".tsx":  "TypeScript",
    ".java": "Java",
    ".cpp":  "C++",
    ".c":    "C",
    ".h":    "C/C++ Header",
    ".cs":   "C#",
    ".go":   "Go",
    ".rb":   "Ruby",
    ".rs":   "Rust",
    ".php":  "PHP",
    ".kt":   "Kotlin",
    ".swift":"Swift",
    ".scala":"Scala",
    ".r":    "R",
    ".sh":   "Shell",
    ".yaml": "YAML",
    ".yml":  "YAML",
    ".json": "JSON",
    ".md":   "Markdown",
    ".html": "HTML",
    ".css":  "CSS",
    ".sql":  "SQL",
    ".toml": "TOML",
    ".ini":  "INI",
    ".cfg":  "Config",
}

# ── Extensions we can compute complexity on (must be Python for radon) ───────
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


def scan_repo(repo_path: str) -> dict:
    """
    Recursively walks a repo and builds a file manifest.

    Args:
        repo_path : Local path to the cloned repo.

    Returns:
        A dict with:
          - files         : list of file dicts (see below)
          - total_files   : int
          - total_loc     : int  (lines of code across all files)
          - language_breakdown : dict {language: file_count}
          - python_files  : list of paths to .py files only (for radon)
    """

    print(f"  [scanner] Scanning {repo_path}...")

    files = []
    language_counts = {}

    for dirpath, dirnames, filenames in os.walk(repo_path):

        # Modify dirnames IN PLACE to prevent os.walk descending into skip dirs
        dirnames[:] = [d for d in dirnames if not should_skip_dir(d)]

        for filename in filenames:
            ext = Path(filename).suffix.lower()

            # Skip files with no recognised extension
            if ext not in LANGUAGE_MAP:
                continue

            full_path = os.path.join(dirpath, filename)

            # Get path relative to repo root (cleaner for display)
            rel_path = os.path.relpath(full_path, repo_path)

            language = LANGUAGE_MAP[ext]
            loc = count_lines(full_path)

            file_entry = {
                "path":        full_path,       # absolute path (for reading)
                "rel_path":    rel_path,         # relative path (for display)
                "filename":    filename,
                "extension":   ext,
                "language":    language,
                "loc":         loc,
                "can_profile": ext in COMPLEXITY_SUPPORTED
            }

            files.append(file_entry)

            # Tally language counts
            language_counts[language] = language_counts.get(language, 0) + 1

    # Sort by LOC descending — biggest files first
    files.sort(key=lambda x: x["loc"], reverse=True)

    total_loc = sum(f["loc"] for f in files)
    python_files = [f["path"] for f in files if f["extension"] == ".py"]

    print(f"  [scanner] ✅ Found {len(files)} files | "
          f"{total_loc} LOC | "
          f"{len(python_files)} Python files")

    return {
        "files":              files,
        "total_files":        len(files),
        "total_loc":          total_loc,
        "language_breakdown": language_counts,
        "python_files":       python_files,
    }