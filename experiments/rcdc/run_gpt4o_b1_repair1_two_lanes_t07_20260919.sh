#!/usr/bin/env bash
# Repair only audit-invalid GPT-4o B1 cases.  Do not reuse the invalid run's directory.
set -euo pipefail

cd /data/home/qyc/Project/drift-new
set -a
source /data/home/qyc/.config/drift/openai.env
set +a
: "${OPENAI_API_KEY:?OPENAI_API_KEY is required}"
: "${OPENAI_BASE_URL:?OPENAI_BASE_URL is required}"

export HTTP_PROXY="http://127.0.0.1:17890"
export HTTPS_PROXY="http://127.0.0.1:17890"
export NO_PROXY="localhost,127.0.0.1"

CONDA_BIN="${CONDA_EXE:-/usr/local/miniconda3/bin/conda}"
RUN_TAG="pcvr_apde_full_b1_gpt4o_t07_20260919_repair1"
OUT_DIR="reports/rcvr_ablation_preflight/full_b1_gpt4o_repair1_two_lanes_t07_20260919"
mkdir -p "$OUT_DIR"

# Authenticated, non-inference preflight over the exact proxy path.  It incurs
# no generation charge and fails before either lane starts on any non-2xx HTTP status.
preflight_status="$(curl --silent --show-error --output /dev/null --write-out '%{http_code}' \
  --connect-timeout 10 --max-time 30 --retry 0 \
  -H "Authorization: Bearer ${OPENAI_API_KEY}" "${OPENAI_BASE_URL%/}/models")"
if [[ ! "$preflight_status" =~ ^2 ]]; then
  printf 'preflight_failed=%s status=%s\n' "$(date -Is)" "$preflight_status" | tee "$OUT_DIR/status"
  exit 70
fi

printf 'started=%s\nrun_tag=%s\nmodel=gpt-4o\ntemperature=0.7\npreflight_http_status=%s\nopenai_max_retries=0\n' \
  "$(date -Is)" "$RUN_TAG" "$preflight_status" > "$OUT_DIR/status"

run_lane() {
  local lane="$1"
  local suites="$2"
  local manifest="$OUT_DIR/${lane}_repair_manifest.json"
  local log="$OUT_DIR/${lane}.log"
  local common=(
    run --no-capture-output -n drift python -B experiments/rcdc/run_rcvr_online.py run
    --config-id B1_RCVR --confirm-online-execution
    --model gpt-4o --temperature 0.7 --benchmark_version v1.2
    --suites "$suites" --run_tag "$RUN_TAG"
    --target_case_manifest "$manifest" --openai_max_retries 0
    --build_constraints --injection_isolation --dynamic_validation
    --taer_mode on --taer_variant full
    --source_flow_validation --source_flow_log source_flow --runtime_drift_trace
  )
  "$CONDA_BIN" "${common[@]}" \
    >"$log" 2>&1
  "$CONDA_BIN" "${common[@]}" --do_attack --attack_type important_instructions \
    >>"$log" 2>&1
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
