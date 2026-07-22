#!/bin/bash
source /home/cg/.config/drift/openai.env
export OPENAI_API_KEY OPENAI_BASE_URL
cd /home/cg/Code/DRIFT
PY=/home/cg/anaconda3/envs/drift/bin/python
M=gpt-4o-mini-2024-07-18
F="--cae_mode repair --source_flow_validation --source_flow_log --dynamic_validation --injection_isolation --do_attack --force_rerun --model $M --benchmark_version v1.2"

echo "--- travel (tasks 1,4,6,7, injections 0,1) ---"
$PY pipeline_main.py --suites travel --target_user_tasks 1,4,6,7 --target_injection_tasks 0,1 $F 2>&1 | grep -E "Utility Success|Attack Success|Overall" | tail -3
echo "travel done $(date)"

echo "--- slack (tasks 0,1,7,10, injections 0,1) ---"
$PY pipeline_main.py --suites slack --target_user_tasks 0,1,7,10 --target_injection_tasks 0,1 $F 2>&1 | grep -E "Utility Success|Attack Success|Overall" | tail -3
echo "slack done $(date)"
