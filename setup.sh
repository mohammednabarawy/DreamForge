#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${ROOT}"

echo ""
echo "  DreamForge setup"
echo "  ================"
echo ""

if command -v python3 >/dev/null 2>&1; then
  PYTHON=python3
elif command -v python >/dev/null 2>&1; then
  PYTHON=python
else
  echo "ERROR: python3 not found. Install Python 3.10+ and retry."
  exit 1
fi

"${PYTHON}" scripts/setup_environment.py "$@"
