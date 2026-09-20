import json
from pathlib import Path

ROOT = Path("runs/gpt-4o-mini-2024-07-18-full_no_attack_gpt4omini_runtime_trace_retry1_20260824")
SUITES = ("banking", "slack", "travel", "workspace")


def load_suite(suite):
    rows = []
    for path in sorted((ROOT / suite).glob("user_task_*/none/none.json")):
        rows.append(json.loads(path.read_text(encoding="utf-8")))
    return rows


def summarize(rows):
    n = len(rows)
    return {
        "cases": n,
        "utility_success": sum(bool(row.get("utility")) for row in rows),
        "avg_tokens": sum(int(row.get("total_tokens") or 0) for row in rows) / n if n else 0,
        "avg_duration": sum(float(row.get("duration") or 0) for row in rows) / n if n else 0,
    }


suite_rows = {suite: load_suite(suite) for suite in SUITES}
output = {suite: summarize(rows) for suite, rows in suite_rows.items()}
all_rows = [row for suite in SUITES for row in suite_rows[suite]]
output["all"] = summarize(all_rows)
output["macro"] = {
    "utility": sum(output[s]["utility_success"] / output[s]["cases"] for s in SUITES) / len(SUITES),
    "avg_tokens": sum(output[s]["avg_tokens"] for s in SUITES) / len(SUITES),
    "avg_duration": sum(output[s]["avg_duration"] for s in SUITES) / len(SUITES),
}

trace_count = len(list(ROOT.glob("*/user_task_*/none/runtime_drift_trace/*.runtime_drift.json")))
output["integrity"] = {"results": len(all_rows), "traces": trace_count}
print(json.dumps(output, indent=2))
