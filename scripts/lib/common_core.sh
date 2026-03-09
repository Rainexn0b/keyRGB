#!/usr/bin/env bash

# Shared installer utilities (core).

set -euo pipefail

KEYRGB_REPO_OWNER="${KEYRGB_REPO_OWNER:-Rainexn0b}"
KEYRGB_REPO_NAME="${KEYRGB_REPO_NAME:-keyRGB}"

log_info() { printf '%s\n' "ℹ️  $*" >&2; }
log_ok() { printf '%s\n' "✓ $*" >&2; }
log_warn() { printf '%s\n' "⚠️  $*" >&2; }
log_err() { printf '%s\n' "❌ $*" >&2; }

die() { log_err "$*"; exit 1; }

_restore_errexit_state() {
  local had_errexit="${1:-0}"
  if [ "$had_errexit" -eq 1 ]; then
    set -e
  else
    set +e
  fi
}

_shell_had_errexit() {
  case "$-" in
    *e*) return 0 ;;
    *) return 1 ;;
  esac
}

is_truthy() {
  case "${1:-}" in
    y|Y|yes|YES|1|true|TRUE|on|ON) return 0 ;;
    *) return 1 ;;
  esac
}

require_not_root() {
  if [ "${EUID:-0}" -eq 0 ]; then
    die "Please run without sudo (script will ask for password when needed)"
  fi
}

have_cmd() { command -v "$1" >/dev/null 2>&1; }
need_cmd() { have_cmd "$1" || die "Required command not found: $1"; }

# --- OS helpers ---
OS_RELEASE_LOADED=0
OS_RELEASE_ID=""
OS_RELEASE_ID_LIKE=""
OS_RELEASE_PRETTY_NAME=""

_unquote_os_release_value() {
  local value="${1:-}"
  value="${value#\"}"
  value="${value%\"}"
  printf '%s' "$value"
}

load_os_release() {
  if [ "${OS_RELEASE_LOADED:-0}" -eq 1 ]; then
    return 0
  fi

  OS_RELEASE_LOADED=1

  if ! [ -r /etc/os-release ]; then
    return 0
  fi

  local line key raw value
  while IFS= read -r line || [ -n "$line" ]; do
    case "$line" in
      ''|\#*) continue ;;
    esac

    key="${line%%=*}"
    raw="${line#*=}"
    value="$(_unquote_os_release_value "$raw")"

    case "$key" in
      ID) OS_RELEASE_ID="${value,,}" ;;
      ID_LIKE) OS_RELEASE_ID_LIKE="${value,,}" ;;
      PRETTY_NAME) OS_RELEASE_PRETTY_NAME="$value" ;;
    esac
  done </etc/os-release
}

os_pretty_name() {
  load_os_release
  if [ -n "${OS_RELEASE_PRETTY_NAME:-}" ]; then
    printf '%s' "$OS_RELEASE_PRETTY_NAME"
    return 0
  fi
  if [ -n "${OS_RELEASE_ID:-}" ]; then
    printf '%s' "$OS_RELEASE_ID"
    return 0
  fi
  printf '%s' "unknown Linux"
}

is_debian_like() {
  load_os_release
  case " ${OS_RELEASE_ID:-} ${OS_RELEASE_ID_LIKE:-} " in
    *" debian "*|*" ubuntu "*|*" linuxmint "*) return 0 ;;
    *) return 1 ;;
  esac
}

is_mint_like() {
  load_os_release
  [ "${OS_RELEASE_ID:-}" = "linuxmint" ]
}

is_fedora_like() {
  load_os_release
  case " ${OS_RELEASE_ID:-} ${OS_RELEASE_ID_LIKE:-} " in
    *" fedora "*|*" rhel "*|*" centos "*|*" rocky "*|*" almalinux "*|*" nobara "*) return 0 ;;
    *) return 1 ;;
  esac
}

is_arch_like() {
  load_os_release
  case " ${OS_RELEASE_ID:-} ${OS_RELEASE_ID_LIKE:-} " in
    *" arch "*|*" manjaro "*|*" endeavouros "*|*" garuda "*) return 0 ;;
    *) return 1 ;;
  esac
}

