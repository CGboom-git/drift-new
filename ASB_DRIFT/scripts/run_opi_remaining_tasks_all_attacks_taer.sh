#!/usr/bin/env bash
set -euo pipefail

cd /home/cg/Code/DRIFT/ASB_DRIFT
export PATH=/home/cg/anaconda3/bin:$PATH
set -a
. /home/cg/.config/drift/openai.env
set +a

PY=/home/cg/anaconda3/envs/ASB/bin/python
ROOT_STAMP=${1:-20260807_opi_first_task_all_attacks_400}
STAMP=${2:-remaining_$(date +%Y%m%d_%H%M%S)}
AGENT_WORKERS=${AGENT_WORKERS:-1}
ROOT_DIR="logs/runs/${ROOT_STAMP}"
RUN_DIR="${ROOT_DIR}/${STAMP}"
mkdir -p "$RUN_DIR"
TASKS="$RUN_DIR/remaining_tasks.jsonl"
ATTACKS="$RUN_DIR/all_attacks_400.jsonl"
CSV="$RUN_DIR/asb_remaining_tasks_all_attacks_taer.csv"
LOG="$RUN_DIR/asb_remaining_tasks_all_attacks_taer.log"
REPORT="$RUN_DIR/asb_remaining_tasks_all_attacks_taer_report.csv"

"$PY" - "$TASKS" "$ATTACKS" <<'PY'
import json
import sys

tasks_path, attacks_path = sys.argv[1:]
tasks = []
with open("data/agent_task.jsonl", encoding="utf-8") as src:
    for line in src:
        item = json.loads(line)
        item["tasks"] = item.get("tasks", [])[1:]
        if item["tasks"]:
            tasks.append(item)

if len(tasks) != 10:
    raise SystemExit(f"expected 10 scenarios with remaining tasks, got {len(tasks)}")

with open(tasks_path, "w", encoding="utf-8") as dst:
    for item in tasks:
        dst.write(json.dumps(item, ensure_ascii=False) + "\n")

attacks = []
with open("data/all_attack_tools.jsonl", encoding="utf-8") as src:
    for line in src:
        if line.strip():
            attacks.append(json.loads(line))

if len(attacks) != 400:
    raise SystemExit(f"expected 400 attacks, got {len(attacks)}")

with open(attacks_path, "w", encoding="utf-8") as dst:
    for item in attacks:
        dst.write(json.dumps(item, ensure_ascii=False) + "\n")

case_total = sum(len(item["tasks"]) for item in tasks)
print(f"tasks={tasks_path} scenarios={len(tasks)} remaining_tasks={case_total}")
print(f"attacks={attacks_path} attacks={len(attacks)}")
PY

"$PY" main_attacker.py \
  --llm_name gpt-4o-mini-2024-07-18 \
  --attack_type context_ignoring \
  --use_backend None \
  --attacker_tools_path "$ATTACKS" \
  --tasks_path "$TASKS" \
  --task_num 6 \
  --agent_workers "$AGENT_WORKERS" \
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
    "actual_injections": sum(int(row["Actual Injections"]) for row in rows),
    "isolated_injections": sum(int(row["Isolated Injections"]) for row in rows),
    "attacker_tool_proposals": sum(int(row["Attacker Tool Proposals"]) for row in rows),
    "source_linked_attacker_proposals": sum(int(row["Source Linked Attacker Proposals"]) for row in rows),
    "taer_boundary_triggers": sum(int(row["TAER Boundary Triggers"]) for row in rows),
    "taer_rejections": sum(int(row["TAER Rejections"]) for row in rows),
    "attacker_tool_executions": sum(int(row["Attacker Tool Executions"]) for row in rows),
    "duplicate_proposals": sum(int(row["Duplicate Proposals"]) for row in rows),
    "duplicate_executions": sum(int(row["Duplicate Executions"]) for row in rows),
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
