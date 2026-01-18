#!/usr/bin/env bash

# Shared installer utilities (loader).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# shellcheck disable=SC1091
source "$SCRIPT_DIR/lib/common_core.sh"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/lib/state.sh"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/lib/optional_components.sh"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/lib/privileged_helpers.sh"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/lib/user_integration.sh"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/lib/user_prompts.sh"
