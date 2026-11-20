import subprocess

from app.core.churn import COMMIT_PREFIX, analyse_churn, parse_numstat_log


def test_numstat_parser_reads_bugfix_and_rename_records():
    raw_log = (
        f"{COMMIT_PREFIX}abc123\x1fA Person\x1fa@example.com\x1f1760000000\x1fFix issue in module\n"
        "5\t2\t{src/old.py => src/new.py}\n\n"
    )

    commits, warnings = parse_numstat_log(raw_log)

    assert not warnings
    assert commits[0]["message"] == "Fix issue in module"
    assert commits[0]["files"]["src/new.py"] == (5, 2)
    assert commits[0]["renames"] == [("src/old.py", "src/new.py")]


def test_churn_tracks_single_pass_history_and_renames(tmp_path):
    repo = tmp_path / "rename repo"
    repo.mkdir()
    subprocess.run(["git", "init", str(repo)], check=True, capture_output=True, timeout=10)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "author@example.com"], check=True, timeout=10)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "Author"], check=True, timeout=10)
    source = repo / "src"
    source.mkdir()
    old_file = source / "old.py"
    old_file.write_text("value = 1\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True, timeout=10)
    subprocess.run(["git", "-C", str(repo), "commit", "-m", "initial"], check=True, capture_output=True, timeout=10)
    old_file.write_text("value = 2\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True, timeout=10)
    subprocess.run(["git", "-C", str(repo), "commit", "-m", "Fix issue"], check=True, capture_output=True, timeout=10)
    new_file = source / "new.py"
    old_file.rename(new_file)
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True, timeout=10)
    subprocess.run(["git", "-C", str(repo), "commit", "-m", "Rename module"], check=True, capture_output=True, timeout=10)

    result = analyse_churn(str(repo), [str(new_file)], max_commits=10)

    file_data = result["file_churn"]["src/new.py"]
    assert result["stats"]["total_commits"] == 3
    assert file_data["commit_count"] >= 2
    assert file_data["bug_fix_count"] == 1
    assert file_data["lines_added"] >= 1
    assert result["renames"]
