import csv
import json
from collections import Counter
from pathlib import Path

POOL_PATH = Path("/tmp/taer_ablation_pool.json") if Path("/tmp/taer_ablation_pool.json").exists() else Path("taer_ablation_pool.json")
POOL = json.load(POOL_PATH.open(encoding="utf-8"))["triggered_cases"]
SERVER_CASE_CSV = Path("runs/gpt-4o-mini-2024-07-18-full_attack_gpt4omini_runtime_trace_retry1_20260823/analysis/runtime_authorization_drift/drift_case_statistics.csv")
CASE_CSV = SERVER_CASE_CSV if SERVER_CASE_CSV.exists() else Path("analysis-output/drift_case_statistics.csv")
OUTPUT_DIR = Path("experiments") if Path("pipeline_main.py").exists() else Path(".")
TARGET = {"banking": 28, "slack": 26, "travel": 14, "workspace": 60}


def task_key(case):
    return "/".join(case["case_id"].split("/")[:2])


selected = {}


def add(case, reason):
    item = selected.setdefault(case["case_id"], {**case, "selection_reasons": []})
    if reason not in item["selection_reasons"]:
        item["selection_reasons"].append(reason)


for case in POOL:
    reasons = []
    if case["relations"].get("REPAIR", 0):
        reasons.append("ALL_REPAIR")
    if case["scope_failed"]:
        reasons.append("ALL_SCOPE_FAILED")
    if case["suite"] == "travel":
        reasons.append("ALL_TRAVEL_TAER")
    if case["attack_success"]:
        reasons.append("ALL_TAER_ATTACK_SUCCESS")
    if case["repeated_authorized_tool"]:
        reasons.append("ALL_REPEATED_AUTHORIZED_TOOL")
    for reason in reasons:
        add(case, reason)


def choose(candidates, count, reason):
    for _ in range(count):
        suite_counts = Counter(x["suite"] for x in selected.values())
        task_counts = Counter(task_key(x) for x in selected.values())
        available = [c for c in candidates if c["case_id"] not in selected]
        if not available:
            raise RuntimeError(f"Not enough candidates for {reason}")
        def score(c):
            deficit = TARGET[c["suite"]] - suite_counts[c["suite"]]
            new_task = task_counts[task_key(c)] == 0
            diversity = len(c.get("relations", {})) + len(c.get("decisions", {}))
            return (deficit, new_task, -task_counts[task_key(c)], diversity, c["case_id"])
        chosen = max(available, key=score)
        add(chosen, reason)


choose([c for c in POOL if c["relations"].get("NEW_GOAL", 0)], 12, "NEW_GOAL_SUPPLEMENT")
choose([c for c in POOL if c["relations"].get("AMBIGUOUS", 0)], 12, "AMBIGUOUS_SUPPLEMENT")
choose([c for c in POOL if c["one_time_grant"]], 19, "ONE_TIME_GRANT_SUPPLEMENT")

# Add 16 cases with no structured out-of-plan TAER decision as negative controls.
all_by_id = {}
with CASE_CSV.open(encoding="utf-8-sig", newline="") as file:
    for row in csv.DictReader(file):
        all_by_id[row["case_id"]] = row

negative_candidates = []
for case_id, row in all_by_id.items():
    if row["TAER_trigger"].lower() == "true":
        continue
    suite, user, injection = case_id.split("/")
    negative_candidates.append({
        "case_id": case_id,
        "suite": suite,
        "utility": row["utility_success"].lower() == "true",
        "attack_success": row["attack_success"].lower() == "true",
        "drift_type": row["drift_type"],
        "taer_trigger": False,
        "event_count": 0,
        "relations": {},
        "decisions": {},
        "scope_evaluated": False,
        "scope_failed": False,
        "one_time_grant": False,
        "repeated_authorized_tool": False,
    })
choose(negative_candidates, 16, "NO_TAER_NEGATIVE_CONTROL")

if len(selected) != 128:
    raise RuntimeError(f"Expected 128 cases, got {len(selected)}")

manifest = []
for case_id, item in selected.items():
    suite, user, injection = case_id.split("/")
    manifest.append({
        "case_id": case_id,
        "suite": suite,
        "user_task_id": int(user.rsplit("_", 1)[1]),
        "injection_task_id": int(injection.rsplit("_", 1)[1]),
        "selection_reasons": item["selection_reasons"],
        "full_drift_type": item["drift_type"],
        "full_relations": sorted(item["relations"]),
        "full_decisions": sorted(item["decisions"]),
        "full_scope_failed": item["scope_failed"],
        "full_one_time_grant": item["one_time_grant"],
        "full_repeated_authorized_tool": item["repeated_authorized_tool"],
        "full_utility_success": item["utility"],
        "full_attack_success": item["attack_success"],
    })
manifest.sort(key=lambda x: (["banking", "slack", "travel", "workspace"].index(x["suite"]),
                             x["user_task_id"], x["injection_task_id"]))

(OUTPUT_DIR / "taer_ablation_128_manifest.json").write_text(
    json.dumps({"schema_version": "1.0", "source_model": "gpt-4o-mini-2024-07-18",
                "source_run": "full_attack_gpt4omini_runtime_trace_retry1_20260823",
                "selection_frozen": True, "case_count": 128, "cases": manifest}, indent=2),
    encoding="utf-8",
)
with (OUTPUT_DIR / "taer_ablation_128_manifest.csv").open("w", encoding="utf-8-sig", newline="") as file:
    fields = list(manifest[0])
    writer = csv.DictWriter(file, fieldnames=fields)
    writer.writeheader()
    for row in manifest:
        writer.writerow({**row, "selection_reasons": "|".join(row["selection_reasons"]),
                         "full_relations": "|".join(row["full_relations"]),
                         "full_decisions": "|".join(row["full_decisions"])})

summary = {
    "cases": len(manifest),
    "suite": Counter(x["suite"] for x in manifest),
    "unique_tasks": len({(x["suite"], x["user_task_id"]) for x in manifest}),
    "selection_reasons": Counter(r for x in manifest for r in x["selection_reasons"]),
    "relations": Counter(r for x in manifest for r in x["full_relations"]),
    "decisions": Counter(r for x in manifest for r in x["full_decisions"]),
    "scope_failed": sum(x["full_scope_failed"] for x in manifest),
    "one_time_grant": sum(x["full_one_time_grant"] for x in manifest),
    "repeated_authorized_tool": sum(x["full_repeated_authorized_tool"] for x in manifest),
    "attack_success": sum(x["full_attack_success"] for x in manifest),
}
print(json.dumps(summary, indent=2, default=dict))
