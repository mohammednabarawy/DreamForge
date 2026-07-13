#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${ROOT}"

echo ""
echo "  DreamForge setup"
echo "  ================"
echo ""

python_compatible() {
  local candidate="$1"
  command -v "${candidate}" >/dev/null 2>&1 || return 1
  "${candidate}" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null || return 1
  if [ "$(uname -s)" = "Darwin" ] && [ "$(uname -m)" = "arm64" ]; then
    "${candidate}" -c 'import platform; raise SystemExit(0 if platform.machine() == "arm64" else 1)' 2>/dev/null || return 1
  fi
}

pick_python() {
  local candidate
  for candidate in /opt/homebrew/bin/python3 /usr/local/bin/python3 python3 python; do
    if python_compatible "${candidate}"; then
      echo "${candidate}"
      return 0
    fi
  done
  return 1
}

PYTHON="$(pick_python)" || {
  echo "ERROR: Compatible Python not found. Install Python 3.10+ and retry."
  if [ "$(uname -s)" = "Darwin" ] && [ "$(uname -m)" = "arm64" ]; then
    echo "  Apple Silicon requires a native arm64 Python (Homebrew recommended)."
  fi
  exit 1
}

"${PYTHON}" scripts/setup_environment.py "$@"
