#!/bin/bash
# KeyRGB Installation Script

set -e

PKG_MGR=""  # dnf|apt|pacman|zypper|apk
APT_UPDATED=0

detect_pkg_manager() {
    if command -v dnf >/dev/null 2>&1; then
        PKG_MGR="dnf"
        return 0
    fi
    if command -v apt-get >/dev/null 2>&1; then
        PKG_MGR="apt"
        return 0
    fi
    if command -v pacman >/dev/null 2>&1; then
        PKG_MGR="pacman"
        return 0
    fi
    if command -v zypper >/dev/null 2>&1; then
        PKG_MGR="zypper"
        return 0
    fi
    if command -v apk >/dev/null 2>&1; then
        PKG_MGR="apk"
        return 0
    fi
    PKG_MGR=""
    return 1
}

pkg_install_best_effort() {
    # Best-effort: do not fail the overall install if system package install fails.
    local pkgs=("$@");
    if [ ${#pkgs[@]} -eq 0 ]; then
        return 0
    fi

    local had_errexit=0
    case "$-" in
        *e*) had_errexit=1 ;;
    esac

    detect_pkg_manager || true
    if [ -z "${PKG_MGR:-}" ]; then
        echo "⚠️  No supported package manager found; skipping system package installation."
        return 0
    fi

    set +e
    case "$PKG_MGR" in
        dnf)
            sudo dnf install -y "${pkgs[@]}" ;;
        apt)
            if [ "${APT_UPDATED:-0}" -ne 1 ]; then
                sudo apt-get update >/dev/null 2>&1 || true
                APT_UPDATED=1
            fi
            sudo apt-get install -y "${pkgs[@]}" ;;
        pacman)
            # Avoid full system upgrades; install only what we need.
            sudo pacman -S --noconfirm --needed "${pkgs[@]}" ;;
        zypper)
            sudo zypper --non-interactive install --no-recommends "${pkgs[@]}" ;;
        apk)
            sudo apk add "${pkgs[@]}" ;;
        *)
            echo "⚠️  Unsupported package manager '$PKG_MGR'; skipping system package installation." ;;
    esac
    rc=$?

    if [ "$had_errexit" -eq 1 ]; then
        set -e
    else
        set +e
    fi

    return $rc
}

usage() {
        cat <<'EOF'
Usage:
    ./install.sh [--appimage] [--clone] [--clone-dir <path>] [--pip] [--version <tag>] [--asset <name>] [--prerelease] [--no-system-deps]

Modes:
    --appimage  Install by downloading the AppImage. (default)
    --pip       Install from this repo via pip (-e). (dev / editable install)
    --clone     Clone the repo (source code) then install via pip (-e).
               Use this if you want to modify the code for your machine.

What gets installed (both modes):
    - System dependencies (best-effort via your package manager when available)
    - Desktop launcher: ~/.local/share/applications/keyrgb.desktop
    - Autostart entry:  ~/.config/autostart/keyrgb.desktop
    - Icon:            ~/.local/share/icons/hicolor/256x256/apps/keyrgb.png
    - udev rule:       /etc/udev/rules.d/99-ite8291-wootbook.rules (requires sudo)

Mode details:
    --appimage
        - Downloads a single AppImage to: ~/.local/bin/keyrgb
        - Does NOT install Python packages via pip
    --clone
        - Clones the KeyRGB repo into a user directory
        - Installs packages into your user site-packages (pip --user -e)
        - Intended for development / local modifications
    --pip
        - Installs Python packages into your user site-packages (pip --user)
        - Intended for development / editable installs

AppImage options:
    --version <tag>  Git tag to download from (e.g. v0.7.9). If omitted, auto-detects the newest stable release containing the AppImage.
    --asset <name>   AppImage asset filename (default: keyrgb-x86_64.AppImage).
    --prerelease     Allow installing from a prerelease if it is the newest matching release.

Env vars:
    KEYRGB_INSTALL_MODE=appimage|clone|pip  Non-interactive mode selection (default: appimage).
    KEYRGB_CLONE_DIR=<path>  Target directory for --clone (default: ~/.local/share/keyrgb-src).
    KEYRGB_INSTALL_POWER_HELPER=y|n  Select the lightweight Power Mode helper.
    KEYRGB_INSTALL_TUXEDO=y|n  Select optional TCC integration.
    KEYRGB_INSTALL_TCC_APP=y|n  If TCC integration is selected, optionally install Tuxedo Control Center via your package manager (best-effort).
    KEYRGB_INSTALL_INPUT_UDEV=y|n  Install udev rule for Reactive Typing to read keypress events via /dev/input (uaccess; security-sensitive; default: n).
    Note: Power Mode helper and TCC integration are mutually exclusive; if both are set truthy, Power Mode is preferred.
    KEYRGB_ALLOW_PRERELEASE=y|n  Allow installing from prereleases (default: n).
    KEYRGB_SKIP_SYSTEM_DEPS=y|n  Skip best-effort system dependency installation (default: n).
EOF
}

MODE=""
KEYRGB_INSTALL_MODE="${KEYRGB_INSTALL_MODE:-}"
KEYRGB_CLONE_DIR="${KEYRGB_CLONE_DIR:-$HOME/.local/share/keyrgb-src}"
KEYRGB_VERSION="${KEYRGB_VERSION:-}"
KEYRGB_APPIMAGE_ASSET="${KEYRGB_APPIMAGE_ASSET:-keyrgb-x86_64.AppImage}"
KEYRGB_ALLOW_PRERELEASE="${KEYRGB_ALLOW_PRERELEASE:-n}"
KEYRGB_INSTALL_TCC_APP="${KEYRGB_INSTALL_TCC_APP:-}"
KEYRGB_INSTALL_INPUT_UDEV="${KEYRGB_INSTALL_INPUT_UDEV:-}"
KEYRGB_SKIP_SYSTEM_DEPS="${KEYRGB_SKIP_SYSTEM_DEPS:-n}"

