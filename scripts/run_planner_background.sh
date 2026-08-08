#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$ROOT_DIR/runs/planner_stability"
PID_FILE="$LOG_DIR/planner_stability.pid"
NOHUP_LOG="$LOG_DIR/planner_stability.nohup.log"

mkdir -p "$LOG_DIR"
rm -f "$ROOT_DIR/runs/planner_stability/planner_runs.jsonl" \
      "$ROOT_DIR/runs/planner_stability/planner_runs.json" \
      "$ROOT_DIR/runs/planner_stability/planner_stability.log" \
      "$NOHUP_LOG" \
      "$PID_FILE"

export OPENAI_API_KEY="${OPENAI_API_KEY:-}"
export OPENAI_BASE_URL="${OPENAI_BASE_URL:-}"

if [[ -z "${OPENAI_API_KEY}" || -z "${OPENAI_BASE_URL}" ]]; then
  if [[ -f "$HOME/.config/drift/openai.env" ]]; then
    # shellcheck disable=SC1090
    source "$HOME/.config/drift/openai.env"
  fi
fi

if [[ -z "${OPENAI_API_KEY:-}" || -z "${OPENAI_BASE_URL:-}" ]]; then
  echo "OPENAI_API_KEY or OPENAI_BASE_URL is missing" >&2
  exit 1
fi

if [[ -f "$HOME/anaconda3/etc/profile.d/conda.sh" ]]; then
  # shellcheck disable=SC1091
  source "$HOME/anaconda3/etc/profile.d/conda.sh"
  conda activate drift
fi

cd "$ROOT_DIR"
nohup python scripts/generate_plans.py --suite all --runs_per_task 5 > "$NOHUP_LOG" 2>&1 </dev/null &
echo $! > "$PID_FILE"
sleep 2
if kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
  echo "Planner background process started: $(cat "$PID_FILE")"
else
  echo "Planner background process failed to start" >&2
  exit 1
fi
