import json
from pathlib import Path

RUNS = {
    "deepseek-v4-flash-0731": "deepseek-v4-flash-0731-full_banking_travel_deepseek_flash_0731_20260821",
    "qwen3.5-plus-2026-02-15": "qwen3.5-plus-2026-02-15-full_attack_qwen35_plus_0215_20260822",
    "qwen3.7-flash-2026-07-15": "qwen3.7-flash-2026-07-15-full_attack_qwen37_flash_0715_20260822",
}
SUITES = ["banking", "slack", "travel", "workspace"]


def load_suite(root, suite):
    files = sorted((root / suite).glob("user_task_*/important_instructions/injection_task_*.json"))
    records, errors = [], []
    for path in files:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if all(key in payload for key in ("utility", "security", "total_tokens")):
                records.append(payload)
            else:
                errors.append(str(path))
        except Exception:
            errors.append(str(path))
    return records, errors


def metrics(records):
    n = len(records)
    return {
        "cases": n,
        "utility_rate": sum(bool(r["utility"]) for r in records) / n if n else None,
        "security_rate": sum(bool(r["security"]) for r in records) / n if n else None,
        "total_tokens": sum(int(r.get("total_tokens") or 0) for r in records),
        "avg_tokens_per_case": sum(int(r.get("total_tokens") or 0) for r in records) / n if n else None,
    }


base = Path("runs")
output = {}
for model, dirname in RUNS.items():
    root = base / dirname
    model_records = []
    model_output = {}
    for suite in SUITES:
        records, errors = load_suite(root, suite)
        model_records.extend(records)
        model_output[suite] = metrics(records) | {"invalid_files": len(errors)}
    model_output["all"] = metrics(model_records)
    output[model] = model_output

print(json.dumps(output, indent=2, ensure_ascii=False))
