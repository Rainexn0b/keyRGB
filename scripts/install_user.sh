#!/usr/bin/env bash

# Minimal user installer:
# - Downloads AppImage from GitHub releases
# - Installs USB udev rule
# - Installs desktop launcher + autostart + icon
# - Optional: install Reactive Typing input udev rule (local file only)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/common.sh"

usage() {
  cat <<'EOF'
Usage:
  install.sh [--version <tag>] [--asset <name>] [--prerelease] [--update-appimage] [--no-system-deps]

Default behavior:
  - Installs the latest stable AppImage to ~/.local/bin/keyrgb
  - Installs udev rule for non-root USB access
  - Installs desktop launcher + autostart entry + icon

Options:
  --version <tag>       Install a specific Git tag (e.g. v0.7.9)
  --asset <name>        AppImage filename (default: keyrgb-x86_64.AppImage)
  --prerelease          Allow picking prereleases when auto-resolving latest
  --update-appimage     Only update the AppImage (non-interactive); still refreshes desktop + udev
  --no-system-deps      Skip best-effort system dependency install

Env vars:
  KEYRGB_ALLOW_PRERELEASE=y|n
  KEYRGB_APPIMAGE_ASSET=<name>
  KEYRGB_VERSION=<tag>
  KEYRGB_SKIP_SYSTEM_DEPS=y|n

  # Legacy parity (optional components)
  KEYRGB_INSTALL_POWER_HELPER=y|n     Install Power Mode pkexec helper (mutually exclusive with KEYRGB_INSTALL_TUXEDO)
  KEYRGB_INSTALL_TUXEDO=y|n           Prefer Tuxedo Control Center (TCC) integration for power profiles

  # Optional parity with legacy installer (off by default)
  KEYRGB_INSTALL_INPUT_UDEV=y|n         Install /dev/input uaccess rule for Reactive Typing (security-sensitive)
  KEYRGB_INSTALL_TCC_APP=y|n            Best-effort install tuxedo-control-center + marker file for uninstall
  KEYRGB_INSTALL_KERNEL_DRIVERS=y|n     Best-effort install tuxedo driver packages + marker file for uninstall

  # Telemetry (best-effort)
  KEYRGB_TELEMETRY=0            Disable success ping (default enabled)
  KEYRGB_TELEMETRY_URL=<url>    Override endpoint (default: https://telemetry.invalid/keyrgb/install-success)
EOF
}

UPDATE_ONLY=0
KEYRGB_VERSION="${KEYRGB_VERSION:-}"

KEYRGB_APPIMAGE_ASSET_SET=0
if [ -n "${KEYRGB_APPIMAGE_ASSET+x}" ]; then
  KEYRGB_APPIMAGE_ASSET_SET=1
fi
KEYRGB_APPIMAGE_ASSET="${KEYRGB_APPIMAGE_ASSET:-keyrgb-x86_64.AppImage}"

KEYRGB_ALLOW_PRERELEASE_SET=0
if [ -n "${KEYRGB_ALLOW_PRERELEASE+x}" ]; then
  KEYRGB_ALLOW_PRERELEASE_SET=1
fi
KEYRGB_ALLOW_PRERELEASE="${KEYRGB_ALLOW_PRERELEASE:-n}"

KEYRGB_SKIP_SYSTEM_DEPS="${KEYRGB_SKIP_SYSTEM_DEPS:-n}"

while [ "$#" -gt 0 ]; do
  case "$1" in
    --version) KEYRGB_VERSION="${2:-}"; shift 2 ;;
    --asset)
      KEYRGB_APPIMAGE_ASSET_SET=1
      KEYRGB_APPIMAGE_ASSET="${2:-}"
      shift 2
      ;;
    --prerelease)
      KEYRGB_ALLOW_PRERELEASE_SET=1
      KEYRGB_ALLOW_PRERELEASE="y"
      shift
      ;;
    --update-appimage|--update) UPDATE_ONLY=1; shift ;;
    --no-system-deps) KEYRGB_SKIP_SYSTEM_DEPS="y"; shift ;;
    -h|--help) usage; exit 0 ;;
    *) die "Unknown argument: $1" ;;
  esac
done

require_not_root

log_info "=== KeyRGB Installation (User) ==="

if [ "$UPDATE_ONLY" -eq 1 ]; then
  log_info "=== KeyRGB AppImage Update ==="
  log_info "Update-only mode: download a fresh AppImage and refresh udev + desktop integration."

  # The release channel comes from saved prefs unless overridden via env/CLI.
  if is_truthy "${KEYRGB_ALLOW_PRERELEASE:-n}"; then
    log_info "Using saved release channel: include prereleases (beta)"
  else
    log_info "Using saved release channel: stable releases only"
  fi
  log_info "Tip: set --prerelease (or KEYRGB_ALLOW_PRERELEASE=y) to override."
fi

# Legacy parity: load saved AppImage prefs unless overridden via env/CLI.
load_saved_appimage_prefs

maybe_prompt_release_channel
configure_optional_components

