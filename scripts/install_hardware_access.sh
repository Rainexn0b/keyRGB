#!/usr/bin/env bash
#
# Hardware-access entrypoint. Keyboard USB/sysfs rules and the power helper are
# the default, matching the user installer. Reactive input stays opt-in. This
# script does not source the installer loader and does not fall back to main.

set -euo pipefail

SCRIPT_SELF="$(readlink -f -- "${BASH_SOURCE[0]}")"
SCRIPT_DIR="$(cd "$(dirname "$SCRIPT_SELF")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/lib/hardware_access.sh"

usage() {
  cat <<'EOF'
Usage:
  install_hardware_access.sh [--reactive-input] [--power-controls] [--no-power-controls]
                             [--payload-dir <dir>] [--ref <git-ref>] [--hash <rel>=<sha256>]

Installs KeyRGB hardware-access files only. Does not download an AppImage,
change desktop integration, or install packages.

Default:
  USB/hidraw and sysfs keyboard rules, the power helper and its polkit files,
  and membership in the video group when the caller is not already a member.
  A new group membership needs a logout before sysfs backlight access works.

Optional:
  --reactive-input     Also install the keyboard input-event uaccess rule.
  --power-controls     Install the power helper. This is the default.
  --no-power-controls  Skip the power helper and its polkit files.
                       Environment defaults are ignored. Power files need host python3.

Payload:
  --payload-dir <dir> Internal. Directory shaped like system/ (udev/, bin/, polkit/).
                      Rejects '..' and a symlinked directory.
  --ref <git-ref>     Explicit ref when no local system/ tree is available.
                      A failed download does not fall back to main.
  --hash <rel>=<sha256>
                      Expected sha256sum for one payload-relative file. When any
                      hash is given, every selected file needs one.

The unprivileged CLI acquires the payload, then re-execs this script through
sudo. An already-root worker does not call sudo and does not download.
EOF
}

PAYLOAD_DIR=""
REF=""
REACTIVE=0
POWER=1
HASH_ARGS=()

while [ "$#" -gt 0 ]; do
  case "$1" in
    --reactive-input)
      REACTIVE=1
      shift
      ;;
    --power-controls)
      POWER=1
      shift
      ;;
    --no-power-controls)
      POWER=0
      shift
      ;;
    --payload-dir)
      PAYLOAD_DIR="${2:-}"
      shift 2
      ;;
    --ref)
      REF="${2:-}"
      shift 2
      ;;
    --hash)
      HASH_ARGS+=("${2:-}")
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      printf 'unknown argument: %s\n' "$1" >&2
      hardware_access_finish "$HARDWARE_ACCESS_EXIT_FAILED" failed "unknown-argument written=none"
      ;;
  esac
done

if [ -z "$REF" ]; then
  REF="${KEYRGB_BOOTSTRAP_REF:-}"
fi

forward_flags=()
if [ "$REACTIVE" -eq 1 ]; then
  forward_flags+=(--reactive-input)
fi
if [ "$POWER" -eq 1 ]; then
  forward_flags+=(--power-controls)
else
  forward_flags+=(--no-power-controls)
fi
if [ "${#HASH_ARGS[@]}" -gt 0 ]; then
  for hash_arg in "${HASH_ARGS[@]}"; do
    forward_flags+=(--hash "$hash_arg")
  done
fi

if [ "${EUID}" -ne 0 ]; then
  cleanup=0
  if [ -z "$PAYLOAD_DIR" ]; then
    if checkout="$(hardware_access_checkout_system_dir)"; then
      PAYLOAD_DIR="$checkout"
    else
      if [ -z "$REF" ] || ! hardware_access_validate_ref "$REF"; then
        hardware_access_finish "$HARDWARE_ACCESS_EXIT_PREREQUISITE" prerequisite bad-ref
      fi
      PAYLOAD_DIR="$(mktemp -d)"
      cleanup=1
      if ! hardware_access_fetch_payload "$REF" "$PAYLOAD_DIR" "$REACTIVE" "$POWER"; then
        rm -rf -- "$PAYLOAD_DIR"
        hardware_access_finish "$HARDWARE_ACCESS_EXIT_FAILED" failed "download-failed written=none"
      fi
    fi
  fi
  if ! hardware_access_validate_payload_dir "$PAYLOAD_DIR"; then
    if [ "$cleanup" -eq 1 ]; then
      rm -rf -- "$PAYLOAD_DIR"
    fi
    hardware_access_finish "$HARDWARE_ACCESS_EXIT_PREREQUISITE" prerequisite bad-payload-dir
  fi
  PAYLOAD_DIR="$(readlink -f -- "$PAYLOAD_DIR")"
  # Do not exec: a fetched payload directory has to be removed after sudo returns.
  sudo_args=(/bin/bash "$SCRIPT_SELF" --payload-dir "$PAYLOAD_DIR")
  if [ "${#forward_flags[@]}" -gt 0 ]; then
    sudo_args+=("${forward_flags[@]}")
  fi
  sudo -- "${sudo_args[@]}"
  status=$?
  if [ "$cleanup" -eq 1 ]; then
    rm -rf -- "$PAYLOAD_DIR"
  fi
  exit "$status"
fi

if [ -z "$PAYLOAD_DIR" ]; then
  hardware_access_finish "$HARDWARE_ACCESS_EXIT_PREREQUISITE" prerequisite missing-payload
fi
if ! hardware_access_validate_payload_dir "$PAYLOAD_DIR"; then
  hardware_access_finish "$HARDWARE_ACCESS_EXIT_PREREQUISITE" prerequisite bad-payload-dir
fi
PAYLOAD_DIR="$(readlink -f -- "$PAYLOAD_DIR")"

hash_file=""
if [ "${#HASH_ARGS[@]}" -gt 0 ]; then
  hash_file="$(mktemp)"
  trap 'rm -f -- "$hash_file"' EXIT
  printf '%s\n' "${HASH_ARGS[@]}" >"$hash_file"
fi

hardware_access_apply "$PAYLOAD_DIR" / "$REACTIVE" "$POWER" "$hash_file"
