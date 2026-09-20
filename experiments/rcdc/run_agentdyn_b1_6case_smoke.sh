#!/usr/bin/env bash
# Sequential AgentDyn B1 acceptance smoke.  Each target has its own frozen
# preflight root and run tag; a failed command stops the queue immediately.
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

tag_prefix=agentdyn_b1_smoke6_fixedv2_t07
status=reports/rcvr_ablation_preflight/agentdyn_b1_smoke6.status
mkdir -p reports/rcvr_ablation_preflight
printf 'started %s\n' "$(date -Iseconds)" > "$status"

for suite in shopping github dailylife; do
  root="reports/rcvr_ablation_preflight/agentdyn_b1_smoke6_${suite}_u0_i0"
  conda run -n drift python -B experiments/rcdc/prepare_agentdyn_rcvr_preflight.py \
    --suite "$suite" --user-task user_task_0 --injection-task injection_task_0 \
    --output-root "$root"

  printf 'running %s clean %s\n' "$suite" "$(date -Iseconds)" >> "$status"
  conda run -n drift python -B experiments/rcdc/run_rcvr_online.py run \
    --config-id B1_RCVR --confirm-online-execution --preflight-root "$root" \
    --suites "$suite" --contract_profile agentdyn --target_user_tasks 0 --target_injection_tasks 0 \
    --force_rerun --build_constraints --injection_isolation --dynamic_validation \
    --taer_mode on --taer_variant full --source_flow_validation --source_flow_log source_flow \
    --runtime_drift_trace --temperature 0.7 --run_tag "${tag_prefix}_${suite}_clean"
  printf 'completed %s clean %s\n' "$suite" "$(date -Iseconds)" >> "$status"

  printf 'running %s attack %s\n' "$suite" "$(date -Iseconds)" >> "$status"
  conda run -n drift python -B experiments/rcdc/run_rcvr_online.py run \
    --config-id B1_RCVR --confirm-online-execution --preflight-root "$root" \
    --suites "$suite" --contract_profile agentdyn --target_user_tasks 0 --target_injection_tasks 0 \
    --do_attack --force_rerun --build_constraints --injection_isolation --dynamic_validation \
    --taer_mode on --taer_variant full --source_flow_validation --source_flow_log source_flow \
    --runtime_drift_trace --temperature 0.7 --run_tag "${tag_prefix}_${suite}_attack"
  printf 'completed %s attack %s\n' "$suite" "$(date -Iseconds)" >> "$status"
done

printf 'completed_all %s\n' "$(date -Iseconds)" >> "$status"
