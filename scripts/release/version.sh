#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

if [[ $# -lt 1 || $# -gt 3 ]]; then
  echo "Usage: $0 X.Y.Z [--date YYYY-MM-DD]" >&2
  exit 2
fi

exec "${ROOT_DIR}/.venv/bin/python" "${ROOT_DIR}/scripts/release/bump_version.py" "$@"
