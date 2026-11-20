import subprocess

from app.core.scanner import scan_repo


def _git_repo(path):
    subprocess.run(["git", "init", str(path)], check=True, capture_output=True, timeout=10)
    subprocess.run(["git", "-C", str(path), "config", "user.email", "test@example.com"], check=True, timeout=10)
    subprocess.run(["git", "-C", str(path), "config", "user.name", "Test"], check=True, timeout=10)


def test_scanner_filters_and_classifies_fixture_repo(tmp_path):
    repo = tmp_path / "space repo"
    repo.mkdir()
    _git_repo(repo)
    (repo / "src").mkdir()
    (repo / "tests").mkdir()
    (repo / "docs").mkdir()
    (repo / "src" / "module.py").write_text(
        '"""Module docs."""\nimport os\n\ndef run(value):\n    """Run it."""\n    return value if value else os.getcwd()\n',
        encoding="utf-8",
    )
    (repo / "tests" / "test_module.py").write_text("def test_run():\n    assert True\n", encoding="utf-8")
    (repo / "src" / "ui.ts").write_text("import React from 'react';\n", encoding="utf-8")
    (repo / "docs" / "guide.md").write_text("# Guide\n", encoding="utf-8")
    (repo / "src" / "legacy.py").write_bytes("# encoding: latin-1\nname = 'caf\xe9'\n".encode("latin-1"))
    (repo / "src" / "broken.py").write_text("def broken(:\n", encoding="utf-8")
    (repo / "src" / "binary.py").write_bytes(b"valid\x00binary")
    (repo / "src" / "generated.py").write_text("# auto-generated; do not edit\nvalue = 1\n", encoding="utf-8")
    (repo / "src" / "large.py").write_bytes(b"x = 1\n" + b"#" * (1024 * 1024))
    (repo / "src" / "bundle.js").write_text("const data = '" + ("x" * 20_000) + "';\n", encoding="utf-8")
    (repo / "package-lock.json").write_text("{}", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True, timeout=10)

    manifest = scan_repo(str(repo), cache_dir=str(tmp_path / "cache"))

    by_path = {entry["rel_path"]: entry for entry in manifest["files"]}
    assert "src/module.py" in by_path
    assert by_path["src/module.py"]["role"] == "source"
    assert by_path["tests/test_module.py"]["role"] == "test"
    assert by_path["src/module.py"]["complexity"]["hotspot_fn"] == "run"
    assert by_path["src/module.py"]["imports"][0]["module"] == "os"
    assert by_path["src/module.py"]["lizard"] is None
    assert by_path["src/ui.ts"]["lizard"] is not None
    assert "src/generated.py" not in by_path
    assert "src/binary.py" not in by_path
    assert "src/large.py" not in by_path
    assert any(item["file"] == "src/broken.py" for item in manifest["diagnostics"])


def test_scanner_uses_content_cache_on_unchanged_files(tmp_path):
    repo = tmp_path / "cached"
    repo.mkdir()
    _git_repo(repo)
    (repo / "main.py").write_text("def main():\n    return 1\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True, timeout=10)
    cache_dir = str(tmp_path / "cache")

    first = scan_repo(str(repo), cache_dir=cache_dir)
    second = scan_repo(str(repo), cache_dir=cache_dir)

    assert first["cache"]["misses"] == 1
    assert second["cache"]["hits"] == 1
    assert second["cache"]["misses"] == 0
    assert second["files"][0]["complexity"] == first["files"][0]["complexity"]


def test_scanner_handles_empty_repository(tmp_path):
    repo = tmp_path / "empty"
    repo.mkdir()
    _git_repo(repo)

    manifest = scan_repo(str(repo), cache_dir=str(tmp_path / "cache"))

    assert manifest["files"] == []
    assert manifest["python_files"] == []
    assert manifest["total_files"] == 0
