#!/usr/bin/env bash

# Modular uninstall implementation.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}" )" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/common.sh"

usage() {
  cat <<'EOF'
Usage: uninstall.sh [--yes] [--purge-config] [--remove-appimage]

--yes             Do not prompt (best-effort).
--purge-config    Also remove ~/.config/keyrgb (profiles/settings).
--remove-appimage Remove ~/.local/bin/keyrgb if it looks like an AppImage.

Notes:
  - Removes both AppImage-mode and pip-mode installs (with prompts).
  - Does NOT remove system packages installed by install.sh (except optional TCC removal when KeyRGB installed it).
EOF
}

YES=0
PURGE_CONFIG=0
REMOVE_APPIMAGE=0

while [ "$#" -gt 0 ]; do
  case "$1" in
    -y|--yes) YES=1; shift ;;
    --purge-config) PURGE_CONFIG=1; shift ;;
    --remove-appimage) REMOVE_APPIMAGE=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) die "Unknown argument: $1" ;;
  esac
done

require_not_root

confirm() {
  local prompt="$1"
  if [ "$YES" -eq 1 ] || ! [ -t 0 ]; then
    return 0
  fi
  local reply=""
  read -r -p "$prompt [y/N] " reply || reply=""
  reply="${reply,,}"
  [[ "$reply" == "y" || "$reply" == "yes" ]]
}

file_has_marker() {
  local path="$1" marker="$2"
  [ -f "$path" ] || return 1
  grep -Fqs -- "$marker" "$path" 2>/dev/null
}

STATE_DIR="$HOME/.local/share/keyrgb"
TCC_MARKER="$STATE_DIR/tcc-installed-by-keyrgb"
KERNEL_DRIVERS_MARKER="$STATE_DIR/kernel-drivers-installed-by-keyrgb"

log_info "=== KeyRGB Uninstall ==="

looks_like_appimage() {
  local path="$1"
  [ -f "$path" ] || return 1

  python3 - "$path" <<'PY'
from __future__ import annotations

import sys
from pathlib import Path

p = Path(sys.argv[1])
data = p.read_bytes()

if not data.startswith(b"\x7fELF"):
    raise SystemExit(1)

if b"AppImage" in data[:2_000_000]:
    raise SystemExit(0)
raise SystemExit(1)
PY
}

APPIMAGE_BIN="$HOME/.local/bin/keyrgb"
if [ "$REMOVE_APPIMAGE" -eq 1 ] && looks_like_appimage "$APPIMAGE_BIN"; then
  rm -f "$APPIMAGE_BIN" || true
  log_ok "Removed AppImage binary: $APPIMAGE_BIN"
elif looks_like_appimage "$APPIMAGE_BIN"; then
  if confirm "Remove AppImage binary $APPIMAGE_BIN ?"; then
    rm -f "$APPIMAGE_BIN" || true
    log_ok "Removed AppImage binary"
  else
    log_info "Skipped removing AppImage binary"
  fi
fi

APP_FILE="$HOME/.local/share/applications/keyrgb.desktop"
AUTOSTART_FILE="$HOME/.config/autostart/keyrgb.desktop"
ICON_FILE_PNG="$HOME/.local/share/icons/keyrgb.png"
ICON_FILE_JPG="$HOME/.local/share/icons/keyrgb.jpg"
ICON_FILE_THEME_PNG="$HOME/.local/share/icons/hicolor/256x256/apps/keyrgb.png"

if confirm "Remove desktop launcher + autostart entries?"; then
  rm -f "$APP_FILE" || true
  rm -f "$AUTOSTART_FILE" || true
  rm -f "$ICON_FILE_PNG" || true
  rm -f "$ICON_FILE_JPG" || true
  rm -f "$ICON_FILE_THEME_PNG" || true
  log_ok "Removed desktop entries + icon (if present)"
else
  log_info "Skipped removing desktop entries"
fi

