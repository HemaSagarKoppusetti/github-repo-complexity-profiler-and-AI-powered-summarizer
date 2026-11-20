"""Compatibility namespace for the documented `python -m core.exporters` CLI."""

from __future__ import annotations

import sys
from importlib import import_module
from pathlib import Path

_BACKEND = str(Path(__file__).resolve().parents[2] / "backend")
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

_exporters = import_module("app.core.exporters")
export_all = _exporters.export_all
export_report = _exporters.export_report

__all__ = ["export_all", "export_report"]
