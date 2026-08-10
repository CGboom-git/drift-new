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

python pipeline_main.py \
  --suites slack \
  --do_attack \
  --attack_type important_instructions \
  --build_constraints \
  --injection_isolation \
  --dynamic_validation \
  --source_flow_validation \
  --source_flow_log source_flow \
  --taer_mode on \
  --planner_mode replay \
  --fixed_plan_file data/canonical_plans_97.json \
  --force_rerun \
  --run_tag replayexact_taeron_slack_fix_test \
  --model gpt-4o-mini-2024-07-18
