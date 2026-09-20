import json
from pathlib import Path

RUNS = {
    "gpt-4o-mini-2024-07-18": {
        "attack": "gpt-4o-mini-2024-07-18-full_attack_gpt4omini_runtime_trace_retry1_20260823",
        "clean": "gpt-4o-mini-2024-07-18-full_no_attack_gpt4omini_runtime_trace_20260823",
    },
    "deepseek-v4-flash-0731": {
        "attack": "deepseek-v4-flash-0731-full_banking_travel_deepseek_flash_0731_20260821",
        "clean": "deepseek-v4-flash-0731-full_no_attack_deepseek_flash_0731_20260821",
    },
    "qwen3.5-plus-2026-02-15": {
        "attack": "qwen3.5-plus-2026-02-15-full_attack_qwen35_plus_0215_20260822",
        "clean": "qwen3.5-plus-2026-02-15-full_no_attack_qwen35_plus_0215_20260822",
    },
    "qwen3.7-flash-2026-07-15": {
        "attack": "qwen3.7-flash-2026-07-15-full_attack_qwen37_flash_0715_20260822",
        "clean": "qwen3.7-flash-2026-07-15-full_no_attack_qwen37_flash_0715_20260822",
    },
}
SUITES = ["banking", "slack", "travel", "workspace"]


def load(pattern):
    records = []
    for path in sorted(Path("runs").glob(pattern)):
        try:
            item = json.loads(path.read_text(encoding="utf-8"))
            if "utility" in item:
                records.append(item)
        except Exception:
            pass
    return records


output = {}
for model, paths in RUNS.items():
    output[model] = {}
    all_clean, all_attack = [], []
    for suite in SUITES:
        clean = load(f"{paths['clean']}/{suite}/user_task_*/none/none.json")
        attack = load(f"{paths['attack']}/{suite}/user_task_*/important_instructions/injection_task_*.json")
        all_clean += clean
        all_attack += attack
        output[model][suite] = {
            "clean_cases": len(clean),
            "attack_cases": len(attack),
            "clean_utility": sum(bool(x["utility"]) for x in clean) / len(clean) if clean else None,
            "attack_utility": sum(bool(x["utility"]) for x in attack) / len(attack) if attack else None,
            "asr": sum(bool(x.get("security")) for x in attack) / len(attack) if attack else None,
            "clean_avg_tokens": sum(int(x.get("total_tokens") or 0) for x in clean) / len(clean) if clean else None,
            "attack_avg_tokens": sum(int(x.get("total_tokens") or 0) for x in attack) / len(attack) if attack else None,
            "clean_avg_duration": sum(float(x.get("duration") or 0) for x in clean) / len(clean) if clean else None,
            "attack_avg_duration": sum(float(x.get("duration") or 0) for x in attack) / len(attack) if attack else None,
        }
    output[model]["all"] = {
        "clean_cases": len(all_clean),
        "attack_cases": len(all_attack),
        "clean_utility": sum(bool(x["utility"]) for x in all_clean) / len(all_clean) if all_clean else None,
        "attack_utility": sum(bool(x["utility"]) for x in all_attack) / len(all_attack) if all_attack else None,
        "asr": sum(bool(x.get("security")) for x in all_attack) / len(all_attack) if all_attack else None,
        "clean_avg_tokens": sum(int(x.get("total_tokens") or 0) for x in all_clean) / len(all_clean) if all_clean else None,
        "attack_avg_tokens": sum(int(x.get("total_tokens") or 0) for x in all_attack) / len(all_attack) if all_attack else None,
        "clean_avg_duration": sum(float(x.get("duration") or 0) for x in all_clean) / len(all_clean) if all_clean else None,
        "attack_avg_duration": sum(float(x.get("duration") or 0) for x in all_attack) / len(all_attack) if all_attack else None,
    }

print(json.dumps(output, indent=2))
