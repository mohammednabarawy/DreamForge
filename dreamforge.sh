#!/usr/bin/env bash
set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "${SCRIPT_DIR}"

if [ "$(uname -s)" = "Darwin" ] && [ -f "${SCRIPT_DIR}/scripts/macos_arm_env.sh" ]; then
    # shellcheck source=scripts/macos_arm_env.sh
    source "${SCRIPT_DIR}/scripts/macos_arm_env.sh"
    dreamforge_setup_macos_arm_env
elif [ "$(uname -m)" = "arm64" ] && [ -x "${HOME}/.cargo/bin/cargo" ]; then
    export PATH="${HOME}/.cargo/bin:${PATH}"
fi

# ComfyUI subprocesses on macOS (same as DreamForge.command).
export OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES
if [ "$(uname -s)" = "Darwin" ]; then
    export PYTORCH_ENABLE_MPS_FALLBACK="${PYTORCH_ENABLE_MPS_FALLBACK:-1}"
fi

run_venv_python() {
    if declare -F dreamforge_run_python >/dev/null 2>&1; then
        dreamforge_run_python "$@"
    else
        "$@"
    fi
}

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

if [ -x "${SCRIPT_DIR}/venv/bin/python" ]; then
    if ! run_venv_python "${SCRIPT_DIR}/venv/bin/python" -c 'import os,platform,sys; ok=sys.version_info >= (3,10); expect_arm64=(os.environ.get("DREAMFORGE_MAC_ARM64")=="1"); ok=ok and not (platform.system()=="Darwin" and expect_arm64 and platform.machine()!="arm64"); raise SystemExit(0 if ok else 1)' 2>/dev/null; then
        echo "Repairing incompatible Python environment..."
        "${SCRIPT_DIR}/setup.sh" --skip-npm
    fi
fi

# Apple Silicon: Tauri native bindings must match Node arch (arm64, not Rosetta x64).
if [ "${DREAMFORGE_MAC_ARM64:-0}" = "1" ] && [ "$(node -p 'process.arch')" = "x64" ]; then
    echo "ERROR: Node is x86_64-only (Rosetta). DreamForge desktop needs native arm64 Node."
    echo "  brew install node  (or: nvm install 24 && nvm use 24)"
    exit 1
fi

tauri_binding_dir() {
    if [ "$(uname -s)" = "Darwin" ]; then
        case "$(node -p 'process.arch')" in
            arm64) echo "${DESKTOP_DIR}/node_modules/@tauri-apps/cli-darwin-arm64" ;;
            x64)   echo "${DESKTOP_DIR}/node_modules/@tauri-apps/cli-darwin-x64" ;;
            *)     echo "" ;;
        esac
    else
        case "$(node -p 'process.arch')" in
            arm64) echo "${DESKTOP_DIR}/node_modules/@tauri-apps/cli-linux-arm64-gnu" ;;
            x64)   echo "${DESKTOP_DIR}/node_modules/@tauri-apps/cli-linux-x64-gnu" ;;
            *)     echo "" ;;
        esac
    fi
}

ensure_rollup_native() {
    (cd "${DESKTOP_DIR}" && node -e "require('rollup/dist/native.js')" 2>/dev/null) && return 0
    if [ "$(uname -s)" = "Darwin" ]; then
        local node_arch rollup_version
        node_arch="$(node -p 'process.arch')"
        rollup_version="$(cd "${DESKTOP_DIR}" && node -p "require('rollup/package.json').version")"
        echo "Installing Rollup native binding for macOS ${node_arch}..."
        (cd "${DESKTOP_DIR}" && npm install --no-save --package-lock=false "@rollup/rollup-darwin-${node_arch}@${rollup_version}")
    fi
    (cd "${DESKTOP_DIR}" && node -e "require('rollup/dist/native.js')" 2>/dev/null)
}

ensure_desktop_node_modules() {
    local binding_dir
    binding_dir="$(tauri_binding_dir)"
    if [ -n "${binding_dir}" ] \
        && [ -d "${binding_dir}" ] \
        && ls "${binding_dir}"/*.node &>/dev/null \
        && ensure_rollup_native; then
        return 0
    fi
    echo "Installing DreamForge desktop dependencies (native bindings)..."
    (cd "${DESKTOP_DIR}" && npm install)
    ensure_rollup_native
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
STALE_PORT_PID=$(lsof -t -i :5173 2>/dev/null || true)
if [ -n "${STALE_PORT_PID}" ]; then
    echo "Stopping stale process on port 5173 (PID ${STALE_PORT_PID})..."
    kill -9 ${STALE_PORT_PID} 2>/dev/null || true
fi

echo "Launching DreamForge Desktop Studio..."
cd "${DESKTOP_DIR}"
npm run tauri dev
