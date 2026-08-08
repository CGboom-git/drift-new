#!/usr/bin/env bash
set -euo pipefail

cd /home/cg/Code/DRIFT/ASB_DRIFT
export PATH=/home/cg/anaconda3/bin:$PATH
set -a
. /home/cg/.config/drift/openai.env
set +a

PY=/home/cg/anaconda3/envs/ASB/bin/python
STAMP=${1:-$(date +%Y%m%d_%H%M%S)}
TASKS=data/asb_matched_10_tasks.jsonl
ATTACKS=data/asb_matched_10_attacks.jsonl
RUN_DIR=logs/runs/${STAMP}
mkdir -p "$RUN_DIR"

"$PY" -c 'import json; src=[json.loads(x) for x in open("data/agent_task.jsonl")]; [open("data/asb_matched_10_tasks.jsonl","w").write("\n".join(json.dumps(dict(x, tasks=x["tasks"][:2])) for x in src[:5])+"\n")]'
"$PY" -c 'import json; agents={json.loads(x)["agent_name"] for x in open("data/asb_matched_10_tasks.jsonl")}; n={a:0 for a in agents}; out=[]; [out.append(d) or n.__setitem__(d["Corresponding Agent"],n[d["Corresponding Agent"]]+1) for d in map(json.loads,open("data/all_attack_tools.jsonl")) if d["Corresponding Agent"] in agents and n[d["Corresponding Agent"]]<1]; open("data/asb_matched_10_attacks.jsonl","w").write("\n".join(json.dumps(x) for x in out)+"\n")'

for mode in off on; do
  for suite in clean opi dpi; do
    csv="$RUN_DIR/asb_matched10_${suite}_taer_${mode}.csv"
    log="$RUN_DIR/asb_matched10_${suite}_taer_${mode}.log"
    flags=()
    if [ "$suite" = clean ]; then flags+=(--clean); fi
    if [ "$suite" = opi ]; then flags+=(--observation_prompt_injection); fi
    if [ "$suite" = dpi ]; then flags+=(--direct_prompt_injection); fi
    "$PY" main_attacker.py --llm_name gpt-4o-mini --attack_type context_ignoring --use_backend None \
      --attacker_tools_path "$ATTACKS" --tasks_path "$TASKS" --task_num 2 --res_file "$csv" \
      --database memory_db/direct_prompt_injection/context_ignoring_gpt-4o-mini --taer_mode "$mode" "${flags[@]}" > "$log" 2>&1
    echo "$suite,$mode,$csv,$log"
  done
done
