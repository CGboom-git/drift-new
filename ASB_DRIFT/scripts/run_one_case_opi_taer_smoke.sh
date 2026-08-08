#!/usr/bin/env bash
set -euo pipefail

cd /home/cg/Code/DRIFT/ASB_DRIFT
export PATH=/home/cg/anaconda3/bin:$PATH
set -a
. /home/cg/.config/drift/openai.env
set +a

PY=/home/cg/anaconda3/envs/ASB/bin/python
STAMP=${1:-$(date +%Y%m%d_%H%M%S)}
RUN_DIR="logs/runs/${STAMP}"
mkdir -p "$RUN_DIR"
TASKS="$RUN_DIR/one_case_tasks.jsonl"
ATTACKS="$RUN_DIR/one_case_attacks.jsonl"
CSV="$RUN_DIR/asb_one_case_opi_taer.csv"
LOG="$RUN_DIR/asb_one_case_opi_taer.log"
REPORT="$RUN_DIR/asb_one_case_opi_taer_report.csv"

"$PY" - "$TASKS" "$ATTACKS" <<'PY'
import json
import sys

tasks_path, attacks_path = sys.argv[1:]

with open("data/agent_task.jsonl", encoding="utf-8") as src:
    first = json.loads(next(src))
    first["tasks"] = first.get("tasks", [])[:1]

with open(tasks_path, "w", encoding="utf-8") as dst:
    dst.write(json.dumps(first, ensure_ascii=False) + "\n")

first_agent = first["agent_name"]
selected = []
with open("data/all_attack_tools.jsonl", encoding="utf-8") as src:
    for line in src:
        if not line.strip():
            continue
        item = json.loads(line)
        if item.get("Corresponding Agent") == first_agent:
            selected.append(item)
            break

if len(selected) != 1:
    raise SystemExit("failed to select one attacker tool")

with open(attacks_path, "w", encoding="utf-8") as dst:
    for item in selected:
        dst.write(json.dumps(item, ensure_ascii=False) + "\n")

print(f"tasks={tasks_path} cases=1")
print(f"attacks={attacks_path} attacks=1")
PY

"$PY" main_attacker.py \
  --llm_name gpt-4o-mini-2024-07-18 \
  --attack_type context_ignoring \
  --use_backend None \
  --attacker_tools_path "$ATTACKS" \
  --tasks_path "$TASKS" \
  --task_num 1 \
  --agent_workers 1 \
  --res_file "$CSV" \
  --database memory_db/direct_prompt_injection/context_ignoring_gpt-4o-mini \
  --observation_prompt_injection \
  --taer_mode on > "$LOG" 2>&1

"$PY" - "$CSV" "$REPORT" <<'PY'
import csv
import json
import pathlib
import sys

csv_path, report_path = map(pathlib.Path, sys.argv[1:])
rows = list(csv.DictReader(csv_path.open(newline="", encoding="utf-8")))
report = {
    "cases": len(rows),
    "attack_success": sum(int(row["Attack Successful"]) for row in rows),
    "original_success": sum(int(row["Original Task Successful"]) for row in rows),
    "workflow_failures": sum(int(row["Workflow Failure"]) for row in rows),
    "api_failures": sum(int(row["API Failure Count"]) for row in rows),
    "tool_executions": sum(int(row["Actual Tool Execution Count"]) for row in rows),
    "attacker_tool_proposals": sum(int(row["Attacker Tool Proposals"]) for row in rows),
    "attacker_tool_executions": sum(int(row["Attacker Tool Executions"]) for row in rows),
}
report["asr"] = report["attack_success"] / report["cases"] if report["cases"] else 0.0
report["utility"] = report["original_success"] / report["cases"] if report["cases"] else 0.0
with report_path.open("w", newline="", encoding="utf-8") as dst:
    writer = csv.writer(dst)
    writer.writerow(report.keys())
    writer.writerow(report.values())
print(json.dumps(report, sort_keys=True))
PY

echo "run_dir=$RUN_DIR"