if confirm "Uninstall Python packages (keyrgb) from your user site-packages?"; then
  python3 -m pip uninstall -y keyrgb >/dev/null 2>&1 || true
  python3 -m pip uninstall -y ite8291r3-ctl >/dev/null 2>&1 || true
  python3 -m pip uninstall -y ite8291r3_ctl >/dev/null 2>&1 || true
  log_ok "Uninstalled pip packages (best-effort)"
else
  log_info "Skipped pip uninstall"
fi

REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
UDEV_DST="/etc/udev/rules.d/99-ite8291-wootbook.rules"
UDEV_SRC="$REPO_DIR/system/udev/99-ite8291-wootbook.rules"

SYSFS_UDEV_DST="/etc/udev/rules.d/99-keyrgb-sysfs-leds.rules"
SYSFS_UDEV_SRC="$REPO_DIR/system/udev/99-keyrgb-sysfs-leds.rules"

INPUT_UDEV_DST="/etc/udev/rules.d/99-keyrgb-input-uaccess.rules"
INPUT_UDEV_SRC="$REPO_DIR/system/udev/99-keyrgb-input-uaccess.rules"

POWER_HELPER_DST="/usr/local/bin/keyrgb-power-helper"
POWER_HELPER_SRC="$REPO_DIR/system/bin/keyrgb-power-helper"
POWER_POLKIT_DST="/etc/polkit-1/rules.d/90-keyrgb-power-helper.rules"
POWER_POLKIT_SRC="$REPO_DIR/system/polkit/90-keyrgb-power-helper.rules"

if [ -f "$UDEV_DST" ]; then
  udev_matches_repo=0
  if [ -f "$UDEV_SRC" ] && cmp -s "$UDEV_SRC" "$UDEV_DST"; then
    udev_matches_repo=1
  fi
  udev_looks_like_keyrgb=0
  if file_has_marker "$UDEV_DST" "Allow user access to ITE 8291 USB device."; then
    udev_looks_like_keyrgb=1
  fi

  if [ "$udev_matches_repo" -eq 1 ] || [ "$udev_looks_like_keyrgb" -eq 1 ]; then
    if [ "$udev_matches_repo" -ne 1 ]; then
      log_warn "udev rule does not match this repo version, but appears to be KeyRGB-managed: $UDEV_DST"
    fi
    if confirm "Remove udev rule $UDEV_DST (requires sudo)?"; then
      sudo rm -f "$UDEV_DST"
      reload_udev_rules_best_effort
      log_ok "Removed udev rule"
    else
      log_info "Skipped removing udev rule"
    fi
  else
    log_warn "udev rule exists but does not look KeyRGB-managed; not removing: $UDEV_DST"
  fi
fi

if [ -f "$SYSFS_UDEV_DST" ]; then
  sysfs_matches_repo=0
  if [ -f "$SYSFS_UDEV_SRC" ] && cmp -s "$SYSFS_UDEV_SRC" "$SYSFS_UDEV_DST"; then
    sysfs_matches_repo=1
  fi
  sysfs_looks_like_keyrgb=0
  if file_has_marker "$SYSFS_UDEV_DST" "Allow KeyRGB to write keyboard backlight sysfs LED attributes."; then
    sysfs_looks_like_keyrgb=1
  fi

  if [ "$sysfs_matches_repo" -eq 1 ] || [ "$sysfs_looks_like_keyrgb" -eq 1 ]; then
    if [ "$sysfs_matches_repo" -ne 1 ]; then
      log_warn "sysfs LED udev rule does not match this repo version, but appears to be KeyRGB-managed: $SYSFS_UDEV_DST"
    fi
    if confirm "Remove sysfs LED udev rule $SYSFS_UDEV_DST (requires sudo)?"; then
      sudo rm -f "$SYSFS_UDEV_DST"
      reload_udev_rules_best_effort
      log_ok "Removed sysfs LED udev rule"
    else
      log_info "Skipped removing sysfs LED udev rule"
    fi
  else
    log_warn "sysfs LED udev rule exists but does not look KeyRGB-managed; not removing: $SYSFS_UDEV_DST"
  fi
