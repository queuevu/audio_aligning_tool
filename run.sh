#!/usr/bin/env bash
# Runs the app, setting up .venv automatically on first use.
# Usage: ./run.sh [entry-script] [args...]
#   ./run.sh                -> main.py (word alignment tool)
#   ./run.sh bible_main.py  -> Bible batch alignment tool
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

ENTRY="${1:-main.py}"
[ $# -gt 0 ] && shift || true

if [ ! -d .venv ] || [ ! -x .venv/bin/python ]; then
    echo "No virtual environment found, running setup..."
    ./setup.sh
fi

exec .venv/bin/python "$ENTRY" "$@"
