"""Emit aggregate clean/attack metrics for the completed PCVR B1--B4 runs.

This reads evaluator JSON only and prints no prompts, tool arguments, or model
outputs.  Invalid evaluator files are reported rather than scored.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path


MODEL = "gpt-4o-mini-2024-07-18"
TAGS = {
    "B1 Full RCVR": "pcvr_apde_full_b1_v12_t07_20260911",
    "B2 w/o Binding": "pcvr_apde_full_b2_v12_t07_20260913",
    "B3 UNKNOWN→Reject": "pcvr_apde_full_b3_v12_t07_20260913",
    "B4 UNKNOWN→Allow": "pcvr_apde_full_b4_v12_t07_20260914",
    "B5 w/o Evidence Isolation": "pcvr_apde_full_b5_v12_t07_20260914",
}
SUITES = ("banking", "slack", "travel", "workspace")


def new_bucket() -> dict[str, int]:
    return {"clean_n": 0, "clean_utility": 0, "attack_n": 0, "attack_utility": 0, "attack_success": 0, "invalid": 0}


def pct(num: int, den: int) -> float | None:
    return None if not den else round(100 * num / den, 1)


def report_bucket(bucket: dict[str, int]) -> dict[str, object]:
    return {
        **bucket,
        "clean_utility_pct": pct(bucket["clean_utility"], bucket["clean_n"]),
        "attack_utility_pct": pct(bucket["attack_utility"], bucket["attack_n"]),
        "asr_pct": pct(bucket["attack_success"], bucket["attack_n"]),
    }


def summarize(tag: str) -> dict[str, object]:
    root = Path("runs") / f"{MODEL}-{tag}"
    groups: dict[str, dict[str, int]] = defaultdict(new_bucket)
    for path in root.rglob("*.json"):
        posix = path.as_posix()
        if "/source_flow/" in posix or "/runtime_drift_trace/" in posix:
            continue
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
        suite = data["suite_name"]
        bucket = groups[suite]
        if "API_ERROR" in raw or "Generation failed." in raw:
            bucket["invalid"] += 1
            continue
        if data.get("injection_task_id") is None:
            bucket["clean_n"] += 1
            bucket["clean_utility"] += bool(data.get("utility"))
        else:
            bucket["attack_n"] += 1
            bucket["attack_utility"] += bool(data.get("utility"))
            bucket["attack_success"] += bool(data.get("security"))

    total = new_bucket()
    for suite in SUITES:
        for key, value in groups[suite].items():
            total[key] += value
    macro = {
        metric: round(sum(report_bucket(groups[s])[metric] for s in SUITES) / len(SUITES), 1)
        for metric in ("clean_utility_pct", "attack_utility_pct", "asr_pct")
    }
    return {
        "suites": {suite: report_bucket(groups[suite]) for suite in SUITES},
        "total": report_bucket(total),
        "macro": macro,
    }


print(json.dumps({name: summarize(tag) for name, tag in TAGS.items()}, ensure_ascii=False, indent=2))
