#!/usr/bin/env bash
set -euo pipefail

cd /home/cg/Code/DRIFT

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

COMMON=(
  --suites travel
  --do_attack
  --attack_type important_instructions
  --build_constraints
  --injection_isolation
  --dynamic_validation
  --taer_mode off
  --planner_mode replay
  --fixed_plan_file data/canonical_plans_97.json
  --force_rerun
  --run_tag replayexact_drift
  --model gpt-4o-mini-2024-07-18
)

python pipeline_main.py "${COMMON[@]}" \
  --target_user_tasks 7 \
  --target_injection_tasks 4,5

python pipeline_main.py "${COMMON[@]}" \
  --target_user_tasks 8,9,10,11,12,13,14,15,16,17,18,19 \
  --target_injection_tasks 0,1,2,3,4,5,6