STATE_DIR="$HOME/.local/share/keyrgb"
TCC_MARKER="$STATE_DIR/tcc-installed-by-keyrgb"
KERNEL_DRIVERS_MARKER="$STATE_DIR/kernel-drivers-installed-by-keyrgb"

while [ "$#" -gt 0 ]; do
        case "$1" in
                --pip|--repo)
                        MODE="pip"
                        shift
                        ;;
                --clone|--source)
                    MODE="clone"
                    shift
                    ;;
                --clone-dir)
                    KEYRGB_CLONE_DIR="${2:-}"
                    shift 2
                    ;;
                --appimage)
                        MODE="appimage"
                        shift
                        ;;
                --version)
                        KEYRGB_VERSION="${2:-}"
                        shift 2
                        ;;
                --asset)
                        KEYRGB_APPIMAGE_ASSET="${2:-}"
                        shift 2
                        ;;
                --prerelease)
                    KEYRGB_ALLOW_PRERELEASE="y"
                    shift
                    ;;
                --no-system-deps)
                    KEYRGB_SKIP_SYSTEM_DEPS="y"
                    shift
                    ;;
                -h|--help)
                        usage
                        exit 0
                        ;;
                *)
                        echo "Unknown argument: $1" >&2
                        usage
                        exit 2
                        ;;
        esac
done

# Always run relative to the repo root (where this script lives), even if invoked
# from another working directory.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$SCRIPT_DIR"
cd "$REPO_DIR"

echo "=== KeyRGB Installation ==="
echo

select_install_mode() {
    if [ -n "$MODE" ]; then
        return 0
    fi

    # Allow non-interactive selection via env var.
    if [ -n "$KEYRGB_INSTALL_MODE" ]; then
        case "${KEYRGB_INSTALL_MODE,,}" in
            appimage|pip|clone) MODE="${KEYRGB_INSTALL_MODE,,}"; return 0 ;;
        esac
    fi

    # Interactive prompt when possible.
    if [ -t 0 ]; then
        echo "Choose install mode:"
        echo "  1) AppImage (recommended)"
        echo "  2) Source code (clone repo + editable install)"
        echo "  3) Repo editable install (use current folder)"
        local reply
        read -r -p "Select [1-3] (default: 1): " reply || reply=""
        reply="${reply:-1}"
        case "$reply" in
            2) MODE="clone" ;;
            3) MODE="pip" ;;
            *) MODE="appimage" ;;
        esac
        return 0
    fi

    # Default for non-interactive runs.
    MODE="appimage"
}

select_install_mode

echo "Install mode: $MODE"

if [ "$MODE" = "appimage" ]; then
    echo "AppImage install target: $HOME/.local/bin/keyrgb"
elif [ "$MODE" = "clone" ]; then
    echo "Clone target: $KEYRGB_CLONE_DIR"
    echo "Pip install target: user site-packages (pip --user)"
else
    echo "Pip install target: user site-packages (pip --user)"
fi

# AppImage installs can auto-resolve the newest release that contains the AppImage asset.
# For interactive debugging, allow opting into prereleases.
if [ "$MODE" = "appimage" ] && [ -z "${KEYRGB_VERSION:-}" ] && [ -t 0 ]; then
    # Only prompt if the user didn't already choose via flag/env.
    if [ "${KEYRGB_ALLOW_PRERELEASE:-}" = "" ] || [ "${KEYRGB_ALLOW_PRERELEASE,,}" = "n" ] || [ "${KEYRGB_ALLOW_PRERELEASE,,}" = "no" ] || [ "${KEYRGB_ALLOW_PRERELEASE,,}" = "0" ] || [ "${KEYRGB_ALLOW_PRERELEASE,,}" = "false" ]; then
        echo
        echo "Choose AppImage release channel:"
        echo "  1) Latest stable release (recommended)"
        echo "  2) Latest including prereleases (debugging)"
        read -r -p "Select [1-2] (default: 1): " _relchan || _relchan=""
        _relchan="${_relchan:-1}"
        case "$_relchan" in
            2) KEYRGB_ALLOW_PRERELEASE="y" ;;
            *) KEYRGB_ALLOW_PRERELEASE="n" ;;
        esac
    fi
fi

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    echo "❌ Please run without sudo (script will ask for password when needed)"
    exit 1
fi

INSTALL_TUXEDO="n"
INSTALL_TCC_APP="n"
INSTALL_POWER_HELPER="y"
INSTALL_KERNEL_DRIVERS="n"

ask_yes_no() {
    local prompt="$1"
    local default="$2"  # y|n
    local envvar_name="${3:-}"

    # Allow CI/non-interactive override via a specific env var.
    if [ -n "$envvar_name" ]; then
        local envval="${!envvar_name:-}"
        if [ -n "$envval" ]; then
            case "${envval,,}" in
                y|yes|1|true) echo "y"; return 0 ;;
                n|no|0|false) echo "n"; return 0 ;;
            esac
        fi
    fi

    # Non-interactive: pick the default.
    if ! [ -t 0 ]; then
        echo "$default"
        return 0
    fi

    local suffix="[y/N]"
    if [ "$default" = "y" ]; then
        suffix="[Y/n]"
    fi

    local reply
    read -r -p "$prompt $suffix " reply || reply=""
    reply="${reply,,}"
    if [ -z "$reply" ]; then
        echo "$default"
        return 0
    fi

    case "$reply" in
        y|yes) echo "y" ;;
        n|no) echo "n" ;;
        *) echo "$default" ;;
    esac
}

echo
echo "Optional components:"
echo "Choose ONE power integration (to avoid collisions):"
echo "  1) Lightweight Power Mode toggle (recommended)"
echo "     - Adds 'Extreme Saver/Balanced/Performance' tray menu"
echo "     - Installs a helper + polkit rule for passwordless switching"
echo "  2) Tuxedo Control Center (TCC) integration (advanced)"
echo "     - Enables the existing 'Power Profiles (TCC)' UI if TCC is installed"

