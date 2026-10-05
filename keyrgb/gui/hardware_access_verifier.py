"""Fixed pkexec verifier for hardware-access setup.

The script text is a constant. Paths and hashes are positional arguments, not
interpolated into the script. ``/bin/sh`` is dash on Debian and Ubuntu, so the
script stays POSIX.
"""

from __future__ import annotations

VERIFIER = """
set -eu
reject() {
  printf 'keyrgb-hardware-access: failed %s written=none\\n' "$1"
  exit 12
}
copy_verified() {
  src=$1
  expected=$2
  dest=$3
  if [ -L "$src" ] || [ ! -f "$src" ]; then
    reject unsafe-code
  fi
  mode=$(stat -c '%a' -- "$src")
  if [ "$((8#$mode & 8#002))" -ne 0 ] || [ "$((8#$mode & 8#6000))" -ne 0 ]; then
    reject unsafe-code
  fi
  mkdir -p -- "$(dirname -- "$dest")"
  tmp=$(mktemp)
  cp -- "$src" "$tmp"
  actual=$(sha256sum -- "$tmp" | awk 'NR==1 { print $1 }')
  if [ "$actual" != "$expected" ]; then
    rm -f -- "$tmp"
    reject hash-mismatch
  fi
  mv -- "$tmp" "$dest"
  chmod 0700 -- "$dest"
}
if [ "$#" -lt 9 ]; then
  reject bad-invocation
fi
entry_src=$1
entry_hash=$2
lib_src=$3
lib_hash=$4
match_src=$5
match_hash=$6
payload=$7
reactive=$8
power=$9
shift 9
hash_file=$(mktemp)
while [ "$#" -gt 0 ]; do
  if [ "$#" -lt 2 ]; then
    rm -f -- "$hash_file"
    reject bad-hash
  fi
  printf '%s\\n' "$1=$2" >> "$hash_file"
  shift 2
done
root=$(mktemp -d)
trap 'rm -rf -- "$root" "$hash_file"' EXIT
copy_verified "$entry_src" "$entry_hash" "$root/install_hardware_access.sh"
copy_verified "$lib_src" "$lib_hash" "$root/lib/hardware_access.sh"
copy_verified "$match_src" "$match_hash" "$root/lib/uninstall_match.sh"
set -- /bin/bash "$root/install_hardware_access.sh" --payload-dir "$payload"
if [ "$reactive" = 1 ]; then
  set -- "$@" --reactive-input
fi
if [ "$power" = 1 ]; then
  set -- "$@" --power-controls
fi
while IFS= read -r hash_line; do
  set -- "$@" --hash "$hash_line"
done < "$hash_file"
"$@"
status=$?
exit "$status"
"""

PKEXEC_STDERR_MARKERS = (
    "Error executing command as another user",
    "Error checking for authorization",
    "Error creating textual authentication agent",
    "Error registering local authentication agent",
    "No authentication agent found",
    "Not authorized",
)


def is_pkexec_stderr(stderr: str) -> bool:
    return any(marker in stderr for marker in PKEXEC_STDERR_MARKERS)
