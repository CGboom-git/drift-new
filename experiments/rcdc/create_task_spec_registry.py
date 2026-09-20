"""Freeze a reviewable registry for complete RCVR task coverage.

The registry records every benchmark user task. Only ``verified`` entries may
be used by a future declarative compiler. ``needs_semantic_spec`` is an
intentional fail-closed state, so action tasks cannot be accidentally reported
as RCVR-covered merely because they have a ground-truth trajectory.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
inventory_path = ROOT / "task_spec_inventory_v1.json"
output_path = ROOT / "task_spec_registry_v1.json"
inventory = json.loads(inventory_path.read_text(encoding="utf-8"))

existing = {
    ("banking", "user_task_4"): "refund_v1",
    ("slack", "user_task_7"): "channel_selection_v1",
    ("slack", "user_task_12"): "channel_selection_v1",
    ("workspace", "user_task_8"): "calendar_participants_v1",
    ("workspace", "user_task_9"): "calendar_participants_v1",
    ("workspace", "user_task_35"): "file_selection_v1",
}

entries = []
for task in inventory["tasks"]:
    key = (task["suite"], task["user_task_id"])
    status = task["spec_status"]
    entry = {
        "suite": key[0],
        "user_task_id": key[1],
        "potential_case_count": task["potential_case_count"],
        "action_tools": task["ground_truth_action_tool_sequence"],
        "runtime_status": ("verified" if key in existing else
                           "not_applicable_read_only" if status == "read_only_no_rcvr_gate" else
                           "needs_semantic_spec"),
        "spec_family": existing.get(key),
        "authoring_requirements": ([] if key in existing or not task["ground_truth_action_tool_sequence"] else [
            "declare every final action and the user-authorized fixed fields",
            "declare each dynamic action argument's permitted READ source and selection relation",
            "add a deterministic positive, mismatch, and missing-evidence test",
            "independent reviewer marks the entry verified",
        ]),
    }
    entries.append(entry)

assert len(entries) == 97
assert len({(e["suite"], e["user_task_id"]) for e in entries}) == 97
assert sum(e["potential_case_count"] for e in entries) == 1046
assert sum(e["runtime_status"] == "verified" for e in entries) == 6
assert sum(e["runtime_status"] == "needs_semantic_spec" for e in entries) == 54

registry = {
    "version": 1,
    "benchmark_version": "v1.2",
    "purpose": "declarative RCVR task-spec coverage registry",
    "runtime_policy": "only verified entries may emit RCVR ConstraintSpec; all others must be explicitly audited",
    "inventory_sha256": hashlib.sha256(inventory_path.read_bytes()).hexdigest(),
    "task_count": len(entries),
    "potential_case_count": 1046,
    "entries": entries,
}
output_path.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({
    "verified": sum(e["runtime_status"] == "verified" for e in entries),
    "read_only": sum(e["runtime_status"] == "not_applicable_read_only" for e in entries),
    "needs_semantic_spec": sum(e["runtime_status"] == "needs_semantic_spec" for e in entries),
    "output_sha256": hashlib.sha256(output_path.read_bytes()).hexdigest(),
}))
