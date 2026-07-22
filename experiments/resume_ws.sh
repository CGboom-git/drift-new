#!/bin/bash
source /home/cg/.config/drift/openai.env
export OPENAI_API_KEY OPENAI_BASE_URL
cd /home/cg/Code/DRIFT
exec /home/cg/anaconda3/envs/drift/bin/python pipeline_main.py \
  --suites workspace --cae_mode repair \
  --source_flow_validation --source_flow_log \
  --dynamic_validation --injection_isolation --do_attack \
  --model gpt-4o-mini-2024-07-18 --benchmark_version v1.2 \
  > /home/cg/Code/DRIFT/experiments/resume_ws.log 2>&1
