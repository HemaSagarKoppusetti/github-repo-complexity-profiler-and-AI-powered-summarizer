"""Print per-stage timings for a local repository analysis."""

from __future__ import annotations

import argparse
import importlib
import sys
import time
from pathlib import Path
from typing import Any, Callable


def _load_core() -> dict[str, Callable[..., Any]]:
    """Load backend stages after making the backend package importable."""
    backend_path = str(Path(__file__).resolve().parents[1] / "backend")
    if backend_path not in sys.path:
        sys.path.insert(0, backend_path)
    return {
        "scan": importlib.import_module("app.core.scanner").scan_repo,
        "complexity": importlib.import_module("app.core.complexity").analyse_all,
        "graph": importlib.import_module("app.core.graph").build_dependency_graph,
        "churn": importlib.import_module("app.core.churn").analyse_churn,
        "hotspots": importlib.import_module("app.core.hotspots").compute_hotspots,
    }


def _timed(
    timings: list[tuple[str, float, int]],
    name: str,
    operation: Callable[[], Any],
    count: Callable[[Any], int],
) -> Any:
    started = time.perf_counter()
    result = operation()
    timings.append((name, time.perf_counter() - started, count(result)))
    return result


def main(argv: list[str] | None = None) -> int:
    """Run core analysis stages against a local checkout and print timings."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repository", nargs="?", type=Path, default=Path.cwd())
    parser.add_argument("--cache-dir", type=Path)
    args = parser.parse_args(argv)
    repository = args.repository.resolve()
    if not repository.is_dir():
        parser.error(f"Repository directory does not exist: {repository}")

    stages = _load_core()
    timings: list[tuple[str, float, int]] = []
    manifest = _timed(
        timings,
        "scan",
        lambda: stages["scan"](
            str(repository),
            cache_dir=str(args.cache_dir) if args.cache_dir else None,
        ),
        lambda result: len(result.get("files", [])),
    )
    python_files = manifest.get("python_files", [])
    entries = manifest.get("files", [])
    complexity = _timed(
        timings,
        "complexity",
        lambda: stages["complexity"](python_files, file_entries=entries),
        lambda result: len(result.get("results", [])),
    )
    _timed(
        timings,
        "graph",
        lambda: stages["graph"](python_files, str(repository), manifest_files=entries),
        lambda result: result.get("stats", {}).get("node_count", 0),
    )
    churn = _timed(
        timings,
        "churn",
        lambda: stages["churn"](
            str(repository),
            python_files,
            manifest_files=entries,
        ),
        lambda result: result.get("stats", {}).get("total_commits", 0),
    )
    _timed(
        timings,
        "hotspots",
        lambda: stages["hotspots"](
            complexity,
            churn,
            str(repository),
            manifest_files=entries,
        ),
        lambda result: len(result.get("hotspots", [])),
    )

    print(f"Repository: {repository}")
    print(f"{'Stage':<14} {'Seconds':>10} {'Items':>10}")
    print("-" * 36)
    for name, duration, count in timings:
        print(f"{name:<14} {duration:>10.3f} {count:>10}")
    print(f"{'Total':<14} {sum(row[1] for row in timings):>10.3f}")
    cache_stats = manifest.get("cache", {})
    print(f"Scan cache: {cache_stats.get('hits', 0)} hits, {cache_stats.get('misses', 0)} misses")
    for name, duration in manifest.get("stage_timings", {}).items():
        print(f"  {name}: {duration:.3f}s")
    for diagnostic in manifest.get("diagnostics", []):
        if diagnostic.get("severity") == "warning":
            print(f"Scan warning: {diagnostic.get('message', 'Unknown warning')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
