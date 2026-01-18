#!/usr/bin/env bash

# Developer installer:
# - Installs build + runtime dependencies
# - Supports repo-local editable install or cloning

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/common.sh"

usage() {
  cat <<'EOF'
Usage:
  install.sh --dev [--clone] [--clone-dir <path>] [--no-system-deps]

Behavior:
  - Installs build tools (gcc, pkg-config) and common libs (libusb) best-effort.
  - Performs pip editable install of this repo (or cloned repo).

Options:
  --clone              Clone the repo then install from that directory.
  --clone-dir <path>   Clone target (default: ~/.local/share/keyrgb-src)
  --no-system-deps     Skip best-effort system dependency installation
EOF
}

DO_CLONE=0
CLONE_DIR="${KEYRGB_CLONE_DIR:-$HOME/.local/share/keyrgb-src}"
KEYRGB_SKIP_SYSTEM_DEPS="${KEYRGB_SKIP_SYSTEM_DEPS:-n}"

while [ "$#" -gt 0 ]; do
  case "$1" in
    --clone) DO_CLONE=1; shift ;;
    --clone-dir) CLONE_DIR="${2:-}"; shift 2 ;;
    --no-system-deps) KEYRGB_SKIP_SYSTEM_DEPS="y"; shift ;;
    -h|--help) usage; exit 0 ;;
    *) die "Unknown argument: $1" ;;
  esac
done

require_not_root

log_info "=== KeyRGB Installation (Dev) ==="

if ! is_truthy "$KEYRGB_SKIP_SYSTEM_DEPS"; then
  log_info "Installing dev dependencies (best-effort)..."
  detect_pkg_manager || true

  case "${PKG_MGR:-}" in
    dnf)
      pkg_install_best_effort git python3 python3-pip python3-tkinter gcc gcc-c++ make pkgconf-pkg-config libusb1-devel usbutils dbus-tools || true
      ;;
    apt)
      pkg_install_best_effort git python3 python3-pip python3-tk build-essential pkg-config libusb-1.0-0-dev usbutils dbus || true
      ;;
    pacman)
      pkg_install_best_effort git python python-pip tk base-devel pkgconf libusb usbutils dbus || true
      ;;
    zypper)
      pkg_install_best_effort git python3 python3-pip python3-tk gcc gcc-c++ make pkg-config libusb-1_0-devel usbutils dbus-1 dbus-1-tools || true
      ;;
    apk)
      pkg_install_best_effort git python3 py3-pip py3-tkinter build-base pkgconf libusb-dev usbutils dbus || true
      ;;
    *)
      pkg_install_best_effort git python3 python3-pip gcc pkg-config libusb || true
      ;;
  esac
else
  log_info "Skipping system dependency installation (--no-system-deps / KEYRGB_SKIP_SYSTEM_DEPS)."
fi

need_cmd python3
need_cmd git

REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

if [ "$DO_CLONE" -eq 1 ]; then
  [ -n "$CLONE_DIR" ] || die "--clone-dir is empty"
  log_info "Cloning repo into: $CLONE_DIR"
  if [ -d "$CLONE_DIR/.git" ]; then
    log_ok "Using existing clone (won't auto-update): $CLONE_DIR"
  else
    mkdir -p "$(dirname "$CLONE_DIR")"
    git clone --depth 1 "https://github.com/${KEYRGB_REPO_OWNER}/${KEYRGB_REPO_NAME}.git" "$CLONE_DIR"
    log_ok "Cloned repo"
  fi
  REPO_DIR="$CLONE_DIR"
fi

log_info "Updating pip tooling..."
python3 -m pip install --user -U pip setuptools wheel

log_info "Installing Python dependencies..."
python3 -m pip install --user -r "$REPO_DIR/requirements.txt"

log_info "Installing KeyRGB (editable)..."
python3 -m pip install --user -e "$REPO_DIR"

log_ok "Dev installation complete"
log_info "Next: run 'keyrgb' (ensure ~/.local/bin is on PATH)"
