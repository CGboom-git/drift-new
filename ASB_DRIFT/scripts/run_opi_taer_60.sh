#!/usr/bin/env bash
set -euo pipefail

cd /home/cg/Code/DRIFT/ASB_DRIFT
export PATH=/home/cg/anaconda3/bin:$PATH
set -a
. /home/cg/.config/drift/openai.env
set +a

PY=/home/cg/anaconda3/envs/ASB/bin/python
STAMP=${1:-$(date +%Y%m%d_%H%M%S)}
AGENT_WORKERS=${AGENT_WORKERS:-1}
RUN_DIR="logs/runs/${STAMP}"
mkdir -p "$RUN_DIR"
TASKS="$RUN_DIR/opi_tasks_10x6.jsonl"
ATTACKS="$RUN_DIR/opi_attacks_10x1.jsonl"
CSV="$RUN_DIR/asb_opi_taer_on.csv"
LOG="$RUN_DIR/asb_opi_taer_on.log"
REPORT="$RUN_DIR/asb_opi_taer_on_report.csv"

"$PY" - "$TASKS" "$ATTACKS" <<'PY'
import json
import sys

tasks_path, attacks_path = sys.argv[1:]
tasks = []
with open("data/agent_task.jsonl", encoding="utf-8") as src:
    for line in src:
        item = json.loads(line)
        item["tasks"] = item.get("tasks", [])[:6]
        tasks.append(item)

task_counts = [len(item["tasks"]) for item in tasks]
if len(tasks) != 10 or sum(task_counts) != 51 or any(count not in (5, 6) for count in task_counts):
    raise SystemExit(f"expected the original 51 ASB tasks, got {len(tasks)} agents and {task_counts}")

with open(tasks_path, "w", encoding="utf-8") as dst:
    for item in tasks:
        dst.write(json.dumps(item, ensure_ascii=False) + "\n")

agents = {item["agent_name"] for item in tasks}
seen = set()
selected = []
with open("data/all_attack_tools.jsonl", encoding="utf-8") as src:
    for line in src:
        item = json.loads(line)
        agent = item.get("Corresponding Agent")
        if agent in agents and agent not in seen:
            selected.append(item)
            seen.add(agent)

if len(selected) != 10:
    raise SystemExit(f"expected one attack per agent, got {len(selected)}")

with open(attacks_path, "w", encoding="utf-8") as dst:
    for item in selected:
        dst.write(json.dumps(item, ensure_ascii=False) + "\n")

print(f"tasks={tasks_path} agents={len(tasks)} task_counts={task_counts} cases={sum(task_counts)}")
print(f"attacks={attacks_path} attacks={len(selected)}")
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
