#!/bin/bash
source /home/cg/.config/drift/openai.env
export OPENAI_API_KEY OPENAI_BASE_URL
cd /home/cg/Code/DRIFT
exec /home/cg/anaconda3/envs/drift/bin/python pipeline_main.py \
  --suites slack --cae_mode off \
  --build_constraints --injection_isolation --dynamic_validation \
  --source_flow_validation --source_flow_log \
  --do_attack --attack_type important_instructions --force_rerun \
  --model gpt-4o-mini-2024-07-18 --benchmark_version v1.2 \
  > experiments/slack_full.log 2>&1
