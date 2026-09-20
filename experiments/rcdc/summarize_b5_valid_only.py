"""Aggregate B5 metrics after excluding evaluator files with API failures."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path("runs/gpt-4o-mini-2024-07-18-pcvr_apde_full_b5_v12_t07_20260914")
SUITES = ("banking", "slack", "travel", "workspace")


def bucket() -> dict[str, int]:
    return {"clean_n": 0, "clean_utility": 0, "attack_n": 0, "attack_utility": 0, "attack_success": 0, "invalid": 0}


def pct(n: int, d: int) -> float | None:
    return round(100 * n / d, 1) if d else None


rows = {suite: bucket() for suite in SUITES}
for path in ROOT.rglob("*.json"):
    posix = path.as_posix()
    if "/source_flow/" in posix or "/runtime_drift_trace/" in posix:
        continue
    raw = path.read_text(encoding="utf-8")
    data = json.loads(raw)
    row = rows[data["suite_name"]]
    if "API_ERROR" in raw or "Generation failed." in raw:
        row["invalid"] += 1
        continue
    if data.get("injection_task_id") is None:
        row["clean_n"] += 1
        row["clean_utility"] += bool(data.get("utility"))
    else:
        row["attack_n"] += 1
        row["attack_utility"] += bool(data.get("utility"))
        row["attack_success"] += bool(data.get("security"))

total = bucket()
for row in rows.values():
    for key, value in row.items():
        total[key] += value
for row in [*rows.values(), total]:
    row["clean_utility_pct"] = pct(row["clean_utility"], row["clean_n"])
    row["attack_utility_pct"] = pct(row["attack_utility"], row["attack_n"])
    row["asr_pct"] = pct(row["attack_success"], row["attack_n"])

print(json.dumps({"suites": rows, "total": total}, ensure_ascii=False, indent=2))
