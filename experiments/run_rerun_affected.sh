#!/bin/bash
# Rerun ONLY affected cases per md: banking=48, travel=10, slack=36, workspace=150 (total 244)
# Use union of affected injection IDs per suite to minimize extra reruns
source /home/cg/.config/drift/openai.env
export OPENAI_API_KEY OPENAI_BASE_URL
cd /home/cg/Code/DRIFT
PY=/home/cg/anaconda3/envs/drift/bin/python
MODEL=gpt-4o-mini-2024-07-18
FLAGS="--cae_mode off --build_constraints --injection_isolation --dynamic_validation --source_flow_validation --source_flow_log --do_attack --attack_type important_instructions --force_rerun --model $MODEL --benchmark_version v1.2"

start=$(date)
echo "=== RERUN 244 AFFECTED CASES (new cae_mode=off) ==="
echo "Start: $start"

# banking: 48 affected cases, injections {0,1,2,3,5,6,7,8}
echo "--- banking (14 tasks, 8 injs) ---"
$PY pipeline_main.py --suites banking --target_user_tasks 0,1,2,3,4,5,6,7,8,10,11,12,14,15 --target_injection_tasks 0,1,2,3,5,6,7,8 $FLAGS 2>&1 | grep -E "Utility Success|Attack Success|Overall" | tail -5
echo "banking done $(date)"

# travel: 10 affected cases, injections {0,1,2,3,4,5}
echo "--- travel (4 tasks, 6 injs) ---"
$PY pipeline_main.py --suites travel --target_user_tasks 1,4,6,7 --target_injection_tasks 0,1,2,3,4,5 $FLAGS 2>&1 | grep -E "Utility Success|Attack Success|Overall" | tail -5
echo "travel done $(date)"

# workspace: 150 affected cases, injections {0,1,2,3,4,5,6,7,8,9,10,11,12,13}
echo "--- workspace (30 tasks, 14 injs) ---"
$PY pipeline_main.py --suites workspace --target_user_tasks 1,2,4,7,9,10,12,13,16,18,19,20,21,22,23,25,26,27,28,29,31,32,33,34,35,36,37,38,39 $FLAGS 2>&1 | grep -E "Utility Success|Attack Success|Overall" | tail -5
echo "workspace done $(date)"

# slack: 36 affected cases, injections {1,2,3,4,5}
echo "--- slack (12 tasks, 5 injs) ---"
$PY pipeline_main.py --suites slack --target_user_tasks 0,1,7,10,11,12,14,15,16,18,19,20 --target_injection_tasks 1,2,3,4,5 $FLAGS 2>&1 | grep -E "Utility Success|Attack Success|Overall" | tail -5
echo "slack done $(date)"

echo "=== DONE $(date) ==="
