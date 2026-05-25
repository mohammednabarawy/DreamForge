#!/usr/bin/env bash
set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "${SCRIPT_DIR}"

echo ""
echo "  ✦  DreamForge  ✦"
echo "  ───────────────"
echo ""

if [ ! -f "${SCRIPT_DIR}/.dreamforge_setup_ok" ] && [ ! -d "${SCRIPT_DIR}/venv" ]; then
  if command -v python3 >/dev/null 2>&1 || command -v python >/dev/null 2>&1; then
    echo "  First run: installing dependencies…"
    "${SCRIPT_DIR}/setup.sh"
  else
    echo "  ERROR: Run ./setup.sh first (Python 3.10+ required)."
    exit 1
  fi
fi

DESKTOP_DIR="${SCRIPT_DIR}/apps/desktop"

if [ ! -d "${DESKTOP_DIR}/node_modules" ]; then
    echo "  Installing dependencies…"
    (cd "${DESKTOP_DIR}" && npm install)
fi

# Ensure Tauri native binding exists (npm often skips optional deps)
if ! node -e "require('@tauri-apps/cli-darwin-arm64')" 2>/dev/null; then
  echo "  Installing Tauri native binding…"
  (cd "${DESKTOP_DIR}" && npm install @tauri-apps/cli-darwin-arm64 --save-optional)
fi

export OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES
export DREAMFORGE_ROOT="${SCRIPT_DIR}/backend"

# Prefer conda env (Apple Silicon PyTorch) over venv
if [ -d "/opt/anaconda3/envs/dreamforge" ]; then
    export PATH="/opt/anaconda3/envs/dreamforge/bin:${PATH}"
elif [ -d "${SCRIPT_DIR}/venv" ]; then
    source "${SCRIPT_DIR}/venv/bin/activate"
fi

STALE_PORT_PID=$(lsof -t -i :1420 2>/dev/null || true)
if [ -n "${STALE_PORT_PID}" ]; then
    kill -9 ${STALE_PORT_PID} 2>/dev/null || true
fi

echo "  Launching DreamForge Desktop Studio…"
echo ""
cd "${DESKTOP_DIR}"
npm run tauri dev
