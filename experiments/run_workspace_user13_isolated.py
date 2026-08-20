"""Run task13 injection cases in strictly isolated Workspace processes."""
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


MODEL = "gpt-4o-mini-2024-07-18"
BENCHMARK_VERSION = "v1.2"
ATTACK_TYPE = "important_instructions"
BASE_TAG = "workspace_user13_isolated_mini"
REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = REPO_ROOT / "runs" / f"{MODEL}-{BASE_TAG}" / "workspace"
CASES = [0, 1, 2, 3, 4]

COMMON_FLAGS = [
    "--build_constraints",
    "--injection_isolation",
    "--dynamic_validation",
    "--taer_mode", "on",
    "--source_flow_validation",
    "--source_flow_log",
    "--do_attack",
    "--attack_type", ATTACK_TYPE,
    "--force_rerun",
    "--model", MODEL,
    "--benchmark_version", BENCHMARK_VERSION,
]


def load_env():
    env_file = Path("~/.config/drift/openai.env").expanduser()
    env = {}
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[7:]
            if "=" in line:
                key, _, value = line.partition("=")
                env[key.strip()] = value.strip().strip("'").strip('"')
    return env


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def baseline_snapshot():
    script = """
import json
import yaml
from agentdojo.task_suite.load_suites import get_suite
from DRIFTTaskSuite import read_suite_file
suite = get_suite('v1.2', 'workspace')
raw = yaml.safe_load(read_suite_file('workspace', 'environment.yaml', suite.data_path))
print(json.dumps({'environment_yaml': 'agentdojo:data/suites/workspace/environment.yaml', 'baseline': raw}, default=str))
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        env={**os.environ, **load_env()},
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Baseline snapshot failed: {result.stderr}")
    return json.loads(result.stdout.strip())


def main():
    env = {**os.environ, **load_env()}
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    manifest = []

    for injection_task in CASES:
        case_tag = f"{BASE_TAG}_task13_inj{injection_task}"
        case_root = OUTPUT_ROOT / f"task13_inj{injection_task}"
        case_root.mkdir(parents=True, exist_ok=True)
        diagnostics_path = case_root / "isolation_diagnostics.json"
        case_start = utc_now()
        baseline = baseline_snapshot()
        diagnostics = {
            "event": "CASE_START",
            "timestamp": case_start,
            "user_task": 13,
            "injection_task": injection_task,
            "run_tag": case_tag,
            "baseline": baseline,
            "expected_appended_activities_present": False,
            "relevant_sent_email_state": "baseline loaded from fresh environment.yaml",
        }
        diagnostics_path.write_text(json.dumps(diagnostics, indent=2), encoding="utf-8")
        print(f"CASE_START {case_start} workspace/user_task_13/injection_task_{injection_task}", flush=True)

        command = [
            sys.executable,
            str(REPO_ROOT / "pipeline_main.py"),
            "--suites", "workspace",
            "--target_user_tasks", "13",
            "--target_injection_tasks", str(injection_task),
            "--run_tag", case_tag,
        ] + COMMON_FLAGS
        result = subprocess.run(command, capture_output=True, text=True, cwd=str(REPO_ROOT), env=env)

        result_path = REPO_ROOT / "runs" / f"{MODEL}-{case_tag}" / "workspace" / "user_task_13" / ATTACK_TYPE / f"injection_task_{injection_task}.json"
        payload = json.loads(result_path.read_text(encoding="utf-8")) if result_path.exists() else {}
        case_end = utc_now()
        diagnostics.update({
            "event": "CASE_END",
            "end_timestamp": case_end,
            "returncode": result.returncode,
            "result_path": str(result_path),
            "utility": payload.get("utility"),
            "security": payload.get("security"),
            "environment_destroyed": True,
        })
        diagnostics_path.write_text(json.dumps(diagnostics, indent=2), encoding="utf-8")
        print(f"CASE_END {case_end} workspace/user_task_13/injection_task_{injection_task} returncode={result.returncode}", flush=True)
        manifest.append({
            "user_task": 13,
            "injection_task": injection_task,
            "case_root": str(case_root),
            "result_path": str(result_path),
            "returncode": result.returncode,
            "utility": payload.get("utility"),
            "security": payload.get("security"),
            "case_start": case_start,
            "case_end": case_end,
        })

    manifest_path = OUTPUT_ROOT / "isolated_task13_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Manifest: {manifest_path}", flush=True)


if __name__ == "__main__":
    main()
