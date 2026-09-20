"""Select repair2 Slack/Travel cases that still lack a valid repair2 result."""
import json
from pathlib import Path


ROOT = Path("reports/rcvr_ablation_preflight")
R2 = ROOT / "full_b1_gpt4o_repair2_two_lanes_t07_20260919"
OUT = ROOT / "full_b1_gpt4o_repair3_others_t07_20260919"
RESULTS = Path("runs/gpt-4o-pcvr_apde_full_b1_gpt4o_t07_20260919_repair2")


def valid(case):
    leaf = f"{case['injection_task_id']}.json"
    result = RESULTS / case["suite_name"] / case["user_task_id"] / case["attack_type"] / leaf
    if result.with_suffix(".failed.json").exists() or not result.is_file():
        return False
    try:
        payload = json.loads(result.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    return "utility" in payload and "security" in payload


def main():
    source = json.loads((R2 / "others_pending_manifest.json").read_text(encoding="utf-8"))
    cases = [case for case in source["cases"] if not valid(case)]
    if len(cases) != 83:
        raise RuntimeError(f"unexpected_pending_others:{len(cases)}")
    OUT.mkdir(parents=True, exist_ok=True)
    payload = {"purpose": "repair3 after isolated response-path failure", "source_run_tag": "pcvr_apde_full_b1_gpt4o_t07_20260919_repair2", "case_count": len(cases), "cases": cases}
    (OUT / "others_pending_manifest.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"others pending={len(cases)}")


if __name__ == "__main__":
    main()