normalize_distro_support_profile() {
  local value="${1:-auto}"
  value="${value,,}"

  case "$value" in
    ""|auto) printf '%s' "auto" ;;
    fedora|redhat|red-hat|red_hat|rhel|nobara) printf '%s' "fedora" ;;
    debian|ubuntu|linuxmint|mint) printf '%s' "debian" ;;
    arch|archlinux|manjaro|endeavouros|garuda) printf '%s' "arch" ;;
    other|opensuse|suse|zypper) printf '%s' "other" ;;
    *) return 1 ;;
  esac
}

distro_support_profile() {
  local requested="${KEYRGB_DISTRO_PROFILE:-auto}"
  local normalized=""

  if normalized="$(normalize_distro_support_profile "$requested" 2>/dev/null)"; then
    if [ "$normalized" != "auto" ]; then
      printf '%s' "$normalized"
      return 0
    fi
  fi

  if is_fedora_like; then
    printf '%s' "fedora"
  elif is_debian_like; then
    printf '%s' "debian"
  elif is_arch_like; then
    printf '%s' "arch"
  else
    printf '%s' "other"
  fi
}

distro_support_profile_label() {
  case "${1:-other}" in
    fedora) printf '%s' "Fedora / Red Hat family" ;;
    debian) printf '%s' "Debian / Ubuntu / Linux Mint" ;;
    arch) printf '%s' "Arch / EndeavourOS / Manjaro" ;;
    *) printf '%s' "openSUSE / Other Linux" ;;
  esac
}

distro_support_profile_status() {
  case "${1:-other}" in
    fedora) printf '%s' "tested" ;;
    debian|arch) printf '%s' "experimental" ;;
    *) printf '%s' "best-effort" ;;
  esac
}

distro_support_profile_note() {
  case "${1:-other}" in
    fedora)
      printf '%s' "Primary tested path. AppImage plus optional dnf-based helpers is the smoothest install flow."
      ;;
    debian)
      printf '%s' "AppImage-first is recommended. Optional apt kernel-driver installs are best-effort and may require TUXEDO package sources."
      ;;
    arch)
      printf '%s' "AppImage-first is recommended. KeyRGB does not install AUR DKMS packages automatically."
      ;;
    *)
      printf '%s' "AppImage-first is recommended. Package-manager integration is best-effort and manual driver setup may be required."
      ;;
  esac
}

_print_distro_support_profile_line() {
  local profile_id="$1" current_profile="$2"
  local marker=" "
  if [ "$profile_id" = "$current_profile" ]; then
    marker=">"
  fi

  printf '  %s %s (%s)\n' \
    "$marker" \
    "$(distro_support_profile_label "$profile_id")" \
    "$(distro_support_profile_status "$profile_id")"
}

show_distro_support_profile_banner() {
  local current_profile=""
  current_profile="$(distro_support_profile)"

  if [ -t 0 ]; then
    echo
    echo "Distro support profile:"
    _print_distro_support_profile_line "fedora" "$current_profile"
    _print_distro_support_profile_line "debian" "$current_profile"
    _print_distro_support_profile_line "arch" "$current_profile"
    _print_distro_support_profile_line "other" "$current_profile"
    echo "Detected system: $(os_pretty_name)"
    echo "Using profile: $(distro_support_profile_label "$current_profile") ($(distro_support_profile_status "$current_profile"))"
    echo "Recommendation: $(distro_support_profile_note "$current_profile")"
  else
    log_info "Detected system: $(os_pretty_name)"
    log_info "Distro support profile: $(distro_support_profile_label "$current_profile") ($(distro_support_profile_status "$current_profile"))"
    log_info "Recommendation: $(distro_support_profile_note "$current_profile")"
  fi
}

# --- Package manager helpers (best-effort) ---
PKG_MGR=""  # dnf|apt|pacman|zypper|apk
APT_UPDATED=0
APT_BROKEN=0

detect_pkg_manager() {
  if have_cmd dnf; then PKG_MGR="dnf"; return 0; fi
  if have_cmd apt-get; then PKG_MGR="apt"; return 0; fi
  if have_cmd pacman; then PKG_MGR="pacman"; return 0; fi
  if have_cmd zypper; then PKG_MGR="zypper"; return 0; fi
  if have_cmd apk; then PKG_MGR="apk"; return 0; fi
  PKG_MGR=""; return 1
}

