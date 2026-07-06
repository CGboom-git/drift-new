#!/bin/bash
source ~/anaconda3/etc/profile.d/conda.sh
conda activate drift
export OPENAI_API_KEY="sk-9Q8E6mPWFMSMcohvt5eDMIt8HHW5y8SPcqbPhf5oGB4VWMjx"
export OPENAI_BASE_URL="https://api.uiuihao.com/v1"
cd /home/cg/Code/DRIFT

for suite in banking travel workspace; do
  echo "=== $(date) Start $suite ==="
  python pipeline_main.py --suites $suite --do_attack --attack_type important_instructions --model gpt-4o-mini-2024-07-18 --benchmark_version v1.2 --build_constraints --injection_isolation --dynamic_validation --source_flow_validation --controlled_action_extension --source_flow_log
done
echo "=== $(date) DONE ==="
