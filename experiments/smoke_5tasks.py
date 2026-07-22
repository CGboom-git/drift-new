"""Smoke test: specific tasks, 2 injections each."""
import json, subprocess, sys

CASES = [
    ("banking", 6), ("workspace", 12), ("workspace", 29),
    ("travel", 5), ("travel", 10),
]

results = []
for suite, task in CASES:
    print(f"\n=== {suite} task {task} ===", flush=True)
    cmd = [sys.executable, "pipeline_main.py",
           "--suites", suite,
           "--target_user_tasks", str(task),
           "--target_injection_tasks", "0,1",
           "--build_constraints", "--injection_isolation", "--dynamic_validation",
           "--source_flow_validation", "--controlled_action_extension", "--source_flow_log",
           "--do_attack", "--attack_type", "important_instructions", "--force_rerun",
           "--model", "gpt-4o-mini-2024-07-18", "--benchmark_version", "v1.2"]

    r = subprocess.run(cmd, capture_output=True, text=True, timeout=900)

    for line in (r.stdout + "\n" + r.stderr).split("\n"):
        if "Utility Success Ratio" in line or "Attack Success" in line:
            print(f"  {line.strip()}", flush=True)
        if "repair_required" in line or "REJECTED" in line.upper():
            print(f"  [SF] {line.strip()[:120]}", flush=True)

    # Parse results
    import glob
    for rp in glob.glob(f"runs/gpt-4o-mini-2024-07-18/{suite}/user_task_{task}/important_instructions/injection_task_*.json"):
        if "source_flow" in rp: continue
        d = json.load(open(rp))
        results.append({"suite": suite, "task": task, "ut": d.get("utility"), "sec": d.get("security")})
        print(f"  result: ut={d.get('utility')}, sec={d.get('security')}", flush=True)

print(f"\n{'='*40}")
ut = sum(1 for r in results if r["ut"])
sec = sum(1 for r in results if r["sec"])
print(f"TOTAL: {len(results)}, ut={ut}, sec={sec}")
