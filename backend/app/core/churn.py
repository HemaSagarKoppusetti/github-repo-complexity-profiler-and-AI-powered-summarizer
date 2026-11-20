"""Single-pass git history analysis with churn, ownership, and coupling metrics."""

from __future__ import annotations

import logging
import re
import subprocess
from collections import Counter, defaultdict
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from itertools import combinations
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)
COMMIT_PREFIX = "__PROFILER_COMMIT__"
BUG_FIX_PATTERN = re.compile(r"\b(fix|bug|hotfix|regression|issue)\b", re.IGNORECASE)
RENAME_PATTERN = re.compile(r"^(.*)\{(.+?) => (.+?)\}(.*)$")
PLAIN_RENAME_PATTERN = re.compile(r"^(.+?) => (.+?)$")


def _empty_result(warnings: list[str] | None = None) -> dict[str, Any]:
    """Return a schema-shaped empty history result."""
    return {
        "file_churn": {},
        "most_churned": [],
        "temporal_coupling": [],
        "commits_by_month": [],
        "renames": [],
        "warnings": warnings or [],
        "stats": {
            "total_commits": 0,
            "total_authors": 0,
            "repo_age_days": 0,
            "first_commit": "N/A",
            "last_commit": "N/A",
            "history_truncated": False,
            "analysed_window": "No commits available",
        },
    }


def parse_numstat_log(raw_log: str) -> tuple[list[dict[str, Any]], list[str]]:
    """Parse the delimited commit and numstat output from `git log`."""
    commits: list[dict[str, Any]] = []
    warnings: list[str] = []
    current: dict[str, Any] | None = None
    for line in raw_log.splitlines():
        if line.startswith(COMMIT_PREFIX):
            fields = line[len(COMMIT_PREFIX):].split("\x1f", 4)
            if len(fields) != 5:
                warnings.append("Skipped malformed commit header in git history.")
                current = None
                continue
            try:
                timestamp = int(fields[3])
            except ValueError:
                warnings.append("Skipped commit with invalid timestamp.")
                current = None
                continue
            current = {
                "hash": fields[0],
                "author": fields[1],
                "timestamp": timestamp,
                "message": fields[4],
                "files": {},
            }
            commits.append(current)
            continue
        if current is None or not line:
            continue
        fields = line.split("\t", 2)
        if len(fields) != 3:
            continue
        added_text, deleted_text, raw_path = fields
        try:
            added = int(added_text) if added_text != "-" else 0
            deleted = int(deleted_text) if deleted_text != "-" else 0
        except ValueError:
            warnings.append("Skipped malformed numstat line in git history.")
            continue
        rename = RENAME_PATTERN.match(raw_path) or PLAIN_RENAME_PATTERN.match(raw_path)
        if rename:
            if RENAME_PATTERN.match(raw_path):
                old_path = f"{rename.group(1)}{rename.group(2)}{rename.group(4)}"
                new_path = f"{rename.group(1)}{rename.group(3)}{rename.group(4)}"
            else:
                old_path = rename.group(1)
                new_path = rename.group(2)
            old_path = old_path.replace("\\", "/")
            new_path = new_path.replace("\\", "/")
            current["files"][new_path] = (added, deleted)
            current.setdefault("renames", []).append((old_path, new_path))
        else:
            current["files"][raw_path.replace("\\", "/")] = (added, deleted)
    return commits, warnings


def _run_git(args: list[str], cwd: str, timeout: int) -> subprocess.CompletedProcess[str]:
    """Execute a git command without a shell and with an explicit timeout."""
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        check=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )


