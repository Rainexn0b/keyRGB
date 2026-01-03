#!/bin/bash
# KeyRGB Uninstall Script
#
# Removes what install.sh installs:
# - user-level pip installs of keyrgb + ite8291r3-ctl (pip install mode)
# - AppImage binary at ~/.local/bin/keyrgb (AppImage mode)
# - desktop launcher and autostart entries
# - udev rule (with sudo) if it matches this repo's rule
# - optional: input udev rule for Reactive Typing (/dev/input access) if it matches this repo's rule
# - power mode helper + polkit rule (with sudo) if they match this repo's files
# - optionally: Tuxedo Control Center (dnf) ONLY if installed by KeyRGB (marker file)
#
# By default this script does NOT remove system packages installed via dnf.
# The only exception is Tuxedo Control Center, and only when a KeyRGB marker file indicates KeyRGB installed it.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ "${EUID:-0}" -eq 0 ]; then
  echo "❌ Please run without sudo (script will ask for password when needed)" >&2
  exit 1
fi

YES=0
PURGE_CONFIG=0
REMOVE_APPIMAGE=0

usage() {
  cat <<'EOF'
Usage: ./uninstall.sh [--yes] [--purge-config] [--remove-appimage]

--yes             Do not prompt (best-effort).
--purge-config    Also remove ~/.config/keyrgb (profiles/settings).
--remove-appimage Remove ~/.local/bin/keyrgb if it looks like an AppImage.

Notes:
  - This script removes both AppImage-mode and pip-mode installs (with prompts).
  - It does NOT remove system packages installed via dnf (except optional TCC removal when KeyRGB installed it).
EOF
}

for arg in "$@"; do
  case "$arg" in
    -y|--yes) YES=1 ;;
    --purge-config) PURGE_CONFIG=1 ;;
    --remove-appimage) REMOVE_APPIMAGE=1 ;;
    -h|--help) usage; exit 0 ;;
    *)
      echo "Unknown argument: $arg" >&2
      usage
      exit 2
      ;;
  esac
done

confirm() {
  local prompt="$1"
  if [ "$YES" -eq 1 ] || ! [ -t 0 ]; then
    return 0
  fi
  read -r -p "$prompt [y/N] " reply || reply=""
  reply="${reply,,}"
  [[ "$reply" == "y" || "$reply" == "yes" ]]
}

STATE_DIR="$HOME/.local/share/keyrgb"
TCC_MARKER="$STATE_DIR/tcc-installed-by-keyrgb"

echo "=== KeyRGB Uninstall ==="
echo

looks_like_appimage() {
  local path="$1"
  if ! [ -f "$path" ]; then
    return 1
  fi

  python3 - "$path" <<'PY'
from __future__ import annotations

import sys
from pathlib import Path

p = Path(sys.argv[1])
data = p.read_bytes()

if not data.startswith(b"\x7fELF"):
    raise SystemExit(1)

# Heuristic: many AppImages embed the string "AppImage" somewhere in the file.
if b"AppImage" in data[:2_000_000]:
    raise SystemExit(0)
raise SystemExit(1)
PY
}

APPIMAGE_BIN="$HOME/.local/bin/keyrgb"
if [ "$REMOVE_APPIMAGE" -eq 1 ] && looks_like_appimage "$APPIMAGE_BIN"; then
  rm -f "$APPIMAGE_BIN" || true
  echo "✓ Removed AppImage binary: $APPIMAGE_BIN"
elif looks_like_appimage "$APPIMAGE_BIN"; then
  if confirm "Remove AppImage binary $APPIMAGE_BIN ?"; then
    rm -f "$APPIMAGE_BIN" || true
    echo "✓ Removed AppImage binary"
  else
    echo "↷ Skipped removing AppImage binary"
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
  echo "✓ Removed desktop entries + icon (if present)"
else
  echo "↷ Skipped removing desktop entries"
fi

if confirm "Uninstall Python packages (keyrgb, ite8291r3-ctl) from your user site-packages?"; then
  # Best-effort: uninstall the two packages that install.sh installs explicitly.
  python3 -m pip uninstall -y keyrgb >/dev/null 2>&1 || true
  python3 -m pip uninstall -y ite8291r3-ctl >/dev/null 2>&1 || true
  # Some environments register the dist name slightly differently.
  python3 -m pip uninstall -y ite8291r3_ctl >/dev/null 2>&1 || true
  echo "✓ Uninstalled pip packages (best-effort)"
else
  echo "↷ Skipped pip uninstall"
fi

UDEV_DST="/etc/udev/rules.d/99-ite8291-wootbook.rules"
UDEV_SRC="$REPO_DIR/system/udev/99-ite8291-wootbook.rules"

INPUT_UDEV_DST="/etc/udev/rules.d/99-keyrgb-input-uaccess.rules"
INPUT_UDEV_SRC="$REPO_DIR/system/udev/99-keyrgb-input-uaccess.rules"

