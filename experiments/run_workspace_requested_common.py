"""Shared runner for the requested workspace cases."""
import os
import subprocess
import sys
from pathlib import Path


MODEL = "gpt-4o"
BENCHMARK_VERSION = "v1.2"
ATTACK_TYPE = "important_instructions"
RUN_TAG = "workspace_requested_ordered"
REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG_FLAGS = [
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
    "--run_tag", RUN_TAG,
]


def load_env():
    env_file = Path("~/.config/drift/openai.env").expanduser()
    env = {}
    if not env_file.exists():
        return env
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


def run_cases(cases, script_name):
    env = os.environ.copy()
    env.update(load_env())
    print(f"Running {script_name}", flush=True)
    print(f"Shared output dir: runs/{MODEL}-{RUN_TAG}/workspace", flush=True)

    for index, case in enumerate(cases, start=1):
        suite = case["suite"]
        user_task = case["user_task"]
        injection_task = case["injection_task"]
        label = case.get("label", "")
        print(f"\n[{index}/{len(cases)}] {suite}/user_task_{user_task}/injection_task_{injection_task} {label}".strip(), flush=True)

        cmd = [
            sys.executable,
            str(REPO_ROOT / "pipeline_main.py"),
            "--suites", suite,
            "--target_user_tasks", str(user_task),
            "--target_injection_tasks", str(injection_task),
        ] + CONFIG_FLAGS

        result = subprocess.run(cmd, capture_output=True, text=True, env=env, cwd=str(REPO_ROOT))
        tail = (result.stdout + "\n" + result.stderr).splitlines()[-20:]
        for line in tail:
            if line.strip():
                print(line, flush=True)

        if result.returncode != 0:
            print(f"Case failed with exit code {result.returncode}", flush=True)

    print(f"\nDone. Results are under runs/{MODEL}-{RUN_TAG}/workspace", flush=True)
