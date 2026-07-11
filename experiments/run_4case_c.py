"""Quick 4-case Config C smoke test."""
import json, os, subprocess, sys
from pathlib import Path

CASES = [
    ("slack",   15, 4, "injected_post_webpage"),
    ("slack",   18, 1, "todo_delegated_action"),
    ("travel",   6, 3, "privacy_exfil_email"),
    ("travel",   4, 0, "calendar_action"),
]

CONFIG_FLAGS = [
    "--build_constraints", "--injection_isolation", "--dynamic_validation",
    "--source_flow_validation", "--controlled_action_extension", "--source_flow_log",
    "--do_attack", "--attack_type", "important_instructions", "--force_rerun",
    "--model", "gpt-4o-mini-2024-07-18", "--benchmark_version", "v1.2",
]

OUTPUT = Path("runs/sourceflow_4case_c_smoke")

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
for suite, ut, it, tag in CASES:
    print(f"\n{'='*50}")
    print(f"RUN: {suite}/user_task_{ut}/injection_task_{it} ({tag})")
    print(f"{'='*50}")
    run_env = os.environ.copy()
    run_env.update(env)

    cmd = [sys.executable, "pipeline_main.py",
           "--suites", suite,
           "--target_user_tasks", str(ut),
           "--target_injection_tasks", str(it),
           ] + CONFIG_FLAGS

    r = subprocess.run(cmd, capture_output=True, text=True, timeout=600, env=run_env)

    model = "gpt-4o-mini-2024-07-18"
    result_path = Path("runs") / model / suite / f"user_task_{ut}" / "important_instructions" / f"injection_task_{it}.json"
    sf_path = result_path.parent / "source_flow" / f"injection_task_{it}.source_flow.json"

    dest = OUTPUT / f"{suite}_ut{ut}_it{it}"
    dest.mkdir(parents=True, exist_ok=True)

    result_data = None
    if result_path.exists():
        with open(result_path) as f:
            result_data = json.load(f)
        with open(dest / "result.json", "w") as f:
            json.dump(result_data, f, indent=2)
        print(f"  utility={result_data.get('utility')}, security={result_data.get('security')}")

    sf_data = None
    if sf_path.exists():
        with open(sf_path) as f:
            sf_data = json.load(f)
        with open(dest / "source_flow.json", "w") as f:
            json.dump(sf_data, f, indent=2)
        trace = sf_data.get("validation_trace", [])
        key_events = [e for e in trace if e.get("event") in
                      ("controlled_action_extension_candidate", "controlled_action_extension_rejected",
                       "allow_insert_controlled_action_extension", "side_effect_alignment_passed")]
        print(f"  SF events: {len(trace)}, key CAE events: {len(key_events)}")
        for e in key_events:
            d = e.get("details", {})
            print(f"    [{e['event']}] {d.get('tool_name','')} reason={d.get('reason','')} decision={e.get('decision')}")

    if r.returncode != 0:
        print(f"  STDERR: {r.stderr[-500:]}")

print("\nDone. Results in:", str(OUTPUT))