# Non-interactive env var handling (exclusive):
# - If both are set to y, prefer Power Mode to avoid collisions.
if [ "${KEYRGB_INSTALL_POWER_HELPER:-}" != "" ] || [ "${KEYRGB_INSTALL_TUXEDO:-}" != "" ]; then
    ph="$(ask_yes_no "" "y" "KEYRGB_INSTALL_POWER_HELPER")"
    tc="$(ask_yes_no "" "n" "KEYRGB_INSTALL_TUXEDO")"
    if [ "$ph" = "y" ]; then
        INSTALL_POWER_HELPER="y"
        INSTALL_TUXEDO="n"
    elif [ "$tc" = "y" ]; then
        INSTALL_POWER_HELPER="n"
        INSTALL_TUXEDO="y"
    else
        INSTALL_POWER_HELPER="n"
        INSTALL_TUXEDO="n"
    fi
else
    if [ -t 0 ]; then
        read -r -p "Select [1-2] (default: 1): " power_choice || power_choice=""
        power_choice="${power_choice:-1}"
    else
        power_choice="1"
    fi

    case "$power_choice" in
        2)
            INSTALL_POWER_HELPER="n"
            INSTALL_TUXEDO="y"
            ;;
        *)
            INSTALL_POWER_HELPER="y"
            INSTALL_TUXEDO="n"
            ;;
    esac
fi

# Optional: if TCC integration is selected, offer to install the TCC application via dnf.
# This is best-effort because the package may not be available in the user's configured repos.
if [ "$INSTALL_TUXEDO" = "y" ]; then
    if [ "${KEYRGB_INSTALL_TCC_APP:-}" != "" ]; then
        if [ "${KEYRGB_INSTALL_TCC_APP,,}" = "y" ] || [ "${KEYRGB_INSTALL_TCC_APP,,}" = "yes" ] || [ "${KEYRGB_INSTALL_TCC_APP,,}" = "1" ] || [ "${KEYRGB_INSTALL_TCC_APP,,}" = "true" ]; then
            INSTALL_TCC_APP="y"
        else
            INSTALL_TCC_APP="n"
        fi
    elif [ -t 0 ]; then
        echo
        echo "TCC integration was selected."
        ans="$(ask_yes_no "Install Tuxedo Control Center app (best-effort, may not be available in your repos)?" "n")"
        if [ "$ans" = "y" ]; then
            INSTALL_TCC_APP="y"
        fi
    fi
fi

if [ "$INSTALL_POWER_HELPER" = "y" ]; then
    echo "✓ Power Mode helper will be installed"
else
    echo "✓ Skipping Power Mode helper"
fi
if [ "$INSTALL_TUXEDO" = "y" ]; then
    echo "✓ TCC integration deps will be installed (best-effort)"
else
    echo "✓ Skipping TCC integration deps"
fi

if [ "$INSTALL_TCC_APP" = "y" ]; then
    echo "✓ Tuxedo Control Center will be installed (best-effort)"
fi

# Optional: Kernel drivers for better hardware support
if [ "${KEYRGB_INSTALL_KERNEL_DRIVERS:-}" != "" ]; then
    KEYRGB_INSTALL_KERNEL_DRIVERS="$(ask_yes_no "" "n" "KEYRGB_INSTALL_KERNEL_DRIVERS")"
elif [ -t 0 ]; then
    echo
    echo "Kernel Drivers (Advanced):"
    echo "KeyRGB works best with kernel-level drivers for Clevo/Tuxedo laptops."
    echo "These provide safer and more reliable keyboard control than the USB fallback."
    KEYRGB_INSTALL_KERNEL_DRIVERS="$(ask_yes_no "Install/Update kernel drivers (tuxedo-drivers, clevo-xsm-wmi) if available?" "n")"
else
    KEYRGB_INSTALL_KERNEL_DRIVERS="n"
fi

if [ "${KEYRGB_INSTALL_KERNEL_DRIVERS,,}" = "y" ]; then
    INSTALL_KERNEL_DRIVERS="y"
    echo "✓ Kernel drivers will be installed (best-effort)"
else
    echo "✓ Skipping kernel drivers"
fi

# Optional permissions: reactive typing keypress capture.
if [ "${KEYRGB_INSTALL_INPUT_UDEV:-}" != "" ]; then
    # Normalize env var to y/n for consistent behavior.
    KEYRGB_INSTALL_INPUT_UDEV="$(ask_yes_no "" "n" "KEYRGB_INSTALL_INPUT_UDEV")"
elif [ -t 0 ]; then
    echo
    echo "Optional permissions:"
    echo "Reactive Typing effects (Fade/Ripple) can react to real keypress events."
    echo "This requires read access to /dev/input/event* (security-sensitive)."
    echo "KeyRGB can install a seat-based uaccess udev rule so only the active local user gets access."
    KEYRGB_INSTALL_INPUT_UDEV="$(ask_yes_no "Enable Reactive Typing keypress detection (install uaccess rule for keyboard input devices)?" "n")"
else
    # Non-interactive default: do not install the rule.
    KEYRGB_INSTALL_INPUT_UDEV="n"
fi

if [ "${KEYRGB_INSTALL_INPUT_UDEV,,}" = "y" ]; then
    echo "✓ Reactive Typing keypress detection will be enabled (uaccess rule)"
else
    echo "✓ Reactive Typing keypress detection will be disabled (synthetic fallback)"
fi

