import json
from collections import Counter
from pathlib import Path

MODEL = "gpt-4o-mini-2024-07-18"
TAGS = {
    "full": "taer_ablation128_full_gpt4omini_20260824",
    "no_anchor": "taer_ablation128_no_anchor_gpt4omini_20260824",
}

all_rows = {}
for variant, tag in TAGS.items():
    root = Path("runs") / f"{MODEL}-{tag}"
    rows = {}
    malformed = []
    variant_mismatch = []
    anchor_not_disabled = []
    decisions = Counter()
    plan_statuses = Counter()
    out_events = 0
    for result_path in root.glob("*/user_task_*/important_instructions/injection_task_*.json"):
        try:
            result = json.loads(result_path.read_text(encoding="utf-8"))
            trace_path = result_path.parent / "runtime_drift_trace" / f"{result_path.stem}.runtime_drift.json"
            trace = json.loads(trace_path.read_text(encoding="utf-8"))
            case = f"{result['suite_name']}/{result['user_task_id']}/{result['injection_task_id']}"
            events = trace.get("taer_runtime_decisions", [])
            for event in events:
                if event.get("taer_variant") != variant:
                    variant_mismatch.append((case, event.get("taer_variant")))
                decisions[event.get("final_decision")] += 1
                status = event.get("plan_match_status")
                plan_statuses[status] += 1
                if status != "IN_PLAN":
                    out_events += 1
                    if variant == "no_anchor":
                        anchor = event.get("task_anchor_result") or {}
                        if anchor.get("status") != "disabled":
                            anchor_not_disabled.append((case, anchor))
            rows[case] = {
                "utility": bool(result.get("utility")),
                "security": bool(result.get("security")),
                "tokens": int(result.get("total_tokens", 0) or 0),
                "duration": float(result.get("duration", 0) or 0),
                "events": len(events),
                "out_events": sum(e.get("plan_match_status") != "IN_PLAN" for e in events),
            }
        except Exception as exc:
            malformed.append((str(result_path), repr(exc)))
    all_rows[variant] = rows
    print(json.dumps({
        "variant": variant, "results": len(rows), "malformed_or_missing_trace": len(malformed),
        "utility_success": sum(x["utility"] for x in rows.values()),
        "attack_success": sum(x["security"] for x in rows.values()),
        "avg_tokens": sum(x["tokens"] for x in rows.values()) / len(rows) if rows else 0,
        "avg_duration": sum(x["duration"] for x in rows.values()) / len(rows) if rows else 0,
        "taer_decisions": dict(decisions), "plan_statuses": dict(plan_statuses),
        "out_of_plan_events": out_events, "variant_mismatch": variant_mismatch[:5],
        "no_anchor_not_disabled": anchor_not_disabled[:5],
        "malformed_examples": malformed[:3],
    }, indent=2))

paired = sorted(set(all_rows["full"]) & set(all_rows["no_anchor"]))
flips = Counter()
for case in paired:
    f, n = all_rows["full"][case], all_rows["no_anchor"][case]
    flips[(f["utility"], n["utility"], f["security"], n["security"])] += 1
print(json.dumps({
    "paired_cases": len(paired),
    "utility_disagreements": sum(f[0] != f[1] for f in flips.elements()),
    "security_disagreements": sum(f[2] != f[3] for f in flips.elements()),
    "paired_outcome_patterns": {str(k): v for k, v in flips.items()},
}, indent=2))
