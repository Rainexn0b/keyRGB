#!/usr/bin/env bash

# pkexec helpers + polkit rules installation (best-effort).

set -euo pipefail

should_install_power_helper() {
  is_truthy "${KEYRGB_INSTALL_POWER_HELPER:-y}"
}

install_privileged_helpers_local() {
  local repo_dir="$1"

  if is_truthy "${KEYRGB_SKIP_PRIVILEGED_HELPERS:-n}"; then
    log_info "Skipping privileged helper install (KEYRGB_SKIP_PRIVILEGED_HELPERS)."
    return 0
  fi

  local polkit_dir="/etc/polkit-1/rules.d"
  if [ ! -d "$polkit_dir" ]; then
    log_warn "polkit rules directory not found: $polkit_dir"
    log_warn "Skipping privileged helper install."
    return 0
  fi

  local did_any=0

  if should_install_power_helper; then
    if [ -f "$repo_dir/system/bin/keyrgb-power-helper" ] && [ -f "$repo_dir/system/polkit/90-keyrgb-power-helper.rules" ]; then
      log_info "Installing Power Mode helper from local repo (requires sudo)..."
      sudo install -D -m 0755 "$repo_dir/system/bin/keyrgb-power-helper" /usr/local/bin/keyrgb-power-helper
      sudo install -D -m 0644 "$repo_dir/system/polkit/90-keyrgb-power-helper.rules" "$polkit_dir/90-keyrgb-power-helper.rules"
      did_any=1
    else
      log_warn "Local Power Mode helper/rule not found; skipping local install."
    fi
  fi

  if [ "$did_any" -eq 1 ]; then
    log_ok "Privileged helpers installed (local)"
  fi
}

install_privileged_helpers_from_ref() {
  local raw_ref="$1"

  if is_truthy "${KEYRGB_SKIP_PRIVILEGED_HELPERS:-n}"; then
    log_info "Skipping privileged helper install (KEYRGB_SKIP_PRIVILEGED_HELPERS)."
    return 0
  fi

  local polkit_dir="/etc/polkit-1/rules.d"
  if [ ! -d "$polkit_dir" ]; then
    log_warn "polkit rules directory not found: $polkit_dir"
    log_warn "Skipping privileged helper install."
    return 0
  fi

  local tmp
  tmp="$(mktemp -d)"
  trap 'rm -rf "$tmp"' RETURN

  local entries=()
  if should_install_power_helper; then
    entries+=("keyrgb-power-helper|90-keyrgb-power-helper.rules")
  fi

  if [ ${#entries[@]} -eq 0 ]; then
    log_info "No privileged helpers selected for install."
    return 0
  fi

  for ent in "${entries[@]}"; do
    local helper_name rule_name
    IFS='|' read -r helper_name rule_name <<<"$ent"

    local helper_url="https://raw.githubusercontent.com/${KEYRGB_REPO_OWNER}/${KEYRGB_REPO_NAME}/${raw_ref}/system/bin/${helper_name}"
    local rule_url="https://raw.githubusercontent.com/${KEYRGB_REPO_OWNER}/${KEYRGB_REPO_NAME}/${raw_ref}/system/polkit/${rule_name}"

    local helper_tmp="$tmp/$helper_name"
    local rule_tmp="$tmp/$rule_name"

    log_info "Downloading privileged helper: $helper_url"
    if ! download_url "$helper_url" "$helper_tmp"; then
      if [ "$raw_ref" != "main" ]; then
        local helper_url_fallback="https://raw.githubusercontent.com/${KEYRGB_REPO_OWNER}/${KEYRGB_REPO_NAME}/main/system/bin/${helper_name}"
        log_warn "Failed to download helper from ref '$raw_ref'; trying main: $helper_url_fallback"
        download_url "$helper_url_fallback" "$helper_tmp" || { log_warn "Failed to download helper"; continue; }
      else
        log_warn "Failed to download helper: $helper_url"
        continue
      fi
    fi

    log_info "Downloading polkit rule: $rule_url"
    if ! download_url "$rule_url" "$rule_tmp"; then
      if [ "$raw_ref" != "main" ]; then
        local rule_url_fallback="https://raw.githubusercontent.com/${KEYRGB_REPO_OWNER}/${KEYRGB_REPO_NAME}/main/system/polkit/${rule_name}"
        log_warn "Failed to download polkit rule from ref '$raw_ref'; trying main: $rule_url_fallback"
        download_url "$rule_url_fallback" "$rule_tmp" || { log_warn "Failed to download polkit rule"; continue; }
      else
        log_warn "Failed to download polkit rule: $rule_url"
        continue
      fi
    fi

    log_info "Installing helper (requires sudo): /usr/local/bin/${helper_name}"
    sudo install -D -m 0755 "$helper_tmp" "/usr/local/bin/${helper_name}"

    log_info "Installing polkit rule (requires sudo): ${polkit_dir}/${rule_name}"
    sudo install -D -m 0644 "$rule_tmp" "${polkit_dir}/${rule_name}"
  done

  log_ok "Privileged helpers installed (best-effort)"
}
