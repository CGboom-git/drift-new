#!/bin/bash
source /home/cg/.config/drift/openai.env
export OPENAI_API_KEY OPENAI_BASE_URL
cd /home/cg/Code/DRIFT
PY=/home/cg/anaconda3/envs/drift/bin/python
M=gpt-4o-mini-2024-07-18
F="--cae_mode repair --source_flow_validation --source_flow_log --dynamic_validation --injection_isolation --do_attack --force_rerun --model $M --benchmark_version v1.2"

echo "=== FULL BENCHMARK CAE=REPAIR ==="
echo "Start: $(date)"

echo "--- banking ---"
$PY pipeline_main.py --suites banking $F 2>&1 | grep -E "Utilities|Overall|Utility Success|Attack Success" | tail -3
echo "banking done $(date)"

echo "--- slack ---"
$PY pipeline_main.py --suites slack $F 2>&1 | grep -E "Utilities|Overall|Utility Success|Attack Success" | tail -3
echo "slack done $(date)"

echo "--- travel ---"
$PY pipeline_main.py --suites travel $F 2>&1 | grep -E "Utilities|Overall|Utility Success|Attack Success" | tail -3
echo "travel done $(date)"

echo "--- workspace ---"
$PY pipeline_main.py --suites workspace $F 2>&1 | grep -E "Utilities|Overall|Utility Success|Attack Success" | tail -3
echo "workspace done $(date)"

echo "=== DONE $(date) ==="
