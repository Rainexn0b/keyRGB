#!/bin/bash
# KeyRGB Uninstall Script
#
# Removes what install.sh installs:
# - user-level pip installs of keyrgb + ite8291r3-ctl
# - desktop launcher and autostart entries
# - udev rule (with sudo) if it matches this repo's rule
#
# Does NOT remove system packages installed via dnf.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ "${EUID:-0}" -eq 0 ]; then
  echo "❌ Please run without sudo (script will ask for password when needed)" >&2
  exit 1
fi

YES=0
PURGE_CONFIG=0

usage() {
  cat <<'EOF'
Usage: ./uninstall.sh [--yes] [--purge-config]

--yes          Do not prompt (best-effort).
--purge-config Also remove ~/.config/keyrgb (profiles/settings).
EOF
}

for arg in "$@"; do
  case "$arg" in
    -y|--yes) YES=1 ;;
    --purge-config) PURGE_CONFIG=1 ;;
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

echo "=== KeyRGB Uninstall ==="
echo

APP_FILE="$HOME/.local/share/applications/keyrgb.desktop"
AUTOSTART_FILE="$HOME/.config/autostart/keyrgb.desktop"

if confirm "Remove desktop launcher + autostart entries?"; then
  rm -f "$APP_FILE" || true
  rm -f "$AUTOSTART_FILE" || true
  echo "✓ Removed desktop entries (if present)"
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
UDEV_SRC="$REPO_DIR/packaging/udev/99-ite8291-wootbook.rules"

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
echo "Note: install.sh also installs system packages via dnf; those are not removed."