if [ -f "$UDEV_DST" ]; then
  if [ -f "$UDEV_SRC" ] && cmp -s "$UDEV_SRC" "$UDEV_DST"; then
    if confirm "Remove udev rule $UDEV_DST (requires sudo)?"; then
      sudo rm -f "$UDEV_DST"
      if command -v udevadm >/dev/null 2>&1; then
        sudo udevadm control --reload-rules || true
        sudo udevadm trigger || true
      fi
      echo "✓ Removed udev rule"
    else
      echo "↷ Skipped removing udev rule"
    fi
  else
    echo "⚠️  udev rule exists but does not match this repo's rule; not removing: $UDEV_DST"
  fi
fi

if [ -f "$INPUT_UDEV_DST" ]; then
  if [ -f "$INPUT_UDEV_SRC" ] && cmp -s "$INPUT_UDEV_SRC" "$INPUT_UDEV_DST"; then
    if confirm "Remove Reactive Typing input udev rule $INPUT_UDEV_DST (requires sudo)?"; then
      sudo rm -f "$INPUT_UDEV_DST"
      if command -v udevadm >/dev/null 2>&1; then
        sudo udevadm control --reload-rules || true
        sudo udevadm trigger || true
      fi
      echo "✓ Removed Reactive Typing input udev rule"
      echo "  Note: you may need to log out/in for ACLs to refresh."
    else
      echo "↷ Skipped removing Reactive Typing input udev rule"
    fi
  else
    echo "⚠️  Reactive Typing input udev rule exists but does not match this repo's rule; not removing: $INPUT_UDEV_DST"
  fi
fi

POWER_HELPER_DST="/usr/local/bin/keyrgb-power-helper"
POWER_HELPER_SRC="$REPO_DIR/system/bin/keyrgb-power-helper"
POLKIT_DST="/etc/polkit-1/rules.d/90-keyrgb-power-helper.rules"
POLKIT_SRC="$REPO_DIR/system/polkit/90-keyrgb-power-helper.rules"

if [ -f "$POWER_HELPER_DST" ] || [ -f "$POLKIT_DST" ]; then
  # Only remove if the installed files match the repo versions.
  helper_matches=0
  rule_matches=0

  if [ -f "$POWER_HELPER_DST" ] && [ -f "$POWER_HELPER_SRC" ] && cmp -s "$POWER_HELPER_SRC" "$POWER_HELPER_DST"; then
    helper_matches=1
  fi
  if [ -f "$POLKIT_DST" ] && [ -f "$POLKIT_SRC" ] && cmp -s "$POLKIT_SRC" "$POLKIT_DST"; then
    rule_matches=1
  fi

  if [ -f "$POWER_HELPER_DST" ] && [ "$helper_matches" -ne 1 ]; then
    echo "⚠️  Power helper exists but does not match this repo's helper; not removing: $POWER_HELPER_DST"
  fi
  if [ -f "$POLKIT_DST" ] && [ "$rule_matches" -ne 1 ]; then
    echo "⚠️  Polkit rule exists but does not match this repo's rule; not removing: $POLKIT_DST"
  fi

  if [ "$helper_matches" -eq 1 ] || [ "$rule_matches" -eq 1 ]; then
    if confirm "Remove Power Mode helper + polkit rule (requires sudo)?"; then
      if [ "$helper_matches" -eq 1 ]; then
        sudo rm -f "$POWER_HELPER_DST"
        echo "✓ Removed power helper: $POWER_HELPER_DST"
      fi
      if [ "$rule_matches" -eq 1 ]; then
        sudo rm -f "$POLKIT_DST"
        echo "✓ Removed polkit rule: $POLKIT_DST"
      fi
      echo "  Note: you may need to log out/in for polkit caches to refresh."
    else
      echo "↷ Skipped removing Power Mode helper"
    fi
  fi
fi

if [ -f "$TCC_MARKER" ]; then
  if command -v dnf >/dev/null 2>&1; then
    if rpm -q tuxedo-control-center >/dev/null 2>&1; then
      if confirm "Uninstall Tuxedo Control Center (tuxedo-control-center) that was installed by KeyRGB (requires sudo)?"; then
        set +e
        sudo dnf remove -y tuxedo-control-center
        rc=$?
        set -e
        if [ $rc -eq 0 ]; then
          echo "✓ Removed tuxedo-control-center"
          rm -f "$TCC_MARKER" || true
        else
          echo "⚠️  Failed to remove tuxedo-control-center via dnf (exit $rc)."
          echo "   Marker file left in place: $TCC_MARKER"
        fi
      else
        echo "↷ Skipped removing tuxedo-control-center"
      fi
    else
      # Marker exists, but package isn't installed anymore.
      rm -f "$TCC_MARKER" || true
    fi
  else
    echo "⚠️  dnf not found; cannot remove tuxedo-control-center automatically."
    echo "   Marker file: $TCC_MARKER"
  fi
fi

if [ "$PURGE_CONFIG" -eq 1 ]; then
  if confirm "Remove ~/.config/keyrgb (profiles/settings)?"; then
    rm -rf "$HOME/.config/keyrgb" || true
    echo "✓ Removed ~/.config/keyrgb"
  else
    echo "↷ Skipped removing ~/.config/keyrgb"
  fi
fi

echo
echo "=== Uninstall complete ==="
echo "Note: install.sh also installs system packages via dnf; those are not removed by default."