_log_apt_output_summary() {
  local src_file="$1"
  [ -f "$src_file" ] || return 0

  local summary=""
  summary="$(grep -Ei '^(E:|W:)|Encountered a section|Problem with MergeList|Could not be parsed or opened|Unable to locate package|No package .* available' "$src_file" | tail -n 8 || true)"
  if [ -n "$summary" ]; then
    while IFS= read -r line || [ -n "$line" ]; do
      [ -n "$line" ] || continue
      log_warn "apt: $line"
    done <<<"$summary"
  fi
}

apt_update_best_effort() {
  if [ "${APT_UPDATED:-0}" -eq 1 ]; then
    return 0
  fi
  if [ "${APT_BROKEN:-0}" -eq 1 ]; then
    return 1
  fi

  local had_errexit=0
  if _shell_had_errexit; then
    had_errexit=1
  fi

  local tmp=""
  tmp="$(mktemp)" || return 1

  set +e
  sudo apt-get update >"$tmp" 2>&1
  local rc=$?
  _restore_errexit_state "$had_errexit"

  if [ "$rc" -eq 0 ]; then
    APT_UPDATED=1
    rm -f "$tmp" 2>/dev/null || true
    return 0
  fi

  APT_BROKEN=1
  log_warn "apt-get update failed; skipping best-effort apt package changes."
  if is_debian_like; then
    log_warn "This does not block the AppImage install; only optional apt-managed components are being skipped."
  fi
  _log_apt_output_summary "$tmp"
  if grep -Eqi 'MergeList|Package: header|could not be parsed or opened' "$tmp"; then
    log_warn "APT package lists appear unhealthy. Fix apt first, then rerun if you want optional package installs."
  fi
  rm -f "$tmp" 2>/dev/null || true
  return 1
}

apt_install_best_effort() {
  local pkgs=("$@")
  [ ${#pkgs[@]} -eq 0 ] && return 0

  if ! apt_update_best_effort; then
    return 1
  fi

  local had_errexit=0
  if _shell_had_errexit; then
    had_errexit=1
  fi

  local tmp=""
  tmp="$(mktemp)" || return 1

  set +e
  sudo apt-get install -y "${pkgs[@]}" >"$tmp" 2>&1
  local rc=$?
  _restore_errexit_state "$had_errexit"

  if [ "$rc" -ne 0 ]; then
    _log_apt_output_summary "$tmp"
  fi

  rm -f "$tmp" 2>/dev/null || true
  return $rc
}

pkg_install_best_effort() {
  local pkgs=("$@")
  [ ${#pkgs[@]} -eq 0 ] && return 0

  detect_pkg_manager || { log_warn "No supported package manager found; skipping system package installation."; return 0; }

  local had_errexit=0
  if _shell_had_errexit; then
    had_errexit=1
  fi

  set +e
  case "$PKG_MGR" in
    dnf) sudo dnf install -y "${pkgs[@]}" ;;
    apt) apt_install_best_effort "${pkgs[@]}" ;;
    pacman) sudo pacman -S --noconfirm --needed "${pkgs[@]}" ;;
    zypper) sudo zypper --non-interactive install --no-recommends "${pkgs[@]}" ;;
    apk) sudo apk add "${pkgs[@]}" ;;
    *) log_warn "Unsupported package manager '$PKG_MGR'; skipping system package installation." ;;
  esac
  local rc=$?

  _restore_errexit_state "$had_errexit"
  return $rc
}

pkg_remove_best_effort() {
  local pkg="$1"
  detect_pkg_manager || return 1

  set +e
  case "$PKG_MGR" in
    dnf) sudo dnf remove -y "$pkg" ;;
    apt) sudo apt-get remove -y "$pkg" ;;
    pacman) sudo pacman -R --noconfirm "$pkg" ;;
    zypper) sudo zypper --non-interactive remove "$pkg" ;;
    apk) sudo apk del "$pkg" ;;
    *) log_warn "No supported package manager found to remove $pkg" ;;
  esac
  local rc=$?
  set -e
  return $rc
}

