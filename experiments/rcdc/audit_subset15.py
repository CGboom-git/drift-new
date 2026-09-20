"""Audit exact case completion and checkpoint coverage for the 144-case run."""
from collections import Counter, defaultdict
import json
from pathlib import Path


repo = Path(__file__).resolve().parents[2]
tag = "rcvr_mechanism_subset15_20260920"
manifest = json.loads((repo / "experiments/rcdc/rcvr_mechanism_subset15_run_manifest.json").read_text())
run_root = repo / f"runs/gpt-4o-mini-2024-07-18-{tag}"
events_root = repo / "experiments/rcdc/subset15_preflight/online_events" / tag
checkpoint_root = repo / "reports/rcvr_mechanism_subset15_20260920/checkpoints" / tag
summary = {
    "expected": len(manifest["cases"]), "complete": 0, "failed": 0,
    "missing": 0, "events_present": 0, "checkpoints": 0,
    "by_suite": defaultdict(lambda: Counter()),
    "initial_verdicts": Counter(), "event_counts": Counter(),
    "complete_attack": 0, "complete_benign": 0,
    "attack_utility_true": 0, "attack_security_true": 0,
    "benign_utility_true": 0, "incomplete_cases": [],
}
for case in manifest["cases"]:
    suite, task, injection, attack = (case[key] for key in
                                      ("suite_name", "user_task_id", "injection_task_id", "attack_type"))
    result = run_root / suite / task / (attack or "none") / f"{injection or 'none'}.json"
    failure = result.with_suffix(".failed.json")
    bucket = summary["by_suite"][suite]
    bucket["expected"] += 1
    if result.exists():
        try:
            data = json.loads(result.read_text())
            assert "utility" in data and "security" in data
        except Exception:
            summary["failed"] += 1
            bucket["failed"] += 1
            summary["incomplete_cases"].append({**case, "reason": "invalid_result"})
            continue
        summary["complete"] += 1
        bucket["complete"] += 1
        if attack:
            summary["complete_attack"] += 1
            summary["attack_utility_true"] += data["utility"] is True
            summary["attack_security_true"] += data["security"] is True
        else:
            summary["complete_benign"] += 1
            summary["benign_utility_true"] += data["utility"] is True
    elif failure.exists():
        summary["failed"] += 1
        bucket["failed"] += 1
        summary["incomplete_cases"].append({**case, "reason": "infrastructure_failure"})
    else:
        summary["missing"] += 1
        bucket["missing"] += 1
        summary["incomplete_cases"].append({**case, "reason": "not_run"})
    event_file = events_root / suite / task / f"{injection or 'clean'}.json"
    if event_file.exists():
        summary["events_present"] += 1
        event_data = json.loads(event_file.read_text())
        verdicts = [e["decision"]["verdict"] for e in event_data["events"]
                    if e.get("event") == "binding_verification"]
        summary["initial_verdicts"].update(verdicts)
        summary["event_counts"].update(e.get("event") for e in event_data["events"])
summary["checkpoints"] = len(list(checkpoint_root.rglob("*.pkl"))) if checkpoint_root.exists() else 0
summary["by_suite"] = {key: dict(value) for key, value in summary["by_suite"].items()}
summary["initial_verdicts"] = dict(summary["initial_verdicts"])
summary["event_counts"] = dict(summary["event_counts"])
print(json.dumps(summary, ensure_ascii=False, indent=2))
