#!/usr/bin/env bash
# Entry point for invoking repomap or dbmap with auto-detected environment.
#
# Usage: run.sh <module> [args...]
#   <module> is "repomap" or "dbmap"
#
# Detects:
#   1. Install location (the repo root containing this script — no hardcoding).
#   2. A Python interpreter >= 3.8 on PATH (tries python3.12 down to python3.8,
#      then python3 / python).
#   3. If no suitable Python is found, falls back to a version manager:
#      uv > pyenv > asdf. Emits a clear error if none are available.

set -euo pipefail

if [ $# -lt 1 ]; then
    echo "usage: $(basename "$0") <repomap|dbmap> [args...]" >&2
    exit 2
fi

MODULE="$1"
shift

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"

if [ ! -f "$REPO_DIR/$MODULE/__main__.py" ]; then
    echo "error: $MODULE package not found at $REPO_DIR/$MODULE" >&2
    exit 1
fi

MIN_MAJOR=3
MIN_MINOR=8

python_ok() {
    local candidate="$1"
    command -v "$candidate" >/dev/null 2>&1 || return 1
    "$candidate" -c "import sys; sys.exit(0 if sys.version_info >= (${MIN_MAJOR}, ${MIN_MINOR}) else 1)" 2>/dev/null
}

PYTHON=""
for candidate in python3.13 python3.12 python3.11 python3.10 python3.9 python3.8 python3 python; do
    if python_ok "$candidate"; then
        PYTHON="$candidate"
        break
    fi
done

PYTHON_PREFIX=""
if [ -z "$PYTHON" ]; then
    echo "No Python >= ${MIN_MAJOR}.${MIN_MINOR} found on PATH. Trying a version manager..." >&2
    FALLBACK_VERSION="3.11"

    if command -v uv >/dev/null 2>&1; then
        echo "Using uv to provision Python ${FALLBACK_VERSION}." >&2
        PYTHON_PREFIX="uv run --python ${FALLBACK_VERSION} --"
        PYTHON="python"
    elif command -v pyenv >/dev/null 2>&1; then
        echo "Using pyenv to provision Python ${FALLBACK_VERSION}." >&2
        pyenv install -s "${FALLBACK_VERSION}" >&2
        RESOLVED="$(pyenv prefix "${FALLBACK_VERSION}" 2>/dev/null || true)"
        if [ -n "$RESOLVED" ] && [ -x "$RESOLVED/bin/python" ]; then
            PYTHON="$RESOLVED/bin/python"
        fi
    elif command -v asdf >/dev/null 2>&1; then
        echo "Using asdf to provision Python ${FALLBACK_VERSION}." >&2
        asdf plugin add python >/dev/null 2>&1 || true
        ASDF_VERSION="$(asdf latest python "${FALLBACK_VERSION}" 2>/dev/null || echo "${FALLBACK_VERSION}")"
        asdf install python "$ASDF_VERSION" >&2 || true
        RESOLVED="$(asdf where python "$ASDF_VERSION" 2>/dev/null || true)"
        if [ -n "$RESOLVED" ] && [ -x "$RESOLVED/bin/python" ]; then
            PYTHON="$RESOLVED/bin/python"
        fi
    fi

    if [ -z "$PYTHON" ]; then
        cat >&2 <<EOF
error: no compatible Python found.
repomap needs Python >= ${MIN_MAJOR}.${MIN_MINOR}. Install one of:
  - Python ${MIN_MAJOR}.${MIN_MINOR}+ directly (https://www.python.org/downloads/)
  - uv    (curl -LsSf https://astral.sh/uv/install.sh | sh)
  - pyenv (https://github.com/pyenv/pyenv#installation)
  - asdf  (https://asdf-vm.com/guide/getting-started.html)
EOF
        exit 1
    fi
fi

export PYTHONPATH="$REPO_DIR${PYTHONPATH:+:$PYTHONPATH}"
exec $PYTHON_PREFIX "$PYTHON" -m "$MODULE" "$@"
