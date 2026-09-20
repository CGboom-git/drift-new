#!/usr/bin/env bash
# B4 full benchmark: two suite lanes, each clean then attack.
set -euo pipefail

cd /data/home/qyc/Project/drift-new
set -a
source /data/home/qyc/.config/drift/openai.env
set +a
: "${OPENAI_API_KEY:?OPENAI_API_KEY is required}"

CONDA_BIN="${CONDA_EXE:-/usr/local/miniconda3/bin/conda}"
RUN_TAG="pcvr_apde_full_b4_v12_t07_20260914"
OUT_DIR="reports/rcvr_ablation_preflight/full_b4_t07_20260914"
mkdir -p "$OUT_DIR"

run_lane() {
  local lane="$1"
  local suites="$2"
  local log="$OUT_DIR/${lane}.log"
  local common=(
    run --no-capture-output -n drift python -B experiments/rcdc/run_rcvr_online.py run
    --config-id B4_UNKNOWN_ALLOW --confirm-online-execution
    --model gpt-4o-mini-2024-07-18 --temperature 0.7 --benchmark_version v1.2
    --suites "$suites" --run_tag "$RUN_TAG"
    --build_constraints --injection_isolation --dynamic_validation
    --taer_mode on --taer_variant full
    --source_flow_validation --source_flow_log source_flow --runtime_drift_trace
  )
  "$CONDA_BIN" "${common[@]}" >"$log" 2>&1
  "$CONDA_BIN" "${common[@]}" --do_attack --attack_type important_instructions >>"$log" 2>&1
}

run_lane workspace workspace &
workspace_pid=$!
run_lane others banking,slack,travel &
others_pid=$!
printf '%s\n' "$workspace_pid" > "$OUT_DIR/workspace.pid"
printf '%s\n' "$others_pid" > "$OUT_DIR/others.pid"
wait "$workspace_pid"
wait "$others_pid"
