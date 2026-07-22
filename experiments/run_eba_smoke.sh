#!/bin/bash
source /home/cg/.config/drift/openai.env
export OPENAI_API_KEY OPENAI_BASE_URL
cd /home/cg/Code/DRIFT
PY=/home/cg/anaconda3/envs/drift/bin/python
M=gpt-4o-mini-2024-07-18
F="--cae_mode eba --source_flow_validation --source_flow_log --dynamic_validation --injection_isolation --do_attack --force_rerun --model $M --benchmark_version v1.2"

echo "=== EBA 60-CASE SMOKE (v2) ==="
echo "Start: $(date)"

echo "--- banking (10 x 3 = 30, injections 0,1,2) ---"
$PY pipeline_main.py --suites banking --target_user_tasks 0,5,6,7,8,9,10,11,12,14 --target_injection_tasks 0,1,2 $F 2>&1 | grep -E "Utilities|Overall|Utility Success|Attack Success" | tail -3

echo "--- workspace (10 x 3 = 30, injections 0,1,2) ---"
$PY pipeline_main.py --suites workspace --target_user_tasks 0,7,13,15,16,18,25,28,31,33 --target_injection_tasks 0,1,2 $F 2>&1 | grep -E "Utilities|Overall|Utility Success|Attack Success" | tail -3

echo "=== DONE $(date) ==="
