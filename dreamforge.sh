#!/usr/bin/env bash
set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "${SCRIPT_DIR}"

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

# Check frontend node_modules
DESKTOP_DIR="${SCRIPT_DIR}/apps/desktop"
if [ ! -d "${DESKTOP_DIR}/node_modules" ]; then
    echo "Installing DreamForge desktop dependencies..."
    (cd "${DESKTOP_DIR}" && npm install)
fi

# Set backend root env var
export DREAMFORGE_ROOT="${SCRIPT_DIR}/backend"

# Check if a python virtual environment is in the root
if [ -d "${SCRIPT_DIR}/venv" ]; then
    echo "Activating local Python virtual environment..."
    source "${SCRIPT_DIR}/venv/bin/activate"
fi

# Free up the Tauri development port if occupied
STALE_PORT_PID=$(lsof -t -i :1420 || true)
if [ -n "${STALE_PORT_PID}" ]; then
    echo "Stopping stale process on port 1420 (PID ${STALE_PORT_PID})..."
    kill -9 ${STALE_PORT_PID} 2>/dev/null || true
fi

echo "Launching DreamForge Desktop Studio..."
cd "${DESKTOP_DIR}"
npm run tauri dev
