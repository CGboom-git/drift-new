#!/usr/bin/env bash
set -euo pipefail
cd /data/home/qyc/Project/drift-new
set -a
source /data/home/qyc/.config/drift/openai.env
set +a
: "${OPENAI_API_KEY:?OPENAI_API_KEY is required}"
CONDA_BIN="${CONDA_EXE:-/usr/local/miniconda3/bin/conda}"
COMMON=(
  run --no-capture-output -n drift python -B experiments/rcdc/run_rcvr_online.py run
  --config-id B1_RCVR --confirm-online-execution
  --model gpt-4o-mini-2024-07-18 --temperature 0.7 --benchmark_version v1.2
  --suites banking,slack,travel,workspace
  --run_tag pcvr_apde_full_b1_v12_t07_20260911
  --build_constraints --injection_isolation --dynamic_validation
  --taer_mode on --taer_variant full
  --source_flow_validation --source_flow_log source_flow --runtime_drift_trace
)
"$CONDA_BIN" "${COMMON[@]}"
"$CONDA_BIN" "${COMMON[@]}" --do_attack --attack_type important_instructions
