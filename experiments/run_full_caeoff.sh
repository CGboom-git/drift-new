#!/bin/bash
source /home/cg/.config/drift/openai.env
export OPENAI_API_KEY OPENAI_BASE_URL
cd /home/cg/Code/DRIFT
PY=/home/cg/anaconda3/envs/drift/bin/python
MODEL=gpt-4o-mini-2024-07-18
FLAGS="--cae_mode off --build_constraints --injection_isolation --dynamic_validation --source_flow_validation --source_flow_log --do_attack --attack_type important_instructions --force_rerun --model $MODEL --benchmark_version v1.2"

start=$(date)
echo "=== FULL BENCHMARK CAE=OFF ==="
echo "Start: $start"

for SUITE in banking slack travel workspace; do
    echo "--- $SUITE ---"
    if [ "$SUITE" = "slack" ]; then
        $PY pipeline_main.py --suites $SUITE --target_injection_tasks 1,2 $FLAGS 2>&1 | tail -3
    else
        $PY pipeline_main.py --suites $SUITE $FLAGS 2>&1 | tail -3
    fi
    echo "$SUITE done at $(date)"
done

echo ""
echo "=== DONE ==="
echo "Start: $start"
echo "End: $(date)"
