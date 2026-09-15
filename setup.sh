#!/usr/bin/env bash
# One-time environment setup for the Aeneas Word Alignment Tool.
# Creates .venv and installs all Python dependencies. Safe to re-run.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

PYTHON_BIN="${PYTHON_BIN:-python3.10}"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
    echo "error: $PYTHON_BIN not found." >&2
    echo "aeneas requires Python 3.10. Install it with: brew install python@3.10" >&2
    exit 1
fi

if ! command -v espeak-ng >/dev/null 2>&1 && ! command -v espeak >/dev/null 2>&1; then
    echo "error: espeak/espeak-ng not found." >&2
    echo "Install it with: brew install espeak-ng" >&2
    exit 1
fi

if ! command -v ffmpeg >/dev/null 2>&1; then
    echo "error: ffmpeg not found." >&2
    echo "Install it with: brew install ffmpeg" >&2
    exit 1
fi

if [ ! -d .venv ]; then
    echo "Creating virtual environment (.venv) with $PYTHON_BIN..."
    "$PYTHON_BIN" -m venv .venv
fi

echo "Installing dependencies..."
.venv/bin/pip install --upgrade pip >/dev/null
.venv/bin/pip install -r requirements.txt

echo "Setup complete. Run the app with: ./run.sh"
