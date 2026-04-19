#!/usr/bin/env bash

# Optional install components for legacy parity (best-effort).

set -euo pipefail

install_first_available_pkg_best_effort() {
  local pkg=""
  for pkg in "$@"; do
    if pkg_install_best_effort "$pkg"; then
      printf '%s' "$pkg"
      return 0
    fi
  done
  return 1
}

ensure_polkit_best_effort() {
  # Best-effort only; do not fail install.
  # Most desktop distros already ship polkit; avoid touching the system if pkexec exists.
  if have_cmd pkexec; then
    return 0
  fi
  pkg_install_best_effort polkit || true
}

ensure_appimage_runtime_best_effort() {
  detect_pkg_manager || return 0

  case "${PKG_MGR:-}" in
    pacman)
      if system_has_libfuse2; then
        return 0
      fi

      log_info "Installing FUSE 2 runtime for direct AppImage support (best-effort)..."
      if pkg_install_best_effort fuse2; then
        log_ok "Installed fuse2"
      else
        log_warn "Failed to install fuse2 automatically (best-effort)."
        log_warn "Direct AppImage launches may fail until you install: sudo pacman -S fuse2"
        log_info "The installed ~/.local/bin/keyrgb launcher will still fall back to --appimage-extract-and-run."
      fi
      ;;
  esac
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
      local installed_pkg=""
      installed_pkg="$(install_first_available_pkg_best_effort tuxedo-drivers tuxedo-keyboard)" || true
      if [ -n "$installed_pkg" ]; then
        printf '%s\n' "$installed_pkg" >>"$marker" 2>/dev/null || true
        log_ok "Installed $installed_pkg"
      else
        log_warn "Could not install 'tuxedo-drivers' or 'tuxedo-keyboard' via apt (best-effort)."
        log_warn "On Debian/Ubuntu/Linux Mint, these packages are often provided via TUXEDO's package source rather than the stock distro repo."
        log_warn "KeyRGB does not add third-party apt sources automatically."
        log_warn "See: https://www.tuxedocomputers.com/en/Infos/Help-Support/Instructions/Add-TUXEDO-Computers-software-package-sources.tuxedo"
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