install_system_deps_best_effort() {
    echo
    echo "🔧 Installing system dependencies (best-effort)..."
    echo "   (This may prompt for your sudo password.)"

    detect_pkg_manager || true

    # Minimal common deps.
    local pkgs=()
    case "${PKG_MGR:-}" in
        dnf)
            pkgs+=(python3 python3-tkinter usbutils dbus-tools libappindicator-gtk3 python3-gobject gtk3)
            ;;
        apt)
            pkgs+=(python3 python3-tk usbutils dbus)
            # Tray deps vary by distro/desktop; try common packages when present.
            pkgs+=(python3-gi gir1.2-appindicator3-0.1)
            ;;
        pacman)
            pkgs+=(python tk usbutils dbus)
            pkgs+=(libappindicator-gtk3 python-gobject gtk3)
            ;;
        zypper)
            pkgs+=(python3 python3-tk usbutils dbus-1 dbus-1-tools)
            pkgs+=(python3-gobject gtk3 typelib-1_0-AppIndicator3-0_1)
            ;;
        apk)
            pkgs+=(python3 py3-tkinter usbutils dbus)
            ;;
        *)
            pkgs+=(python3 usbutils)
            ;;
    esac

    # Only needed for source installs.
    if [ "$MODE" = "pip" ] || [ "$MODE" = "clone" ]; then
        case "${PKG_MGR:-}" in
            pacman) pkgs+=(git python-pip) ;;
            *) pkgs+=(git python3-pip) ;;
        esac
    fi

    pkg_install_best_effort "${pkgs[@]}" || true

    if [ "$INSTALL_TUXEDO" = "y" ] || [ "$INSTALL_POWER_HELPER" = "y" ]; then
        pkg_install_best_effort polkit || true
    fi

    if [ "$INSTALL_TCC_APP" = "y" ]; then
        echo
        echo "🧩 Installing Tuxedo Control Center (best-effort)..."
        mkdir -p "$STATE_DIR" || true

        set +e
        pkg_install_best_effort tuxedo-control-center
        rc=$?
        set -e

        if [ $rc -eq 0 ]; then
            echo "✓ Installed tuxedo-control-center"
            printf '%s\n' "tuxedo-control-center" > "$TCC_MARKER" 2>/dev/null || true
        else
            echo "⚠️  Failed to install tuxedo-control-center (best-effort)."
            echo "   This package may not be available in your enabled repos."
            echo "   You can install TCC separately, then KeyRGB will enable the TCC integration UI."
        fi
    fi

    echo "✓ System dependencies installed (best-effort)"
    echo "  Note: KDE Plasma typically shows tray icons out of the box."
    echo "        GNOME may require an AppIndicator extension/package to show tray icons."
}

# Best-effort system dependency installation.
if [ "${KEYRGB_SKIP_SYSTEM_DEPS,,}" = "y" ] || [ "${KEYRGB_SKIP_SYSTEM_DEPS,,}" = "yes" ] || [ "${KEYRGB_SKIP_SYSTEM_DEPS,,}" = "1" ] || [ "${KEYRGB_SKIP_SYSTEM_DEPS,,}" = "true" ]; then
    echo "ℹ️  Skipping system dependency installation (KEYRGB_SKIP_SYSTEM_DEPS / --no-system-deps)."
else
    if detect_pkg_manager; then
        install_system_deps_best_effort
    else
        echo "⚠️  No supported package manager found; skipping system package installation."
        echo "   You may need: python3, pip, tkinter, usbutils, dbus, and tray deps for pystray."
    fi
fi

# Clone mode: fetch source into a user directory, then continue as pip mode.
maybe_clone_source_repo() {
    if [ "$MODE" != "clone" ]; then
        return 0
    fi

    if ! command -v git &> /dev/null; then
        echo "❌ git is required for --clone mode but not installed"
        exit 1
    fi
    if ! command -v python3 &> /dev/null; then
        echo "❌ Python 3 is required for --clone mode but not installed"
        exit 1
    fi

    local clone_dir="$KEYRGB_CLONE_DIR"
    if [ -z "$clone_dir" ]; then
        echo "❌ --clone-dir (or KEYRGB_CLONE_DIR) is empty" >&2
        exit 2
    fi

    echo
    echo "📥 Source install: cloning KeyRGB into: $clone_dir"

    if [ -d "$clone_dir/.git" ]; then
        echo "✓ Using existing clone (won't auto-update): $clone_dir"
    else
        mkdir -p "$(dirname "$clone_dir")"
        git clone --depth 1 https://github.com/Rainexn0b/keyRGB.git "$clone_dir"
        echo "✓ Cloned repo"
    fi

    REPO_DIR="$clone_dir"
    cd "$REPO_DIR"

    # Optional: checkout a specific tag/branch if requested.
    if [ -n "$KEYRGB_VERSION" ]; then
        echo "↪ Checking out: $KEYRGB_VERSION"
        git fetch --tags --force >/dev/null 2>&1 || true
        if ! git checkout "$KEYRGB_VERSION" >/dev/null 2>&1; then
            echo "⚠️  Could not checkout '$KEYRGB_VERSION'; continuing with current branch" >&2
        fi
    fi

    MODE="pip"
}

maybe_clone_source_repo

if [ "$MODE" = "pip" ]; then
    # Repo/pip install requires Python.
    if ! command -v python3 &> /dev/null; then
        echo "❌ Python 3 is required but not installed"
        exit 1
    fi
    echo "✓ Python 3 found: $(python3 --version)"
else
    # AppImage install can use curl/wget (preferred) or python3 as a fallback.
    if command -v curl &> /dev/null; then
        echo "✓ Downloader found: curl"
    elif command -v wget &> /dev/null; then
        echo "✓ Downloader found: wget"
    elif command -v python3 &> /dev/null; then
        echo "✓ Downloader found: python3 ($(python3 --version))"
    else
        echo "❌ Need one of: curl, wget, or python3 (to download the AppImage)" >&2
        exit 1
    fi
fi

# Check for git (needed to fetch upstream ite8291r3-ctl)
if [ "$MODE" = "pip" ]; then
    if ! command -v git &> /dev/null; then
        echo "❌ git is required but not installed"
        exit 1
    fi
fi

if [ "$MODE" = "pip" ]; then
    # Ensure pip is usable
    if ! python3 -m pip --version &> /dev/null; then
        echo "❌ python3-pip is required but pip is not available"
        exit 1
    fi

    echo
    echo "📦 Updating Python packaging tools..."
    python3 -m pip install --user -U pip setuptools wheel
    echo "✓ pip/setuptools/wheel updated"
fi

