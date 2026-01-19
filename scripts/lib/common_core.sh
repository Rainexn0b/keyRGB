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

# --- Package manager helpers (best-effort) ---
PKG_MGR=""  # dnf|apt|pacman|zypper|apk
APT_UPDATED=0

detect_pkg_manager() {
  if have_cmd dnf; then PKG_MGR="dnf"; return 0; fi
  if have_cmd apt-get; then PKG_MGR="apt"; return 0; fi
  if have_cmd pacman; then PKG_MGR="pacman"; return 0; fi
  if have_cmd zypper; then PKG_MGR="zypper"; return 0; fi
  if have_cmd apk; then PKG_MGR="apk"; return 0; fi
  PKG_MGR=""; return 1
}

pkg_install_best_effort() {
  local pkgs=("$@")
  [ ${#pkgs[@]} -eq 0 ] && return 0

  detect_pkg_manager || { log_warn "No supported package manager found; skipping system package installation."; return 0; }

  local had_errexit=0
  case "$-" in *e*) had_errexit=1 ;; esac

  set +e
  case "$PKG_MGR" in
    dnf) sudo dnf install -y "${pkgs[@]}" ;;
    apt)
      if [ "${APT_UPDATED:-0}" -ne 1 ]; then
        sudo apt-get update >/dev/null 2>&1 || true
        APT_UPDATED=1
      fi
      sudo apt-get install -y "${pkgs[@]}" ;;
    pacman) sudo pacman -S --noconfirm --needed "${pkgs[@]}" ;;
    zypper) sudo zypper --non-interactive install --no-recommends "${pkgs[@]}" ;;
    apk) sudo apk add "${pkgs[@]}" ;;
    *) log_warn "Unsupported package manager '$PKG_MGR'; skipping system package installation." ;;
  esac
  local rc=$?

  if [ "$had_errexit" -eq 1 ]; then set -e; else set +e; fi
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

  local tmp
  tmp="$(mktemp "${dst}.tmp.XXXXXX")" || die "Failed to create temp file"

  local show_progress="n"
  if [ "$progress_mode" = "force" ]; then
    show_progress="y"
  elif [ "$progress_mode" = "quiet" ]; then
    show_progress="n"
  else
    # auto: show progress only when stdout is a TTY
    if [ -t 1 ]; then
      show_progress="y"
    fi
  fi

  if have_cmd curl; then
    if [ "$show_progress" = "y" ]; then
      # --progress-bar is readable and keeps stderr quiet unless errors occur.
      curl -L --fail --show-error --progress-bar -o "$tmp" "$url" || { rm -f "$tmp" 2>/dev/null || true; return 1; }
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
    python3 - "$url" "$tmp" <<'PY'
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
