#!/usr/bin/env bash

# Optional install components for legacy parity (best-effort).

set -euo pipefail

ensure_polkit_best_effort() {
  # Best-effort only; do not fail install.
  # Most desktop distros already ship polkit; avoid touching the system if pkexec exists.
  if have_cmd pkexec; then
    return 0
  fi
  pkg_install_best_effort polkit || true
}

install_tcc_app_best_effort() {
  local state_dir="$HOME/.local/share/keyrgb"
  local marker="$state_dir/tcc-installed-by-keyrgb"

  mkdir -p "$state_dir" 2>/dev/null || true

  log_info "Installing Tuxedo Control Center (best-effort)..."
  if pkg_install_best_effort tuxedo-control-center; then
    printf '%s\n' "tuxedo-control-center" >"$marker" 2>/dev/null || true
    log_ok "Installed tuxedo-control-center"
  else
    log_warn "Failed to install tuxedo-control-center (best-effort)."
    log_warn "You can install it manually; KeyRGB will use it when present."
  fi
}

install_kernel_drivers_best_effort() {
  local state_dir="$HOME/.local/share/keyrgb"
  local marker="$state_dir/kernel-drivers-installed-by-keyrgb"

  mkdir -p "$state_dir" 2>/dev/null || true

  detect_pkg_manager || {
    log_warn "No supported package manager found; cannot install kernel drivers automatically."
    return 0
  }

  log_info "Installing kernel drivers (best-effort)..."
  case "${PKG_MGR:-}" in
    dnf)
      if pkg_install_best_effort tuxedo-drivers; then
        printf '%s\n' "tuxedo-drivers" >>"$marker" 2>/dev/null || true
        log_ok "Installed tuxedo-drivers"
      else
        log_warn "Could not install 'tuxedo-drivers' via dnf (best-effort)."
      fi
      if pkg_install_best_effort clevo-xsm-wmi; then
        printf '%s\n' "clevo-xsm-wmi" >>"$marker" 2>/dev/null || true
        log_ok "Installed clevo-xsm-wmi"
      else
        log_info "'clevo-xsm-wmi' not available via dnf (often expected)."
      fi
      ;;
    apt)
      if pkg_install_best_effort tuxedo-keyboard; then
        printf '%s\n' "tuxedo-keyboard" >>"$marker" 2>/dev/null || true
        log_ok "Installed tuxedo-keyboard"
      else
        log_warn "Could not install 'tuxedo-keyboard' via apt (best-effort)."
      fi
      if pkg_install_best_effort clevo-xsm-wmi; then
        printf '%s\n' "clevo-xsm-wmi" >>"$marker" 2>/dev/null || true
        log_ok "Installed clevo-xsm-wmi"
      else
        log_info "'clevo-xsm-wmi' not available via apt (often expected)."
      fi
      ;;
    pacman)
      log_warn "Arch detected; not installing AUR DKMS packages automatically."
      log_warn "Install via AUR if needed: tuxedo-drivers-dkms, clevo-xsm-wmi-dkms"
      ;;
    zypper)
      if pkg_install_best_effort tuxedo-keyboard; then
        printf '%s\n' "tuxedo-keyboard" >>"$marker" 2>/dev/null || true
        log_ok "Installed tuxedo-keyboard"
      else
        log_info "'tuxedo-keyboard' not available via zypper (often expected)."
      fi
      if pkg_install_best_effort clevo-xsm-wmi; then
        printf '%s\n' "clevo-xsm-wmi" >>"$marker" 2>/dev/null || true
        log_ok "Installed clevo-xsm-wmi"
      else
        log_info "'clevo-xsm-wmi' not available via zypper (often expected)."
      fi
      ;;
    apk)
      log_warn "Alpine detected; kernel driver packages typically not available via apk."
      ;;
    *)
      log_warn "Unknown package manager; install kernel drivers manually if needed."
      ;;
  esac
}
