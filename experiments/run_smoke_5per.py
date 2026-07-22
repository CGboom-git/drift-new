"""Quick 4-suite Config C smoke test. 2 tasks x 2 injections per suite."""
import json, os, subprocess, sys
from pathlib import Path

TEST_CASES = [
    {"suite": "banking",   "user_tasks": "0,1",   "inj": "0,1"},
    {"suite": "slack",     "user_tasks": "0,1",   "inj": "0,1"},
    {"suite": "travel",    "user_tasks": "0,1",   "inj": "0,1"},
    {"suite": "workspace", "user_tasks": "0,1",   "inj": "0,1"},
]

CONFIG_FLAGS = [
    "--build_constraints", "--injection_isolation", "--dynamic_validation",
    "--source_flow_validation", "--controlled_action_extension", "--source_flow_log",
    "--do_attack", "--attack_type", "important_instructions", "--force_rerun",
    "--model", "gpt-4o-mini-2024-07-18", "--benchmark_version", "v1.2",
]

def load_env():
    env_file = Path("~/.config/drift/openai.env").expanduser()
    env = {}
    for line in open(env_file):
        line = line.strip()
        if not line or line.startswith("#"): continue
        if line.startswith("export "): line = line[7:]
        if "=" in line:
            k, _, v = line.partition("=")
            env[k.strip()] = v.strip().strip("'").strip('"')
    return env

env = load_env()

for case in TEST_CASES:
    suite = case["suite"]
    print(f"\n=== {suite} ===", flush=True)

    cmd = [sys.executable, "pipeline_main.py",
           "--suites", suite,
           "--target_user_tasks", case["user_tasks"],
           "--target_injection_tasks", case["inj"],
           ] + CONFIG_FLAGS

    run_env = os.environ.copy()
    run_env.update(env)
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=1200, env=run_env)

    # Parse results
    ut_total = 0; sec_total = 0
    for line in (r.stdout + "\n" + r.stderr).split("\n"):
        if "Utility Success Ratio" in line:
            print(f"  {line.strip()}", flush=True)

    model = "gpt-4o-mini-2024-07-18"
    suite_dir = Path("runs") / model / suite
    if suite_dir.exists():
        ut_ok = sec_ok = total = 0
        for rp in suite_dir.rglob("injection_task_*.json"):
            if "source_flow" in str(rp):
                continue
            try:
                d = json.load(open(rp))
                total += 1
                if d.get("utility"): ut_ok += 1
                if d.get("security"): sec_ok += 1
            except: pass
        print(f"  {suite}: {total} cases, ut={ut_ok}, sec={sec_ok}", flush=True)

print("\nDONE")
