"""Build exact repair manifests for the invalid 2026-09-19 GPT-4o B1 run.

The original result JSON files are retained for forensic audit.  This script
uses the console-log-to-source-flow linkage established during the audit, so
only cases preceded by an API transport error are selected for rerun.
"""
import collections
import glob
import json
import re
from pathlib import Path


RUN_TAG = "gpt-4o-pcvr_apde_full_b1_gpt4o_t07_20260919"
LOG_DIR = Path("reports/rcvr_ablation_preflight/full_b1_gpt4o_two_lanes_t07_20260919")
OUT_DIR = Path("reports/rcvr_ablation_preflight/full_b1_gpt4o_repair1_two_lanes_t07_20260919")


def main():
    saved_re = re.compile(
        r"Source-flow log is saved at: (runs/" + re.escape(RUN_TAG) + r"/.+?/source_flow/.+?\.source_flow\.json)"
    )
    error_re = re.compile(r"API call failed: Connection error\.")
    errors_by_result = collections.Counter()
    for log_path in (LOG_DIR / "workspace.log", LOG_DIR / "others.log"):
        pending = 0
        for line in log_path.read_text(encoding="utf-8", errors="replace").splitlines():
            if error_re.search(line):
                pending += 1
            match = saved_re.search(line)
            if match:
                result_path = match.group(1).replace("/source_flow/", "/").replace(".source_flow.json", ".json")
                if pending:
                    errors_by_result[result_path] += pending
                pending = 0
        if pending:
            raise RuntimeError(f"unattributed_api_errors:{log_path}:{pending}")

    lanes = {"workspace": [], "others": []}
    for path in glob.glob(f"runs/{RUN_TAG}/**/*.json", recursive=True):
        normalized = path.replace("\\", "/")
        if "/source_flow/" in normalized or "/runtime_drift_trace/" in normalized:
            continue
        if not errors_by_result[normalized]:
            continue
        result = json.loads(Path(path).read_text(encoding="utf-8"))
        entry = {
            "suite_name": result["suite_name"],
            "attack_type": result.get("attack_type"),
            "user_task_id": result["user_task_id"],
            "injection_task_id": result.get("injection_task_id"),
            "original_result_path": normalized,
            "observed_api_error_count": errors_by_result[normalized],
        }
        lane = "workspace" if entry["suite_name"] == "workspace" else "others"
        lanes[lane].append(entry)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for lane, cases in lanes.items():
        cases.sort(key=lambda row: (row["suite_name"], row["attack_type"] or "", row["user_task_id"], row["injection_task_id"] or ""))
        payload = {
            "purpose": "exact repair scope; entries are infrastructure-invalid and non-scoreable in the original run",
            "source_run_tag": RUN_TAG,
            "lane": lane,
            "case_count": len(cases),
            "cases": cases,
        }
        (OUT_DIR / f"{lane}_repair_manifest.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"{lane}: {len(cases)} cases")
    if sum(map(len, lanes.values())) != 756:
        raise RuntimeError(f"unexpected_repair_count:{sum(map(len, lanes.values()))}")


if __name__ == "__main__":
    main()
