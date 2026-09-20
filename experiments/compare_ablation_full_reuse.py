import json
from pathlib import Path

MODEL = "gpt-4o-mini-2024-07-18"
SOURCE = Path("runs") / f"{MODEL}-full_attack_gpt4omini_runtime_trace_retry1_20260823"
RERUN = Path("runs") / f"{MODEL}-taer_ablation128_full_gpt4omini_20260824"
MANIFEST = Path("experiments/taer_ablation_128_manifest.json")


def result_path(root, case):
    return (
        root
        / case["suite"]
        / f"user_task_{case['user_task_id']}"
        / "important_instructions"
        / f"injection_task_{case['injection_task_id']}.json"
    )


def load(root, case):
    path = result_path(root, case)
    row = json.loads(path.read_text(encoding="utf-8"))
    return {
        "utility": bool(row.get("utility")),
        "security": bool(row.get("security")),
        "tokens": int(row.get("total_tokens") or 0),
        "duration": float(row.get("duration") or 0),
    }


def summary(rows):
    n = len(rows)
    return {
        "cases": n,
        "utility": sum(r["utility"] for r in rows),
        "attack_success": sum(r["security"] for r in rows),
        "avg_tokens": sum(r["tokens"] for r in rows) / n,
        "avg_duration": sum(r["duration"] for r in rows) / n,
    }


cases = json.loads(MANIFEST.read_text(encoding="utf-8"))["cases"]
source_rows = {}
rerun_rows = {}
missing = []
for case in cases:
    key = case["case_id"]
    try:
        source_rows[key] = load(SOURCE, case)
        rerun_rows[key] = load(RERUN, case)
    except Exception as exc:
        missing.append([key, repr(exc)])

paired = sorted(set(source_rows) & set(rerun_rows))
by_suite = {}
for suite in ("banking", "slack", "travel", "workspace", "all"):
    keys = paired if suite == "all" else [k for k in paired if k.startswith(suite + "/")]
    by_suite[suite] = {
        "source_full": summary([source_rows[k] for k in keys]),
        "rerun_full": summary([rerun_rows[k] for k in keys]),
    }

flips = {
    "utility_source_fail_rerun_success": sum(not source_rows[k]["utility"] and rerun_rows[k]["utility"] for k in paired),
    "utility_source_success_rerun_fail": sum(source_rows[k]["utility"] and not rerun_rows[k]["utility"] for k in paired),
    "attack_source_safe_rerun_success": sum(not source_rows[k]["security"] and rerun_rows[k]["security"] for k in paired),
    "attack_source_success_rerun_safe": sum(source_rows[k]["security"] and not rerun_rows[k]["security"] for k in paired),
}
print(json.dumps({"paired": len(paired), "missing": missing, "by_suite": by_suite, "flips": flips}, indent=2))
