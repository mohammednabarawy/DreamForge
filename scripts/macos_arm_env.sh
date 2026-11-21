#!/usr/bin/env bash
# macOS Apple Silicon (arm64) runtime guard for DreamForge.
# Sourced by DreamForge.command, dreamforge.sh, and setup.sh on Darwin.
# Handles two common macOS ARM pitfalls cleanly:
#   1. Launching from an x86_64/Rosetta login shell (e.g. Intel fish/zsh), where
#      `uname -m` reports x86_64 and universal binaries (node, python, /usr/bin/cc)
#      default to their x86_64 slice.
#   2. `/usr/bin/cc` / `xcrun` failing under Rosetta with `unable to load libxcrun`
#      on newer macOS Command Line Tools that ship arm64-only libraries.

dreamforge_is_apple_silicon() {
    [ "$(uname -s)" = "Darwin" ] || return 1
    [ "$(uname -m)" = "arm64" ] && return 0
    [ "$(/usr/sbin/sysctl -n hw.optional.arm64 2>/dev/null || echo 0)" = "1" ]
}

dreamforge_setup_macos_arm_env() {
    [ "$(uname -s)" = "Darwin" ] || return 0

    export OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES
    export PYTORCH_ENABLE_MPS_FALLBACK="${PYTORCH_ENABLE_MPS_FALLBACK:-1}"

    if ! dreamforge_is_apple_silicon; then
        return 0
    fi

    export DREAMFORGE_MAC_ARM64=1

    # Prefer Homebrew (arm64) and Rustup cargo in PATH.
    if [ -d "/opt/homebrew/bin" ] && [[ ":${PATH}:" != *":/opt/homebrew/bin:"* ]]; then
        export PATH="/opt/homebrew/bin:${PATH}"
    fi
    if [ -x "${HOME}/.cargo/bin/cargo" ] && [[ ":${PATH}:" != *":${HOME}/.cargo/bin:"* ]]; then
        export PATH="${HOME}/.cargo/bin:${PATH}"
    fi

    # Point C/ObjC compilers and Cargo linker directly at the active Xcode/CLT
    # native arm64 toolchain so builds never trip over /usr/bin/cc's Rosetta xcrun stub.
    local dev_dir="" clt_bin="" sdk_path=""
    dev_dir="$(xcode-select -p 2>/dev/null || true)"
    if [ -z "${dev_dir}" ] && [ -d "/Library/Developer/CommandLineTools" ]; then
        dev_dir="/Library/Developer/CommandLineTools"
    fi
    if [ -n "${dev_dir}" ]; then
        if [ -x "${dev_dir}/Toolchains/XcodeDefault.xctoolchain/usr/bin/clang" ]; then
            clt_bin="${dev_dir}/Toolchains/XcodeDefault.xctoolchain/usr/bin"
        elif [ -x "${dev_dir}/usr/bin/clang" ]; then
            clt_bin="${dev_dir}/usr/bin"
        fi
        if [ -z "${SDKROOT:-}" ]; then
            for candidate_sdk in \
                "${dev_dir}/SDKs/MacOSX.sdk" \
                "${dev_dir}/Platforms/MacOSX.platform/Developer/SDKs/MacOSX.sdk"; do
                if [ -d "${candidate_sdk}" ]; then
                    sdk_path="${candidate_sdk}"
                    break
                fi
            done
            if [ -n "${sdk_path}" ]; then
                export SDKROOT="${sdk_path}"
            fi
        fi
    fi

    if [ -n "${clt_bin}" ]; then
        if [[ ":${PATH}:" != *":${clt_bin}:"* ]]; then
            export PATH="${clt_bin}:${PATH}"
        fi
        export CC="${CC:-${clt_bin}/clang}"
        export CXX="${CXX:-${clt_bin}/clang++}"
        export HOST_CC="${HOST_CC:-${clt_bin}/clang}"
        export HOST_CXX="${HOST_CXX:-${clt_bin}/clang++}"
        export CC_aarch64_apple_darwin="${CC_aarch64_apple_darwin:-${clt_bin}/clang}"
        export CXX_aarch64_apple_darwin="${CXX_aarch64_apple_darwin:-${clt_bin}/clang++}"
        export CARGO_TARGET_AARCH64_APPLE_DARWIN_LINKER="${CARGO_TARGET_AARCH64_APPLE_DARWIN_LINKER:-${clt_bin}/clang}"
        if [ -x "${clt_bin}/ar" ]; then
            export AR="${AR:-${clt_bin}/ar}"
        fi
        if [ -x "${clt_bin}/ranlib" ]; then
            export RANLIB="${RANLIB:-${clt_bin}/ranlib}"
        fi
    fi

    # Detect whether the shell (or a universal binary launched by it) is running under Rosetta.
    local proc_translated
    proc_translated="$(/usr/sbin/sysctl -n sysctl.proc_translated 2>/dev/null || echo 0)"
    if [ "${proc_translated}" = "1" ] || [ "$(uname -m)" != "arm64" ]; then
        export DREAMFORGE_FORCE_ARM64=1
    fi

    # Ensure Node.js executes natively as arm64 (required by @tauri-apps/cli-darwin-arm64 & Rollup).
    if command -v node >/dev/null 2>&1; then
        if [ "$(node -p 'process.arch' 2>/dev/null || true)" = "x64" ]; then
            # 1) First check for a native arm64 Node installation (nvm / Homebrew).
            local node_bin
            for node_bin in /opt/homebrew/bin/node "${HOME}/.nvm/versions/node"/*/bin/node; do
                [ -x "${node_bin}" ] || continue
                if [ "$("${node_bin}" -p 'process.arch' 2>/dev/null || true)" = "arm64" ]; then
                    export PATH="$(dirname "${node_bin}"):${PATH}"
                    break
                fi
            done
        fi

        # 2) If Node is a universal binary running as x64 under a Rosetta shell,
        #    place a tiny arm64 wrapper first in PATH so `node`, `npm`, `vite`, and `tauri`
        #    all execute the native arm64 slice.
        if [ "$(node -p 'process.arch' 2>/dev/null || true)" = "x64" ]; then
            local real_node
            real_node="$(command -v node)"
            if [ "$(/usr/bin/arch -arm64 "${real_node}" -p 'process.arch' 2>/dev/null || true)" = "arm64" ]; then
                local shim_dir="${TMPDIR:-/tmp}/dreamforge-arm64-shims-$(id -u)"
                mkdir -p "${shim_dir}"
                cat > "${shim_dir}/node" <<EOF
#!/bin/sh
exec /usr/bin/arch -arm64 "${real_node}" "\$@"
EOF
                chmod +x "${shim_dir}/node"
                export PATH="${shim_dir}:${PATH}"
                export DREAMFORGE_FORCE_ARM64=1
            fi
        fi
    fi
}

dreamforge_run_python() {
    local py_bin="$1"
    shift
    if [ "${DREAMFORGE_FORCE_ARM64:-0}" = "1" ] && [ -x "/usr/bin/arch" ]; then
        /usr/bin/arch -arm64 "${py_bin}" "$@"
    else
        "${py_bin}" "$@"
    fi
}
