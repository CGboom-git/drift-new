#!/usr/bin/env bash
set -euo pipefail

cd /home/cg/Code/DRIFT/ASB_DRIFT
export PATH=/home/cg/anaconda3/bin:$PATH
set -a
. /home/cg/.config/drift/openai.env
set +a

PY=/home/cg/anaconda3/envs/ASB/bin/python
STAMP=${1:-$(date +%Y%m%d_%H%M%S)}
RUN_DIR=logs/runs/${STAMP}
mkdir -p "$RUN_DIR"

for mode in off on; do
  for suite in clean opi dpi; do
    csv="$RUN_DIR/asb_matched_${suite}_taer_${mode}.csv"
    log="$RUN_DIR/asb_matched_${suite}_taer_${mode}.log"
    flags=()
    if [ "$suite" = clean ]; then
      flags+=(--clean)
    elif [ "$suite" = opi ]; then
      flags+=(--observation_prompt_injection)
    elif [ "$suite" = dpi ]; then
      flags+=(--direct_prompt_injection)
    fi

    "$PY" main_attacker.py \
      --llm_name gpt-4o-mini \
      --attack_type context_ignoring \
      --use_backend None \
      --attacker_tools_path data/attack_tools_test.jsonl \
      --tasks_path data/agent_task_test.jsonl \
      --task_num 1 \
      --res_file "$csv" \
      --database memory_db/direct_prompt_injection/context_ignoring_gpt-4o-mini \
      --taer_mode "$mode" \
      "${flags[@]}" > "$log" 2>&1
    echo "$suite,$mode,$?,$csv,$log"
  done
done
