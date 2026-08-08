#!/usr/bin/env bash
set -euo pipefail

cd /home/cg/Code/DRIFT/ASB_DRIFT
PY=/home/cg/anaconda3/envs/ASB/bin/python
ROOT_STAMP=${1:-20260807_opi_first_task_all_attacks_400}
REMAINING_STAMP=${2:-remaining_tasks_all_attacks_bg}
ROOT_DIR="logs/runs/${ROOT_STAMP}"
FIRST_CSV="$ROOT_DIR/asb_opi_first_task_all_attacks_taer.csv"
REMAINING_CSV="$ROOT_DIR/$REMAINING_STAMP/asb_remaining_tasks_all_attacks_taer.csv"
FULL_CSV="$ROOT_DIR/asb_opi_full_2040_taer.csv"
REPORT="$ROOT_DIR/asb_opi_full_2040_taer_report.csv"

"$PY" - "$FIRST_CSV" "$REMAINING_CSV" "$FULL_CSV" "$REPORT" <<'PY'
import csv
import json
import pathlib
import sys

first_csv, remaining_csv, full_csv, report_csv = map(pathlib.Path, sys.argv[1:])
for path in (first_csv, remaining_csv):
    if not path.exists():
        raise SystemExit(f"missing input CSV: {path}")

def read_rows(path):
    with path.open(newline="", encoding="utf-8") as src:
        return list(csv.DictReader(src))

first_rows = read_rows(first_csv)
remaining_rows = read_rows(remaining_csv)
rows = first_rows + remaining_rows

if len(first_rows) != 400:
    raise SystemExit(f"expected 400 first-task cases, got {len(first_rows)}")
if len(remaining_rows) != 1640:
    raise SystemExit(f"expected 1640 remaining-task cases, got {len(remaining_rows)}")
if len(rows) != 2040:
    raise SystemExit(f"expected 2040 total cases, got {len(rows)}")

fieldnames = list(rows[0].keys())
with full_csv.open("w", newline="", encoding="utf-8") as dst:
    writer = csv.DictWriter(dst, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)

def isum(field):
    return sum(int(row[field]) for row in rows)

report = {
    "cases": len(rows),
    "first_task_cases": len(first_rows),
    "remaining_task_cases": len(remaining_rows),
    "attack_success": isum("Attack Successful"),
    "original_success": isum("Original Task Successful"),
    "workflow_failures": isum("Workflow Failure"),
    "api_failures": isum("API Failure Count"),
    "tool_executions": isum("Actual Tool Execution Count"),
    "actual_injections": isum("Actual Injections"),
    "isolated_injections": isum("Isolated Injections"),
    "attacker_tool_proposals": isum("Attacker Tool Proposals"),
    "source_linked_attacker_proposals": isum("Source Linked Attacker Proposals"),
    "taer_boundary_triggers": isum("TAER Boundary Triggers"),
    "taer_rejections": isum("TAER Rejections"),
    "attacker_tool_executions": isum("Attacker Tool Executions"),
    "duplicate_proposals": isum("Duplicate Proposals"),
    "duplicate_executions": isum("Duplicate Executions"),
}
report["asr"] = report["attack_success"] / report["cases"]
report["utility"] = report["original_success"] / report["cases"]

with report_csv.open("w", newline="", encoding="utf-8") as dst:
    writer = csv.writer(dst)
    writer.writerow(report.keys())
    writer.writerow(report.values())

print(json.dumps(report, sort_keys=True))
PY

echo "full_csv=$FULL_CSV"
echo "report=$REPORT"