# Check for USB device (common supported ITE 8291r3 IDs)
if command -v lsusb &> /dev/null; then
    if ! lsusb | grep -Eqi "048d:(6004|6006|6008|600b|ce00)"; then
        echo "⚠️  Warning: supported ITE 8291r3 USB device not detected"
        echo "   Expected one of: 048d:6004, 048d:6006, 048d:6008, 048d:600b, 048d:ce00"
        echo "   Please make sure your keyboard is connected"
    fi
else
    echo "⚠️  lsusb not found; skipping USB device detection check."
fi

download_url() {
    local url="$1"
    local dst="$2"

    if [ -z "$dst" ]; then
        echo "❌ download_url: destination path is empty" >&2
        return 2
    fi

    mkdir -p "$(dirname "$dst")"

    local parent
    parent="$(dirname "$dst")"
    if ! [ -d "$parent" ]; then
        echo "❌ Download destination folder does not exist: $parent" >&2
        return 2
    fi
    if ! [ -w "$parent" ]; then
        echo "❌ No write permission to: $parent" >&2
        echo "   Fix: ensure it's writable, or choose a different HOME." >&2
        return 2
    fi

    # Download to a temp file and move into place, to avoid leaving a partial dst.
    local tmp
    tmp="$(mktemp "${dst}.tmp.XXXXXX")" || return 2

    if command -v curl &> /dev/null; then
        if curl -L --fail --silent --show-error -o "$tmp" "$url"; then
            mv -f "$tmp" "$dst"
            return 0
        fi
        rc=$?
        echo "⚠️  curl failed (exit $rc) while downloading: $url" >&2
        if [ "$rc" -eq 23 ]; then
            echo "   curl write error (often: disk full or permission issue)." >&2
            echo "   Target: $dst" >&2
            echo "   Folder: $parent" >&2
            ls -ld "$parent" "$dst" 2>/dev/null || true
            df -h "$parent" 2>/dev/null || true
        fi
        rm -f "$tmp" 2>/dev/null || true
        # Fall through to try other downloaders.
    fi

    if command -v wget &> /dev/null; then
        if wget -q -O "$tmp" "$url"; then
            mv -f "$tmp" "$dst"
            return 0
        fi
        rc=$?
        echo "⚠️  wget failed (exit $rc) while downloading: $url" >&2
        rm -f "$tmp" 2>/dev/null || true
    fi

    if command -v python3 &> /dev/null; then
        python3 - "$url" "$tmp" <<'PY'
from __future__ import annotations

import shutil
import sys
import urllib.request
from pathlib import Path

url = sys.argv[1]
dst = Path(sys.argv[2])
dst.parent.mkdir(parents=True, exist_ok=True)

with urllib.request.urlopen(url) as resp, dst.open("wb") as f:
    shutil.copyfileobj(resp, f)
PY
        rc=$?
        if [ "$rc" -eq 0 ]; then
            mv -f "$tmp" "$dst"
            return 0
        fi
        echo "⚠️  python3 download failed (exit $rc) while downloading: $url" >&2
        rm -f "$tmp" 2>/dev/null || true
    fi

    rm -f "$tmp" 2>/dev/null || true
    echo "❌ No downloader available (need curl, wget, or python3)" >&2
    return 1
}

resolve_release_with_asset() {
    # Prints: <tag>|<browser_download_url>|<is_prerelease>
    # Returns non-zero if no matching release/asset was found.
    local asset_name="$1"
    local allow_prerelease="$2"

    python3 - "$asset_name" "$allow_prerelease" <<'PY'
from __future__ import annotations

import json
import sys
import urllib.request

asset_name = sys.argv[1]
allow_prerelease = (sys.argv[2] or "").strip().lower() in ("y", "yes", "1", "true")

req = urllib.request.Request(
    "https://api.github.com/repos/Rainexn0b/keyRGB/releases",
    headers={"Accept": "application/vnd.github+json", "User-Agent": "keyrgb-install"},
)

with urllib.request.urlopen(req, timeout=30) as resp:
    data = json.loads(resp.read().decode("utf-8"))

if not isinstance(data, list):
    raise SystemExit(1)

for rel in data:
    if not allow_prerelease and bool(rel.get("prerelease")):
        continue
    assets = rel.get("assets") or []
    for asset in assets:
        if asset.get("name") == asset_name:
            tag = rel.get("tag_name") or ""
            url = asset.get("browser_download_url") or ""
            prerelease = bool(rel.get("prerelease"))
            if tag and url:
                sys.stdout.write(f"{tag}|{url}|{'true' if prerelease else 'false'}")
                raise SystemExit(0)

raise SystemExit(2)
PY
}

install_appimage() {
    echo
    echo "📦 Installing KeyRGB AppImage..."

    local user_bin="$HOME/.local/bin"
    local app_dst="$user_bin/keyrgb"

    mkdir -p "$user_bin"

    local url=""
    if [ -n "$KEYRGB_VERSION" ]; then
        url="https://github.com/Rainexn0b/keyRGB/releases/download/$KEYRGB_VERSION/$KEYRGB_APPIMAGE_ASSET"
        echo "✓ Using release tag: $KEYRGB_VERSION"
    else
        local resolved=""
        resolved="$(resolve_release_with_asset "$KEYRGB_APPIMAGE_ASSET" "$KEYRGB_ALLOW_PRERELEASE")" || true
        if [ -n "$resolved" ]; then
            local resolved_tag=""
            local resolved_url=""
            local resolved_prerelease=""
            IFS='|' read -r resolved_tag resolved_url resolved_prerelease <<< "$resolved"

            # Align icon/udev downloads to the same tag when auto-resolving.
            KEYRGB_VERSION="$resolved_tag"
            url="$resolved_url"

            if [ "$resolved_prerelease" = "true" ]; then
                echo "✓ Using release tag: $KEYRGB_VERSION (pre-release)"
            else
                echo "✓ Using release tag: $KEYRGB_VERSION"
            fi
        else
            url="https://github.com/Rainexn0b/keyRGB/releases/latest/download/$KEYRGB_APPIMAGE_ASSET"
            echo "✓ Using GitHub latest release"
        fi
    fi

    echo "⬇️  Downloading: $url"
    download_url "$url" "$app_dst"
    chmod +x "$app_dst"
    echo "✓ Installed AppImage: $app_dst"
}

