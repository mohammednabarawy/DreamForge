#!/usr/bin/env bash
set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "${SCRIPT_DIR}"

if [ "$(uname -m)" = "arm64" ] && [ -x "${HOME}/.cargo/bin/cargo" ]; then
    export PATH="${HOME}/.cargo/bin:${PATH}"
fi

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

if [ -x "${SCRIPT_DIR}/venv/bin/python" ]; then
    if ! "${SCRIPT_DIR}/venv/bin/python" -c 'import platform,sys; ok=sys.version_info >= (3,10); ok=ok and not (platform.system()=="Darwin" and platform.machine()!=__import__("subprocess").check_output(["uname","-m"],text=True).strip()); raise SystemExit(0 if ok else 1)' 2>/dev/null; then
        echo "  Repairing incompatible Python environment…"
        "${SCRIPT_DIR}/setup.sh" --skip-npm
    fi
fi

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

ensure_rollup_native() {
    (cd "${DESKTOP_DIR}" && node -e "require('rollup/dist/native.js')" 2>/dev/null) && return 0
    local node_arch rollup_version
    node_arch="$(node -p 'process.arch')"
    rollup_version="$(cd "${DESKTOP_DIR}" && node -p "require('rollup/package.json').version")"
    echo "  Installing Rollup native binding for macOS ${node_arch}…"
    (cd "${DESKTOP_DIR}" && npm install --no-save --package-lock=false "@rollup/rollup-darwin-${node_arch}@${rollup_version}")
    (cd "${DESKTOP_DIR}" && node -e "require('rollup/dist/native.js')" 2>/dev/null)
}

tauri_binding_ready() {
    local dir
    case "$(node -p 'process.arch')" in
        arm64) dir="${DESKTOP_DIR}/node_modules/@tauri-apps/cli-darwin-arm64" ;;
        x64)   dir="${DESKTOP_DIR}/node_modules/@tauri-apps/cli-darwin-x64" ;;
        *)     return 1 ;;
    esac
    [ -d "${dir}" ] && ls "${dir}"/*.node &>/dev/null && ensure_rollup_native
}

if [ ! -d "${DESKTOP_DIR}/node_modules" ] || ! tauri_binding_ready; then
    echo "  Installing desktop dependencies…"
    (cd "${DESKTOP_DIR}" && npm install)
    ensure_rollup_native
fi

export OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES
export PYTORCH_ENABLE_MPS_FALLBACK="${PYTORCH_ENABLE_MPS_FALLBACK:-1}"
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
