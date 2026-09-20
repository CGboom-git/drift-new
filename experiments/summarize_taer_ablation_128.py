import json
from collections import Counter
from pathlib import Path

MODEL = "gpt-4o-mini-2024-07-18"
TAGS = {
    "full": "taer_ablation128_full_gpt4omini_20260824",
    "no_anchor": "taer_ablation128_no_anchor_gpt4omini_20260824",
    "no_scope": "taer_ablation128_no_scope_gpt4omini_20260824",
    "no_ephemeral": "taer_ablation128_no_ephemeral_gpt4omini_20260824",
}


def load_variant(variant, tag):
    root = Path("runs") / f"{MODEL}-{tag}"
    rows = {}
    decisions = Counter()
    plans = Counter()
    malformed = []
    for path in root.glob("*/user_task_*/important_instructions/injection_task_*.json"):
        try:
            result = json.loads(path.read_text(encoding="utf-8"))
            trace_path = path.parent / "runtime_drift_trace" / f"{path.stem}.runtime_drift.json"
            trace = json.loads(trace_path.read_text(encoding="utf-8"))
            case = f"{result['suite_name']}/{result['user_task_id']}/{result['injection_task_id']}"
            events = trace.get("taer_runtime_decisions", [])
            decisions.update(e.get("final_decision") for e in events)
            plans.update(e.get("plan_match_status") for e in events)
            rows[case] = {
                "suite": result["suite_name"],
                "utility": bool(result.get("utility")),
                "security": bool(result.get("security")),
                "tokens": int(result.get("total_tokens", 0) or 0),
                "duration": float(result.get("duration", 0) or 0),
                "events": len(events),
            }
        except Exception as exc:
            malformed.append([str(path), repr(exc)])
    n = len(rows)
    summary = {
        "variant": variant,
        "cases": n,
        "utility": sum(r["utility"] for r in rows.values()),
        "attack_success": sum(r["security"] for r in rows.values()),
        "avg_tokens": sum(r["tokens"] for r in rows.values()) / n if n else 0,
        "avg_duration": sum(r["duration"] for r in rows.values()) / n if n else 0,
        "events": sum(r["events"] for r in rows.values()),
        "allow": decisions["ALLOW"],
        "reject": decisions["REJECT"],
        "in_plan": plans["IN_PLAN"],
        "out_of_plan": sum(v for k, v in plans.items() if k != "IN_PLAN"),
        "malformed": len(malformed),
    }
    return rows, summary


all_rows = {}
summaries = []
suite_summaries = []
for variant, tag in TAGS.items():
    rows, summary = load_variant(variant, tag)
    all_rows[variant] = rows
    summaries.append(summary)
    for suite in ("banking", "slack", "travel", "workspace", "all"):
        selected = list(rows.values()) if suite == "all" else [
            row for row in rows.values() if row["suite"] == suite
        ]
        n = len(selected)
        suite_summaries.append({
            "variant": variant,
            "suite": suite,
            "cases": n,
            "utility": sum(row["utility"] for row in selected),
            "attack_success": sum(row["security"] for row in selected),
            "avg_tokens": sum(row["tokens"] for row in selected) / n if n else 0,
            "avg_duration": sum(row["duration"] for row in selected) / n if n else 0,
        })

full = all_rows["full"]
paired = {}
for variant in TAGS:
    if variant == "full":
        continue
    common = sorted(set(full) & set(all_rows[variant]))
    other = all_rows[variant]
    paired[variant] = {
        "cases": len(common),
        "utility_gain": sum(not full[c]["utility"] and other[c]["utility"] for c in common),
        "utility_loss": sum(full[c]["utility"] and not other[c]["utility"] for c in common),
        "attack_new": sum(not full[c]["security"] and other[c]["security"] for c in common),
        "attack_prevented": sum(full[c]["security"] and not other[c]["security"] for c in common),
    }

print(json.dumps({
    "summaries": summaries,
    "suite_summaries": suite_summaries,
    "paired_vs_full": paired,
}, indent=2))
