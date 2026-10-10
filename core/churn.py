# core/churn.py
# Analyses git commit history to compute per-file churn metrics.
# Churn = how frequently a file changes over the repo's lifetime.

import os
from datetime import datetime, timezone
from git import Repo, InvalidGitRepositoryError


def analyse_churn(repo_path: str, python_files: list) -> dict:
    """
    Reads git log to compute churn metrics for every Python file.

    Args:
        repo_path    : local path to the cloned repo
        python_files : list of absolute file paths (from scanner manifest)

    Returns a dict with:
      - file_churn   : dict {rel_path → churn_data}
      - most_churned : top 5 files by commit count
      - stats        : repo-wide git stats
    """

    print(f"  [churn] Reading git history at {repo_path}...")

    try:
        repo = Repo(repo_path)
    except InvalidGitRepositoryError:
        print("  [churn] ❌ Not a valid git repo")
        return _empty_result()

    # ── Repo-wide stats ───────────────────────────────────────────────────
    all_commits = list(repo.iter_commits())
    total_commits = len(all_commits)

    if total_commits == 0:
        print("  [churn] ⚠️  No commits found")
        return _empty_result()

    first_commit_dt = datetime.fromtimestamp(
        all_commits[-1].committed_date, tz=timezone.utc
    )
    last_commit_dt = datetime.fromtimestamp(
        all_commits[0].committed_date, tz=timezone.utc
    )
    repo_age_days = max((last_commit_dt - first_commit_dt).days, 1)

    # Collect unique authors
    authors = set(c.author.email for c in all_commits if c.author.email)

    # ── Per-file churn ────────────────────────────────────────────────────
    file_churn = {}

    for filepath in python_files:
        rel_path = os.path.relpath(filepath, repo_path)
        # Git expects forward slashes even on Windows
        git_path = rel_path.replace(os.sep, "/")

        try:
            commits = list(repo.iter_commits(paths=git_path))
        except Exception:
            commits = []

        commit_count = len(commits)

        if commit_count == 0:
            file_churn[rel_path] = {
                "rel_path":      rel_path,
                "commit_count":  0,
                "authors":       [],
                "author_count":  0,
                "first_changed": None,
                "last_changed":  None,
                "age_days":      0,
                "churn_rate":    0.0,   # commits per month
            }
            continue

        file_authors = list(set(
            c.author.name for c in commits if c.author.name
        ))

        first_changed = datetime.fromtimestamp(
            commits[-1].committed_date, tz=timezone.utc
        ).strftime("%Y-%m-%d")

        last_changed = datetime.fromtimestamp(
            commits[0].committed_date, tz=timezone.utc
        ).strftime("%Y-%m-%d")

        age_days = max(
            (datetime.fromtimestamp(commits[0].committed_date, tz=timezone.utc) -
             datetime.fromtimestamp(commits[-1].committed_date, tz=timezone.utc)).days,
            1
        )

        # Churn rate: commits per 30 days (normalised)
        churn_rate = round((commit_count / age_days) * 30, 2)

        file_churn[rel_path] = {
            "rel_path":      rel_path,
            "commit_count":  commit_count,
            "authors":       file_authors,
            "author_count":  len(file_authors),
            "first_changed": first_changed,
            "last_changed":  last_changed,
            "age_days":      age_days,
            "churn_rate":    churn_rate,
        }

    # ── Top churned files ──────────────────────────────────────────────────
    most_churned = sorted(
        [v for v in file_churn.values() if v["commit_count"] > 0],
        key=lambda x: x["commit_count"],
        reverse=True
    )[:5]

    # ── Repo-wide stats ────────────────────────────────────────────────────
    stats = {
        "total_commits":  total_commits,
        "total_authors":  len(authors),
        "repo_age_days":  repo_age_days,
        "first_commit":   first_commit_dt.strftime("%Y-%m-%d"),
        "last_commit":    last_commit_dt.strftime("%Y-%m-%d"),
    }

    print(f"  [churn] ✅ {total_commits} commits | "
          f"{len(authors)} authors | "
          f"{repo_age_days} days old | "
          f"{len(file_churn)} files tracked")

    return {
        "file_churn":   file_churn,
        "most_churned": most_churned,
        "stats":        stats,
    }


def _empty_result() -> dict:
    return {
        "file_churn":   {},
        "most_churned": [],
        "stats": {
            "total_commits": 0,
            "total_authors": 0,
            "repo_age_days": 0,
            "first_commit":  "N/A",
            "last_commit":   "N/A",
        }
    }