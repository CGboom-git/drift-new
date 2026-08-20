#!/usr/bin/env bash
set -euo pipefail
cd /home/cg/Code/drift-new-bestbackup
set -a
source /home/cg/.config/drift/openai.env
set +a
exec /home/cg/anaconda3/bin/conda run -n drift python pipeline_main.py --model gpt-4o --suites workspace --run_tag clean_runtime_grounding_gpt4o_workspace_first2_20260820 --build_constraints --injection_isolation --dynamic_validation --taer_mode on --source_flow_validation --source_flow_log --do_attack --attack_type important_instructions --target_injection_tasks 0,1 --force_rerun --benchmark_version v1.2
