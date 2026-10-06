#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# uv selects the project's Python 3.12 environment even inside Conda (base).
if command -v uv >/dev/null 2>&1; then
    exec uv run --locked python -m uvicorn backend.app.main:app \
        --reload --reload-dir "$PROJECT_ROOT/backend" "$@"
elif [[ -x "$PROJECT_ROOT/.venv/bin/python" ]]; then
    exec "$PROJECT_ROOT/.venv/bin/python" -m uvicorn backend.app.main:app \
        --reload --reload-dir "$PROJECT_ROOT/backend" "$@"
else
    printf '%s\n' 'Create the project environment first:' \
        '  python3.12 -m venv .venv' \
        '  .venv/bin/python -m pip install -r requirements.txt' >&2
    exit 1
fi
