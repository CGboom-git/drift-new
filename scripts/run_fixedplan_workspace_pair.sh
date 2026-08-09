#!/usr/bin/env bash
set -euo pipefail

cd /home/cg/Code/DRIFT
mkdir -p experiments

export HTTP_PROXY=http://127.0.0.1:7890
export HTTPS_PROXY=http://127.0.0.1:7890
unset ALL_PROXY || true

if [[ -f /home/cg/.config/drift/openai.env ]]; then
  set -a
  source /home/cg/.config/drift/openai.env
  set +a
fi

source /home/cg/anaconda3/etc/profile.d/conda.sh
conda activate drift

nohup python pipeline_main.py \
  --suites workspace \
  --do_attack \
  --attack_type important_instructions \
  --build_constraints \
  --injection_isolation \
  --dynamic_validation \
  --taer_mode off \
  --fixed_plan_file data/canonical_plans_97_selection_audit.json \
  --force_rerun \
  --run_tag fixedplan_workspace_drift \
  --model gpt-4o-mini-2024-07-18 \
  > experiments/fixedplan_workspace_drift.out.log 2>&1 </dev/null &
echo $! > experiments/fixedplan_workspace_drift.pid

sleep 90

nohup python pipeline_main.py \
  --suites workspace \
  --do_attack \
  --attack_type important_instructions \
  --build_constraints \
  --injection_isolation \
  --dynamic_validation \
  --source_flow_validation \
  --source_flow_log source_flow \
  --taer_mode off \
  --fixed_plan_file data/canonical_plans_97_selection_audit.json \
  --force_rerun \
  --run_tag fixedplan_workspace_sourceflow_taeroff \
  --model gpt-4o-mini-2024-07-18 \
  > experiments/fixedplan_workspace_sourceflow_taeroff.out.log 2>&1 </dev/null &
echo $! > experiments/fixedplan_workspace_sourceflow_taeroff.pid

echo "started drift pid $(cat experiments/fixedplan_workspace_drift.pid)"
echo "started sourceflow pid $(cat experiments/fixedplan_workspace_sourceflow_taeroff.pid)"
