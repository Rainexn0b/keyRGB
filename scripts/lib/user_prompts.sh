#!/usr/bin/env bash

# Interactive prompts for the user installer (legacy parity).

set -euo pipefail

ask_yes_no() {
  local prompt="$1" default="$2" env_var="${3:-}"

  if [ -n "$env_var" ] && [ -n "${!env_var:-}" ]; then
    local v="${!env_var,,}"
    case "$v" in
      y|yes|1|true|on) printf '%s\n' "y"; return 0 ;;
      n|no|0|false|off) printf '%s\n' "n"; return 0 ;;
    esac
  fi

  # Non-interactive: pick default.
  if ! [ -t 0 ]; then
    printf '%s\n' "$default"
    return 0
  fi

  local suffix='[y/N]'
  if [ "$default" = "y" ]; then
    suffix='[Y/n]'
  fi

  local reply
  read -r -p "$prompt $suffix " reply || reply=""
  reply="${reply,,}"
  if [ -z "$reply" ]; then
    printf '%s\n' "$default"
    return 0
  fi

  case "$reply" in
    y|yes) printf '%s\n' "y" ;;
    n|no) printf '%s\n' "n" ;;
    *) printf '%s\n' "$default" ;;
  esac
}

maybe_prompt_release_channel() {
  # Uses global vars:
  # - KEYRGB_VERSION, UPDATE_ONLY, KEYRGB_ALLOW_PRERELEASE_SET, KEYRGB_ALLOW_PRERELEASE
  if [ -n "${KEYRGB_VERSION:-}" ]; then
    return 0
  fi
  if [ "${UPDATE_ONLY:-0}" -eq 1 ]; then
    return 0
  fi
  if [ "${KEYRGB_ALLOW_PRERELEASE_SET:-0}" -eq 1 ]; then
    return 0
  fi
  if ! [ -t 0 ]; then
    return 0
  fi

  echo
  echo "Choose AppImage release channel:"
  echo "  1) Latest stable release (recommended)"
  echo "  2) Latest including prereleases (beta)"

  local relchan_default="1"
  if is_truthy "${KEYRGB_ALLOW_PRERELEASE:-n}"; then
    relchan_default="2"
  fi

  local relchan
  read -r -p "Select [1-2] (default: ${relchan_default}): " relchan || relchan=""
  relchan="${relchan:-${relchan_default}}"
  case "$relchan" in
    2) KEYRGB_ALLOW_PRERELEASE="y" ;;
    *) KEYRGB_ALLOW_PRERELEASE="n" ;;
  esac
}

configure_optional_components() {
  # Sets/updates these vars:
  # - KEYRGB_INSTALL_POWER_HELPER
  # - KEYRGB_INSTALL_TCC_APP
  # - KEYRGB_INSTALL_KERNEL_DRIVERS
  # - KEYRGB_INSTALL_INPUT_UDEV
  # Respects:
  # - UPDATE_ONLY
  # - KEYRGB_INSTALL_POWER_HELPER, KEYRGB_INSTALL_TUXEDO env overrides

  if [ "${UPDATE_ONLY:-0}" -eq 1 ]; then
    return 0
  fi

  local install_power_helper="y"
  local install_tuxedo="n"

  if [ "${KEYRGB_INSTALL_POWER_HELPER:-}" != "" ] || [ "${KEYRGB_INSTALL_TUXEDO:-}" != "" ]; then
    local ph tc
    ph="$(ask_yes_no "" "y" "KEYRGB_INSTALL_POWER_HELPER")"
    tc="$(ask_yes_no "" "n" "KEYRGB_INSTALL_TUXEDO")"
    if [ "$ph" = "y" ]; then
      install_power_helper="y"; install_tuxedo="n"
    elif [ "$tc" = "y" ]; then
      install_power_helper="n"; install_tuxedo="y"
    else
      install_power_helper="n"; install_tuxedo="n"
    fi
  else
    local power_choice
    if [ -t 0 ]; then
      echo
      echo "Optional components:"
      echo "Choose ONE power integration (to avoid collisions):"
      echo "  1) Lightweight Power Mode toggle (recommended)"
      echo "     - Adds 'Extreme Saver/Balanced/Performance' tray menu"
      echo "     - Installs a helper + polkit rule for passwordless switching"
      echo "  2) Tuxedo Control Center (TCC) integration (advanced)"
      echo "     - Enables the existing 'Power Profiles (TCC)' UI if TCC is installed"
      read -r -p "Select [1-2] (default: 1): " power_choice || power_choice=""
      power_choice="${power_choice:-1}"
    else
      power_choice="1"
    fi

    case "$power_choice" in
      2) install_power_helper="n"; install_tuxedo="y" ;;
      *) install_power_helper="y"; install_tuxedo="n" ;;
    esac
  fi

  if [ "$install_power_helper" = "y" ]; then
    KEYRGB_INSTALL_POWER_HELPER="y"
  else
    KEYRGB_INSTALL_POWER_HELPER="n"
  fi

  if [ "$install_tuxedo" = "y" ]; then
    if [ "${KEYRGB_INSTALL_TCC_APP:-}" = "" ] && [ -t 0 ]; then
      echo
      echo "TCC integration was selected."
      local ans
      ans="$(ask_yes_no "Install Tuxedo Control Center app (best-effort, may not be available in your repos)?" "n")"
      if [ "$ans" = "y" ]; then
        KEYRGB_INSTALL_TCC_APP="y"
      else
        KEYRGB_INSTALL_TCC_APP="n"
      fi
    fi
  fi

  if [ "${KEYRGB_INSTALL_KERNEL_DRIVERS:-}" = "" ] && [ -t 0 ]; then
    echo
    echo "Kernel Drivers (Advanced):"
    echo "KeyRGB works best with kernel-level drivers for Clevo/Tuxedo laptops."
    echo "These provide safer and more reliable keyboard control than the USB fallback."
    KEYRGB_INSTALL_KERNEL_DRIVERS="$(ask_yes_no "Install/Update kernel drivers (best-effort) if available?" "n")"
  fi

  if [ "${KEYRGB_INSTALL_INPUT_UDEV:-}" = "" ] && [ -t 0 ]; then
    echo
    echo "Optional permissions:"
    echo "Reactive Typing effects (Fade/Ripple) can react to real keypress events."
    echo "This requires read access to /dev/input/event* (security-sensitive)."
    echo "KeyRGB can install a seat-based uaccess udev rule so only the active local user gets access."
    KEYRGB_INSTALL_INPUT_UDEV="$(ask_yes_no "Enable Reactive Typing keypress detection (install uaccess rule)?" "n")"
  fi
}
