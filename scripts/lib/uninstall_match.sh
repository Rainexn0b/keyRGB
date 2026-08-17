#!/usr/bin/env bash

# Shared KeyRGB uninstall matching helpers.
#
# Installer-managed system files are identified by either:
# - exact byte match against the checkout/bootstrap source copy, or
# - stable KEYRGB_MANAGED_* markers (plus legacy comment markers for older installs).
#
# Bootstrap curl uninstalls often lack the source tree under system/, so marker
# matching must remain sufficient on its own.

file_has_marker() {
  local path="$1" marker="$2"
  [ -f "$path" ] || return 1
  grep -Fqs -- "$marker" "$path" 2>/dev/null
}

files_match_exactly() {
  local left="$1" right="$2"
  [ -f "$left" ] && [ -f "$right" ] && cmp -s "$left" "$right"
}

# Stable markers written into current managed artifacts.
KEYRGB_MANAGED_UDEV_USB_MARKER='KEYRGB_MANAGED_UDEV_RULE=usb-hidraw'
KEYRGB_MANAGED_UDEV_SYSFS_MARKER='KEYRGB_MANAGED_UDEV_RULE=sysfs-leds'
KEYRGB_MANAGED_UDEV_INPUT_MARKER='KEYRGB_MANAGED_UDEV_RULE=input-uaccess'

is_keyrgb_managed_usb_udev_rule() {
  local path="$1"
  file_has_marker "$path" "$KEYRGB_MANAGED_UDEV_USB_MARKER" && return 0
  # Legacy headers from older KeyRGB releases.
  file_has_marker "$path" "Allow user access to ITE 8291 USB device." && return 0
  file_has_marker "$path" "Allow user access to supported ITE / Lenovo USB / hidraw devices." && return 0
  return 1
}

is_keyrgb_managed_sysfs_udev_rule() {
  local path="$1"
  file_has_marker "$path" "$KEYRGB_MANAGED_UDEV_SYSFS_MARKER" && return 0
  file_has_marker "$path" "Allow KeyRGB to write keyboard backlight sysfs LED attributes." && return 0
  return 1
}

is_keyrgb_managed_input_udev_rule() {
  local path="$1"
  file_has_marker "$path" "$KEYRGB_MANAGED_UDEV_INPUT_MARKER" && return 0
  # Legacy markers: older uninstall looked for "Reactive Typing effects"; current
  # rule text uses "reactive effects" in the security warning sentence.
  file_has_marker "$path" "Reactive Typing effects" && return 0
  file_has_marker "$path" "for reactive effects." && return 0
  return 1
}

should_remove_managed_file() {
  # Args: installed_path source_path is_managed_fn_name
  local installed_path="$1" source_path="$2" is_managed_fn="$3"
  if [ ! -f "$installed_path" ]; then
    return 1
  fi
  if files_match_exactly "$source_path" "$installed_path"; then
    return 0
  fi
  "$is_managed_fn" "$installed_path"
}
