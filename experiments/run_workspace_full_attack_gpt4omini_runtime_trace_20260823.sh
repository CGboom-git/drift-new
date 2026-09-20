#!/usr/bin/env bash
set -euo pipefail
source /usr/local/miniconda3/etc/profile.d/conda.sh
source /data/home/qyc/.config/drift/openai.env
cd /data/home/qyc/Project/drift-new
exec conda run --no-capture-output -n drift python -B pipeline_main.py \
  --model gpt-4o-mini-2024-07-18 \
  --suites workspace \
  --run_tag full_attack_gpt4omini_runtime_trace_20260823 \
  --benchmark_version v1.2 \
  --build_constraints \
  --injection_isolation \
  --dynamic_validation \
  --taer_mode on \
  --taer_variant full \
  --source_flow_validation \
  --source_flow_log source_flow \
  --runtime_drift_trace \
  --do_attack \
  --attack_type important_instructions \
  --force_rerun
