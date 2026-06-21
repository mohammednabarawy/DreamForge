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

if ! command -v npm &>/dev/null; then
    echo "  ERROR: npm not found. Install Node.js 20+ from https://nodejs.org/"
    exit 1
fi

if [ "$(uname -m)" = "arm64" ] && [ "$(node -p 'process.arch')" = "x64" ]; then
    for node_bin in "${HOME}/.nvm/versions/node"/*/bin/node /opt/homebrew/bin/node; do
        [ -x "${node_bin}" ] || continue
        if [ "$("${node_bin}" -p 'process.arch')" = "arm64" ]; then
            export PATH="$(dirname "${node_bin}"):${PATH}"
            break
        fi
    done
fi

if [ "$(uname -m)" = "arm64" ] && [ "$(node -p 'process.arch')" = "x64" ]; then
    echo "  ERROR: Node is x86_64 (Rosetta). Use native arm64 Node (nvm install 24 && nvm use 24)."
    exit 1
fi

tauri_binding_ready() {
    local dir
    case "$(node -p 'process.arch')" in
        arm64) dir="${DESKTOP_DIR}/node_modules/@tauri-apps/cli-darwin-arm64" ;;
        x64)   dir="${DESKTOP_DIR}/node_modules/@tauri-apps/cli-darwin-x64" ;;
        *)     return 1 ;;
    esac
    [ -d "${dir}" ] && ls "${dir}"/*.node &>/dev/null
}

if [ ! -d "${DESKTOP_DIR}/node_modules" ] || ! tauri_binding_ready; then
    echo "  Installing desktop dependencies…"
    (cd "${DESKTOP_DIR}" && rm -rf node_modules package-lock.json && npm install)
fi

export OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES
export DREAMFORGE_ROOT="${SCRIPT_DIR}/backend"

if [ -d "${SCRIPT_DIR}/venv" ]; then
    source "${SCRIPT_DIR}/venv/bin/activate"
fi

STALE_PORT_PID=$(lsof -t -i :5173 2>/dev/null || true)
if [ -n "${STALE_PORT_PID}" ]; then
    kill -9 ${STALE_PORT_PID} 2>/dev/null || true
fi

echo "  Launching DreamForge Desktop Studio…"
echo ""
cd "${DESKTOP_DIR}"
npm run tauri dev
