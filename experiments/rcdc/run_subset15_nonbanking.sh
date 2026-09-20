#!/usr/bin/env bash
set -euo pipefail
cd /data/home/qyc/Project/drift-new
out=reports/rcvr_mechanism_subset15_20260920
trap 'status=$?; printf "%s exit=%s\n" "$(date -Is)" "$status" > "$out/nonbanking_finished.status"' EXIT
set -a
source /data/home/qyc/.config/drift/openai.env
set +a
/usr/local/miniconda3/bin/conda run --no-capture-output -n drift \
  python -B experiments/rcdc/run_rcvr_online.py run \
  --config-id B1_RCVR --confirm-online-execution \
  --preflight-root experiments/rcdc/subset15_preflight \
  --checkpoint-dir "$out/checkpoints" \
  --target_case_manifest experiments/rcdc/rcvr_mechanism_subset15_run_manifest.json \
  --model gpt-4o-mini-2024-07-18 --temperature 0.7 \
  --benchmark_version v1.2 --suites slack,travel,workspace \
  --run_tag rcvr_mechanism_subset15_20260920 \
  --build_constraints --injection_isolation --dynamic_validation \
  --taer_mode on --taer_variant full \
  --source_flow_validation --source_flow_log source_flow \
  --runtime_drift_trace --do_attack --attack_type important_instructions \
  > "$out/nonbanking_attacked.log" 2>&1
