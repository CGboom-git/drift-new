"""Build a one-process, exact-case rerun script for API-invalid B1 outputs.

The script deliberately selects only result JSON files containing the runner's
API-error sentinel.  It never selects failed benchmark outcomes as retries.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path


MODEL = "gpt-4o-mini-2024-07-18"
RUN_TAG = "pcvr_apde_full_b1_v12_t07_20260911"
REPO = Path(__file__).resolve().parents[2]
ROOT = REPO / "runs" / f"{MODEL}-{RUN_TAG}"
OUT = REPO / "reports" / "rcvr_ablation_preflight" / "full_b1_t07_20260911"

COMMON = (
    "--config-id B1_RCVR --confirm-online-execution "
    f"--model {MODEL} --temperature 0.7 --benchmark_version v1.2 "
    f"--run_tag {RUN_TAG} --build_constraints --injection_isolation "
    "--dynamic_validation --taer_mode on --taer_variant full "
    "--source_flow_validation --source_flow_log source_flow --runtime_drift_trace "
    "--force_rerun"
)


def is_api_invalid(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    return "API_ERROR" in text or "Generation failed." in text


def main() -> None:
    cases: list[dict[str, object]] = []
    for path in ROOT.rglob("*.json"):
        if "/source_flow/" in path.as_posix() or "/runtime_drift_trace/" in path.as_posix():
            continue
        if not is_api_invalid(path):
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        user = str(data["user_task_id"]).rsplit("_", 1)[1]
        injection = data.get("injection_task_id")
        cases.append(
            {
                "suite": data["suite_name"],
                "user_task": int(user),
                "injection_task": None if injection is None else int(str(injection).rsplit("_", 1)[1]),
            }
        )

    cases.sort(key=lambda x: (str(x["suite"]), int(x["user_task"]), -1 if x["injection_task"] is None else int(x["injection_task"])))
    (OUT / "b1_invalid_rerun_manifest.json").write_text(json.dumps(cases, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        "cd /data/home/qyc/Project/drift-new",
        "set -a",
        "source /data/home/qyc/.config/drift/openai.env",
        "set +a",
        ': "${OPENAI_API_KEY:?OPENAI_API_KEY is required}"',
        'CONDA_BIN="${CONDA_EXE:-/usr/local/miniconda3/bin/conda}"',
        "",
    ]
    for case in cases:
        command = (
            '"$CONDA_BIN" run --no-capture-output -n drift python -B '
            "experiments/rcdc/run_rcvr_online.py run "
            f"--suites {case['suite']} --target_user_tasks {case['user_task']} {COMMON}"
        )
        if case["injection_task"] is not None:
            command += f" --do_attack --attack_type important_instructions --target_injection_tasks {case['injection_task']}"
        lines.append(command)
    script = OUT / "run_b1_invalid_rerun_t07_20260912.sh"
    script.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"case_count": len(cases), "manifest": str(OUT / "b1_invalid_rerun_manifest.json"), "script": str(script)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