install_icon_and_desktop_entries() {
    local icon_dir="$HOME/.local/share/icons/hicolor/256x256/apps"
    local icon_file="$icon_dir/keyrgb.png"
    local app_dir="$HOME/.local/share/applications"
    local app_file="$app_dir/keyrgb.desktop"
    local autostart_dir="$HOME/.config/autostart"
    local autostart_file="$autostart_dir/keyrgb.desktop"
    local icon_ref="keyrgb"

    mkdir -p "$icon_dir" "$app_dir" "$autostart_dir"

    if [ "$MODE" = "pip" ]; then
        local icon_src="$REPO_DIR/assets/logo-keyrgb.png"
        if ! [ -f "$icon_src" ]; then
            echo "❌ Logo not found: $icon_src" >&2
            exit 1
        fi
        install -m 0644 "$icon_src" "$icon_file"
    else
        local raw_ref="main"
        if [ -n "$KEYRGB_VERSION" ]; then
            raw_ref="$KEYRGB_VERSION"
        fi
        local icon_url="https://raw.githubusercontent.com/Rainexn0b/keyRGB/$raw_ref/assets/logo-keyrgb.png"
        echo "⬇️  Downloading icon: $icon_url"
        download_url "$icon_url" "$icon_file"
    fi

    echo "✓ Installed icon: $icon_file"

    # Desktop environments frequently do not include ~/.local/bin in PATH
    # for .desktop Exec resolution. Use an absolute path.
    local keyrgb_exec
    keyrgb_exec="$(command -v keyrgb || true)"
    if [ -z "$keyrgb_exec" ]; then
        keyrgb_exec="$HOME/.local/bin/keyrgb"
    fi

    cat > "$app_file" << EOF
[Desktop Entry]
Type=Application
Name=KeyRGB
Comment=RGB Keyboard Controller
Exec=$keyrgb_exec
Icon=$icon_ref
Terminal=false
Categories=Utility;System;
StartupNotify=false
EOF

    echo "✓ App launcher installed (KeyRGB will appear in your app menu)"

    cat > "$autostart_file" << EOF
[Desktop Entry]
Type=Application
Name=KeyRGB
Comment=RGB Keyboard Controller
Exec=$keyrgb_exec
Icon=$icon_ref
Terminal=false
Categories=Utility;System;
X-KDE-autostart-after=plasma-workspace
X-KDE-StartupNotify=false
EOF

    echo "✓ Autostart configured"
}

install_udev_rule() {
    local src_rule
    local dst_rule="/etc/udev/rules.d/99-ite8291-wootbook.rules"
    local tmp_rule=""

    if [ "$MODE" = "pip" ]; then
        src_rule="$REPO_DIR/system/udev/99-ite8291-wootbook.rules"
        if ! [ -f "$src_rule" ]; then
            echo "⚠️  udev rule file not found: $src_rule"
            return 0
        fi
    else
        local raw_ref="main"
        if [ -n "$KEYRGB_VERSION" ]; then
            raw_ref="$KEYRGB_VERSION"
        fi
        local rule_url="https://raw.githubusercontent.com/Rainexn0b/keyRGB/$raw_ref/system/udev/99-ite8291-wootbook.rules"
        tmp_rule="$(mktemp)"
        echo "⬇️  Downloading udev rule: $rule_url"
        download_url "$rule_url" "$tmp_rule"
        src_rule="$tmp_rule"
    fi

    if ! command -v udevadm &> /dev/null; then
        echo "⚠️  udevadm not found; cannot install udev rule automatically."
        echo "   To fix permissions manually, copy a 99-ite8291-wootbook.rules into: $dst_rule"
        return 0
    fi

    echo
    echo "🔐 Installing udev rule for non-root USB access..."
    echo "   (This enables access to common ITE 8291 USB VID:PID pairs without running KeyRGB as root.)"
    echo "   (This may prompt for your sudo password.)"

    # Only overwrite if changed.
    if [ -f "$dst_rule" ] && cmp -s "$src_rule" "$dst_rule"; then
        echo "✓ udev rule already installed: $dst_rule"
    else
        sudo install -D -m 0644 "$src_rule" "$dst_rule"
        echo "✓ Installed udev rule: $dst_rule"
    fi

    sudo udevadm control --reload-rules
    sudo udevadm trigger
    echo "✓ Reloaded udev rules"
    echo "  If KeyRGB is already running, quit and re-open it."
    echo "  If it still says permission denied, reboot once."

    if [ -n "$tmp_rule" ]; then
        rm -f "$tmp_rule" 2>/dev/null || true
    fi
}

install_input_udev_rule() {
    local src_rule="$REPO_DIR/system/udev/99-keyrgb-input-uaccess.rules"
    local dst_rule="/etc/udev/rules.d/99-keyrgb-input-uaccess.rules"

    if [ "${KEYRGB_INSTALL_INPUT_UDEV,,}" = "n" ] || [ "${KEYRGB_INSTALL_INPUT_UDEV,,}" = "no" ] || [ "${KEYRGB_INSTALL_INPUT_UDEV,,}" = "0" ] || [ "${KEYRGB_INSTALL_INPUT_UDEV,,}" = "false" ]; then
        return 0
    fi

    if ! command -v udevadm &> /dev/null; then
        echo "⚠️  udevadm not found; cannot install input udev rule automatically."
        echo "   If you want reactive typing to use real keypress events, copy: $src_rule"
        echo "   into: $dst_rule"
        return 0
    fi

    if [ ! -f "$src_rule" ]; then
        echo "⚠️  input udev rule file not found: $src_rule"
        return 0
    fi

    echo
    echo "🔐 Installing input udev rule for Reactive Typing (uaccess)..."
    echo "   (This allows the active local user session to read keyboard input events.)"
    echo "   (This may prompt for your sudo password.)"

    if [ -f "$dst_rule" ] && cmp -s "$src_rule" "$dst_rule"; then
        echo "✓ input udev rule already installed: $dst_rule"
    else
        sudo install -D -m 0644 "$src_rule" "$dst_rule"
        echo "✓ Installed input udev rule: $dst_rule"
    fi

    sudo udevadm control --reload-rules
    sudo udevadm trigger
    echo "✓ Reloaded udev rules"
}

