#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/run_workspace_batch_common.sh"

run_case 39 0
run_case 39 3
run_case 30 0
run_case 30 3