def analyse_churn(
    repo_path: str,
    python_files: list[str],
    progress_cb: Callable[[int, int, str], None] | None = None,
    manifest_files: list[dict[str, Any]] | None = None,
    max_commits: int = 2000,
    coupling_threshold: int = 1,
    max_coupling_pairs: int = 100_000,
) -> dict[str, Any]:
    """Read bounded history once and compute per-file change and ownership data."""
    root = Path(repo_path).resolve()
    if manifest_files is None:
        tracked = {
            Path(path).resolve().relative_to(root).as_posix()
            for path in python_files
        }
        source_paths = set(tracked)
    else:
        tracked = {
            str(entry.get("rel_path", "")).replace("\\", "/")
            for entry in manifest_files
            if entry.get("rel_path")
        }
        source_paths = {
            str(entry.get("rel_path", "")).replace("\\", "/")
            for entry in manifest_files
            if entry.get("rel_path") and entry.get("role") == "source"
        }
    if not tracked:
        return _empty_result()

    try:
        log_result = _run_git(
            [
                "log",
                "--numstat",
                "--no-merges",
                "-M",
                f"--max-count={max(1, max_commits)}",
                f"--format={COMMIT_PREFIX}%H%x1f%an%x1f%ae%x1f%at%x1f%s",
            ],
            str(root),
            timeout=60,
        )
        commits, warnings = parse_numstat_log(log_result.stdout)
    except (OSError, subprocess.SubprocessError) as exc:
        logger.warning("[churn] Git history unavailable: %s", type(exc).__name__)
        return _empty_result([f"Git history unavailable ({type(exc).__name__})."])

    if not commits:
        result = _empty_result(warnings)
        result["file_churn"] = {
            path: {
                "rel_path": path,
                "commit_count": 0,
                "lines_added": 0,
                "lines_deleted": 0,
                "authors": [],
                "author_count": 0,
                "top_author_share": 0.0,
                "bus_factor": 0,
                "bug_fix_count": 0,
                "first_changed": None,
                "last_changed": None,
                "age_days": 0,
                "churn_rate": 0.0,
                "commits_last_90_days": 0,
            }
            for path in sorted(tracked)
        }
        return result

    aliases: dict[str, str] = {}
    renames: list[dict[str, str]] = []
    for commit in commits:
        for old_path, new_path in commit.get("renames", []):
            aliases[old_path] = new_path
            renames.append({"from": old_path, "to": new_path, "commit": commit["hash"]})

    def canonical(path: str) -> str:
        seen: set[str] = set()
        while path in aliases and path not in seen:
            seen.add(path)
            path = aliases[path]
        return path

    events: dict[str, list[dict[str, Any]]] = defaultdict(list)
    temporal_counts: Counter[tuple[str, str]] = Counter()
    unique_authors: set[str] = set()
    timestamps: list[int] = []
    for index, commit in enumerate(commits, 1):
        author = str(commit.get("author") or "Unknown")
        unique_authors.add(author)
        timestamp = int(commit["timestamp"])
        timestamps.append(timestamp)
        commit_paths = []
        is_bug_fix = bool(BUG_FIX_PATTERN.search(str(commit.get("message", ""))))
        for path, (added, deleted) in commit["files"].items():
            resolved_path = canonical(path)
            if resolved_path not in tracked and path not in tracked:
                continue
            events[resolved_path].append({
                "author": author,
                "timestamp": timestamp,
                "added": added,
                "deleted": deleted,
                "bug_fix": is_bug_fix,
            })
            if resolved_path in source_paths:
                commit_paths.append(resolved_path)
        if len(commit_paths) > 1:
            for pair in combinations(sorted(set(commit_paths)), 2):
                temporal_counts[pair] += 1
                if len(temporal_counts) >= max_coupling_pairs:
                    break
        if progress_cb and (index % 100 == 0 or index == len(commits)):
            progress_cb(index, len(commits), str(commit.get("message", ""))[:80])

    tracked_current = {canonical(path) for path in tracked}
    file_churn: dict[str, dict[str, Any]] = {}
    now = datetime.now(UTC)
    for path in sorted(tracked_current):
        file_events = events.get(path, [])
        if not file_events:
            file_churn[path] = {
                "rel_path": path,
                "commit_count": 0,
                "lines_added": 0,
                "lines_deleted": 0,
                "authors": [],
                "author_count": 0,
                "top_author_share": 0.0,
                "bus_factor": 0,
                "bug_fix_count": 0,
                "first_changed": None,
                "last_changed": None,
                "age_days": 0,
                "churn_rate": 0.0,
                "commits_last_90_days": 0,
            }
            continue
        author_counts = Counter(event["author"] for event in file_events)
        author_names = sorted(author_counts)
        first_ts = min(event["timestamp"] for event in file_events)
        last_ts = max(event["timestamp"] for event in file_events)
        age_days = max((last_ts - first_ts) // 86400, 1)
        ordered_author_counts = sorted(author_counts.values(), reverse=True)
        threshold = len(file_events) * 0.8
        authors_needed = 0
        covered = 0
        for author_count in ordered_author_counts:
            authors_needed += 1
            covered += author_count
            if covered >= threshold:
                break
        recent_cutoff = int((now - timedelta(days=90)).timestamp())
        file_churn[path] = {
            "rel_path": path,
            "commit_count": len(file_events),
            "lines_added": sum(event["added"] for event in file_events),
            "lines_deleted": sum(event["deleted"] for event in file_events),
            "authors": author_names,
            "author_count": len(author_names),
            "top_author_share": round(max(author_counts.values()) / len(file_events), 4),
            "bus_factor": authors_needed,
            "bug_fix_count": sum(event["bug_fix"] for event in file_events),
            "first_changed": datetime.fromtimestamp(first_ts, tz=UTC).strftime("%Y-%m-%d"),
            "last_changed": datetime.fromtimestamp(last_ts, tz=UTC).strftime("%Y-%m-%d"),
            "last_changed_timestamp": last_ts,
            "age_days": age_days,
            "churn_rate": round((len(file_events) / age_days) * 30, 2),
            "commits_last_90_days": sum(event["timestamp"] >= recent_cutoff for event in file_events),
        }

    try:
        shallow = _run_git(["rev-parse", "--is-shallow-repository"], str(root), timeout=10).stdout.strip() == "true"
    except (OSError, subprocess.SubprocessError):
        shallow = False
        warnings.append("Could not determine whether repository history is shallow.")
    history_truncated = shallow or len(commits) >= max_commits
    first_dt = datetime.fromtimestamp(min(timestamps), tz=UTC)
    last_dt = datetime.fromtimestamp(max(timestamps), tz=UTC)
    repo_age_days = max((last_dt - first_dt).days, 1)
    month_counts = Counter(
        datetime.fromtimestamp(timestamp, tz=UTC).strftime("%Y-%m")
        for timestamp in timestamps
    )
    commits_by_month = [
        {"month": month, "commits": count}
        for month, count in sorted(month_counts.items())[-36:]
    ]
    coupling: list[dict[str, Any]] = [
        {"files": list(pair), "cochange_count": count}
        for pair, count in temporal_counts.items()
        if count > coupling_threshold
    ]
    coupling.sort(key=lambda item: (-item["cochange_count"], item["files"]))
    most_churned = sorted(
        (item for item in file_churn.values() if item["commit_count"] > 0),
        key=lambda item: (-item["commit_count"], item["rel_path"]),
    )[:10]
    stats = {
        "total_commits": len(commits),
        "total_authors": len(unique_authors),
        "repo_age_days": repo_age_days,
        "first_commit": first_dt.strftime("%Y-%m-%d"),
        "last_commit": last_dt.strftime("%Y-%m-%d"),
        "history_truncated": history_truncated,
        "analysed_window": f"{first_dt.strftime('%Y-%m-%d')} to {last_dt.strftime('%Y-%m-%d')} ({len(commits)} commits)",
        "max_commits": max_commits,
    }
    return {
        "file_churn": file_churn,
        "most_churned": most_churned,
        "temporal_coupling": coupling[:10],
        "commits_by_month": commits_by_month,
        "renames": renames,
        "warnings": warnings,
        "stats": stats,
    }
