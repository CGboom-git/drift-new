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

RUN_TAG="fixedplan_all_taeron"

nohup python pipeline_main.py \
  --suites workspace \
  --do_attack \
  --attack_type important_instructions \
  --build_constraints \
  --injection_isolation \
  --dynamic_validation \
  --source_flow_validation \
  --source_flow_log source_flow \
  --taer_mode on \
  --fixed_plan_file data/canonical_plans_97_selection_audit.json \
  --force_rerun \
  --run_tag "$RUN_TAG" \
  --model gpt-4o-mini-2024-07-18 \
  > experiments/fixedplan_taeron_workspace.out.log 2>&1 </dev/null &
echo $! > experiments/fixedplan_taeron_workspace.pid

sleep 90

nohup python pipeline_main.py \
  --suites banking,slack,travel \
  --do_attack \
  --attack_type important_instructions \
  --build_constraints \
  --injection_isolation \
  --dynamic_validation \
  --source_flow_validation \
  --source_flow_log source_flow \
  --taer_mode on \
  --fixed_plan_file data/canonical_plans_97_selection_audit.json \
  --force_rerun \
  --run_tag "$RUN_TAG" \
  --model gpt-4o-mini-2024-07-18 \
  > experiments/fixedplan_taeron_remaining.out.log 2>&1 </dev/null &
echo $! > experiments/fixedplan_taeron_remaining.pid

echo "started workspace pid $(cat experiments/fixedplan_taeron_workspace.pid)"
echo "started remaining pid $(cat experiments/fixedplan_taeron_remaining.pid)"
