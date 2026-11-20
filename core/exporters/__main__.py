"""Root-workspace wrapper for the backend report export CLI."""

from app.core.exporters.__main__ import main

if __name__ == "__main__":
    raise SystemExit(main())
