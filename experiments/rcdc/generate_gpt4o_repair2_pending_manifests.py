"""Create repair2 manifests from repair1 cases that lack a valid result."""
import json
from pathlib import Path


ROOT = Path("reports/rcvr_ablation_preflight")
REPAIR1 = ROOT / "full_b1_gpt4o_repair1_two_lanes_t07_20260919"
REPAIR2 = ROOT / "full_b1_gpt4o_repair2_two_lanes_t07_20260919"
RESULTS1 = Path("runs/gpt-4o-pcvr_apde_full_b1_gpt4o_t07_20260919_repair1")


def result_path(case):
    attack_dir = case["attack_type"] if case["attack_type"] else "none"
    leaf = f"{case['injection_task_id']}.json" if case["injection_task_id"] else "none.json"
    return RESULTS1 / case["suite_name"] / case["user_task_id"] / attack_dir / leaf


def is_valid(case):
    path = result_path(case)
    failure = path.with_suffix(".failed.json")
    if failure.exists() or not path.is_file():
        return False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    return "utility" in payload and "security" in payload


def main():
    REPAIR2.mkdir(parents=True, exist_ok=True)
    total = 0
    for lane in ("workspace", "others"):
        prior = json.loads((REPAIR1 / f"{lane}_repair_manifest.json").read_text(encoding="utf-8"))
        pending = [case for case in prior["cases"] if not is_valid(case)]
        payload = {
            "purpose": "repair2 exact scope; every entry lacks a valid repair1 result",
            "source_run_tag": "pcvr_apde_full_b1_gpt4o_t07_20260919_repair1",
            "lane": lane,
            "case_count": len(pending),
            "cases": pending,
        }
        (REPAIR2 / f"{lane}_pending_manifest.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
        total += len(pending)
        print(f"{lane}: pending={len(pending)} valid_repair1={prior['case_count'] - len(pending)}")
    if total != 290:
        raise RuntimeError(f"unexpected_pending_count:{total}")


if __name__ == "__main__":
    main()
