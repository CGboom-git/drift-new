#!/bin/bash
# CAE ablation: banking + workspace, 5 tasks, ATTACK, v2_clean
# Run CAE ON then CAE OFF, save to custom dirs
source /home/cg/.config/drift/openai.env
export OPENAI_API_KEY OPENAI_BASE_URL
cd /home/cg/Code/DRIFT

PY=/home/cg/anaconda3/envs/drift/bin/python
MODEL=gpt-4o-mini-2024-07-18
SUITES="banking workspace"
TASKS="0,1,2,3,4"
INJ="0,1"
BASE_FLAGS="--build_constraints --injection_isolation --dynamic_validation --source_flow_validation --source_flow_log --do_attack --attack_type important_instructions --force_rerun --model $MODEL --benchmark_version v1.2"

echo "=== CAE ABLATION START ==="
echo "Model: $MODEL, Suites: $SUITES, Tasks: $TASKS"
echo "Date: $(date)"

for SUITE in banking workspace; do
    echo ""
    echo "--- $SUITE CAE=ON ---"
    $PY pipeline_main.py --suites $SUITE --target_user_tasks $TASKS --target_injection_tasks $INJ $BASE_FLAGS --controlled_action_extension 2>&1 | tail -5
    if [ -d "runs/$MODEL/$SUITE" ]; then
        mkdir -p runs/v2_cae_on
        cp -r runs/$MODEL/$SUITE runs/v2_cae_on/$SUITE
        echo "  saved to runs/v2_cae_on/$SUITE"
    fi
    
    echo ""
    echo "--- $SUITE CAE=OFF ---"
    $PY pipeline_main.py --suites $SUITE --target_user_tasks $TASKS --target_injection_tasks $INJ $BASE_FLAGS 2>&1 | tail -5
    if [ -d "runs/$MODEL/$SUITE" ]; then
        mkdir -p runs/v2_cae_off
        cp -r runs/$MODEL/$SUITE runs/v2_cae_off/$SUITE
        echo "  saved to runs/v2_cae_off/$SUITE"
    fi
done

echo ""
echo "=== CAE ABLATION DONE $(date) ==="
echo "Results: runs/v2_cae_on/ and runs/v2_cae_off/"
