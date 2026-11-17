#!/usr/bin/env bash
set -euo pipefail
project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_dir"
if command -v uv >/dev/null 2>&1; then
    uv sync --locked --no-dev
else
    python3 -m venv .venv
    .venv/bin/python -m pip install .
fi
.venv/bin/python scripts/install_desktop.py
