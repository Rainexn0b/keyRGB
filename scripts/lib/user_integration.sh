#!/usr/bin/env bash

# Desktop integration + udev rules + AppImage install helpers.

set -euo pipefail

# --- Desktop integration + system rules ---
install_icon_and_desktop_entries() {
  local keyrgb_exec="$1" raw_ref="$2"

  local icon_dir="$HOME/.local/share/icons/hicolor/256x256/apps"
  local icon_file="$icon_dir/keyrgb.png"
  local app_dir="$HOME/.local/share/applications"
  local app_file="$app_dir/keyrgb.desktop"
  local autostart_dir="$HOME/.config/autostart"
  local autostart_file="$autostart_dir/keyrgb.desktop"

  mkdir -p "$icon_dir" "$app_dir" "$autostart_dir"

  local icon_url="https://raw.githubusercontent.com/${KEYRGB_REPO_OWNER}/${KEYRGB_REPO_NAME}/${raw_ref}/assets/logo-keyrgb.png"
  log_info "Downloading icon: $icon_url"
  download_url_quiet "$icon_url" "$icon_file"
  log_ok "Installed icon: $icon_file"

  cat >"$app_file" <<EOF
[Desktop Entry]
Type=Application
Name=KeyRGB
Comment=RGB Keyboard Controller
Exec=$keyrgb_exec
Icon=keyrgb
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
Icon=keyrgb
Terminal=false
Categories=Utility;System;
X-KDE-autostart-after=plasma-workspace
X-KDE-StartupNotify=false
EOF

  log_ok "Desktop launcher installed + autostart configured"
}

reload_udev_rules_best_effort() {
  if have_cmd udevadm; then
    sudo udevadm control --reload-rules || true
    sudo udevadm trigger || true
    log_ok "Reloaded udev rules"
  else
    log_warn "udevadm not found; cannot reload udev rules automatically"
  fi
}

install_udev_rule_from_ref() {
  local raw_ref="$1"
  local dst_rule="/etc/udev/rules.d/99-ite8291-wootbook.rules"

  if ! have_cmd udevadm; then
    log_warn "udevadm not found; cannot install udev rule automatically."
    log_warn "Copy the rule manually to: $dst_rule"
    return 0
  fi

  local tmp_rule
  tmp_rule="$(mktemp)"

  local rule_url="https://raw.githubusercontent.com/${KEYRGB_REPO_OWNER}/${KEYRGB_REPO_NAME}/${raw_ref}/system/udev/99-ite8291-wootbook.rules"
  log_info "Downloading udev rule: $rule_url"
  download_url_quiet "$rule_url" "$tmp_rule"

  log_info "Installing udev rule (requires sudo): $dst_rule"
  sudo install -D -m 0644 "$tmp_rule" "$dst_rule"
  rm -f "$tmp_rule" 2>/dev/null || true

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
  download_url "$url" "$dst_path"
  chmod +x "$dst_path"
  log_ok "Installed AppImage: $dst_path"

  printf '%s' "$resolved_tag"
}

warn_if_no_usb_device_best_effort() {
  if ! have_cmd lsusb; then
    return 0
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
