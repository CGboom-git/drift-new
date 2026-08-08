#!/usr/bin/env bash
set -euo pipefail

cd /home/cg/Code/DRIFT/ASB_DRIFT

PY=/home/cg/anaconda3/envs/ASB/bin/python
export PATH=/home/cg/anaconda3/bin:$PATH

set -a
. /home/cg/.config/drift/openai.env
set +a

STAMP=${1:-$(date +%Y%m%d_%H%M%S)}
TASKS=data/asb_small_5tasks.jsonl
ATTACKS=data/asb_small_2attacks.jsonl
RUN_DIR=logs/runs/${STAMP}
mkdir -p "$RUN_DIR"
SUMMARY="$RUN_DIR/asb_small_taer_summary.csv"

"$PY" - <<'PY'
import json
from collections import defaultdict

tasks_out = "data/asb_small_5tasks.jsonl"
attacks_out = "data/asb_small_2attacks.jsonl"

agents = []
with open("data/agent_task.jsonl", "r", encoding="utf-8") as src, open(tasks_out, "w", encoding="utf-8") as dst:
    for line in src:
        item = json.loads(line)
        if len(agents) >= 5:
            break
        item["tasks"] = item.get("tasks", [])[:1]
        agents.append(item["agent_name"])
        dst.write(json.dumps(item, ensure_ascii=False) + "\n")

counts = defaultdict(int)
with open("data/all_attack_tools.jsonl", "r", encoding="utf-8") as src, open(attacks_out, "w", encoding="utf-8") as dst:
    for line in src:
        item = json.loads(line)
        agent = item.get("Corresponding Agent")
        if agent in agents and counts[agent] < 2:
            dst.write(json.dumps(item, ensure_ascii=False) + "\n")
            counts[agent] += 1

print("agents=" + ",".join(agents))
print("tasks_file=" + tasks_out)
print("attacks_file=" + attacks_out)
print("attacks_per_agent=" + json.dumps(dict(counts), sort_keys=True))
PY

run_suite() {
  local suite=$1
  local attack_type=$2
  shift 2
  local csv="$RUN_DIR/asb_small_taer_${suite}.csv"
  local log="$RUN_DIR/asb_small_taer_${suite}.log"

  "$PY" main_attacker.py \
    --llm_name gpt-4o-mini \
    --attack_type "$attack_type" \
    --use_backend None \
    --attacker_tools_path "$ATTACKS" \
    --tasks_path "$TASKS" \
    --task_num 1 \
    --res_file "$csv" \
    --database "memory_db/direct_prompt_injection/${attack_type}_gpt-4o-mini" \
    --taer_mode on \
    "$@" > "$log" 2>&1

  printf '%s,%s,%s\n' "$suite" "$csv" "$log"
}

{
  echo "suite,csv,log"
  run_suite dpi context_ignoring --direct_prompt_injection
  run_suite opi context_ignoring --observation_prompt_injection
  run_suite mp combined_attack --memory_attack --read_db
} > "$SUMMARY"

"$PY" - "$SUMMARY" <<'PY'
import csv
import pathlib
import sys

summary_path = pathlib.Path(sys.argv[1])
rows = list(csv.DictReader(summary_path.open(newline="")))
print("suite,cases,attack_success,original_success,refuse,asr,orig_rate,refuse_rate,csv,log")
for row in rows:
    csv_path = pathlib.Path(row["csv"])
    records = list(csv.DictReader(csv_path.open(newline=""))) if csv_path.exists() else []
    cases = len(records)
    attack_success = sum(int(r["Attack Successful"]) for r in records)
    original_success = sum(int(r["Original Task Successful"]) for r in records)
    refuse = sum(int(r["Refuse Result"]) for r in records)
    asr = attack_success / cases if cases else 0.0
    orig_rate = original_success / cases if cases else 0.0
    refuse_rate = refuse / cases if cases else 0.0
    print(f"{row['suite']},{cases},{attack_success},{original_success},{refuse},{asr:.4f},{orig_rate:.4f},{refuse_rate:.4f},{row['csv']},{row['log']}")
PY

echo "summary=$SUMMARY"
