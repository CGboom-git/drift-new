#!/bin/bash
# CAE three-mode ablation: on / off / strict
# banking + workspace, tasks 0-4, attack, save to runs/cae_v2_{mode}/
source /home/cg/.config/drift/openai.env
export OPENAI_API_KEY OPENAI_BASE_URL
cd /home/cg/Code/DRIFT
PY=/home/cg/anaconda3/envs/drift/bin/python
MODEL=gpt-4o-mini-2024-07-18
FLAGS="--build_constraints --injection_isolation --dynamic_validation --source_flow_validation --source_flow_log --do_attack --attack_type important_instructions --force_rerun --model $MODEL --benchmark_version v1.2 --target_user_tasks 0,1,2,3,4 --target_injection_tasks 0,1"

start=$(date)
echo "=== CAE 3-MODE ABLATION ==="
echo "Start: $start"

for MODE in on off strict; do
    echo ""
    echo "========== CAE=$MODE =========="
    for SUITE in banking workspace; do
        echo "--- $SUITE CAE=$MODE ---"
        $PY pipeline_main.py --suites $SUITE --cae_mode $MODE $FLAGS 2>&1 | tail -5
        if [ -d "runs/$MODEL/$SUITE" ]; then
            mkdir -p runs/cae_v2_$MODE
            cp -r runs/$MODEL/$SUITE runs/cae_v2_$MODE/$SUITE
        fi
    done
    echo "CAE=$MODE done"
done

echo ""
echo "=== DONE ==="
echo "Start: $start"
echo "End: $(date)"
echo "Results: runs/cae_v2_on/ runs/cae_v2_off/ runs/cae_v2_strict/"
