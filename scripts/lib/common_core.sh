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

# Internal seam for the os-release source path. Production always reads
# /etc/os-release; tests override this function to point at a fixture.
# No public environment variable selects the path.
_keyrgb_os_release_path() {
  printf '%s' "/etc/os-release"
}

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

  local os_release_path=""
  os_release_path="$(_keyrgb_os_release_path)"

  if ! [ -r "$os_release_path" ]; then
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
  done <"$os_release_path"
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
    arch|archlinux|cachyos|manjaro|endeavouros|garuda) printf '%s' "arch" ;;
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
    arch) printf '%s' "Arch / CachyOS / EndeavourOS / Manjaro" ;;
    *) printf '%s' "openSUSE / Other Linux" ;;
  esac
}

distro_support_profile_status() {
  case "${1:-other}" in
    fedora) printf '%s' "tested" ;;
    debian) printf '%s' "experimental" ;;
    arch) printf '%s' "tested" ;;
    *) printf '%s' "best-effort" ;;
  esac
}

distro_support_profile_note() {
  case "${1:-other}" in
    fedora)
      printf '%s' "Tested path. AppImage plus optional dnf-based helpers is the smoothest install flow."
      ;;
    debian)
      printf '%s' "AppImage-first is recommended. Optional apt kernel-driver installs are best-effort and may require TUXEDO package sources."
      ;;
    arch)
      printf '%s' "Tested path. AppImage-first is recommended. KeyRGB does not install AUR DKMS packages automatically."
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
  # Capture apt output in a user-owned tempfile; sudo must not own the redirect.
  # shellcheck disable=SC2024
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
  # Capture apt output in a user-owned tempfile; sudo must not own the redirect.
  # shellcheck disable=SC2024
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

# _keyrgb_release_tag_is_historical: true only for well-formed stable release
# tags that predate published SHA-256 sidecars (before v0.23.4).
# - Accepts exactly <major>.<minor>.<patch> with an optional leading 'v',
#   using canonical numeric components (0 or non-zero without leading zeros).
# - Anything else (empty, 'main', mutable branch names, non-semver refs,
#   leading-zero components, or prerelease suffixes such as '-rc1') is NOT
#   historical and stays strict.
# - Comparison is string-based (length then lexicographic) so absurdly large
#   numeric components cannot overflow into a historical classification.
_keyrgb_release_tag_is_historical() {
  local tag="${1:-}"
  local ver="$tag"
  case "$ver" in
    v*) ver="${ver#v}" ;;
  esac

  local major="" minor="" patch=""
  local semver_re='^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$'
  if [[ "$ver" =~ $semver_re ]]; then
    major="${BASH_REMATCH[1]}"
    minor="${BASH_REMATCH[2]}"
    patch="${BASH_REMATCH[3]}"
  else
    return 1
  fi

  [ "$major" = "0" ] || return 1
  case "$minor" in
    [0-9]) return 0 ;;
    1[0-9]|2[0-2]) return 0 ;;
    23) : ;;
    *) return 1 ;;
  esac
  # Only minor "23" reaches here.
  case "$patch" in
    [0-3]) return 0 ;;
    *) return 1 ;;
  esac
}

