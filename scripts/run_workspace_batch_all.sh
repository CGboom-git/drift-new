#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

bash "$SCRIPT_DIR/run_workspace_batch_1.sh"
bash "$SCRIPT_DIR/run_workspace_batch_2.sh"
bash "$SCRIPT_DIR/run_workspace_batch_3.sh"
bash "$SCRIPT_DIR/run_workspace_batch_4.sh"
