#!/bin/bash
source /home/cg/.config/drift/openai.env
export OPENAI_API_KEY OPENAI_BASE_URL
cd /home/cg/Code/DRIFT
PY=/home/cg/anaconda3/envs/drift/bin/python
M=gpt-4o-mini-2024-07-18
F="--cae_mode repair --build_constraints --injection_isolation --dynamic_validation --source_flow_validation --source_flow_log --do_attack --attack_type important_instructions --force_rerun --model $M --benchmark_version v1.2 --target_injection_tasks 0,1"

echo "=== CAE=REPAIR 20-CASE SMOKE ==="
echo "Start: $(date)"

echo "--- banking ---"
$PY pipeline_main.py --suites banking --target_user_tasks 0,5,6,10,14 $F 2>&1 | grep -E "Utility Success|Attack Success|Overall" | tail -3
echo "--- workspace ---"
$PY pipeline_main.py --suites workspace --target_user_tasks 12,13,20,33,35 $F 2>&1 | grep -E "Utility Success|Attack Success|Overall" | tail -3

echo "=== DONE $(date) ==="