# --- Downloads ---
_download_url_impl() {
  local url="$1" dst="$2" progress_mode="${3:-auto}"
  [ -n "$dst" ] || die "download_url: destination path is empty"
  mkdir -p "$(dirname "$dst")"

  # Clean up any stale temp files from previous interrupted downloads
  rm -f "${dst}".tmp.* 2>/dev/null || true

  local tmp=""
  tmp="$(mktemp "${dst}.tmp.XXXXXX")" || die "Failed to create temp file"

  local show_progress="n"
  if [ "$progress_mode" = "force" ]; then
    show_progress="y"
  elif [ "$progress_mode" = "quiet" ]; then
    show_progress="n"
  else
    # auto: show progress only when output is a TTY.
    # curl renders its progress meter to stderr, so consider either stream.
    if [ -t 1 ] || [ -t 2 ]; then
      show_progress="y"
    fi
  fi

  if have_cmd curl; then
    if [ "$show_progress" = "y" ]; then
      # -# (hash meter) is widely supported and consistently visible in terminals.
      curl -L --fail --show-error -# -o "$tmp" "$url" || { rm -f "$tmp" 2>/dev/null || true; return 1; }
    else
      curl -L --fail --silent --show-error -o "$tmp" "$url" || { rm -f "$tmp" 2>/dev/null || true; return 1; }
    fi
    mv -f "$tmp" "$dst"; return 0
  fi

  if have_cmd wget; then
    if [ "$show_progress" = "y" ]; then
      wget --progress=bar:force:noscroll -O "$tmp" "$url" || { rm -f "$tmp" 2>/dev/null || true; return 1; }
    else
      wget -q -O "$tmp" "$url" || { rm -f "$tmp" 2>/dev/null || true; return 1; }
    fi
    mv -f "$tmp" "$dst"; return 0
  fi

  if have_cmd python3; then
    python3 - "$url" "$tmp" <<'PY' || { rm -f "$tmp" 2>/dev/null || true; return 1; }
from __future__ import annotations

import shutil
import sys
import urllib.request
from pathlib import Path

url = sys.argv[1]
dst = Path(sys.argv[2])
dst.parent.mkdir(parents=True, exist_ok=True)

with urllib.request.urlopen(url, timeout=60) as resp, dst.open("wb") as f:
    shutil.copyfileobj(resp, f)
PY
    mv -f "$tmp" "$dst"; return 0
  fi

  rm -f "$tmp" 2>/dev/null || true
  die "No downloader available (need curl, wget, or python3)"
}

# download_url: default best-effort downloader.
# - Shows a progress bar when stdout is a TTY.
download_url() {
  _download_url_impl "$1" "$2" "auto"
}

# download_url_progress: always show progress (when supported by the downloader).
download_url_progress() {
  _download_url_impl "$1" "$2" "force"
}

# download_url_quiet: always quiet, even in interactive terminals.
download_url_quiet() {
  _download_url_impl "$1" "$2" "quiet"
}


# --- GitHub release resolution (no jq dependency) ---
resolve_release_with_asset() {
  local asset_name="$1" allow_prerelease="$2"
  need_cmd python3

  python3 - "$KEYRGB_REPO_OWNER" "$KEYRGB_REPO_NAME" "$asset_name" "$allow_prerelease" <<'PY'
from __future__ import annotations

import json
import sys
import urllib.request

owner = sys.argv[1]
repo = sys.argv[2]
asset_name = sys.argv[3]
allow_prerelease = (sys.argv[4] or "").strip().lower() in ("y", "yes", "1", "true")

req = urllib.request.Request(
    f"https://api.github.com/repos/{owner}/{repo}/releases",
    headers={"Accept": "application/vnd.github+json", "User-Agent": "keyrgb-install"},
)

with urllib.request.urlopen(req, timeout=30) as resp:
    data = json.loads(resp.read().decode("utf-8"))

if not isinstance(data, list):
    raise SystemExit(1)

for rel in data:
    if not allow_prerelease and bool(rel.get("prerelease")):
        continue

    for asset in (rel.get("assets") or []):
        if asset.get("name") == asset_name:
            tag = rel.get("tag_name") or ""
            url = asset.get("browser_download_url") or ""
            prerelease = bool(rel.get("prerelease"))
            if tag and url:
                sys.stdout.write(f"{tag}|{url}|{'true' if prerelease else 'false'}")
                raise SystemExit(0)

raise SystemExit(2)
PY
}
