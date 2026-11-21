#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${ROOT}"

if [ "$(uname -s)" = "Darwin" ] && [ -f "${ROOT}/scripts/macos_arm_env.sh" ]; then
  # shellcheck source=scripts/macos_arm_env.sh
  source "${ROOT}/scripts/macos_arm_env.sh"
  dreamforge_setup_macos_arm_env
fi

echo ""
echo "  DreamForge setup"
echo "  ================"
echo ""

run_py() {
  if declare -F dreamforge_run_python >/dev/null 2>&1; then
    dreamforge_run_python "$@"
  else
    "$@"
  fi
}

python_compatible() {
  local candidate="$1"
  command -v "${candidate}" >/dev/null 2>&1 || return 1
  run_py "${candidate}" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null || return 1
  if [ "${DREAMFORGE_MAC_ARM64:-0}" = "1" ]; then
    run_py "${candidate}" -c 'import platform; raise SystemExit(0 if platform.machine() == "arm64" else 1)' 2>/dev/null || return 1
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
  if [ "${DREAMFORGE_MAC_ARM64:-0}" = "1" ]; then
    echo "  Apple Silicon requires a native arm64 Python (Homebrew recommended)."
  fi
  exit 1
}

run_py "${PYTHON}" scripts/setup_environment.py "$@"
