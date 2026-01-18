#!/usr/bin/env bash

# Installer state helpers (best-effort).

set -euo pipefail

STATE_DIR="${HOME}/.local/share/keyrgb"
INSTALLER_STATE_FILE="$STATE_DIR/installer-state"

load_saved_appimage_prefs() {
  # Uses global variables if present:
  # - KEYRGB_ALLOW_PRERELEASE_SET (0/1)
  # - KEYRGB_APPIMAGE_ASSET_SET (0/1)
  # - KEYRGB_ALLOW_PRERELEASE
  # - KEYRGB_APPIMAGE_ASSET

  [ -f "$INSTALLER_STATE_FILE" ] || return 0

  local allow_set="${KEYRGB_ALLOW_PRERELEASE_SET:-0}"
  local asset_set="${KEYRGB_APPIMAGE_ASSET_SET:-0}"

  local line key val
  while IFS= read -r line || [ -n "$line" ]; do
    case "$line" in
      ""|\#*) continue ;;
    esac

    key="${line%%=*}"
    val="${line#*=}"

    case "$key" in
      allow_prerelease)
        if [ "$allow_set" -eq 0 ]; then
          case "${val,,}" in
            y|yes|1|true) KEYRGB_ALLOW_PRERELEASE="y" ;;
            n|no|0|false) KEYRGB_ALLOW_PRERELEASE="n" ;;
          esac
        fi
        ;;
      appimage_asset)
        if [ "$asset_set" -eq 0 ]; then
          if printf '%s' "$val" | grep -Eq '^[A-Za-z0-9._-]+$'; then
            KEYRGB_APPIMAGE_ASSET="$val"
          fi
        fi
        ;;
    esac
  done < "$INSTALLER_STATE_FILE"
}

save_appimage_prefs_best_effort() {
  mkdir -p "$STATE_DIR" 2>/dev/null || true

  {
    printf '%s\n' "# KeyRGB installer state (best-effort)"
    printf '%s\n' "install_mode=appimage"
    printf '%s\n' "allow_prerelease=${KEYRGB_ALLOW_PRERELEASE:-n}"
    printf '%s\n' "appimage_asset=${KEYRGB_APPIMAGE_ASSET:-keyrgb-x86_64.AppImage}"
    if [ -n "${KEYRGB_VERSION:-}" ]; then
      printf '%s\n' "last_tag=${KEYRGB_VERSION}"
    fi
  } > "$INSTALLER_STATE_FILE" 2>/dev/null || true
}
