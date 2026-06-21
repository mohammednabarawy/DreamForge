#!/usr/bin/env bash
set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "${SCRIPT_DIR}"

# ComfyUI subprocesses on macOS (same as DreamForge.command).
export OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES

if [ ! -f "${SCRIPT_DIR}/.dreamforge_setup_ok" ] && [ ! -d "${SCRIPT_DIR}/venv" ]; then
  if command -v python3 >/dev/null 2>&1 || command -v python >/dev/null 2>&1; then
    echo "First run: installing DreamForge dependencies..."
    "${SCRIPT_DIR}/setup.sh"
  else
    echo "ERROR: Run ./setup.sh first (Python 3.10+ required)."
    exit 1
  fi
fi

echo "Checking system prerequisites..."

# Check cargo (Rust compiler/package manager)
if ! command -v cargo &> /dev/null; then
    echo "ERROR: cargo not found. Install Rust from https://rustup.rs/"
    exit 1
fi

# Check node & npm
if ! command -v npm &> /dev/null; then
    echo "ERROR: npm not found. Install Node.js from https://nodejs.org/"
    exit 1
fi

DESKTOP_DIR="${SCRIPT_DIR}/apps/desktop"

# Apple Silicon: Tauri native bindings must match Node arch (arm64, not Rosetta x64).
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
    echo "ERROR: Node is x86_64 (Rosetta). DreamForge desktop needs native arm64 Node."
    echo "  nvm install 24 && nvm use 24"
    echo "  Or: export PATH=\"/opt/homebrew/bin:\$PATH\""
    exit 1
fi

tauri_binding_dir() {
    case "$(node -p 'process.arch')" in
        arm64) echo "${DESKTOP_DIR}/node_modules/@tauri-apps/cli-darwin-arm64" ;;
        x64)   echo "${DESKTOP_DIR}/node_modules/@tauri-apps/cli-darwin-x64" ;;
        *)     echo "" ;;
    esac
}

ensure_desktop_node_modules() {
    local binding_dir
    binding_dir="$(tauri_binding_dir)"
    if [ -n "${binding_dir}" ] && [ -d "${binding_dir}" ] && ls "${binding_dir}"/*.node &>/dev/null; then
        return 0
    fi
    echo "Installing DreamForge desktop dependencies (Tauri native binding)..."
    (cd "${DESKTOP_DIR}" && rm -rf node_modules package-lock.json && npm install)
}

ensure_desktop_node_modules

# Set backend root env var
export DREAMFORGE_ROOT="${SCRIPT_DIR}/backend"

# Check if a python virtual environment is in the root
if [ -d "${SCRIPT_DIR}/venv" ]; then
    echo "Activating local Python virtual environment..."
    source "${SCRIPT_DIR}/venv/bin/activate"
fi

# Free up the Tauri development port if occupied
STALE_PORT_PID=$(lsof -t -i :5173 || true)
if [ -n "${STALE_PORT_PID}" ]; then
    echo "Stopping stale process on port 5173 (PID ${STALE_PORT_PID})..."
    kill -9 ${STALE_PORT_PID} 2>/dev/null || true
fi

echo "Launching DreamForge Desktop Studio..."
cd "${DESKTOP_DIR}"
npm run tauri dev
