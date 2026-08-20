#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="/home/cg/Code/drift-new-bestbackup"
LOG_FILE="$ROOT_DIR/experiments/workspace_selected_20260819.out.log"
PID_FILE="$ROOT_DIR/experiments/workspace_selected_20260819.pid"

mkdir -p "$ROOT_DIR/experiments"
cd "$ROOT_DIR"

nohup bash "$ROOT_DIR/scripts/run_workspace_batch_all.sh" > "$LOG_FILE" 2>&1 < /dev/null &
echo $! > "$PID_FILE"
echo "started $(cat "$PID_FILE")"
echo "log: $LOG_FILE"
