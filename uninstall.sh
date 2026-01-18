#!/usr/bin/env bash

# KeyRGB modular uninstaller (dispatcher)
#
# Works both:
# - from a repo checkout (uses ./scripts/uninstall.sh)
# - via curl-pipe installs (bootstraps scripts from GitHub raw)

set -euo pipefail

KEYRGB_REPO_OWNER="${KEYRGB_REPO_OWNER:-Rainexn0b}"
KEYRGB_REPO_NAME="${KEYRGB_REPO_NAME:-keyRGB}"
KEYRGB_BOOTSTRAP_REF="${KEYRGB_BOOTSTRAP_REF:-main}"

usage() {
  cat <<'EOF'
Usage:
  uninstall.sh [--ref <git-ref>] [--help] [...uninstall args]

Bootstrap (curl installs):
  --ref <git-ref>    Git ref for downloading scripts/ from GitHub raw (default: main)
  KEYRGB_BOOTSTRAP_REF can also be used.

Example:
  curl -fsSL https://raw.githubusercontent.com/Rainexn0b/keyRGB/main/uninstall.sh | bash -- --yes
EOF
}

REF_OVERRIDE=""
args=("$@")
i=0
while [ $i -lt ${#args[@]} ]; do
  case "${args[$i]}" in
    --ref)
      j=$((i+1))
      REF_OVERRIDE="${args[$j]:-}"
      unset 'args[$i]'
      unset 'args[$j]'
      i=$((i+1))
      ;;
    -h|--help)
      usage
      exit 0
      ;;
  esac
  i=$((i+1))
done

if [ -n "$REF_OVERRIDE" ]; then
  KEYRGB_BOOTSTRAP_REF="$REF_OVERRIDE"
fi

NEW_ARGS=()
for a in "${args[@]}"; do
  if [ -n "${a:-}" ]; then
    NEW_ARGS+=("$a")
  fi
done

SCRIPT_SELF="${BASH_SOURCE[0]:-}"
SCRIPT_DIR=""
if [ -n "$SCRIPT_SELF" ] && [ -f "$SCRIPT_SELF" ]; then
  SCRIPT_DIR="$(cd "$(dirname "$SCRIPT_SELF")" && pwd)"
fi

if [ -n "$SCRIPT_DIR" ] && [ -f "$SCRIPT_DIR/scripts/uninstall.sh" ]; then
  exec bash "$SCRIPT_DIR/scripts/uninstall.sh" "${NEW_ARGS[@]}"
fi

command -v curl >/dev/null 2>&1 || {
  echo "❌ curl is required for curl-pipe uninstalls" >&2
  exit 1
}

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
mkdir -p "$tmp/scripts"
mkdir -p "$tmp/scripts/lib"

base="https://raw.githubusercontent.com/${KEYRGB_REPO_OWNER}/${KEYRGB_REPO_NAME}/${KEYRGB_BOOTSTRAP_REF}"
curl -fsSL "$base/scripts/common.sh" -o "$tmp/scripts/common.sh"
curl -fsSL "$base/scripts/lib/common_core.sh" -o "$tmp/scripts/lib/common_core.sh"
curl -fsSL "$base/scripts/lib/state.sh" -o "$tmp/scripts/lib/state.sh"
curl -fsSL "$base/scripts/lib/optional_components.sh" -o "$tmp/scripts/lib/optional_components.sh"
curl -fsSL "$base/scripts/lib/privileged_helpers.sh" -o "$tmp/scripts/lib/privileged_helpers.sh"
curl -fsSL "$base/scripts/lib/user_integration.sh" -o "$tmp/scripts/lib/user_integration.sh"
curl -fsSL "$base/scripts/lib/user_prompts.sh" -o "$tmp/scripts/lib/user_prompts.sh"
curl -fsSL "$base/scripts/uninstall.sh" -o "$tmp/scripts/uninstall.sh"

exec bash "$tmp/scripts/uninstall.sh" "${NEW_ARGS[@]}"

exit 0

# Legacy monolithic uninstaller has been moved to scripts/uninstall.legacy.sh
