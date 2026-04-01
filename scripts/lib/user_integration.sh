#!/usr/bin/env bash

# Desktop integration + udev rules + AppImage install helpers.

set -euo pipefail

is_appimage_file() {
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

refresh_desktop_integration_caches_best_effort() {
  local icon_theme_dir="$HOME/.local/share/icons/hicolor"
  local app_dir="$HOME/.local/share/applications"

  if have_cmd gtk-update-icon-cache && [ -d "$icon_theme_dir" ]; then
    gtk-update-icon-cache -f -t "$icon_theme_dir" >/dev/null 2>&1 || \
      log_warn "Could not refresh GTK icon cache automatically"
  fi

  if have_cmd update-desktop-database && [ -d "$app_dir" ]; then
    update-desktop-database "$app_dir" >/dev/null 2>&1 || \
      log_warn "Could not refresh desktop database automatically"
  fi

  if have_cmd kbuildsycoca6; then
    kbuildsycoca6 >/dev/null 2>&1 || log_warn "Could not refresh KDE service cache automatically"
  elif have_cmd kbuildsycoca5; then
    kbuildsycoca5 >/dev/null 2>&1 || log_warn "Could not refresh KDE service cache automatically"
  fi
}

local_icon_asset_path() {
  local relative_path="$1"
  local repo_dir
  repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

  if [ -f "$repo_dir/$relative_path" ]; then
    printf '%s' "$repo_dir/$relative_path"
    return 0
  fi

  return 1
}

install_icon_asset() {
  local relative_path="$1" dst_path="$2" raw_ref="$3" label="$4"
  local local_src=""

  local_src="$(local_icon_asset_path "$relative_path" 2>/dev/null || true)"
  if [ -n "$local_src" ] && [ -f "$local_src" ]; then
    log_info "Installing $label from local checkout: $local_src"
    install -D -m 0644 "$local_src" "$dst_path"
    return 0
  fi

  local asset_url="https://raw.githubusercontent.com/${KEYRGB_REPO_OWNER}/${KEYRGB_REPO_NAME}/${raw_ref}/${relative_path}"
  log_info "Downloading $label: $asset_url"
  if download_url_quiet "$asset_url" "$dst_path"; then
    return 0
  fi

  if [ "$raw_ref" != "main" ]; then
    local fallback_url="https://raw.githubusercontent.com/${KEYRGB_REPO_OWNER}/${KEYRGB_REPO_NAME}/main/${relative_path}"
    log_warn "Failed to download $label from ref '$raw_ref'; trying main: $fallback_url"
    if download_url_quiet "$fallback_url" "$dst_path"; then
      return 0
    fi
  fi

  rm -f "$dst_path" 2>/dev/null || true
  return 1
}

# --- Desktop integration + system rules ---
install_icon_and_desktop_entries() {
  local keyrgb_exec="$1" raw_ref="$2"

  local icon_dir_legacy="$HOME/.local/share/icons"
  local icon_file_legacy_svg="$icon_dir_legacy/keyrgb.svg"
  local icon_dir_svg="$HOME/.local/share/icons/hicolor/scalable/apps"
  local icon_file_svg="$icon_dir_svg/keyrgb.svg"
  local app_dir="$HOME/.local/share/applications"
  local app_file="$app_dir/keyrgb.desktop"
  local autostart_dir="$HOME/.config/autostart"
  local autostart_file="$autostart_dir/keyrgb.desktop"

  mkdir -p "$icon_dir_legacy" "$icon_dir_svg" "$app_dir" "$autostart_dir"

  local desktop_icon="$icon_file_svg"
  if install_icon_asset "assets/logo-keyrgb.svg" "$icon_file_svg" "$raw_ref" "scalable icon"; then
    log_ok "Installed scalable icon: $icon_file_svg"
    cp -f "$icon_file_svg" "$icon_file_legacy_svg"

    # Remove any stale raster icon so launchers do not keep picking the legacy art.
    rm -f "$icon_dir_legacy/keyrgb.png" 2>/dev/null || true
    rm -f "$HOME/.local/share/icons/hicolor/256x256/apps/keyrgb.png" 2>/dev/null || true
  elif install_icon_asset "assets/legacy/logo-tray-squircle.png" "$icon_dir_legacy/keyrgb.png" "$raw_ref" "legacy raster icon"; then
    desktop_icon="$icon_dir_legacy/keyrgb.png"
    rm -f "$icon_file_svg" 2>/dev/null || true
    rm -f "$icon_file_legacy_svg" 2>/dev/null || true
    log_warn "Using legacy PNG icon fallback because the SVG icon could not be installed"
  else
    rm -f "$icon_file_svg" 2>/dev/null || true
    rm -f "$icon_file_legacy_svg" 2>/dev/null || true
    rm -f "$icon_dir_legacy/keyrgb.png" 2>/dev/null || true
    log_warn "Could not install any desktop icon; keeping launcher entries without refreshing the icon asset"
    desktop_icon="keyrgb"
  fi

  rm -f "$icon_dir_legacy/keyrgb.jpg" 2>/dev/null || true

  cat >"$app_file" <<EOF
[Desktop Entry]
Type=Application
Name=KeyRGB
Comment=RGB Keyboard Controller
Exec=$keyrgb_exec
Icon=$desktop_icon
Terminal=false
Categories=Utility;System;
StartupNotify=false
EOF

  cat >"$autostart_file" <<EOF
[Desktop Entry]
Type=Application
Name=KeyRGB
Comment=RGB Keyboard Controller
Exec=$keyrgb_exec
Icon=$desktop_icon
Terminal=false
Categories=Utility;System;
X-KDE-autostart-after=plasma-workspace
X-KDE-StartupNotify=false
EOF

  refresh_desktop_integration_caches_best_effort
  log_ok "Desktop launcher installed + autostart configured"
}

reload_udev_rules_best_effort() {
  if have_cmd udevadm; then
    sudo udevadm control --reload-rules || true
    # Default is usually action=change; keep it explicit so behavior is stable.
    sudo udevadm trigger --action=change || true

    # Some systems (notably some Ubuntu LTS installs) can be conservative about
    # reapplying ACLs for already-present internal devices. Send targeted add
    # events as a best-effort nudge.
    sudo udevadm trigger --action=add --subsystem-match=usb --attr-match=idVendor=048d || true
    sudo udevadm trigger --action=add --subsystem-match=input --property-match=ID_INPUT_KEYBOARD=1 || true
    sudo udevadm trigger --action=add --subsystem-match=leds || true

    sudo udevadm settle || true
    log_ok "Reloaded udev rules"
    log_info "If permissions still don't update, try logging out/in or rebooting (some systems apply uaccess ACLs only at boot/login)."
  else
    log_warn "udevadm not found; cannot reload udev rules automatically"
  fi
}

install_udev_rule_from_ref() {
  local raw_ref="$1"
  local dst_usb_rule="/etc/udev/rules.d/99-ite8291-wootbook.rules"
  local dst_sysfs_rule="/etc/udev/rules.d/99-keyrgb-sysfs-leds.rules"

  if ! have_cmd udevadm; then
    log_warn "udevadm not found; cannot install udev rule automatically."
    log_warn "Copy the rules manually to: $dst_usb_rule and $dst_sysfs_rule"
    return 0
  fi

  _install_rule() {
    local filename="$1" dst="$2"

    local tmp_rule
    tmp_rule="$(mktemp)"

    local rule_url="https://raw.githubusercontent.com/${KEYRGB_REPO_OWNER}/${KEYRGB_REPO_NAME}/${raw_ref}/system/udev/${filename}"
    log_info "Downloading udev rule: $rule_url"
    if ! download_url_quiet "$rule_url" "$tmp_rule"; then
      if [ "$raw_ref" != "main" ]; then
        local rule_url_fallback="https://raw.githubusercontent.com/${KEYRGB_REPO_OWNER}/${KEYRGB_REPO_NAME}/main/system/udev/${filename}"
        log_warn "Failed to download udev rule from ref '$raw_ref'; trying main: $rule_url_fallback"
        if ! download_url_quiet "$rule_url_fallback" "$tmp_rule"; then
          log_warn "Failed to download udev rule: ${filename}"
          rm -f "$tmp_rule" 2>/dev/null || true
          return 0
        fi
      else
        log_warn "Failed to download udev rule: ${filename}"
        rm -f "$tmp_rule" 2>/dev/null || true
        return 0
      fi
    fi

    log_info "Installing udev rule (requires sudo): $dst"
    sudo install -D -m 0644 "$tmp_rule" "$dst"
    rm -f "$tmp_rule" 2>/dev/null || true
  }

  # 1) USB direct backends (ITE 8291r3) permissions
  _install_rule "99-ite8291-wootbook.rules" "$dst_usb_rule"
  # 2) Sysfs LED backends (kernel drivers) permissions
  _install_rule "99-keyrgb-sysfs-leds.rules" "$dst_sysfs_rule"

  reload_udev_rules_best_effort
}

install_input_udev_rule_local() {
  local src_rule="$1"
  local dst_rule="/etc/udev/rules.d/99-keyrgb-input-uaccess.rules"

  if ! have_cmd udevadm; then
    log_warn "udevadm not found; cannot install input udev rule automatically."
    log_warn "Copy the rule manually to: $dst_rule"
    return 0
  fi

  if [ ! -f "$src_rule" ]; then
    log_warn "input udev rule file not found: $src_rule"
    return 0
  fi

  log_info "Installing input udev rule (requires sudo): $dst_rule"
  sudo install -D -m 0644 "$src_rule" "$dst_rule"
  reload_udev_rules_best_effort
}

install_input_udev_rule_from_ref() {
  local raw_ref="$1"
  local dst_rule="/etc/udev/rules.d/99-keyrgb-input-uaccess.rules"

  if ! have_cmd udevadm; then
    log_warn "udevadm not found; cannot install input udev rule automatically."
    log_warn "Copy the rule manually to: $dst_rule"
    return 0
  fi

  local tmp_rule
  tmp_rule="$(mktemp)"

  local rule_url="https://raw.githubusercontent.com/${KEYRGB_REPO_OWNER}/${KEYRGB_REPO_NAME}/${raw_ref}/system/udev/99-keyrgb-input-uaccess.rules"
  log_info "Downloading input udev rule: $rule_url"
  if ! download_url_quiet "$rule_url" "$tmp_rule"; then
    if [ "$raw_ref" != "main" ]; then
      local rule_url_fallback="https://raw.githubusercontent.com/${KEYRGB_REPO_OWNER}/${KEYRGB_REPO_NAME}/main/system/udev/99-keyrgb-input-uaccess.rules"
      log_warn "Failed to download input udev rule from ref '$raw_ref'; trying main: $rule_url_fallback"
      if ! download_url_quiet "$rule_url_fallback" "$tmp_rule"; then
        log_warn "Failed to download input udev rule"
        rm -f "$tmp_rule" 2>/dev/null || true
        return 0
      fi
    else
      log_warn "Failed to download input udev rule"
      rm -f "$tmp_rule" 2>/dev/null || true
      return 0
    fi
  fi

  log_info "Installing input udev rule (requires sudo): $dst_rule"
  sudo install -D -m 0644 "$tmp_rule" "$dst_rule"
  rm -f "$tmp_rule" 2>/dev/null || true
  reload_udev_rules_best_effort
}

# --- AppImage install ---
appimage_install() {
  local dst_path="$1" asset_name="$2" version_tag="$3" allow_prerelease="$4"
  mkdir -p "$(dirname "$dst_path")"

  local url="" resolved_tag=""
  local resolved_prerelease="false"

  if [ -n "$version_tag" ]; then
    url="https://github.com/${KEYRGB_REPO_OWNER}/${KEYRGB_REPO_NAME}/releases/download/${version_tag}/${asset_name}"
    resolved_tag="$version_tag"
  else
    local resolved=""
    resolved="$(resolve_release_with_asset "$asset_name" "$allow_prerelease" 2>/dev/null)" || true
    if [ -n "$resolved" ]; then
      local resolved_url
      IFS='|' read -r resolved_tag resolved_url resolved_prerelease <<<"$resolved"
      url="$resolved_url"
    else
      url="https://github.com/${KEYRGB_REPO_OWNER}/${KEYRGB_REPO_NAME}/releases/latest/download/${asset_name}"
      resolved_tag="main"
    fi
  fi

  if [ -n "$resolved_tag" ] && [ "$resolved_tag" != "main" ]; then
    if [ "$resolved_prerelease" = "true" ]; then
      log_info "Selected release: $resolved_tag (prerelease)"
    else
      log_info "Selected release: $resolved_tag"
    fi
  fi

  log_info "Downloading AppImage (this may take a while): $url"
  download_url_progress "$url" "$dst_path"
  chmod +x "$dst_path"
  log_ok "Installed AppImage: $dst_path"

  printf '%s' "$resolved_tag"
}

install_appimage_launcher() {
  local launcher_path="$1" appimage_path="$2"
  mkdir -p "$(dirname "$launcher_path")"

  cat >"$launcher_path" <<EOF
#!/usr/bin/env bash

# KeyRGB AppImage launcher.
# Falls back to AppImage extract-and-run mode on hosts without libfuse.so.2.

set -euo pipefail

APPIMAGE_PATH="$appimage_path"

has_libfuse2() {
  if command -v ldconfig >/dev/null 2>&1; then
    if ldconfig -p 2>/dev/null | grep -Fq "libfuse.so.2"; then
      return 0
    fi
  fi

  local candidate
  for candidate in \
    /lib/libfuse.so.2 \
    /lib/libfuse.so.2.* \
    /lib64/libfuse.so.2 \
    /lib64/libfuse.so.2.* \
    /usr/lib/libfuse.so.2 \
    /usr/lib/libfuse.so.2.* \
    /usr/lib64/libfuse.so.2 \
    /usr/lib64/libfuse.so.2.*
  do
    if [ -e "\$candidate" ]; then
      return 0
    fi
  done

  return 1
}

if [ ! -x "\$APPIMAGE_PATH" ]; then
  echo "KeyRGB AppImage not found or not executable: \$APPIMAGE_PATH" >&2
  exit 1
fi

if has_libfuse2; then
  exec "\$APPIMAGE_PATH" "\$@"
fi

exec "\$APPIMAGE_PATH" --appimage-extract-and-run "\$@"
EOF

  chmod +x "$launcher_path"
  log_ok "Installed AppImage launcher: $launcher_path"
}

warn_if_no_usb_device_best_effort() {
  if ! have_cmd lsusb; then
    return 0
  fi

  # Some supported laptops expose keyboard lighting via kernel sysfs LEDs (e.g.
  # tuxedo_keyboard / clevo_wmi) and won't show an ITE USB controller in lsusb.
  # Avoid a confusing warning in that case.
  if [ -d /sys/class/leds ]; then
    if ls /sys/class/leds 2>/dev/null | grep -Eqi "kbd_backlight"; then
      return 0
    fi
  fi

  # Common supported ITE 8291r3 IDs.
  if ! lsusb | grep -Eqi "048d:(6004|6006|6008|600b|ce00)"; then
    log_warn "Supported ITE 8291 USB device not detected (best-effort check)."
    log_warn "Expected one of: 048d:6004, 048d:6006, 048d:6008, 048d:600b, 048d:ce00"
  fi
}

warn_if_local_bin_missing_from_path() {
  local user_bin="$HOME/.local/bin"
  if ! printf '%s' ":$PATH:" | grep -q ":$user_bin:"; then
    log_warn "Your PATH does not include $user_bin"
    log_warn "Add to ~/.profile: export PATH=\"$user_bin:\$PATH\""
  fi
}