# verify_downloaded_sha256: verify a downloaded file against a .sha256 sidecar URL.
# Usage: verify_downloaded_sha256 <file_path> <sha256_url> [release_tag]
# - Default is strict (fail closed): current releases (v0.23.4 and later),
#   empty/unknown/non-semver tags, and mutable refs such as 'main' fail
#   closed when 'sha256sum' is missing, the sidecar cannot be downloaded, or
#   the sidecar is empty or malformed. Hash mismatches always fail closed.
# - Historical compatibility is limited to well-formed stable tags before
#   v0.23.4 (the first release that published sidecars): for those tags only,
#   a missing sidecar or missing 'sha256sum' warns and continues. A present
#   but empty/malformed sidecar, a hash-tool failure, or a hash mismatch
#   still fails closed for historical tags.
# - Set KEYRGB_REQUIRE_CHECKSUM=1 (or true/yes/on) to force strict
#   verification even for historical tags. A false/unset value never weakens
#   strict verification of current or unknown tags.
# - Every rejection removes the downloaded file; temporary sidecars are
#   always cleaned up.
verify_downloaded_sha256() {
  local file_path="$1" sha256_url="$2" release_tag="${3:-}"
  local base_name=""
  base_name="$(basename "$file_path")"
  local display_tag="${release_tag:-unknown}"

  local require_checksum=0
  if is_truthy "${KEYRGB_REQUIRE_CHECKSUM:-}"; then
    require_checksum=1
  fi

  local strict=1
  if [ "$require_checksum" -eq 0 ] && _keyrgb_release_tag_is_historical "$release_tag"; then
    strict=0
  fi

  local env_note=""
  if [ "$require_checksum" -eq 1 ]; then
    env_note=" (KEYRGB_REQUIRE_CHECKSUM=1)"
  fi

  if ! have_cmd sha256sum; then
    if [ "$strict" -eq 1 ]; then
      rm -f "$file_path" 2>/dev/null || true
      die "Integrity verification failed for $base_name (release '$display_tag'): sha256sum not found; cannot verify SHA-256 integrity. Removed $base_name.$env_note"
    fi
    log_warn "Historical release '$release_tag' predates checksum sidecars (historical compatibility): sha256sum not found; skipping integrity verification of $base_name."
    log_warn "Set KEYRGB_REQUIRE_CHECKSUM=1 to require strict checksum verification for historical releases."
    return 0
  fi

  local sha256_tmp=""
  if ! sha256_tmp="$(mktemp)"; then
    rm -f "$file_path" 2>/dev/null || true
    die "Integrity verification failed for $base_name (release '$display_tag'): could not create a temporary file to verify SHA-256 integrity. Removed $base_name."
  fi

  if ! download_url_quiet "$sha256_url" "$sha256_tmp" 2>/dev/null; then
    rm -f "$sha256_tmp" 2>/dev/null || true
    if [ "$strict" -eq 1 ]; then
      rm -f "$file_path" 2>/dev/null || true
      die "Integrity verification failed for $base_name (release '$display_tag'): no SHA-256 sidecar found at: $sha256_url. Removed $base_name. Current releases must publish a .sha256 sidecar.$env_note"
    fi
    log_warn "Historical release '$release_tag' predates checksum sidecars (historical compatibility): no SHA-256 sidecar found at: $sha256_url; skipping integrity verification of $base_name."
    log_warn "Set KEYRGB_REQUIRE_CHECKSUM=1 to require strict checksum verification for historical releases."
    return 0
  fi

  # Parse the sidecar with shell builtins only, so a failing parser utility
  # can never leave the payload behind: anything other than exactly one
  # nonempty entry falls through to the fail-closed path below, which
  # always removes the payload.
  local nonempty_count=0
  local entry=""
  local line=""
  if ! while IFS= read -r line || [ -n "$line" ]; do
    line="${line%$'\r'}"
    case "$line" in
      *[^[:space:]]*)
        nonempty_count=$((nonempty_count + 1))
        entry="$line"
        ;;
    esac
  done <"$sha256_tmp"; then
    rm -f "$sha256_tmp" 2>/dev/null || true
    rm -f "$file_path" 2>/dev/null || true
    die "Integrity verification failed for $base_name (release '$display_tag'): checksum sidecar could not be read (expected exactly one SHA-256 entry: a 64-character hex digest, optionally followed by standard sha256sum separator and filename). Removed $base_name."
  fi

  local expected_hash=""
  if [ "$nonempty_count" -eq 1 ]; then
    local digest_only_re='^[[:space:]]*([0-9A-Fa-f]{64})[[:space:]]*$'
    local sha256sum_line_re='^[[:space:]]*([0-9A-Fa-f]{64}) ([ *])[^[:space:]].*'
    if [[ "$entry" =~ $digest_only_re ]]; then
      expected_hash="${BASH_REMATCH[1]}"
    elif [[ "$entry" =~ $sha256sum_line_re ]]; then
      expected_hash="${BASH_REMATCH[1]}"
    fi
  fi
  rm -f "$sha256_tmp" 2>/dev/null || true

  if [ -z "$expected_hash" ]; then
    rm -f "$file_path" 2>/dev/null || true
    if [ "$strict" -eq 0 ]; then
      die "Integrity verification failed for $base_name (release '$display_tag'): checksum sidecar is empty or malformed (expected exactly one SHA-256 entry: a 64-character hex digest, optionally followed by standard sha256sum separator and filename). Removed $base_name. Historical compatibility covers only missing sidecars, never malformed ones."
    fi
    die "Integrity verification failed for $base_name (release '$display_tag'): checksum sidecar is empty or malformed (expected exactly one SHA-256 entry: a 64-character hex digest, optionally followed by standard sha256sum separator and filename). Removed $base_name.$env_note"
  fi
  expected_hash="${expected_hash,,}"

  local actual_output=""
  if ! actual_output="$(sha256sum "$file_path" 2>/dev/null)"; then
    rm -f "$file_path" 2>/dev/null || true
    die "Integrity verification failed for $base_name (release '$display_tag'): could not compute SHA-256 integrity (sha256sum failed). Removed $base_name."
  fi

  # sha256sum must print exactly one line; extra output lines are malformed.
  if [ "$actual_output" != "${actual_output%%$'\n'*}" ]; then
    rm -f "$file_path" 2>/dev/null || true
    die "Integrity verification failed for $base_name (release '$display_tag'): could not compute SHA-256 integrity (sha256sum returned malformed output). Removed $base_name."
  fi

  local actual_hash=""
  local actual_sha256sum_re='^([0-9A-Fa-f]{64}) ([ *])[^[:space:]].*$'
  if [[ "$actual_output" =~ $actual_sha256sum_re ]]; then
    actual_hash="${BASH_REMATCH[1]}"
  else
    rm -f "$file_path" 2>/dev/null || true
    die "Integrity verification failed for $base_name (release '$display_tag'): could not compute SHA-256 integrity (sha256sum returned malformed output). Removed $base_name."
  fi
  actual_hash="${actual_hash,,}"

  if [ "$actual_hash" = "$expected_hash" ]; then
    log_ok "Integrity verified (SHA-256 match: ${actual_hash:0:16}…)"
  else
    rm -f "$file_path" 2>/dev/null || true
    die "Integrity verification failed for $base_name (release '$display_tag'): SHA-256 mismatch.
  Expected: $expected_hash
  Got:      $actual_hash
  The downloaded file has been removed. Aborting for safety."
  fi
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
