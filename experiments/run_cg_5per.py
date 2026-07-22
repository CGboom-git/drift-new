"""4-suite x 5-tasks (tasks 5-9) smoke test with SourceFlow, under attack."""
import json, os, subprocess, sys
from pathlib import Path

TEST_CASES = [
    {"suite": "banking",   "user_tasks": "5,6,7,8,9",   "inj": "0,1"},
    {"suite": "slack",     "user_tasks": "5,6,7,8,9",   "inj": "0,1"},
    {"suite": "travel",    "user_tasks": "5,6,7,8,9",   "inj": "0,1"},
    {"suite": "workspace", "user_tasks": "5,6,7,8,9",   "inj": "0,1"},
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
    if env_file.exists():
        for line in open(env_file):
            line = line.strip()
            if not line or line.startswith("#"): continue
            if line.startswith("export "): line = line[7:]
            if "=" in line:
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip().strip("'").strip('"')
    return env

env = load_env()
print(f"Using API base: {env.get('OPENAI_BASE_URL', 'default')}", flush=True)

start_time = __import__("datetime").datetime.now()
print(f"Start: {start_time}", flush=True)

all_results = []

for case in TEST_CASES:
    suite = case["suite"]
    print(f"\n{'='*60}", flush=True)
    print(f"=== SUITE: {suite} ===", flush=True)
    print(f"{'='*60}", flush=True)

    cmd = [sys.executable, "pipeline_main.py",
           "--suites", suite,
           "--target_user_tasks", case["user_tasks"],
           "--target_injection_tasks", case["inj"],
           ] + CONFIG_FLAGS

    run_env = os.environ.copy()
    run_env.update(env)
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=3600, env=run_env)

    for line in (r.stdout + "\n" + r.stderr).split("\n"):
        if any(k in line for k in ("Utility Success Ratio", "Attack Success", "REJECTED",
             "repair_required", "baseline_fallback", "EVIDENCE GAP",
             "checklist_uncertainty", "true_violation")):
            print(f"  {line.strip()[:200]}", flush=True)

    suite_ut = suite_sec = suite_total = 0
    model = "gpt-4o-mini-2024-07-18"
    suite_dir = Path("runs") / model / suite
    if suite_dir.exists():
        for rp in sorted(suite_dir.rglob("injection_task_*.json")):
            if "source_flow" in str(rp):
                continue
            task_name = rp.parent.parent.name
            task_num = int(task_name.replace("user_task_", ""))
            if 5 <= task_num <= 9:
                try:
                    d = json.load(open(rp))
                    suite_total += 1
                    if d.get("utility"): suite_ut += 1
                    if d.get("security"): suite_sec += 1
                    all_results.append({"suite": suite, "task": task_num,
                                        "inj": rp.stem.replace("injection_task_", ""),
                                        "ut": d.get("utility"), "sec": d.get("security")})
                except: pass
    print(f"  {suite}: {suite_total} cases, ut={suite_ut}, sec={suite_sec}", flush=True)

total_ut = sum(1 for r in all_results if r["ut"])
total_sec = sum(1 for r in all_results if r["sec"])
end_time = __import__("datetime").datetime.now()

print(f"\n{'='*60}", flush=True)
print(f"FINAL: {len(all_results)} cases, ut={total_ut}, sec={total_sec}", flush=True)
print(f"Duration: {end_time - start_time}", flush=True)
print("DONE", flush=True)
