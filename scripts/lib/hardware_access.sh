#!/usr/bin/env bash
#
# Fail-closed hardware-access writer.
#
# This file is the shared file-placement seam. It does not download AppImages,
# source the installer loader, or fall back to the main branch. The new-mode
# entrypoint is the only caller that reports the stable result line. Existing
# install helpers may call hardware_access_place_file_privileged for the write
# itself; they keep their own acquisition and reload policy.

# More than one installer helper loads this file. Skip a second source.
if [ "${HARDWARE_ACCESS_LOADED:-}" = 1 ]; then
  return 0
fi
HARDWARE_ACCESS_LOADED=1

# shellcheck disable=SC1091
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/uninstall_match.sh"

# Worker statuses. Never 126 or 127: those belong to pkexec launch classification.
readonly HARDWARE_ACCESS_EXIT_OK=0
readonly HARDWARE_ACCESS_EXIT_PREREQUISITE=10
readonly HARDWARE_ACCESS_EXIT_CONFLICT=11
readonly HARDWARE_ACCESS_EXIT_FAILED=12

hardware_access_finish() {
  local code="$1"
  local outcome="$2"
  shift 2
  if [ "$#" -eq 0 ]; then
    printf 'keyrgb-hardware-access: %s\n' "$outcome"
  else
    printf 'keyrgb-hardware-access: %s %s\n' "$outcome" "$*"
  fi
  exit "$code"
}

hardware_access_sha256() {
  local path="$1"
  sha256sum -- "$path" | awk 'NR==1 { print $1 }'
}

hardware_access_mode_value() {
  local path="$1"
  local mode
  mode="$(stat -c '%a' -- "$path")"
  printf '%s\n' "$((8#$mode))"
}

hardware_access_under() {
  local root="$1"
  local rel="$2"
  root="${root%/}"
  printf '%s/%s\n' "$root" "$rel"
}

hardware_access_is_managed_kind() {
  local kind="$1"
  local path="$2"
  case "$kind" in
    usb) is_keyrgb_managed_usb_udev_rule "$path" ;;
    sysfs) is_keyrgb_managed_sysfs_udev_rule "$path" ;;
    input) is_keyrgb_managed_input_udev_rule "$path" ;;
    helper) file_has_marker "$path" "KEYRGB_CPUFREQ_ROOT" ;;
    polkit-rule) file_has_marker "$path" "Installed by KeyRGB's install.sh" ;;
    polkit-action) file_has_marker "$path" "org.keyrgb.power-helper.apply" ;;
    *) return 1 ;;
  esac
}

hardware_access_reject_unsafe_file() {
  local path="$1"
  local mode
  if [ -L "$path" ] || [ ! -f "$path" ]; then
    return 1
  fi
  mode="$(stat -c '%a' -- "$path")"
  if [ "$((8#$mode & 8#002))" -ne 0 ]; then
    return 1
  fi
  if [ "$((8#$mode & 8#6000))" -ne 0 ]; then
    return 1
  fi
  return 0
}

hardware_access_checkout_system_dir() {
  local lib_dir repo_system
  lib_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  repo_system="$(cd "$lib_dir/../.." && pwd)/system"
  if [ -f "$repo_system/udev/99-ite8291-wootbook.rules" ] \
    && [ -f "$repo_system/udev/99-keyrgb-sysfs-leds.rules" ] \
    && [ ! -L "$repo_system/udev/99-ite8291-wootbook.rules" ] \
    && [ ! -L "$repo_system/udev/99-keyrgb-sysfs-leds.rules" ]; then
    printf '%s\n' "$repo_system"
    return 0
  fi
  return 1
}

hardware_access_validate_ref() {
  printf '%s' "$1" | grep -Eq '^[A-Za-z0-9._-]{1,128}$'
}

hardware_access_validate_owner() {
  printf '%s' "$1" | grep -Eq '^[a-zA-Z0-9-]{1,39}$'
}

hardware_access_validate_repo() {
  printf '%s' "$1" | grep -Eq '^[A-Za-z0-9._-]{1,100}$'
}

hardware_access_validate_payload_dir() {
  local dir="$1"
  case "$dir" in
    ""|*..*) return 1 ;;
  esac
  if [ ! -d "$dir" ] || [ -L "$dir" ]; then
    return 1
  fi
  if [ ! -f "$dir/udev/99-ite8291-wootbook.rules" ] \
    || [ ! -f "$dir/udev/99-keyrgb-sysfs-leds.rules" ] \
    || [ -L "$dir/udev/99-ite8291-wootbook.rules" ] \
    || [ -L "$dir/udev/99-keyrgb-sysfs-leds.rules" ]; then
    return 1
  fi
  return 0
}

