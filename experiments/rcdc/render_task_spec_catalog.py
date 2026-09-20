"""Render the offline task-spec inventory as a concise reviewer catalog."""
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
inventory = json.loads((ROOT / "task_spec_inventory_v1.json").read_text(encoding="utf-8"))
lines = ["# AgentDojo v1.2 task-spec authoring catalog", ""]
for task in inventory["tasks"]:
    lines.extend([
        f"## {task['suite']}/{task['user_task_id']}", "",
        task["prompt"], "",
        f"Ground-truth authoring reference tools: `{', '.join(task['ground_truth_tool_sequence'])}`", "",
        f"Current compiler: `{task['current_compiler_family'] or 'none'}`", "",
    ])
(ROOT / "task_spec_catalog_v1.md").write_text("\n".join(lines), encoding="utf-8")
print(len(inventory["tasks"]))
