#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${ROOT}"

echo ""
echo "  DreamForge setup"
echo "  ================"
echo ""

pick_python() {
  if command -v python3 >/dev/null 2>&1; then
    echo python3
  elif command -v python >/dev/null 2>&1; then
    echo python
  else
    return 1
  fi
}

PYTHON="$(pick_python)" || {
  echo "ERROR: python3 not found. Install Python 3.10+ and retry."
  exit 1
}

# Apple Silicon: avoid Anaconda/Rosetta x86_64 (torch capped at 2.2 on PyPI).
if [ "$(uname -m)" = "arm64" ]; then
  for candidate in /opt/homebrew/bin/python3 /usr/local/bin/python3 /usr/bin/python3; do
    if [ -x "${candidate}" ] && "${candidate}" -c 'import platform; raise SystemExit(0 if platform.machine() == "arm64" else 1)' 2>/dev/null; then
      PYTHON="${candidate}"
      break
    fi
  done
fi

"${PYTHON}" scripts/setup_environment.py "$@"