fi

if [ -f "$INPUT_UDEV_DST" ]; then
  input_matches_repo=0
  if [ -f "$INPUT_UDEV_SRC" ] && cmp -s "$INPUT_UDEV_SRC" "$INPUT_UDEV_DST"; then
    input_matches_repo=1
  fi
  input_looks_like_keyrgb=0
  if file_has_marker "$INPUT_UDEV_DST" "Reactive Typing effects"; then
    input_looks_like_keyrgb=1
  fi

  if [ "$input_matches_repo" -eq 1 ] || [ "$input_looks_like_keyrgb" -eq 1 ]; then
    if [ "$input_matches_repo" -ne 1 ]; then
      log_warn "Reactive Typing input udev rule does not match this repo version, but appears KeyRGB-managed: $INPUT_UDEV_DST"
    fi
    if confirm "Remove Reactive Typing input udev rule $INPUT_UDEV_DST (requires sudo)?"; then
      sudo rm -f "$INPUT_UDEV_DST"
      reload_udev_rules_best_effort
      log_ok "Removed Reactive Typing input udev rule"
      log_info "You may need to log out/in for ACLs to refresh."
    else
      log_info "Skipped removing Reactive Typing input udev rule"
    fi
  else
    log_warn "Reactive Typing input udev rule exists but does not look KeyRGB-managed; not removing: $INPUT_UDEV_DST"
  fi
fi

remove_helper_and_rule_if_match() {
  local helper_dst="$1" helper_src="$2" rule_dst="$3" rule_src="$4" label="$5"

  if [ ! -f "$helper_dst" ] && [ ! -f "$rule_dst" ]; then
    return 0
  fi

  local helper_matches=0
  local rule_matches=0
  local helper_looks_like_keyrgb=0
  local rule_looks_like_keyrgb=0

  if [ -f "$helper_dst" ] && [ -f "$helper_src" ] && cmp -s "$helper_src" "$helper_dst"; then
    helper_matches=1
  fi
  if [ -f "$rule_dst" ] && [ -f "$rule_src" ] && cmp -s "$rule_src" "$rule_dst"; then
    rule_matches=1
  fi

  # Allow removing a KeyRGB-managed helper/rule even if the repo version differs.
  if file_has_marker "$helper_dst" "KEYRGB_CPUFREQ_ROOT"; then
    helper_looks_like_keyrgb=1
  fi
  if file_has_marker "$rule_dst" "Installed by KeyRGB's install.sh"; then
    rule_looks_like_keyrgb=1
  fi

  if [ -f "$helper_dst" ] && [ "$helper_matches" -ne 1 ] && [ "$helper_looks_like_keyrgb" -ne 1 ]; then
    log_warn "$label helper exists but does not look KeyRGB-managed; not removing: $helper_dst"
  elif [ -f "$helper_dst" ] && [ "$helper_matches" -ne 1 ] && [ "$helper_looks_like_keyrgb" -eq 1 ]; then
    log_warn "$label helper does not match this repo version, but appears KeyRGB-managed: $helper_dst"
  fi

  if [ -f "$rule_dst" ] && [ "$rule_matches" -ne 1 ] && [ "$rule_looks_like_keyrgb" -ne 1 ]; then
    log_warn "$label polkit rule exists but does not look KeyRGB-managed; not removing: $rule_dst"
  elif [ -f "$rule_dst" ] && [ "$rule_matches" -ne 1 ] && [ "$rule_looks_like_keyrgb" -eq 1 ]; then
    log_warn "$label polkit rule does not match this repo version, but appears KeyRGB-managed: $rule_dst"
  fi

  if [ "$helper_matches" -eq 1 ] || [ "$rule_matches" -eq 1 ] || [ "$helper_looks_like_keyrgb" -eq 1 ] || [ "$rule_looks_like_keyrgb" -eq 1 ]; then
    if confirm "Remove $label helper + polkit rule (requires sudo)?"; then
      if [ "$helper_matches" -eq 1 ] || [ "$helper_looks_like_keyrgb" -eq 1 ]; then
        sudo rm -f "$helper_dst" || true
      fi
      if [ "$rule_matches" -eq 1 ] || [ "$rule_looks_like_keyrgb" -eq 1 ]; then
        sudo rm -f "$rule_dst" || true
      fi
      log_ok "Removed $label helper/polkit (best-effort)"
    else
      log_info "Skipped removing $label helper/polkit"
    fi
  fi
}