install_power_mode_helper() {
    if [ "$INSTALL_POWER_HELPER" != "y" ]; then
        return 0
    fi

    local src_helper
    local src_rule
    local dst_helper="/usr/local/bin/keyrgb-power-helper"
    local dst_rule="/etc/polkit-1/rules.d/90-keyrgb-power-helper.rules"
    local tmp_helper=""
    local tmp_rule=""

    if [ "$MODE" = "pip" ]; then
        src_helper="$REPO_DIR/system/bin/keyrgb-power-helper"
        src_rule="$REPO_DIR/system/polkit/90-keyrgb-power-helper.rules"
        if ! [ -f "$src_helper" ]; then
            echo "⚠️  Power helper file not found: $src_helper"
            return 0
        fi
        if ! [ -f "$src_rule" ]; then
            echo "⚠️  Polkit rule file not found: $src_rule"
            return 0
        fi
    else
        local raw_ref="main"
        if [ -n "$KEYRGB_VERSION" ]; then
            raw_ref="$KEYRGB_VERSION"
        fi
        local helper_url="https://raw.githubusercontent.com/Rainexn0b/keyRGB/$raw_ref/system/bin/keyrgb-power-helper"
        local rule_url="https://raw.githubusercontent.com/Rainexn0b/keyRGB/$raw_ref/system/polkit/90-keyrgb-power-helper.rules"

        tmp_helper="$(mktemp)"
        tmp_rule="$(mktemp)"
        echo "⬇️  Downloading power helper: $helper_url"
        download_url "$helper_url" "$tmp_helper"
        echo "⬇️  Downloading polkit rule: $rule_url"
        download_url "$rule_url" "$tmp_rule"

        src_helper="$tmp_helper"
        src_rule="$tmp_rule"
    fi

    echo
    echo "🔋 Installing lightweight Power Mode helper (no-password via polkit when available)..."
    echo "   (This may prompt for your sudo password.)"

    sudo install -D -m 0755 "$src_helper" "$dst_helper"
    sudo install -D -m 0644 "$src_rule" "$dst_rule"

    echo "✓ Installed helper: $dst_helper"
    echo "✓ Installed polkit rule: $dst_rule"
    echo "  If pkexec still prompts for a password, try logging out/in or rebooting once."

    if [ -n "$tmp_helper" ]; then
        rm -f "$tmp_helper" 2>/dev/null || true
    fi
    if [ -n "$tmp_rule" ]; then
        rm -f "$tmp_rule" 2>/dev/null || true
    fi
}

install_kernel_drivers() {
    if [ "$INSTALL_KERNEL_DRIVERS" != "y" ]; then
        return 0
    fi

    echo
    echo "🔧 Installing kernel drivers (best-effort)..."
    echo "   (This may prompt for your sudo password.)"

    # Prepare marker file
    mkdir -p "$STATE_DIR" || true
    # We append to the marker file in case multiple runs add different things, 
    # but we should probably clear it if we are doing a full re-install logic. 
    # For now, let's just ensure the directory exists. 
    # Actually, let's clear it for this run to avoid duplicates if the user re-runs install.sh
    # But wait, if they installed one driver previously and now install another, we want both.
    # Let's just append and handle duplicates in uninstall or just let them be.
    # Better: clear it if we are about to try installing.
    # But if we fail to install one, we don't want to lose the record of the other?
    # Let's just append. `sort -u` in uninstall could handle it.
    
    if command -v dnf &> /dev/null; then
        # Fedora
        echo "   Detected Fedora (dnf)."
        # Try to install tuxedo-drivers. It might be in a COPR or standard repo depending on setup.
        # We can try to install it.
        set +e
        if sudo dnf install -y tuxedo-drivers; then
            echo "✓ Installed tuxedo-drivers"
            echo "tuxedo-drivers" >> "$KERNEL_DRIVERS_MARKER"
        else
            echo "⚠️  Could not install 'tuxedo-drivers' via dnf."
            echo "   You may need to enable a COPR repository first."
            echo "   See: https://github.com/tuxedocomputers/tuxedo-drivers"
        fi
        
        # clevo-xsm-wmi is usually not in standard repos.
        if sudo dnf install -y clevo-xsm-wmi; then
             echo "✓ Installed clevo-xsm-wmi"
             echo "clevo-xsm-wmi" >> "$KERNEL_DRIVERS_MARKER"
        else
             echo "ℹ️  'clevo-xsm-wmi' package not found in dnf repos (expected)."
        fi
        set -e

    elif command -v apt-get &> /dev/null; then
        # Debian/Ubuntu
        echo "   Detected Debian/Ubuntu (apt)."
        # Tuxedo computers have their own repo.
        set +e
        if sudo apt-get install -y tuxedo-keyboard; then
            echo "✓ Installed tuxedo-keyboard"
            echo "tuxedo-keyboard" >> "$KERNEL_DRIVERS_MARKER"
        else
            echo "⚠️  Could not install 'tuxedo-keyboard'."
            echo "   You may need to add the Tuxedo Computers repository."
            echo "   See: https://www.tuxedocomputers.com/en/Infos/Help-Support/Instructions/Add-TUXEDO-Computers-software-package-sources.tuxedo"
        fi
        
        # clevo-xsm-wmi
        if sudo apt-get install -y clevo-xsm-wmi; then
            echo "✓ Installed clevo-xsm-wmi"
            echo "clevo-xsm-wmi" >> "$KERNEL_DRIVERS_MARKER"
        else
             echo "ℹ️  'clevo-xsm-wmi' package not found in apt repos."
        fi
        set -e

    elif command -v pacman &> /dev/null; then
        # Arch
        echo "   Detected Arch Linux."
        echo "⚠️  Arch Linux detected. Please install drivers via AUR:"
        echo "   - tuxedo-drivers-dkms"
        echo "   - clevo-xsm-wmi-dkms"
        echo "   (KeyRGB installer does not handle AUR packages automatically.)"
    else
        echo "⚠️  Unknown package manager. Please install 'tuxedo-drivers' or 'clevo-xsm-wmi' manually."
    fi
}

