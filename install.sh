#!/usr/bin/env bash

# KeyRGB modular installer (dispatcher)
#
# Default: user install (AppImage + udev + desktop entry)
# Dev:     pass --dev for editable pip install + build deps
#
# This file is designed to work both:
# - from a repo checkout (uses ./scripts/*.sh)
# - via curl-pipe installs (bootstraps scripts from GitHub raw)

set -euo pipefail

KEYRGB_REPO_OWNER="${KEYRGB_REPO_OWNER:-Rainexn0b}"
KEYRGB_REPO_NAME="${KEYRGB_REPO_NAME:-keyRGB}"
KEYRGB_BOOTSTRAP_REF="${KEYRGB_BOOTSTRAP_REF:-main}"

usage() {
    cat <<'EOF'
Usage:
    install.sh [--dev] [--ref <git-ref>] [--help] [...module args]

Modes:
    (default)  User install: AppImage + udev + desktop integration
    --dev      Dev install: build deps + pip editable install

Bootstrap (curl installs):
    --ref <git-ref>    Git ref for downloading scripts/ from GitHub raw (default: main)
    KEYRGB_BOOTSTRAP_REF can also be used.

Examples:
    curl -fsSL https://raw.githubusercontent.com/Rainexn0b/keyRGB/main/install.sh | bash
    ./install.sh --dev
EOF
}

MODE="user"
REF_OVERRIDE=""

# Legacy parity: when run interactively with no args, offer a mode selection.
# This keeps the dispatcher small and forwards to the modular scripts.
if [ "$#" -eq 0 ] && [ -t 0 ]; then
    case "${KEYRGB_INSTALL_MODE:-}" in
        appimage|APPIMAGE)
            MODE="user"
            ;;
        clone|CLONE)
            MODE="dev"
            NEW_ARGS=("--clone")
            exec bash "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/scripts/install_dev.sh" "${NEW_ARGS[@]}"
            ;;
        pip|PIP)
            MODE="dev"
            exec bash "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/scripts/install_dev.sh"
            ;;
        "")
            echo "Choose install mode:"
            echo "  1) AppImage (recommended)"
            echo "  2) Source code (clone repo + editable install)"
            echo "  3) Repo editable install (use current folder)"
            read -r -p "Select [1-3] (default: 1): " reply || reply=""
            reply="${reply:-1}"
            case "$reply" in
                2)
                    MODE="dev"
                    NEW_ARGS=("--clone")
                    exec bash "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/scripts/install_dev.sh" "${NEW_ARGS[@]}"
                    ;;
                3)
                    MODE="dev"
                    exec bash "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/scripts/install_dev.sh"
                    ;;
                *)
                    MODE="user"
                    ;;
            esac
            ;;
    esac
fi

args=("$@")
i=0
while [ $i -lt ${#args[@]} ]; do
    case "${args[$i]}" in
        --dev)
            MODE="dev"
            unset 'args[$i]'
            ;;
        --ref)
            j=$((i+1))
            REF_OVERRIDE="${args[$j]:-}"
            unset 'args[$i]'
            unset 'args[$j]'
            i=$((i+1))
            ;;
        -h|--help)
            usage
            exit 0
            ;;
    esac
    i=$((i+1))
done

if [ -n "$REF_OVERRIDE" ]; then
    KEYRGB_BOOTSTRAP_REF="$REF_OVERRIDE"
fi

# Re-pack args with removed items.
NEW_ARGS=()
for a in "${args[@]}"; do
    if [ -n "${a:-}" ]; then
        NEW_ARGS+=("$a")
    fi
done

SCRIPT_SELF="${BASH_SOURCE[0]:-}"
SCRIPT_DIR=""
if [ -n "$SCRIPT_SELF" ] && [ -f "$SCRIPT_SELF" ]; then
    SCRIPT_DIR="$(cd "$(dirname "$SCRIPT_SELF")" && pwd)"
fi

run_local() {
    local target="$1"; shift
    exec bash "$target" "$@"
}

bootstrap_and_run() {
    local target_rel="$1"; shift

    command -v curl >/dev/null 2>&1 || {
        echo "❌ curl is required for curl-pipe installs" >&2
        exit 1
    }

    local tmp
    tmp="$(mktemp -d)"
    trap 'rm -rf "$tmp"' EXIT

    mkdir -p "$tmp/scripts"
    mkdir -p "$tmp/scripts/lib"

    local base="https://raw.githubusercontent.com/${KEYRGB_REPO_OWNER}/${KEYRGB_REPO_NAME}/${KEYRGB_BOOTSTRAP_REF}"
    curl -fsSL "$base/scripts/common.sh" -o "$tmp/scripts/common.sh"
    curl -fsSL "$base/scripts/lib/common_core.sh" -o "$tmp/scripts/lib/common_core.sh"
    curl -fsSL "$base/scripts/lib/state.sh" -o "$tmp/scripts/lib/state.sh"
    curl -fsSL "$base/scripts/lib/optional_components.sh" -o "$tmp/scripts/lib/optional_components.sh"
    curl -fsSL "$base/scripts/lib/privileged_helpers.sh" -o "$tmp/scripts/lib/privileged_helpers.sh"
    curl -fsSL "$base/scripts/lib/user_integration.sh" -o "$tmp/scripts/lib/user_integration.sh"
    curl -fsSL "$base/scripts/lib/user_prompts.sh" -o "$tmp/scripts/lib/user_prompts.sh"
    curl -fsSL "$base/scripts/install_user.sh" -o "$tmp/scripts/install_user.sh"
    curl -fsSL "$base/scripts/install_dev.sh" -o "$tmp/scripts/install_dev.sh"
    curl -fsSL "$base/scripts/uninstall.sh" -o "$tmp/scripts/uninstall.sh"

    exec bash "$tmp/$target_rel" "$@"
}

if [ -n "$SCRIPT_DIR" ] && [ -f "$SCRIPT_DIR/scripts/common.sh" ]; then
    if [ "$MODE" = "dev" ]; then
        run_local "$SCRIPT_DIR/scripts/install_dev.sh" "${NEW_ARGS[@]}"
    else
        run_local "$SCRIPT_DIR/scripts/install_user.sh" "${NEW_ARGS[@]}"
    fi
else
    if [ "$MODE" = "dev" ]; then
        bootstrap_and_run "scripts/install_dev.sh" "${NEW_ARGS[@]}"
    else
        bootstrap_and_run "scripts/install_user.sh" "${NEW_ARGS[@]}"
    fi
fi

exit 0

# Legacy monolithic installer has been moved to scripts/install.legacy.sh