remove_helper_and_rule_if_match "$POWER_HELPER_DST" "$POWER_HELPER_SRC" "$POWER_POLKIT_DST" "$POWER_POLKIT_SRC" "Power Mode"

# Remove TCC if marker exists and package still installed.
if [ -f "$TCC_MARKER" ]; then
  if detect_pkg_manager; then
    if confirm "Uninstall Tuxedo Control Center (tuxedo-control-center) that was installed by KeyRGB (requires sudo)?"; then
      if pkg_remove_best_effort tuxedo-control-center; then
        rm -f "$TCC_MARKER" || true
        log_ok "Removed tuxedo-control-center"
      else
        log_warn "Failed to remove tuxedo-control-center; marker file left: $TCC_MARKER"
      fi
    fi
  else
    log_warn "No supported package manager found; cannot remove tuxedo-control-center automatically."
    log_warn "Marker file: $TCC_MARKER"
  fi
fi

# Kernel drivers marker: prompt per entry.
if [ -f "$KERNEL_DRIVERS_MARKER" ]; then
  log_info "Found kernel drivers installed by KeyRGB:"
  mapfile -t driver_pkgs < <(sort -u "$KERNEL_DRIVERS_MARKER" | sed '/^$/d')

  remaining_pkgs=()
  for pkg in "${driver_pkgs[@]}"; do
    if confirm "Uninstall kernel driver '$pkg' (requires sudo)?"; then
      if pkg_remove_best_effort "$pkg"; then
        :
      else
        log_warn "Failed to remove $pkg (best-effort)."
        remaining_pkgs+=("$pkg")
      fi
    else
      remaining_pkgs+=("$pkg")
    fi
  done

  if [ ${#remaining_pkgs[@]} -eq 0 ]; then
    rm -f "$KERNEL_DRIVERS_MARKER" || true
  else
    printf '%s\n' "${remaining_pkgs[@]}" > "$KERNEL_DRIVERS_MARKER" 2>/dev/null || true
  fi
fi

if [ "$PURGE_CONFIG" -eq 1 ]; then
  if confirm "Remove ~/.config/keyrgb (profiles/settings)?"; then
    rm -rf "$HOME/.config/keyrgb" || true
    log_ok "Removed ~/.config/keyrgb"
  else
    log_info "Skipped removing ~/.config/keyrgb"
  fi
fi

if [ -d "$STATE_DIR" ]; then
  if confirm "Remove KeyRGB installer state ($STATE_DIR)?"; then
    rm -rf "$STATE_DIR" || true
    log_ok "Removed KeyRGB installer state"
  else
    log_info "Skipped removing KeyRGB installer state"
  fi
fi

log_ok "Uninstall complete"
log_info "Note: system packages installed by install.sh are not removed by default."

log_info "If you uninstalled because KeyRGB didn't work on your hardware, please consider opening an issue:"
log_info "  https://github.com/${KEYRGB_REPO_OWNER}/${KEYRGB_REPO_NAME}/issues"
log_info "Include: distro/version, lsusb output, and KeyRGB diagnostics/logs (KEYRGB_DEBUG=1)."
