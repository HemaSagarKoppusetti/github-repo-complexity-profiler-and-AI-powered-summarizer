"""Fast, bounded repository discovery with content-addressed analysis caching."""

from __future__ import annotations

import ast
import hashlib
import json
import logging
import os
import re
import subprocess
import time
from concurrent.futures import Future, ProcessPoolExecutor, ThreadPoolExecutor
from pathlib import Path
from typing import Any

from radon.complexity import cc_rank, cc_visit_ast
from radon.metrics import mi_rank, mi_visit

logger = logging.getLogger(__name__)

SKIP_DIRS = {
    ".git", ".github", ".venv", "venv", "env", ".env", "node_modules",
    "__pycache__", ".mypy_cache", ".pytest_cache", "dist", "build", "eggs",
    ".eggs", ".tox", ".nox", "site-packages", ".idea", ".vscode",
    "migrations", "staticfiles", "media", "vendor", "target", "coverage",
}
SKIP_FILES = {
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock",
    "pipfile.lock", "cargo.lock", "composer.lock", "gemfile.lock",
}
LANGUAGE_MAP = {
    ".py": "Python", ".js": "JavaScript", ".ts": "TypeScript",
    ".jsx": "JavaScript", ".tsx": "TypeScript", ".java": "Java",
    ".cpp": "C++", ".cc": "C++", ".cxx": "C++", ".c": "C",
    ".h": "C/C++ Header", ".hpp": "C++", ".cs": "C#", ".go": "Go",
    ".rb": "Ruby", ".rs": "Rust", ".php": "PHP", ".kt": "Kotlin",
    ".swift": "Swift", ".scala": "Scala", ".r": "R", ".sh": "Shell",
    ".yaml": "YAML", ".yml": "YAML", ".json": "JSON", ".md": "Markdown",
    ".rst": "reStructuredText", ".html": "HTML", ".css": "CSS",
    ".sql": "SQL", ".toml": "TOML", ".ini": "INI", ".cfg": "Config",
    ".xml": "XML", ".mjs": "JavaScript", ".cjs": "JavaScript",
    ".vue": "JavaScript", ".svelte": "JavaScript",
}
LOCKFILE_NAMES = SKIP_FILES | {"package-lock.json"}
MAX_FILE_BYTES = 1024 * 1024
MINIFIED_AVG_LINE_LENGTH = 500
MINIFIED_MIN_BYTES = 10_000
SOURCE_EXTENSIONS = {".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".cpp", ".cc", ".cxx", ".c", ".h", ".hpp", ".cs", ".go", ".rb", ".php", ".rs", ".kt", ".swift", ".scala"}
LIZARD_LANGUAGES = {
    "JavaScript",
    "TypeScript",
    "Java",
    "Go",
    "C",
    "C++",
    "C#",
    "Ruby",
    "PHP",
}


def _classify_role(path: str, header: str) -> str:
    """Classify a repository path for prioritization and risk weighting."""
    normalized = path.lower()
    if "auto-generated" in header.lower() or "do not edit" in header.lower():
        return "generated"
    if any(part in normalized.split("/") for part in ("test", "tests", "__tests__", "spec")) or re.search(
        r"(^|[_./])(test|spec)([_./]|$)", normalized
    ):
        return "test"
    if normalized.endswith((".md", ".rst")) or normalized.startswith(("docs/", "doc/")):
        return "docs"
    if Path(path).suffix.lower() in {".yaml", ".yml", ".json", ".toml", ".ini", ".cfg", ".xml"}:
        return "config"
    if normalized.endswith((".lock", ".min.js", ".min.css")):
        return "generated"
    return "source"


def _decode(raw: bytes) -> str:
    """Decode a text file as UTF-8, falling back to Latin-1."""
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("latin-1", errors="replace")


def _python_analysis(source: str) -> dict[str, Any]:
    """Parse Python source once and return portable AST-derived summaries."""
    tree = ast.parse(source)
    imports: list[dict[str, Any]] = []
    functions: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(
                {"module": alias.name, "level": 0, "name": None}
                for alias in node.names
            )
        elif isinstance(node, ast.ImportFrom):
            imports.extend({
                "module": node.module or "",
                "level": node.level,
                "name": alias.name,
            } for alias in node.names)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args = [arg.arg for arg in node.args.posonlyargs + node.args.args]
            args.extend(arg.arg for arg in node.args.kwonlyargs)
            if node.args.vararg:
                args.append(f"*{node.args.vararg.arg}")
            if node.args.kwarg:
                args.append(f"**{node.args.kwarg.arg}")
            docstring = ast.get_docstring(node)
            functions.append({
                "name": node.name,
                "signature": f"{node.name}({', '.join(args)})",
                "docstring": docstring.splitlines()[0] if docstring else "",
                "lineno": node.lineno,
            })

    cc_results = cc_visit_ast(tree)
    complexity_functions = [{
        "name": block.name,
        "type": type(block).__name__,
        "complexity": block.complexity,
        "rank": cc_rank(block.complexity),
        "lineno": block.lineno,
    } for block in cc_results]
    mi_score = round(float(mi_visit(source, multi=True)), 2)
    complexity_functions.sort(key=lambda item: item["complexity"], reverse=True)
    return {
        "imports": imports,
        "functions": functions,
        "complexity": {
            "mi_score": mi_score,
            "mi_rank": mi_rank(mi_score),
            "functions": complexity_functions,
            "avg_cc": round(
                sum(item["complexity"] for item in complexity_functions) / len(complexity_functions),
                2,
            ) if complexity_functions else 0.0,
            "max_cc": complexity_functions[0]["complexity"] if complexity_functions else 0,
            "hotspot_fn": complexity_functions[0]["name"] if complexity_functions else None,
            "error": None,
        },
    }


def _analyze_content(payload: tuple[str, str, str, str]) -> dict[str, Any]:
    """Analyze source content in a worker process; the function is spawn-picklable."""
    rel_path, extension, language, source = payload
    result: dict[str, Any] = {"imports": [], "functions": [], "complexity": None, "lizard": None}
    try:
        if extension == ".py":
            result.update(_python_analysis(source))
        elif extension in {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".vue", ".svelte"}:
            result["imports"] = [
                {"module": match.group(2) or match.group(4), "level": 0, "name": None}
                for match in re.finditer(
                    r"""(?m)^\s*import\s+(?:[^'"]*?\s+from\s+)?(['"])([^'"]+)\1|require\(\s*(['"])([^'"]+)\3\s*\)""",
                    source,
                )
            ]
        elif extension == ".java":
            result["imports"] = [
                {"module": match.group(1), "level": 0, "name": None}
                for match in re.finditer(r"(?m)^\s*import\s+(?:static\s+)?([\w.]+)\s*;", source)
            ]
        if language in LIZARD_LANGUAGES:
            try:
                import lizard

                parsed = lizard.analyze_file.analyze_source_code(rel_path, source)
                result["lizard"] = [{
                    "name": function.name,
                    "complexity": function.cyclomatic_complexity,
                    "nloc": function.nloc,
                    "parameter_count": function.parameter_count,
                    "line": function.start_line,
                } for function in parsed.function_list]
            except ImportError:
                pass
            except Exception as exc:
                result["lizard_error"] = str(exc)
    except SyntaxError as exc:
        result["analysis_error"] = f"Syntax error at line {exc.lineno or 0}: {exc.msg}"
    except Exception as exc:
        result["analysis_error"] = f"Analysis failed: {type(exc).__name__}"
    return result


def _read_candidate(path: Path) -> tuple[bytes | None, str | None]:
    """Read one candidate file for the bounded I/O worker pool."""
    try:
        return path.read_bytes(), None
    except Exception as exc:
        return None, type(exc).__name__


def _read_cache_candidate(
    cache_file: Path,
) -> tuple[dict[str, Any] | None, str | None]:
    """Read one known cache entry without failing its repository scan."""
    try:
        value = json.loads(cache_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None, "invalid JSON"
    except OSError as exc:
        return None, type(exc).__name__
    return (value, None) if isinstance(value, dict) else (None, "invalid data")


def _tracked_paths(repo_path: Path) -> tuple[list[str], str | None]:
    """Use git ls-files, with an os.walk fallback for untracked fixture folders."""
    try:
        completed = subprocess.run(
            ["git", "ls-files", "-z"],
            cwd=repo_path,
            capture_output=True,
            check=True,
            timeout=15,
        )
        paths = [
            item.decode("utf-8", errors="surrogateescape").replace("\\", "/")
            for item in completed.stdout.split(b"\0") if item
        ]
        return paths, None
    except (OSError, subprocess.SubprocessError) as exc:
        paths = []
        for root, dirs, names in os.walk(repo_path, followlinks=False):
            dirs[:] = [name for name in dirs if name not in SKIP_DIRS and not name.endswith(".egg-info")]
            for name in names:
                paths.append((Path(root) / name).relative_to(repo_path).as_posix())
        return paths, f"git ls-files unavailable; used filesystem traversal ({type(exc).__name__})."


def _cache_path(cache_dir: Path, digest: str, extension: str) -> Path:
    """Return the cache entry for a content hash."""
    return cache_dir / f"{digest}-{extension.lstrip('.')}.json"


def _language_for(path: Path, extension: str) -> str | None:
    """Resolve language from an extension, then common executable shebangs."""
    language = LANGUAGE_MAP.get(extension)
    if language:
        return language
    if path.name.lower() in {"dockerfile", "makefile"}:
        return "Dockerfile" if path.name.lower() == "dockerfile" else "Makefile"
    try:
        with path.open("rb") as stream:
            first_line = stream.readline(256).decode("utf-8", errors="ignore").lower()
    except OSError:
        return None
    if first_line.startswith("#!") and "python" in first_line:
        return "Python"
    if first_line.startswith("#!") and any(shell in first_line for shell in ("sh", "bash", "zsh")):
        return "Shell"
    return None


def count_lines(filepath: str) -> int:
    """Count non-empty lines in a file, returning zero on read errors."""
    try:
        with open(filepath, encoding="utf-8", errors="replace") as stream:
            return sum(1 for line in stream if line.strip())
    except OSError:
        return 0


def should_skip_dir(dirname: str) -> bool:
    """Return whether a directory is excluded from discovery."""
    return dirname in SKIP_DIRS or dirname.endswith(".egg-info")


def scan_repo(
    repo_path: str,
    max_python_files: int = 2000,
    max_files: int = 5000,
    max_analysis_time_seconds: int = 600,
    cache_dir: str | None = None,
) -> dict[str, Any]:
    """Discover and analyze bounded repository files while preserving legacy keys."""
    started = time.monotonic()
    root = Path(repo_path).resolve()
    cache_root = Path(cache_dir) if cache_dir else Path(__file__).resolve().parents[3] / ".cache" / "profiler"
    diagnostics: list[dict[str, str]] = []
    paths, discovery_warning = _tracked_paths(root)
    if discovery_warning:
        diagnostics.append({"stage": "scan", "file": "", "severity": "warning", "message": discovery_warning})

    candidates: list[tuple[str, Path, str, str]] = []
    for relative in paths:
        path = root / Path(relative)
        extension = path.suffix.lower()
        language = _language_for(path, extension)
        if not language or path.name.lower() in LOCKFILE_NAMES or path.name.lower().endswith((".min.js", ".min.css")):
            continue
        if any(part in SKIP_DIRS for part in Path(relative).parts):
            continue
        try:
            if path.is_symlink() and not path.resolve().is_relative_to(root):
                diagnostics.append({
                    "stage": "scan", "file": relative, "severity": "warning",
                    "message": "Skipped symlink resolving outside the repository.",
                })
                continue
            size = path.stat().st_size
        except OSError as exc:
            diagnostics.append({
                "stage": "scan", "file": relative, "severity": "warning",
                "message": f"File metadata unavailable ({type(exc).__name__}).",
            })
            continue
        if size > MAX_FILE_BYTES:
            diagnostics.append({
                "stage": "scan", "file": relative, "severity": "info",
                "message": f"Skipped file larger than {MAX_FILE_BYTES} bytes.",
            })
            continue
        candidates.append((relative, path, extension, language))

    role_order = {"source": 0, "test": 1, "config": 2, "docs": 3, "generated": 4}
    candidates.sort(key=lambda row: (role_order[_classify_role(row[0], "")], row[0]))
    truncated = len(candidates) > max_files
    if truncated:
        diagnostics.append({
            "stage": "scan", "file": "", "severity": "warning",
            "message": f"File limit reached ({max_files}); prioritised source, tests, configuration, and documentation.",
        })
        candidates = candidates[:max_files]

    discovery_duration = time.monotonic() - started
    file_entries: list[dict[str, Any]] = []
    worker_payloads: list[tuple[str, str, str, str]] = []
    cache_pending: list[tuple[dict[str, Any], Path]] = []
    cache_lookup_pending: list[
        tuple[
            str,
            dict[str, Any],
            str,
            Path,
            str,
            Future[tuple[dict[str, Any] | None, str | None]] | None,
        ]
    ] = []
    cached_count = 0
    content_read_duration = 0.0
    try:
        cache_root.mkdir(parents=True, exist_ok=True)
        cache_names = set(os.listdir(cache_root))
    except OSError as exc:
        cache_names = set()
        diagnostics.append({
            "stage": "scan",
            "file": "",
            "severity": "warning",
            "message": f"Analysis cache unavailable ({type(exc).__name__}); scanning without cached results.",
        })

    batch_size = 128
    io_workers = min(os.cpu_count() or 1, 16)
    with ThreadPoolExecutor(max_workers=io_workers) as read_pool:
        for offset in range(0, len(candidates), batch_size):
            batch = candidates[offset:offset + batch_size]
            if time.monotonic() - started >= max_analysis_time_seconds:
                truncated = True
                diagnostics.append({
                    "stage": "scan",
                    "file": batch[0][0],
                    "severity": "warning",
                    "message": f"Analysis time limit reached ({max_analysis_time_seconds}s); remaining files were skipped.",
                })
                break

            read_started = time.monotonic()
            read_results = list(read_pool.map(_read_candidate, (item[1] for item in batch)))
            content_read_duration += time.monotonic() - read_started
            for (relative, path, extension, language), (raw, read_error) in zip(
                batch, read_results, strict=True
            ):
                if raw is None:
                    diagnostics.append({
                        "stage": "scan",
                        "file": relative,
                        "severity": "warning",
                        "message": f"File read failed ({read_error or 'unknown error'}).",
                    })
                    continue
                if b"\0" in raw[:8192]:
                    diagnostics.append({
                        "stage": "scan", "file": relative, "severity": "info",
                        "message": "Skipped binary file.",
                    })
                    continue
                source = _decode(raw)
                header = "\n".join(source.splitlines()[:5])
                role = _classify_role(relative, header)
                if role == "generated":
                    diagnostics.append({
                        "stage": "scan", "file": relative, "severity": "info",
                        "message": "Skipped generated source.",
                    })
                    continue
                lines = source.splitlines()
                average_line_length = len(source) / max(1, len(lines))
                if average_line_length > MINIFIED_AVG_LINE_LENGTH and len(raw) >= MINIFIED_MIN_BYTES:
                    diagnostics.append({
                        "stage": "scan", "file": relative, "severity": "info",
                        "message": "Skipped minified or generated file with unusually long lines.",
                    })
                    continue

                digest = hashlib.sha1(raw).hexdigest()
                entry: dict[str, Any] = {
                    "path": str(path),
                    "rel_path": relative.replace("\\", "/"),
                    "filename": path.name,
                    "extension": extension,
                    "language": language,
                    "role": role,
                    "loc": sum(bool(line.strip()) for line in lines),
                    "size_bytes": len(raw),
                    "content_sha1": digest,
                    "can_profile": language == "Python",
                }
                analysis_extension = extension or (".py" if language == "Python" else "")
                cache_file = _cache_path(cache_root, digest, analysis_extension)
                cache_future = (
                    read_pool.submit(_read_cache_candidate, cache_file)
                    if cache_file.name in cache_names
                    else None
                )
                cache_lookup_pending.append(
                    (relative, entry, source, cache_file, analysis_extension, cache_future)
                )
                file_entries.append(entry)

    file_loading_duration = time.monotonic() - started - discovery_duration
    for relative, entry, source, cache_file, analysis_extension, cache_future in cache_lookup_pending:
        cached: dict[str, Any] | None = None
        if cache_future is not None:
            cached, cache_error = cache_future.result()
            if cache_error:
                diagnostics.append({
                    "stage": "scan",
                    "file": relative,
                    "severity": "warning",
                    "message": (
                        "Cached analysis was invalid and will be recomputed."
                        if cache_error in {"invalid JSON", "invalid data"}
                        else f"Cached analysis could not be read ({cache_error})."
                    ),
                })
        if cached is not None:
            entry.update(cached)
            cached_count += 1
            if entry.get("analysis_error"):
                diagnostics.append({
                    "stage": "scan", "file": relative, "severity": "warning",
                    "message": entry["analysis_error"],
                })
        else:
            worker_payloads.append(
                (relative, analysis_extension, entry["language"], source)
            )
            cache_pending.append((entry, cache_file))
    analysis_errors = 0
    worker_count = min(os.cpu_count() or 1, 8)
    worker_results: list[dict[str, Any]]
    if len(worker_payloads) > 1:
        try:
            with ProcessPoolExecutor(max_workers=worker_count) as pool:
                worker_results = list(pool.map(_analyze_content, worker_payloads, chunksize=32))
        except Exception as exc:
            diagnostics.append({
                "stage": "scan", "file": "", "severity": "warning",
                "message": f"Parallel analysis unavailable; processed files serially ({type(exc).__name__}).",
            })
            worker_results = [_analyze_content(item) for item in worker_payloads]
    else:
        worker_results = [_analyze_content(item) for item in worker_payloads]

    worker_duration = time.monotonic() - started - discovery_duration - file_loading_duration
    cache_write_started = time.monotonic()
    for (entry, cache_file), analysis in zip(cache_pending, worker_results, strict=True):
        entry.update(analysis)
        cached_data = {key: value for key, value in analysis.items()}
        temporary = cache_file.with_suffix(".tmp")
        try:
            temporary.write_text(json.dumps(cached_data), encoding="utf-8")
            temporary.replace(cache_file)
            cache_names.add(cache_file.name)
        except OSError as exc:
            diagnostics.append({
                "stage": "scan", "file": entry["rel_path"], "severity": "warning",
                "message": f"Analysis cache write failed ({type(exc).__name__}).",
            })
        if analysis.get("analysis_error"):
            analysis_errors += 1
            diagnostics.append({
                "stage": "scan", "file": entry["rel_path"], "severity": "warning",
                "message": analysis["analysis_error"],
            })
        if analysis.get("lizard_error"):
            diagnostics.append({
                "stage": "scan", "file": entry["rel_path"], "severity": "info",
                "message": "Multi-language complexity unavailable for this file.",
            })
    cache_write_duration = time.monotonic() - cache_write_started

    python_entries = [entry for entry in file_entries if entry["language"] == "Python"]
    python_entries = sorted(python_entries, key=lambda entry: (entry["role"] != "source", -entry["loc"]))
    python_files = [entry["path"] for entry in python_entries[:max_python_files]]
    if len(python_entries) > max_python_files:
        truncated = True
        diagnostics.append({
            "stage": "scan", "file": "", "severity": "warning",
            "message": f"Python complexity analysis capped at {max_python_files} files.",
        })

    language_counts: dict[str, int] = {}
    role_counts: dict[str, int] = {}
    for entry in file_entries:
        language_counts[entry["language"]] = language_counts.get(entry["language"], 0) + 1
        role_counts[entry["role"]] = role_counts.get(entry["role"], 0) + 1

    elapsed = round(time.monotonic() - started, 3)
    return {
        "files": file_entries,
        "total_files": len(file_entries),
        "total_loc": sum(entry["loc"] for entry in file_entries),
        "language_breakdown": language_counts,
        "role_breakdown": role_counts,
        "python_files": python_files,
        "total_python_files": len(python_entries),
        "truncated": truncated,
        "warning": "Analysis was truncated; see diagnostics." if truncated else None,
        "diagnostics": diagnostics,
        "cache": {"hits": cached_count, "misses": len(worker_payloads)},
        "stage_timings": {
            "discovery": round(discovery_duration, 3),
            "file_loading_and_cache_lookup": round(file_loading_duration, 3),
            "content_reads": round(content_read_duration, 3),
            "worker_analysis": round(worker_duration, 3),
            "cache_writes": round(cache_write_duration, 3),
        },
        "duration_seconds": elapsed,
        "analysis_errors": analysis_errors,
    }
