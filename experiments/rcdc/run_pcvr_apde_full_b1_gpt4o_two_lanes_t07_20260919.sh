#!/usr/bin/env bash
# Full AgentDojo RCVR (B1) run: GPT-4o, temperature 0.7, two isolated lanes.
set -euo pipefail

cd /data/home/qyc/Project/drift-new
set -a
source /data/home/qyc/.config/drift/openai.env
set +a
: "${OPENAI_API_KEY:?OPENAI_API_KEY is required}"

export HTTP_PROXY="http://127.0.0.1:17890"
export HTTPS_PROXY="http://127.0.0.1:17890"
export NO_PROXY="localhost,127.0.0.1"

CONDA_BIN="${CONDA_EXE:-/usr/local/miniconda3/bin/conda}"
RUN_TAG="pcvr_apde_full_b1_gpt4o_t07_20260919"
OUT_DIR="reports/rcvr_ablation_preflight/full_b1_gpt4o_two_lanes_t07_20260919"
mkdir -p "$OUT_DIR"
printf 'started=%s\nrun_tag=%s\nmodel=gpt-4o\ntemperature=0.7\n' "$(date -Is)" "$RUN_TAG" > "$OUT_DIR/status"

run_lane() {
  local lane="$1"
  local suites="$2"
  local log="$OUT_DIR/${lane}.log"
  local common=(
    run --no-capture-output -n drift python -B experiments/rcdc/run_rcvr_online.py run
    --config-id B1_RCVR --confirm-online-execution
    --model gpt-4o --temperature 0.7 --benchmark_version v1.2
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
printf 'completed=%s\n' "$(date -Is)" >> "$OUT_DIR/status"
