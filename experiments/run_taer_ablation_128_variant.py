"""Run the frozen 128-case TAER ablation manifest for one variant."""
import argparse
import json
import os
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

MODEL = "gpt-4o-mini-2024-07-18"
ATTACK = "important_instructions"
REPO = Path(__file__).resolve().parents[1]
MANIFEST = REPO / "experiments" / "taer_ablation_128_manifest.json"
SUITE_ORDER = {"banking": 0, "slack": 1, "travel": 2, "workspace": 3}


def load_env():
    result = os.environ.copy()
    path = Path("~/.config/drift/openai.env").expanduser()
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:]
        if "=" in line:
            key, value = line.split("=", 1)
            result[key.strip()] = value.strip().strip("'\"")
    return result


def result_path(run_tag, suite, user, injection):
    return (REPO / "runs" / f"{MODEL}-{run_tag}" / suite / f"user_task_{user}" /
            ATTACK / f"injection_task_{injection}.json")


def complete(path):
    if not path.exists():
        return False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        trace = path.parent / "runtime_drift_trace" / f"{path.stem}.runtime_drift.json"
        return "utility" in payload and "security" in payload and trace.exists()
    except Exception:
        return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--variant", required=True,
                        choices=["full", "no_anchor", "no_scope", "no_ephemeral"])
    parser.add_argument("--run_tag", default=None,
                        help="Optional output tag; defaults to the original ablation tag.")
    args = parser.parse_args()
    run_tag = args.run_tag or f"taer_ablation128_{args.variant}_gpt4omini_20260824"
    cases = json.loads(MANIFEST.read_text(encoding="utf-8"))["cases"]
    groups = defaultdict(list)
    for case in cases:
        groups[(case["suite"], case["user_task_id"])].append(case["injection_task_id"])
    ordered = sorted(groups.items(), key=lambda x: (SUITE_ORDER[x[0][0]], x[0][1]))
    env = load_env()
    failures = []
    print(f"variant={args.variant} run_tag={run_tag} cases={len(cases)} groups={len(ordered)}", flush=True)
    for index, ((suite, user), injections) in enumerate(ordered, 1):
        missing = [i for i in sorted(injections) if not complete(result_path(run_tag, suite, user, i))]
        if not missing:
            print(f"[{index}/{len(ordered)}] skip complete {suite}/user_task_{user}", flush=True)
            continue
        command = [
            sys.executable, "-B", str(REPO / "pipeline_main.py"),
            "--model", MODEL, "--suites", suite,
            "--target_user_tasks", str(user),
            "--target_injection_tasks", ",".join(map(str, missing)),
            "--run_tag", run_tag, "--benchmark_version", "v1.2",
            "--build_constraints", "--injection_isolation", "--dynamic_validation",
            "--taer_mode", "on", "--taer_variant", args.variant,
            "--source_flow_validation", "--source_flow_log", "source_flow",
            "--runtime_drift_trace", "--do_attack", "--attack_type", ATTACK,
            "--force_rerun",
        ]
        print(f"[{index}/{len(ordered)}] {suite}/user_task_{user} injections={missing}", flush=True)
        result = subprocess.run(command, cwd=REPO, env=env)
        unresolved = [i for i in missing if not complete(result_path(run_tag, suite, user, i))]
        if result.returncode or unresolved:
            failures.append({"suite": suite, "user_task": user, "injections": missing,
                             "returncode": result.returncode, "unresolved": unresolved})
    output_root = REPO / "runs" / f"{MODEL}-{run_tag}"
    output_root.mkdir(parents=True, exist_ok=True)
    progress = {"variant": args.variant, "run_tag": run_tag, "expected_cases": len(cases),
                "failures": failures, "status": "complete" if not failures else "failed"}
    (output_root / "ablation_progress.json").write_text(json.dumps(progress, indent=2), encoding="utf-8")
    print(json.dumps(progress, indent=2), flush=True)
    raise SystemExit(1 if failures else 0)


if __name__ == "__main__":
    main()
