#!/bin/bash
source /home/cg/.config/drift/openai.env
export OPENAI_API_KEY OPENAI_BASE_URL
cd /home/cg/Code/DRIFT
PY=/home/cg/anaconda3/envs/drift/bin/python
M=gpt-4o-mini-2024-07-18
F="--cae_mode repair --source_flow_validation --source_flow_log --dynamic_validation --injection_isolation --do_attack --force_rerun --model $M --benchmark_version v1.2"

echo "=== CAE REPAIR 48-CASE SMOKE ==="
echo "Start: $(date)"

echo "--- banking (6 tasks x 3 inj = 18 cases) ---"
$PY pipeline_main.py --suites banking --target_user_tasks 0,5,6,10,12,14 --target_injection_tasks 0,1,2 $F 2>&1 | grep -E "Utility Success|Attack Success|Overall" | tail -3

echo "--- workspace (7 tasks x 2 inj = 14 cases) ---"
$PY pipeline_main.py --suites workspace --target_user_tasks 12,13,20,29,33,35,38 --target_injection_tasks 0,1 $F 2>&1 | grep -E "Utility Success|Attack Success|Overall" | tail -3

echo "--- travel (4 tasks x 2 inj = 8 cases) ---"
$PY pipeline_main.py --suites travel --target_user_tasks 1,4,6,7 --target_injection_tasks 0,1 $F 2>&1 | grep -E "Utility Success|Attack Success|Overall" | tail -3

echo "--- slack (4 tasks x 2 inj = 8 cases) ---"
$PY pipeline_main.py --suites slack --target_user_tasks 0,1,7,10 --target_injection_tasks 1,2 $F 2>&1 | grep -E "Utility Success|Attack Success|Overall" | tail -3

echo "=== DONE $(date) ==="
