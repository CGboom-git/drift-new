#!/usr/bin/env bash
set -euo pipefail
if [ "$#" -ne 1 ]; then
  echo "usage: $0 SUITES_CSV" >&2
  exit 2
fi
set -a
source /data/home/qyc/.config/drift/openai.env
set +a
: "${OPENAI_API_KEY:?OPENAI_API_KEY is required}"
CONDA_BIN="${CONDA_EXE:-/usr/local/miniconda3/bin/conda}"
COMMON=(
  run --no-capture-output -n drift python -B experiments/rcdc/run_rcvr_online.py run
  --config-id B1_RCVR --confirm-online-execution
  --model gpt-4o-mini-2024-07-18 --temperature 0.7 --benchmark_version v1.2
  --suites "$1" --run_tag rcvr_full_b1_agentdojo_v12_t07_20260911
  --build_constraints --injection_isolation --dynamic_validation --taer_mode off
)
"$CONDA_BIN" "${COMMON[@]}"
"$CONDA_BIN" "${COMMON[@]}" --do_attack --attack_type important_instructions
