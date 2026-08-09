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

RUN_TAG="replayexact_drift"

nohup python pipeline_main.py \
  --suites workspace \
  --do_attack \
  --attack_type important_instructions \
  --build_constraints \
  --injection_isolation \
  --dynamic_validation \
  --taer_mode off \
  --planner_mode replay \
  --fixed_plan_file data/canonical_plans_97.json \
  --force_rerun \
  --run_tag "$RUN_TAG" \
  --model gpt-4o-mini-2024-07-18 \
  > experiments/replayexact_drift_workspace.out.log 2>&1 </dev/null &
echo $! > experiments/replayexact_drift_workspace.pid

sleep 90

nohup python pipeline_main.py \
  --suites banking,slack,travel \
  --do_attack \
  --attack_type important_instructions \
  --build_constraints \
  --injection_isolation \
  --dynamic_validation \
  --taer_mode off \
  --planner_mode replay \
  --fixed_plan_file data/canonical_plans_97.json \
  --force_rerun \
  --run_tag "$RUN_TAG" \
  --model gpt-4o-mini-2024-07-18 \
  > experiments/replayexact_drift_remaining.out.log 2>&1 </dev/null &
echo $! > experiments/replayexact_drift_remaining.pid

echo "started workspace pid $(cat experiments/replayexact_drift_workspace.pid)"
echo "started remaining pid $(cat experiments/replayexact_drift_remaining.pid)"
