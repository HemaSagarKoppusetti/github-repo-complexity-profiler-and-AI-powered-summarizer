# backend/app/core/churn.py
"""Analyses git commit history to compute per-file churn metrics.

Uses an efficient single-pass git log parser to prevent hanging on large
codebases.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from git import InvalidGitRepositoryError, Repo

logger = logging.getLogger(__name__)


def _empty_result() -> dict[str, Any]:
    return {
        "file_churn": {},
        "most_churned": [],
        "stats": {
            "total_commits": 0,
            "total_authors": 0,
            "repo_age_days": 0,
            "first_commit": "N/A",
            "last_commit": "N/A",
        },
    }


def analyse_churn(
    repo_path: str,
    python_files: list[str],
    progress_cb: Callable[[int, int, str], None] | None = None,
) -> dict[str, Any]:
    """Reads git log in a single pass to compute churn metrics for every Python file.

    Args:
        repo_path: local path to the cloned repo
        python_files: list of absolute file paths (from scanner manifest)
        progress_cb: optional progress callback

    Returns:
        dict with file_churn, most_churned, stats
    """
    logger.info("[churn] Reading git history at %s...", repo_path)

    try:
        repo = Repo(repo_path)
    except (InvalidGitRepositoryError, Exception) as e:
        logger.warning("[churn] ❌ Invalid git repository: %s", e)
        return _empty_result()

    # Pre-map all python files by normalized rel_path
    tracked_files: set[str] = set()
    for fp in python_files:
        rel = os.path.relpath(fp, repo_path).replace("\\", "/")
        tracked_files.add(rel)

    # Fast single-pass git log extraction
    try:
        raw_log = repo.git.log(
            "--name-only",
            "--pretty=format:__COMMIT__%H|%an|%ae|%at",
        )
    except Exception as e:
        logger.warning("[churn] Failed to retrieve git log: %s", e)
        return _empty_result()

    if not raw_log.strip():
        logger.info("[churn] ⚠️ No commits found")
        return _empty_result()

    commits_by_hash: dict[str, dict[str, Any]] = {}
    file_events: dict[str, list[dict[str, Any]]] = {
        rf: [] for rf in tracked_files
    }
    all_authors: set[str] = set()
    all_timestamps: list[int] = []

    current_commit: dict[str, Any] | None = None

    for line in raw_log.splitlines():
        line = line.strip()
        if not line:
            continue

        if line.startswith("__COMMIT__"):
            parts = line[len("__COMMIT__"):].split("|")
            if len(parts) >= 4:
                commit_hash = parts[0]
                author_name = parts[1]
                author_email = parts[2]
                ts = int(parts[3])
                current_commit = {
                    "hash": commit_hash,
                    "author": author_name,
                    "email": author_email,
                    "timestamp": ts,
                }
                commits_by_hash[commit_hash] = current_commit
                if author_email:
                    all_authors.add(author_email)
                all_timestamps.append(ts)
        elif current_commit:
            norm_file = line.replace("\\", "/")
            if norm_file in file_events:
                file_events[norm_file].append(current_commit)

    total_commits = len(commits_by_hash)
    if total_commits == 0 or not all_timestamps:
        return _empty_result()

    min_ts = min(all_timestamps)
    max_ts = max(all_timestamps)
    first_commit_dt = datetime.fromtimestamp(min_ts, tz=UTC)
    last_commit_dt = datetime.fromtimestamp(max_ts, tz=UTC)
    repo_age_days = max((last_commit_dt - first_commit_dt).days, 1)

    file_churn: dict[str, Any] = {}
    for rel_path, events in file_events.items():
        commit_count = len(events)
        if commit_count == 0:
            file_churn[rel_path] = {
                "rel_path": rel_path,
                "commit_count": 0,
                "authors": [],
                "author_count": 0,
                "first_changed": None,
                "last_changed": None,
                "age_days": 0,
                "churn_rate": 0.0,
            }
            continue

        authors = list({e["author"] for e in events if e.get("author")})
        event_timestamps = [e["timestamp"] for e in events]
        f_min_ts = min(event_timestamps)
        f_max_ts = max(event_timestamps)

        first_changed = datetime.fromtimestamp(
            f_min_ts, tz=UTC
        ).strftime("%Y-%m-%d")
        last_changed = datetime.fromtimestamp(
            f_max_ts, tz=UTC
        ).strftime("%Y-%m-%d")

        f_age_days = max(
            (
                datetime.fromtimestamp(f_max_ts, tz=UTC)
                - datetime.fromtimestamp(f_min_ts, tz=UTC)
            ).days,
            1,
        )

        churn_rate = round((commit_count / f_age_days) * 30, 2)

        file_churn[rel_path] = {
            "rel_path": rel_path,
            "commit_count": commit_count,
            "authors": authors,
            "author_count": len(authors),
            "first_changed": first_changed,
            "last_changed": last_changed,
            "age_days": f_age_days,
            "churn_rate": churn_rate,
        }

    most_churned = sorted(
        [v for v in file_churn.values() if v["commit_count"] > 0],
        key=lambda x: x["commit_count"],
        reverse=True,
    )[:10]

    stats = {
        "total_commits": total_commits,
        "total_authors": len(all_authors),
        "repo_age_days": repo_age_days,
        "first_commit": first_commit_dt.strftime("%Y-%m-%d"),
        "last_commit": last_commit_dt.strftime("%Y-%m-%d"),
    }

    logger.info(
        "[churn] ✅ %d commits | %d authors | %d days old | %d files tracked",
        total_commits,
        len(all_authors),
        repo_age_days,
        len(file_churn),
    )

    return {
        "file_churn": file_churn,
        "most_churned": most_churned,
        "stats": stats,
    }
