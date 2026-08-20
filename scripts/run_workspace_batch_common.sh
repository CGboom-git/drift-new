#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="/home/cg/Code/drift-new-bestbackup"
cd "$ROOT_DIR"

RUN_TAG="workspace_selected_20260819"
MODEL="gpt-4o"
BENCHMARK_VERSION="v1.2"
CONDA="/home/cg/anaconda3/bin/conda"
PYTHON=("$CONDA" run -n drift python)

if [[ -f /home/cg/.config/drift/openai.env ]]; then
  set -a
  # shellcheck disable=SC1091
  source /home/cg/.config/drift/openai.env
  set +a
fi

COMMON_FLAGS=(
  --suites workspace
  --do_attack
  --attack_type important_instructions
  --build_constraints
  --injection_isolation
  --dynamic_validation
  --taer_mode on
  --source_flow_validation
  --source_flow_log
  --force_rerun
  --model "$MODEL"
  --benchmark_version "$BENCHMARK_VERSION"
  --run_tag "$RUN_TAG"
)

run_case() {
  local user_task="$1"
  local injection_task="$2"

  echo "Running workspace/user_task_${user_task}/injection_task_${injection_task}"
  "${PYTHON[@]}" pipeline_main.py \
    --target_user_tasks "$user_task" \
    --target_injection_tasks "$injection_task" \
    "${COMMON_FLAGS[@]}"
}

echo "Workspace selected batch run tag: $RUN_TAG"
echo "Results directory: $ROOT_DIR/runs/${MODEL}-${RUN_TAG}/workspace"
