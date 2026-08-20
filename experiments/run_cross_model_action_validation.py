"""Run the focused cross-model authorization validation set."""
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CASES = [
    ("gpt-4o-mini-2024-07-18", 13, 4, "cross_model_action_mini_task13_inj4"),
    ("gpt-4o-mini-2024-07-18", 13, 0, "cross_model_action_mini_task13_clean"),
    ("gpt-4o", 13, 0, "cross_model_action_gpt4o_task13"),
    ("gpt-4o", 20, 0, "cross_model_action_gpt4o_task20"),
    ("gpt-4o", 34, 0, "cross_model_action_gpt4o_task34"),
]
FLAGS = [
    "--build_constraints", "--injection_isolation", "--dynamic_validation",
    "--taer_mode", "on", "--source_flow_validation", "--source_flow_log",
    "--do_attack", "--attack_type", "important_instructions", "--force_rerun",
    "--benchmark_version", "v1.2",
]


def load_env():
    env = dict(os.environ)
    path = Path("~/.config/drift/openai.env").expanduser()
    if path.exists():
        for line in path.read_text().splitlines():
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
    env = load_env()
    for model, user_task, injection_task, tag in CASES:
        print(f"RUN {model} workspace/user_task_{user_task}/injection_task_{injection_task}", flush=True)
        command = [
            sys.executable, str(ROOT / "pipeline_main.py"),
            "--model", model, "--suites", "workspace",
            "--target_user_tasks", str(user_task),
            "--target_injection_tasks", str(injection_task),
            "--run_tag", tag,
        ] + FLAGS
        result = subprocess.run(command, cwd=str(ROOT), env=env, capture_output=True, text=True)
        for line in (result.stdout + "\n" + result.stderr).splitlines()[-12:]:
            if line.strip():
                print(line, flush=True)
        print(f"RETURN_CODE {result.returncode}", flush=True)


if __name__ == "__main__":
    main()
