"""Command-line entry point for report generation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from app.core.exporters import export_all


def main(argv: Sequence[str] | None = None) -> int:
    """Load an analysis JSON file and export selected report formats."""
    parser = argparse.ArgumentParser(description="Export a repository profiler report.")
    parser.add_argument("analysis_json", type=Path)
    parser.add_argument("--formats", default="pdf,html,docx")
    parser.add_argument("--out", type=Path, default=Path("reports"))
    args = parser.parse_args(argv)
    payload = json.loads(args.analysis_json.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        parser.error("analysis JSON must contain an object.")
    exports = export_all(
        payload,
        (fmt.strip() for fmt in args.formats.split(",") if fmt.strip()),
        args.out,
    )
    for fmt, path in exports.items():
        print(f"{fmt}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
