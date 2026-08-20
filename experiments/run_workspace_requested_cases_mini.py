"""Run the requested 14 workspace cases with gpt-4o-mini."""
import json
import os
import subprocess
import sys
from pathlib import Path


MODEL = "gpt-4o-mini-2024-07-18"
BENCHMARK_VERSION = "v1.2"
ATTACK_TYPE = "important_instructions"
RUN_TAG = "workspace_requested_cases_mini"
REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = REPO_ROOT / "runs" / f"{MODEL}-{RUN_TAG}" / "workspace"

CASES = [
    (13, 0), (13, 2), (13, 4),
    (20, 0), (20, 3),
    (34, 0), (34, 2),
    (39, 0), (39, 3),
    (30, 0), (30, 3),
    (2, 0),
    (19, 0), (19, 3),
]

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


def main():
    env = os.environ.copy()
    env.update(load_env())
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    manifest = []

    print(f"Running {len(CASES)} requested workspace cases with {MODEL}", flush=True)
    print(f"Shared output dir: {OUTPUT_ROOT}", flush=True)

    for index, (user_task, injection_task) in enumerate(CASES, start=1):
        print(f"\n[{index}/{len(CASES)}] workspace/user_task_{user_task}/injection_task_{injection_task}", flush=True)
        command = [
            sys.executable,
            str(REPO_ROOT / "pipeline_main.py"),
            "--suites", "workspace",
            "--target_user_tasks", str(user_task),
            "--target_injection_tasks", str(injection_task),
        ] + CONFIG_FLAGS
        result = subprocess.run(command, capture_output=True, text=True, env=env, cwd=str(REPO_ROOT))
        for line in (result.stdout + "\n" + result.stderr).splitlines()[-20:]:
            if line.strip():
                print(line, flush=True)

        result_path = OUTPUT_ROOT / f"user_task_{user_task}" / ATTACK_TYPE / f"injection_task_{injection_task}.json"
        record = {
            "user_task": user_task,
            "injection_task": injection_task,
            "result_path": str(result_path),
            "returncode": result.returncode,
        }
        if result_path.exists():
            payload = json.loads(result_path.read_text(encoding="utf-8"))
            record.update({
                "utility": payload.get("utility"),
                "security": payload.get("security"),
                "duration": payload.get("duration"),
            })
        manifest.append(record)

    manifest_path = OUTPUT_ROOT / "requested_cases_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"\nDone. Results are under {OUTPUT_ROOT}", flush=True)
    print(f"Manifest: {manifest_path}", flush=True)
    print(f"Utility: {sum(1 for item in manifest if item.get('utility'))}/{len(manifest)}", flush=True)
    print(f"Security: {sum(1 for item in manifest if item.get('security'))}/{len(manifest)}", flush=True)


if __name__ == "__main__":
    main()
