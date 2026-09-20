#!/usr/bin/env bash
# Sequential full AgentDyn B1 run.  One suite/mode process at a time.
set -euo pipefail
source /usr/local/miniconda3/etc/profile.d/conda.sh
set -a
source /data/home/qyc/.config/drift/openai.env
set +a
cd /data/home/qyc/Project/drift-new
export PYTHONPATH=/data/home/qyc/Project/AgentDyn/src:${PYTHONPATH:-}
export HTTP_PROXY=http://127.0.0.1:17890
export HTTPS_PROXY=http://127.0.0.1:17890
export NO_PROXY=localhost,127.0.0.1

tag_prefix=agentdyn_b1_full_fixedv2_t07_20260916
status=reports/rcvr_ablation_preflight/agentdyn_b1_full.status
mkdir -p reports/rcvr_ablation_preflight
printf 'started %s\n' "$(date -Iseconds)" > "$status"

for suite in shopping github dailylife; do
  root="reports/rcvr_ablation_preflight/agentdyn_b1_full_${suite}"
  conda run -n drift python -B experiments/rcdc/prepare_agentdyn_rcvr_preflight.py \
    --suite "$suite" --all --output-root "$root"
  for mode in clean attack; do
    printf 'running %s %s %s\n' "$suite" "$mode" "$(date -Iseconds)" >> "$status"
    args=(run --config-id B1_RCVR --confirm-online-execution --preflight-root "$root"
      --suites "$suite" --contract_profile agentdyn --force_rerun
      --build_constraints --injection_isolation --dynamic_validation
      --taer_mode on --taer_variant full --source_flow_validation --source_flow_log source_flow
      --runtime_drift_trace --temperature 0.7 --run_tag "${tag_prefix}_${suite}_${mode}")
    if [[ "$mode" == attack ]]; then args+=(--do_attack); fi
    conda run -n drift python -B experiments/rcdc/run_rcvr_online.py "${args[@]}"
    printf 'completed %s %s %s\n' "$suite" "$mode" "$(date -Iseconds)" >> "$status"
  done
done
printf 'completed_all %s\n' "$(date -Iseconds)" >> "$status"