if [ "$MODE" = "pip" ]; then
    # Install ite8291r3-ctl library (upstream + tiny local patch for Wootbook 0x600B)
    echo
    echo "📦 Installing ite8291r3-ctl library (upstream)..."

    TMPDIR="$(mktemp -d)"
    cleanup() {
        rm -rf "$TMPDIR"
    }
    trap cleanup EXIT

    git clone --depth 1 https://github.com/pobrn/ite8291r3-ctl.git "$TMPDIR/ite8291r3-ctl"

    python3 - "$TMPDIR/ite8291r3-ctl/ite8291r3_ctl/ite8291r3.py" << 'PY'
from __future__ import annotations

import re
import sys
from pathlib import Path

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")

if "0x600B" in text or "0x600b" in text:
    print("✓ ite8291r3-ctl already contains 0x600B")
    raise SystemExit(0)

# Fast path: exact upstream line.
text2 = text.replace(
    "PRODUCT_IDS = [0x6004, 0x6006, 0xCE00]",
    "PRODUCT_IDS = [0x6004, 0x6006, 0x600B, 0xCE00]  # Added 0x600B for Wootbook",
)

if text2 == text:
    # Generic path: patch PRODUCT_IDS assignment (single-line or multi-line).
    m = re.search(r"(?m)^PRODUCT_IDS\s*=\s*\[", text)
    if not m:
        raise SystemExit(f"Failed to locate PRODUCT_IDS in {path}")

    start = m.end()  # position right after '['
    end = text.find("]", start)
    if end == -1:
        raise SystemExit(f"Failed to find closing ']' for PRODUCT_IDS in {path}")

    body = text[start:end]
    if "0x600B" in body or "0x600b" in body:
        print("✓ ite8291r3-ctl already contains 0x600B")
        raise SystemExit(0)

    # If it's a single-line list, keep it single-line.
    if "\n" not in body:
        inner_stripped = body.strip()
        if inner_stripped and not inner_stripped.endswith(","):
            inner_stripped += ","
        new_body = f" {inner_stripped} 0x600B" + "  # Added 0x600B for Wootbook"
        text2 = text[:start] + new_body + text[end:]
    else:
        # Multi-line list: insert a new element before the closing bracket.
        last_nl = text.rfind("\n", 0, end)
        line_start = last_nl + 1 if last_nl != -1 else 0
        indent = re.match(r"\s*", text[line_start:end]).group(0)
        insertion = f"\n{indent}0x600B,  # Added 0x600B for Wootbook"
        text2 = text[:end] + insertion + text[end:]

path.write_text(text2, encoding="utf-8")
print("✓ Patched ite8291r3-ctl: added 0x600B to PRODUCT_IDS")
PY

    python3 -m pip install --user "$TMPDIR/ite8291r3-ctl"

    echo "✓ ite8291r3-ctl installed (upstream + local patch)"

    # Install Python dependencies
    echo
    echo "📦 Installing Python dependencies..."
    python3 -m pip install --user -r "$REPO_DIR/requirements.txt"
    echo "✓ Dependencies installed"

    # Install KeyRGB itself (provides the `keyrgb` console script)
    echo
    echo "📦 Installing KeyRGB..."
    python3 -m pip install --user -e "$REPO_DIR"
    echo "✓ KeyRGB installed"
else
    install_appimage
fi
install_udev_rule
install_input_udev_rule
install_power_mode_helper
install_kernel_drivers

# Many distros don't include ~/.local/bin on PATH by default.
USER_BIN="$HOME/.local/bin"
if ! echo ":$PATH:" | grep -q ":$USER_BIN:"; then
    echo
    echo "⚠️  Your PATH does not include $USER_BIN"
    echo "   The 'keyrgb' command was installed there, so you may not be able to run it yet."
    echo
    echo "   To fix (bash/zsh), add this line to ~/.profile (or ~/.bashrc / ~/.zshrc):"
    echo "     export PATH=\"$USER_BIN:\$PATH\""
    echo
    echo "   Then restart your terminal (or log out/in)."
fi

if [ "$MODE" = "pip" ]; then
    # Make scripts executable
    echo
    echo "🔧 Making scripts executable..."
    chmod +x "$REPO_DIR/keyrgb"

    # Optional / legacy scripts (don't fail if absent)
    for f in keyrgb-editor.py keyrgb-editor-qt.py effects.py; do
        if [ -f "$f" ]; then
            chmod +x "$f"
        fi
    done

    echo "✓ Scripts are executable"
fi

echo
echo "🧷 Installing application launcher entry..."
install_icon_and_desktop_entries

echo
echo "=== Installation Complete ==="
echo
echo "KeyRGB is now installed!"
echo
echo "Next steps:"
echo "  1. Run 'keyrgb' to start the tray app"
echo "     (Dev/repo mode: you can also run './keyrgb' from the repo folder.)"
echo "  2. Look for the pink/magenta keyboard icon in your system tray"
echo "  3. Right-click the icon to access effects, speed, and brightness"
echo "  4. KeyRGB will auto-start on next login"
echo "  5. If 'keyrgb' isn't found, ensure ~/.local/bin is on PATH"
echo "  6. If you quit the tray, you can re-open it from your app menu (KeyRGB)"
echo
echo "Troubleshooting:"
echo "  - If icon doesn't appear, check terminal for errors"
echo "  - If keyboard doesn't light up, check USB device: lsusb | grep 048d"
echo "  - Per-key editor: Right-click tray icon → Per-Key Editor"
echo
