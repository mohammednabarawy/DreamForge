#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-run}"
APP_NAME="DreamForge"
PROCESS_NAME="dreamforge"
BUNDLE_ID="com.dreamforge.studio"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DESKTOP_DIR="${ROOT_DIR}/apps/desktop"
APP_BUNDLE="${DESKTOP_DIR}/src-tauri/target/debug/bundle/macos/${APP_NAME}.app"
APP_BINARY="${APP_BUNDLE}/Contents/MacOS/${PROCESS_NAME}"

if [ "$(uname -m)" = "arm64" ] && [ -x "${HOME}/.cargo/bin/cargo" ]; then
    export PATH="${HOME}/.cargo/bin:${PATH}"
fi

pkill -x "${PROCESS_NAME}" >/dev/null 2>&1 || true

cd "${DESKTOP_DIR}"
# Debug runs use the repository backend directly.  Omitting release bundle
# resources avoids copying multi-gigabyte models and traversing nested checkout
# metadata every time the Run action is used.
npm run tauri build -- --debug --bundles app --config '{"bundle":{"resources":[]}}'

open_app() {
    /usr/bin/open -n "${APP_BUNDLE}"
}

case "${MODE}" in
    run)
        open_app
        ;;
    --debug|debug)
        lldb -- "${APP_BINARY}"
        ;;
    --logs|logs)
        open_app
        /usr/bin/log stream --info --style compact --predicate "process == \"${PROCESS_NAME}\""
        ;;
    --telemetry|telemetry)
        open_app
        /usr/bin/log stream --info --style compact --predicate "subsystem == \"${BUNDLE_ID}\""
        ;;
    --verify|verify)
        open_app
        sleep 5
        pgrep -x "${PROCESS_NAME}" >/dev/null
        ;;
    *)
        echo "usage: $0 [run|--debug|--logs|--telemetry|--verify]" >&2
        exit 2
        ;;
esac