# Download selected payload files for an explicit ref. No main fallback.
# Returns non-zero on failure. Does not print the result line.
hardware_access_fetch_payload() {
  local ref="$1"
  local dest_root="$2"
  local reactive="$3"
  local power="$4"
  local owner repo rel url tmp dest

  owner="${KEYRGB_REPO_OWNER:-Rainexn0b}"
  repo="${KEYRGB_REPO_NAME:-keyRGB}"
  if ! hardware_access_validate_ref "$ref" \
    || ! hardware_access_validate_owner "$owner" \
    || ! hardware_access_validate_repo "$repo"; then
    printf 'invalid hardware-access ref or repository\n' >&2
    return 1
  fi
  if ! command -v curl >/dev/null 2>&1; then
    printf 'curl is required to download hardware-access payloads\n' >&2
    return 1
  fi

  local -a rels=(
    "udev/99-ite8291-wootbook.rules"
    "udev/99-keyrgb-sysfs-leds.rules"
  )
  if [ "$reactive" = 1 ]; then
    rels+=("udev/99-keyrgb-input-uaccess.rules")
  fi
  if [ "$power" = 1 ]; then
    rels+=(
      "bin/keyrgb-power-helper"
      "polkit/90-keyrgb-power-helper.rules"
      "polkit/org.keyrgb.power-helper.policy"
    )
  fi

  for rel in "${rels[@]}"; do
    case "$rel" in
      */*) ;;
      *) return 1 ;;
    esac
    dest="$dest_root/$rel"
    mkdir -p -- "$(dirname "$dest")"
    tmp="$(mktemp)"
    url="https://raw.githubusercontent.com/${owner}/${repo}/${ref}/system/${rel}"
    if ! curl -fsSL -- "$url" -o "$tmp"; then
      rm -f -- "$tmp"
      printf 'failed to download %s\n' "$rel" >&2
      return 1
    fi
    if [ ! -s "$tmp" ]; then
      rm -f -- "$tmp"
      printf 'downloaded empty payload %s\n' "$rel" >&2
      return 1
    fi
    mv -f -- "$tmp" "$dest"
  done
  return 0
}

hardware_access_selected_rows() {
  local reactive="$1"
  local power="$2"
  HARDWARE_ACCESS_ROWS=(
    "usb|udev/99-ite8291-wootbook.rules|etc/udev/rules.d/99-ite8291-wootbook.rules|0644"
    "sysfs|udev/99-keyrgb-sysfs-leds.rules|etc/udev/rules.d/99-keyrgb-sysfs-leds.rules|0644"
  )
  if [ "$reactive" = 1 ]; then
    HARDWARE_ACCESS_ROWS+=(
      "input|udev/99-keyrgb-input-uaccess.rules|etc/udev/rules.d/99-keyrgb-input-uaccess.rules|0644"
    )
  fi
  if [ "$power" = 1 ]; then
    HARDWARE_ACCESS_ROWS+=(
      "helper|bin/keyrgb-power-helper|usr/local/bin/keyrgb-power-helper|0755"
      "polkit-rule|polkit/90-keyrgb-power-helper.rules|etc/polkit-1/rules.d/90-keyrgb-power-helper.rules|0644"
      "polkit-action|polkit/org.keyrgb.power-helper.policy|usr/share/polkit-1/actions/org.keyrgb.power-helper.policy|0644"
    )
  fi
}

# Classify an existing destination. Prints skip, update, or create.
# Returns 11 on a foreign file. Returns 12 if the destination is unsafe.
hardware_access_classify_dest() {
  local dest="$1"
  local src="$2"
  local mode="$3"
  local kind="$4"
  local expected_mode current_mode

  if [ -L "$dest" ] || { [ -e "$dest" ] && [ ! -f "$dest" ]; }; then
    return 11
  fi
  if [ ! -e "$dest" ]; then
    printf 'create\n'
    return 0
  fi
  expected_mode="$((8#$mode))"
  current_mode="$(hardware_access_mode_value "$dest")"
  if cmp -s -- "$src" "$dest" && [ "$current_mode" = "$expected_mode" ]; then
    printf 'skip\n'
    return 0
  fi
  if hardware_access_is_managed_kind "$kind" "$dest"; then
    printf 'update\n'
    return 0
  fi
  return 11
}

# Copy once, optionally verify sha256sum of that copy, then install from it.
# Does not call sudo. Prints nothing. Returns 0, 11, or 12.
hardware_access_place_file() {
  local src="$1"
  local dest="$2"
  local mode="$3"
  local kind="$4"
  local expected_hash="${5:-}"
  local action copy actual parent

  if ! hardware_access_reject_unsafe_file "$src"; then
    return 12
  fi
  parent="$(dirname -- "$dest")"
  if [ ! -d "$parent" ] || [ ! -w "$parent" ]; then
    return 12
  fi
  if ! action="$(hardware_access_classify_dest "$dest" "$src" "$mode" "$kind")"; then
    return 11
  fi
  if [ "$action" = "skip" ]; then
    HARDWARE_ACCESS_LAST_ACTION="skipped"
    return 0
  fi

  copy="$(mktemp)"
  if ! cp -- "$src" "$copy"; then
    rm -f -- "$copy"
    return 12
  fi
  if [ -n "$expected_hash" ]; then
    actual="$(hardware_access_sha256 "$copy")"
    if [ "$actual" != "$expected_hash" ]; then
      rm -f -- "$copy"
      return 12
    fi
  fi
  if ! install -D -m "$mode" -- "$copy" "$dest"; then
    rm -f -- "$copy"
    return 12
  fi
  rm -f -- "$copy"
  HARDWARE_ACCESS_LAST_ACTION="wrote"
  return 0
}

# Full-installer write adapter. Uses sudo only when not already root.
hardware_access_place_file_privileged() {
  local src="$1"
  local dest="$2"
  local mode="$3"
  local kind="$4"
  local lib
  if [ "${EUID}" -eq 0 ]; then
    hardware_access_place_file "$src" "$dest" "$mode" "$kind" ""
    return $?
  fi
  lib="$(readlink -f -- "${BASH_SOURCE[0]}")"
  sudo /bin/bash -c 'source "$1" && hardware_access_place_file "$2" "$3" "$4" "$5" ""' _ \
    "$lib" "$src" "$dest" "$mode" "$kind"
}

hardware_access_load_hashes() {
  local hash_file="$1"
  local line rel hex
  declare -gA HARDWARE_ACCESS_HASHES=()
  HARDWARE_ACCESS_HASH_COUNT=0
  if [ -z "$hash_file" ]; then
    return 0
  fi
  if [ ! -f "$hash_file" ]; then
    return 1
  fi
  while IFS= read -r line || [ -n "$line" ]; do
    case "$line" in
      ""|\#*) continue ;;
    esac
    rel="${line%%=*}"
    hex="${line#*=}"
    if [ "$rel" = "$line" ] || [ -z "$rel" ] || [ "$rel" = "$hex" ]; then
      return 1
    fi
    if ! printf '%s' "$hex" | grep -Eq '^[0-9A-Fa-f]{64}$'; then
      return 1
    fi
    HARDWARE_ACCESS_HASHES["$rel"]="$(printf '%s' "$hex" | awk '{print tolower($0)}')"
    HARDWARE_ACCESS_HASH_COUNT=$((HARDWARE_ACCESS_HASH_COUNT + 1))
  done <"$hash_file"
  return 0
}

hardware_access_reload() {
  udevadm control --reload-rules
  udevadm trigger --action=change
  udevadm trigger --action=add --subsystem-match=usb --attr-match=idVendor=048d
  udevadm trigger --action=add --subsystem-match=input --property-match=ID_INPUT_KEYBOARD=1
  udevadm trigger --action=add --subsystem-match=leds
  udevadm settle
}

# The authenticated caller. pkexec sets PKEXEC_UID; sudo sets SUDO_USER.
# Prints the name or returns 1. Never returns root.
hardware_access_invoking_user() {
  local name
  if [ -n "${PKEXEC_UID:-}" ]; then
    case "$PKEXEC_UID" in
      ''|*[!0-9]*) return 1 ;;
    esac
    name="$(id -nu "$PKEXEC_UID")" || return 1
  elif [ -n "${SUDO_USER:-}" ]; then
    name="$SUDO_USER"
  else
    return 1
  fi
  hardware_access_user_is_safe "$name" || return 1
  printf '%s\n' "$name"
}

hardware_access_user_is_safe() {
  local user="$1"
  [ -n "$user" ] || return 1
  [ "$user" != "root" ] || return 1
  printf '%s' "$user" | grep -Eq '^[a-zA-Z_][a-zA-Z0-9._-]{0,31}$'
}

# Add the invoking user to video when missing. Prints "added" or "already".
# Already-root caller. Does not create the video group.
hardware_access_ensure_video_group() {
  local user="$1"
  local groups
  if [ "$(id -u)" -ne 0 ]; then
    printf 'not-root\n' >&2
    return 1
  fi
  hardware_access_user_is_safe "$user" || {
    printf 'unsafe-user\n' >&2
    return 1
  }
  if ! getent passwd "$user" >/dev/null; then
    printf 'unknown-user\n' >&2
    return 1
  fi
  if ! getent group video >/dev/null; then
    printf 'missing-video-group\n' >&2
    return 1
  fi
  groups="$(id -nG "$user")"
  case " $groups " in
    *" video "*)
      printf 'already\n'
      return 0
      ;;
  esac
  if ! command -v usermod >/dev/null 2>&1; then
    printf 'missing-usermod\n' >&2
    return 1
  fi
  if ! usermod -a -G video "$user"; then
    printf 'usermod-failed\n' >&2
    return 1
  fi
  printf 'added\n'
}

# User-install entry. Uses sudo when the caller is not already root.
hardware_access_ensure_invoking_video_group() {
  local user lib
  if [ "$(id -u)" -eq 0 ]; then
    user="$(hardware_access_invoking_user)" || {
      printf 'missing-invoking-user\n' >&2
      return 1
    }
    hardware_access_ensure_video_group "$user"
    return
  fi
  user="$(id -un)"
  lib="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/hardware_access.sh"
  sudo /bin/bash -c 'source "$1" && hardware_access_ensure_video_group "$2"' _ "$lib" "$user"
}

# Install selected payloads under dest_root. Already-root caller. No sudo.
# hash_file empty means CLI checkout: hashes are not required.
hardware_access_apply() {
  local payload_dir="$1"
  local dest_root="$2"
  local reactive="$3"
  local power="$4"
  local hash_file="${5:-}"
  local row kind rel dest_rel mode src dest parent expected actual key known action old_ifs
  local target_user video_state video_err video_reason
  local -a written=()
  local written_csv=""

  if [ "$reactive" != 0 ] && [ "$reactive" != 1 ]; then
    hardware_access_finish "$HARDWARE_ACCESS_EXIT_FAILED" failed "bad-selection written=none"
  fi
  if [ "$power" != 0 ] && [ "$power" != 1 ]; then
    hardware_access_finish "$HARDWARE_ACCESS_EXIT_FAILED" failed "bad-selection written=none"
  fi
  if ! hardware_access_validate_payload_dir "$payload_dir"; then
    hardware_access_finish "$HARDWARE_ACCESS_EXIT_PREREQUISITE" prerequisite bad-payload-dir
  fi
  if ! command -v sha256sum >/dev/null 2>&1; then
    hardware_access_finish "$HARDWARE_ACCESS_EXIT_PREREQUISITE" prerequisite missing-sha256sum
  fi
  if ! command -v install >/dev/null 2>&1; then
    hardware_access_finish "$HARDWARE_ACCESS_EXIT_PREREQUISITE" prerequisite missing-install
  fi
  if ! command -v udevadm >/dev/null 2>&1; then
    hardware_access_finish "$HARDWARE_ACCESS_EXIT_PREREQUISITE" prerequisite missing-udevadm
  fi
  if [ "$power" = 1 ] && ! command -v python3 >/dev/null 2>&1; then
    hardware_access_finish "$HARDWARE_ACCESS_EXIT_PREREQUISITE" prerequisite missing-python3
  fi
  if ! target_user="$(hardware_access_invoking_user)"; then
    hardware_access_finish "$HARDWARE_ACCESS_EXIT_PREREQUISITE" prerequisite missing-invoking-user
  fi
  if ! getent group video >/dev/null; then
    hardware_access_finish "$HARDWARE_ACCESS_EXIT_PREREQUISITE" prerequisite missing-video-group
  fi
  if ! hardware_access_load_hashes "$hash_file"; then
    hardware_access_finish "$HARDWARE_ACCESS_EXIT_FAILED" failed "bad-hash written=none"
  fi

  hardware_access_selected_rows "$reactive" "$power"
  if [ "$HARDWARE_ACCESS_HASH_COUNT" -gt 0 ]; then
    for key in "${!HARDWARE_ACCESS_HASHES[@]}"; do
      known=0
      for row in "${HARDWARE_ACCESS_ROWS[@]}"; do
        rel="${row#*|}"
        rel="${rel%%|*}"
        if [ "$rel" = "$key" ]; then
          known=1
        fi
      done
      if [ "$known" -ne 1 ]; then
        hardware_access_finish "$HARDWARE_ACCESS_EXIT_FAILED" failed "unknown-hash written=none"
      fi
    done
  fi

  old_ifs="$IFS"
  for row in "${HARDWARE_ACCESS_ROWS[@]}"; do
    IFS='|' read -r kind rel dest_rel mode <<<"$row"
    IFS="$old_ifs"
    src="$(hardware_access_under "$payload_dir" "$rel")"
    dest="$(hardware_access_under "$dest_root" "$dest_rel")"
    if [ ! -f "$src" ] || [ -L "$src" ]; then
      hardware_access_finish "$HARDWARE_ACCESS_EXIT_PREREQUISITE" prerequisite missing-payload
    fi
    if ! hardware_access_reject_unsafe_file "$src"; then
      hardware_access_finish "$HARDWARE_ACCESS_EXIT_PREREQUISITE" prerequisite unsafe-payload
    fi
    if [ "$HARDWARE_ACCESS_HASH_COUNT" -gt 0 ]; then
      if [ -z "${HARDWARE_ACCESS_HASHES[$rel]+x}" ]; then
        hardware_access_finish "$HARDWARE_ACCESS_EXIT_FAILED" failed "missing-hash written=none"
      fi
      actual="$(hardware_access_sha256 "$src")"
      if [ "$actual" != "${HARDWARE_ACCESS_HASHES[$rel]}" ]; then
        hardware_access_finish "$HARDWARE_ACCESS_EXIT_FAILED" failed "hash-mismatch written=none"
      fi
    fi
    parent="$(dirname -- "$dest")"
    if [ ! -d "$parent" ] || [ ! -w "$parent" ]; then
      hardware_access_finish "$HARDWARE_ACCESS_EXIT_PREREQUISITE" prerequisite unwritable-destination
    fi
    if ! action="$(hardware_access_classify_dest "$dest" "$src" "$mode" "$kind")"; then
      hardware_access_finish "$HARDWARE_ACCESS_EXIT_CONFLICT" conflict "$dest"
    fi
  done

  for row in "${HARDWARE_ACCESS_ROWS[@]}"; do
    IFS='|' read -r kind rel dest_rel mode <<<"$row"
    IFS="$old_ifs"
    src="$(hardware_access_under "$payload_dir" "$rel")"
    dest="$(hardware_access_under "$dest_root" "$dest_rel")"
    expected=""
    if [ "$HARDWARE_ACCESS_HASH_COUNT" -gt 0 ]; then
      expected="${HARDWARE_ACCESS_HASHES[$rel]}"
    fi
    if ! hardware_access_place_file "$src" "$dest" "$mode" "$kind" "$expected"; then
      written_csv="none"
      if [ "${#written[@]}" -gt 0 ]; then
        written_csv="$(IFS=','; printf '%s' "${written[*]}")"
      fi
      hardware_access_finish "$HARDWARE_ACCESS_EXIT_FAILED" failed "install written=${written_csv}"
    fi
    if [ "${HARDWARE_ACCESS_LAST_ACTION:-}" = "wrote" ]; then
      written+=("$dest")
    fi
  done

  if ! hardware_access_reload; then
    written_csv="none"
    if [ "${#written[@]}" -gt 0 ]; then
      written_csv="$(IFS=','; printf '%s' "${written[*]}")"
    fi
    hardware_access_finish "$HARDWARE_ACCESS_EXIT_FAILED" failed "reload written=${written_csv}"
  fi
  video_err="$(mktemp)"
  if ! video_state="$(hardware_access_ensure_video_group "$target_user" 2>"$video_err")"; then
    video_reason="$(head -n 1 "$video_err" 2>/dev/null || true)"
    rm -f -- "$video_err"
    written_csv="none"
    if [ "${#written[@]}" -gt 0 ]; then
      written_csv="$(IFS=','; printf '%s' "${written[*]}")"
    fi
    hardware_access_finish "$HARDWARE_ACCESS_EXIT_FAILED" failed "video-group ${video_reason:-group-add} written=${written_csv}"
  fi
  rm -f -- "$video_err"
  hardware_access_finish "$HARDWARE_ACCESS_EXIT_OK" installed "video-group=${video_state}"
}
