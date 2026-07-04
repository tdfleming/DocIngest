#!/usr/bin/env python3
"""Export the FastAPI OpenAPI schema to a JSON file.

Imports the DocIngest app and dumps `app.openapi()` without starting a server
or touching any datastore. Used by the docs build to publish an API reference.

Usage:
  python scripts/export_openapi.py [output_path]   # default: docs-site/openapi.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from docingest.api.app import app


def main() -> int:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("docs-site/openapi.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(app.openapi(), indent=2), encoding="utf-8")
    print(f"wrote {out} ({out.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