if [ "$UPDATE_ONLY" -ne 1 ] && ! is_truthy "$KEYRGB_SKIP_SYSTEM_DEPS"; then
  log_info "Installing system dependencies (best-effort)..."
  detect_pkg_manager || true

  # Keep this lightweight: runtime + tray deps only.
  case "${PKG_MGR:-}" in
    dnf) pkg_install_best_effort python3 python3-tkinter usbutils dbus-tools libappindicator-gtk3 python3-gobject gtk3 || true ;;
    apt) pkg_install_best_effort python3 python3-tk usbutils dbus python3-gi gir1.2-appindicator3-0.1 || true ;;
    pacman) pkg_install_best_effort python tk usbutils dbus libappindicator-gtk3 python-gobject gtk3 || true ;;
    zypper) pkg_install_best_effort python3 python3-tk usbutils dbus-1 dbus-1-tools python3-gobject gtk3 typelib-1_0-AppIndicator3-0_1 || true ;;
    apk) pkg_install_best_effort python3 py3-tkinter usbutils dbus || true ;;
    *) pkg_install_best_effort python3 usbutils || true ;;
  esac

  # If the user will use pkexec helpers, ensure polkit exists best-effort.
  if ! is_truthy "${KEYRGB_SKIP_PRIVILEGED_HELPERS:-n}"; then
    ensure_polkit_best_effort
  fi

  # Optional legacy behaviors (off by default).
  if is_truthy "${KEYRGB_INSTALL_TCC_APP:-n}"; then
    install_tcc_app_best_effort
  fi
  if is_truthy "${KEYRGB_INSTALL_KERNEL_DRIVERS:-n}"; then
    install_kernel_drivers_best_effort
  fi
else
  if [ "$UPDATE_ONLY" -eq 1 ]; then
    log_info "Skipping system dependency installation (update-only)."
  else
    log_info "Skipping system dependency installation (--no-system-deps / KEYRGB_SKIP_SYSTEM_DEPS)."
  fi
fi

APPIMAGE_DST="$HOME/.local/bin/keyrgb"

resolved_ref=""

# If KeyRGB is already installed, don't force a 100MB re-download on every run.
# `--update-appimage` keeps the old behavior.
if [ "$UPDATE_ONLY" -eq 0 ] \
  && ! is_truthy "${KEYRGB_FORCE_APPIMAGE_DOWNLOAD:-n}" \
  && [ -f "$APPIMAGE_DST" ] \
  && [ -x "$APPIMAGE_DST" ]; then
  log_info "AppImage already present; skipping download (set KEYRGB_FORCE_APPIMAGE_DOWNLOAD=y to force)."
  log_info "No AppImage download performed, so no progress meter will be shown."

  # Still try to resolve a tag so icon/udev downloads can use a stable ref.
  resolved="$(resolve_release_with_asset "$KEYRGB_APPIMAGE_ASSET" "$KEYRGB_ALLOW_PRERELEASE" 2>/dev/null)" || true
  if [ -n "${resolved:-}" ]; then
    IFS='|' read -r resolved_ref _resolved_url _resolved_prerelease <<<"$resolved"
  else
    resolved_ref="main"
  fi
else
  resolved_ref="$(appimage_install "$APPIMAGE_DST" "$KEYRGB_APPIMAGE_ASSET" "$KEYRGB_VERSION" "$KEYRGB_ALLOW_PRERELEASE")"
fi

# If we resolved a tag, use it for icon/udev. Otherwise fall back to main.
RAW_REF="${resolved_ref:-main}"

# Always refresh udev + desktop integration; it's quick and keeps things consistent.
install_udev_rule_from_ref "$RAW_REF"

if [ "$UPDATE_ONLY" -ne 1 ]; then
  # Install narrowly-scoped pkexec helpers + polkit rules so sysfs writes (power mode,
  # battery charging profile) don't prompt for a password each click.
  REPO_DIR_LOCAL="$(cd "$SCRIPT_DIR/.." && pwd)"
  use_local_helpers=0
  if [ -d "$REPO_DIR_LOCAL/system" ]; then
    local_ok=1

    if is_truthy "${KEYRGB_INSTALL_POWER_HELPER:-y}"; then
      if ! [ -f "$REPO_DIR_LOCAL/system/bin/keyrgb-power-helper" ] || ! [ -f "$REPO_DIR_LOCAL/system/polkit/90-keyrgb-power-helper.rules" ]; then
        local_ok=0
      fi
    fi

    if [ "$local_ok" -eq 1 ]; then
      use_local_helpers=1
    fi
  fi

  if [ "$use_local_helpers" -eq 1 ]; then
    install_privileged_helpers_local "$REPO_DIR_LOCAL" || true
  else
    install_privileged_helpers_from_ref "$RAW_REF" || true
  fi

  # Optional local-only input udev rule (security-sensitive): only when running from a repo checkout.
  if is_truthy "${KEYRGB_INSTALL_INPUT_UDEV:-0}"; then
    REPO_DIR_LOCAL_FOR_INPUT="$(cd "$SCRIPT_DIR/.." && pwd)"
    local_input_rule="$REPO_DIR_LOCAL_FOR_INPUT/system/udev/99-keyrgb-input-uaccess.rules"
    if [ -f "$local_input_rule" ]; then
      install_input_udev_rule_local "$local_input_rule"
    else
      install_input_udev_rule_from_ref "$RAW_REF"
    fi
    log_ok "Reactive Typing input udev rule installed (best-effort)"
  fi
fi

# Desktop exec should be absolute path.
install_icon_and_desktop_entries "$APPIMAGE_DST" "$RAW_REF"

save_appimage_prefs_best_effort

success_hook() {
  if is_truthy "${KEYRGB_TELEMETRY:-1}"; then
    if ! have_cmd curl; then
      log_warn "Telemetry: curl not found; skipping success ping."
      return 0
    fi

    local url="${KEYRGB_TELEMETRY_URL:-https://telemetry.invalid/keyrgb/install-success}"
    # Best-effort, fast timeout, ignore failures.
    curl -fsS --connect-timeout 2 --max-time 3 \
      -H 'User-Agent: keyrgb-install' \
      "$url" >/dev/null 2>&1 || true
  fi
}

if [ "$UPDATE_ONLY" -eq 1 ]; then
  log_ok "AppImage update complete"
else
  log_ok "Installation complete"
fi

log_info "Next steps: run '$APPIMAGE_DST' (or add ~/.local/bin to PATH and run 'keyrgb')"

success_hook
