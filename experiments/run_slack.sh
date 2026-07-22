#!/bin/bash
source /home/cg/.config/drift/openai.env
export OPENAI_API_KEY OPENAI_BASE_URL
cd /home/cg/Code/DRIFT
exec /home/cg/anaconda3/envs/drift/bin/python pipeline_main.py \
  --suites slack \
  --target_user_tasks 0,1,2,3,4 \
  --target_injection_tasks 1,2 \
  --build_constraints --injection_isolation --dynamic_validation \
  --source_flow_validation --controlled_action_extension --source_flow_log \
  --do_attack --attack_type important_instructions --force_rerun \
  --model gpt-4o-mini-2024-07-18 --benchmark_version v1.2 \
  > experiments/slack_5per.log 2>&1
