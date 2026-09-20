"""Freeze the final missing Travel cases after repair1--3."""
import json
from pathlib import Path

BASE = Path("reports/rcvr_ablation_preflight/full_b1_gpt4o_repair1_two_lanes_t07_20260919")
OUT = Path("reports/rcvr_ablation_preflight/full_b1_gpt4o_repair4_travel_t07_20260919")
TAGS = ("repair1", "repair2", "repair3")


def key(row):
    return (row.get("suite_name"), row.get("attack_type"), row.get("user_task_id"), row.get("injection_task_id"))


all_cases = []
for lane in ("workspace", "others"):
    all_cases.extend(json.loads((BASE / f"{lane}_repair_manifest.json").read_text(encoding="utf-8"))["cases"])
valid = set()
for tag in TAGS:
    root = Path("runs") / f"gpt-4o-pcvr_apde_full_b1_gpt4o_t07_20260919_{tag}"
    if not root.exists():
        continue
    for path in root.glob("**/*.json"):
        if path.name.endswith(".failed.json") or "source_flow" in path.parts or "runtime_drift_trace" in path.parts:
            continue
        row = json.loads(path.read_text(encoding="utf-8"))
        if "utility" in row and "security" in row:
            valid.add(key(row))
pending = [case for case in all_cases if key(case) not in valid]
if len(pending) != 60 or {case["suite_name"] for case in pending} != {"travel"}:
    raise RuntimeError(f"unexpected_repair4_scope:{len(pending)}")
OUT.mkdir(parents=True, exist_ok=True)
(OUT / "travel_pending_manifest.json").write_text(json.dumps({
    "purpose": "repair4 after channel switch; all cases lacking valid repair1--3 output",
    "case_count": len(pending), "cases": pending,
}, indent=2), encoding="utf-8")
print(f"travel pending={len(pending)}")
