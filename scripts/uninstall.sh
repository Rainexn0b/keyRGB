#!/usr/bin/env bash

# Modular uninstall implementation.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}" )" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/common.sh"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/lib/uninstall_match.sh"

usage() {
  cat <<'EOF'
Usage: uninstall.sh [--yes] [--purge-config] [--remove-appimage]

--yes             Do not prompt (best-effort).
--purge-config    Also remove ~/.config/keyrgb (profiles/settings).
--remove-appimage Remove the KeyRGB AppImage launcher/binary from ~/.local/bin.

Notes:
  - Removes both AppImage-mode and pip-mode installs (with prompts).
  - Does NOT remove system packages installed by install.sh.
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

STATE_DIR="$HOME/.local/share/keyrgb"
KERNEL_DRIVERS_MARKER="$STATE_DIR/kernel-drivers-installed-by-keyrgb"

log_info "=== KeyRGB Uninstall ==="

APPIMAGE_WRAPPER="$HOME/.local/bin/keyrgb"
APPIMAGE_BIN="$HOME/.local/bin/keyrgb.AppImage"
HAS_APPIMAGE_INSTALL=0

if is_appimage_file "$APPIMAGE_BIN"; then
  HAS_APPIMAGE_INSTALL=1
fi
if is_appimage_file "$APPIMAGE_WRAPPER" || file_has_marker "$APPIMAGE_WRAPPER" "KeyRGB AppImage launcher."; then
  HAS_APPIMAGE_INSTALL=1
fi

if [ "$HAS_APPIMAGE_INSTALL" -eq 1 ]; then
  if [ "$REMOVE_APPIMAGE" -eq 1 ] || confirm "Remove KeyRGB AppImage launcher/binary from ~/.local/bin ?"; then
    rm -f "$APPIMAGE_WRAPPER" || true
    rm -f "$APPIMAGE_BIN" || true
    log_ok "Removed AppImage launcher/binary (if present)"
  else
    log_info "Skipped removing AppImage launcher/binary"
  fi
fi

APP_FILE="$HOME/.local/share/applications/keyrgb.desktop"
AUTOSTART_FILE="$HOME/.config/autostart/keyrgb.desktop"
ICON_FILE_PNG="$HOME/.local/share/icons/keyrgb.png"
ICON_FILE_SVG="$HOME/.local/share/icons/keyrgb.svg"
ICON_FILE_JPG="$HOME/.local/share/icons/keyrgb.jpg"
ICON_FILE_THEME_PNG="$HOME/.local/share/icons/hicolor/256x256/apps/keyrgb.png"
ICON_FILE_THEME_SVG="$HOME/.local/share/icons/hicolor/scalable/apps/keyrgb.svg"

if confirm "Remove desktop launcher + autostart entries?"; then
  rm -f "$APP_FILE" || true
  rm -f "$AUTOSTART_FILE" || true
  rm -f "$ICON_FILE_PNG" || true
  rm -f "$ICON_FILE_SVG" || true
  rm -f "$ICON_FILE_JPG" || true
  rm -f "$ICON_FILE_THEME_PNG" || true
  rm -f "$ICON_FILE_THEME_SVG" || true
  refresh_desktop_integration_caches_best_effort || true
  log_ok "Removed desktop entries + icon (if present)"
else
  log_info "Skipped removing desktop entries"
fi

if confirm "Uninstall Python packages (keyrgb, plus legacy helper packages if present) from your user site-packages?"; then
  python3 -m pip uninstall -y keyrgb >/dev/null 2>&1 || true
  # Older KeyRGB installs pulled in the external helper package separately.
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
POWER_POLKIT_ACTION_DST="/usr/share/polkit-1/actions/org.keyrgb.power-helper.policy"
POWER_POLKIT_ACTION_SRC="$REPO_DIR/system/polkit/org.keyrgb.power-helper.policy"

maybe_remove_udev_rule() {
  local dst="$1" src="$2" label="$3" is_managed_fn="$4" post_remove_note="${5:-}"
  if [ ! -f "$dst" ]; then
    return 0
  fi

  local matches_repo=0
  if files_match_exactly "$src" "$dst"; then
    matches_repo=1
  fi
  local looks_like_keyrgb=0
  if "$is_managed_fn" "$dst"; then
    looks_like_keyrgb=1
  fi

  if [ "$matches_repo" -eq 1 ] || [ "$looks_like_keyrgb" -eq 1 ]; then
    if [ "$matches_repo" -ne 1 ]; then
      log_warn "$label does not match this repo version, but appears to be KeyRGB-managed: $dst"
    fi
    if confirm "Remove $label $dst (requires sudo)?"; then
      sudo rm -f "$dst"
      reload_udev_rules_best_effort
      log_ok "Removed $label"
      if [ -n "$post_remove_note" ]; then
        log_info "$post_remove_note"
      fi
    else
      log_info "Skipped removing $label"
    fi
  else
    log_warn "$label exists but does not look KeyRGB-managed; not removing: $dst"
  fi
}

maybe_remove_udev_rule "$UDEV_DST" "$UDEV_SRC" "udev rule" is_keyrgb_managed_usb_udev_rule
maybe_remove_udev_rule "$SYSFS_UDEV_DST" "$SYSFS_UDEV_SRC" "sysfs LED udev rule" is_keyrgb_managed_sysfs_udev_rule
maybe_remove_udev_rule \
  "$INPUT_UDEV_DST" \
  "$INPUT_UDEV_SRC" \
  "Reactive Typing input udev rule" \
  is_keyrgb_managed_input_udev_rule \
  "You may need to log out/in for ACLs to refresh."

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

if [ -f "$POWER_POLKIT_ACTION_DST" ]; then
  action_matches_repo=0
  if [ -f "$POWER_POLKIT_ACTION_SRC" ] && cmp -s "$POWER_POLKIT_ACTION_SRC" "$POWER_POLKIT_ACTION_DST"; then
    action_matches_repo=1
  fi
  action_looks_like_keyrgb=0
  if file_has_marker "$POWER_POLKIT_ACTION_DST" "org.keyrgb.power-helper.apply"; then
    action_looks_like_keyrgb=1
  fi

  if [ "$action_matches_repo" -eq 1 ] || [ "$action_looks_like_keyrgb" -eq 1 ]; then
    if [ "$action_matches_repo" -ne 1 ]; then
      log_warn "Power Mode polkit action does not match this repo version, but appears KeyRGB-managed: $POWER_POLKIT_ACTION_DST"
    fi
    if confirm "Remove Power Mode polkit action (requires sudo)?"; then
      sudo rm -f "$POWER_POLKIT_ACTION_DST" || true
      log_ok "Removed Power Mode polkit action"
    else
      log_info "Skipped removing Power Mode polkit action"
    fi
  else
    log_warn "Power Mode polkit action exists but does not look KeyRGB-managed; not removing: $POWER_POLKIT_ACTION_DST"
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
