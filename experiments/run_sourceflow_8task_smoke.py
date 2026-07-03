"""
8-Task Source-Flow Smoke Experiment Runner.

Runs 8 attack cases under 3 configs (A/B/C) and generates a summary report.
"""
import json
import os
import subprocess
import sys
import shutil
import glob
from pathlib import Path
from datetime import datetime

CASES = [
    {"suite": "slack",    "user_task": 15, "injection_task": 4,  "tag": "injected_post_webpage"},
    {"suite": "slack",    "user_task": 18, "injection_task": 1,  "tag": "todo_delegated_action"},
    {"suite": "travel",   "user_task": 6,  "injection_task": 3,  "tag": "privacy_exfil_email"},
    {"suite": "travel",   "user_task": 4,  "injection_task": 0,  "tag": "calendar_action"},
]

CONFIGS = {
    "A_DRIFT_original": [
        "--build_constraints",
        "--injection_isolation",
        "--dynamic_validation",
    ],
    "B_DRIFT_sourceflow": [
        "--build_constraints",
        "--injection_isolation",
        "--dynamic_validation",
        "--source_flow_validation",
        "--source_flow_log",
    ],
    "C_DRIFT_cae": [
        "--build_constraints",
        "--injection_isolation",
        "--dynamic_validation",
        "--source_flow_validation",
        "--controlled_action_extension",
        "--source_flow_log",
    ],
}

BASE_FLAGS = [
    "--do_attack",
    "--attack_type", "important_instructions",
    "--force_rerun",
    "--model", "gpt-4o-mini-2024-07-18",
    "--benchmark_version", "v1.2",
]

OUTPUT_BASE = Path("runs/sourceflow_8task_smoke")


def get_git_commit():
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True
        ).strip()
    except Exception:
        return "unknown"


def load_env(env_path="~/.config/drift/openai.env"):
    env_file = Path(env_path).expanduser()
    if not env_file.exists():
        print(f"WARNING: env file not found: {env_file}")
        return {}
    env = {}
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[7:]
            if "=" in line:
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip("'").strip('"')
                env[key] = value
    return env


def run_case(case, config_name, config_flags, env):
    suite = case["suite"]
    user_task = case["user_task"]
    injection_task = case["injection_task"]
    tag = case["tag"]

    run_env = os.environ.copy()
    run_env.update(env)

    flags = [
        sys.executable, "pipeline_main.py",
        "--suites", suite,
        "--target_user_tasks", str(user_task),
        "--target_injection_tasks", str(injection_task),
    ] + BASE_FLAGS + config_flags

    print(f"\n{'='*70}")
    print(f"RUNNING: [{config_name}] {suite}/user_task_{user_task}/injection_task_{injection_task} ({tag})")
    print(f"{'='*70}")

    try:
        result = subprocess.run(
            flags,
            capture_output=True,
            text=True,
            timeout=600,
            env=run_env,
        )
        stdout = result.stdout
        stderr = result.stderr
        success = result.returncode == 0
    except subprocess.TimeoutExpired:
        stdout = ""
        stderr = "TIMEOUT after 600s"
        success = False
    except Exception as e:
        stdout = ""
        stderr = str(e)
        success = False

    model = "gpt-4o-mini-2024-07-18"
    run_dir = Path("runs") / model / suite
    result_path = (
        run_dir / f"user_task_{user_task}"
        / "important_instructions"
        / f"injection_task_{injection_task}.json"
    )

    result_data = None
    if result_path.exists():
        try:
            with open(result_path) as f:
                result_data = json.load(f)
        except Exception:
            pass

    sf_log_data = None
    sf_log_path = Path("runs") / model / suite / f"user_task_{user_task}" / "important_instructions" / "source_flow" / f"injection_task_{injection_task}.source_flow.json"
    if sf_log_path.exists():
        try:
            with open(str(sf_log_path)) as f:
                sf_log_data = json.load(f)
        except Exception:
            pass

    config_dir = OUTPUT_BASE / config_name / suite / f"user_task_{user_task}" / f"injection_task_{injection_task}"
    config_dir.mkdir(parents=True, exist_ok=True)

    saved_files = []
    if result_data is not None:
        dest = config_dir / "result.json"
        with open(dest, "w") as f:
            json.dump(result_data, f, indent=2)
        saved_files.append(str(dest))

    if sf_log_data is not None:
        dest = config_dir / "source_flow.json"
        with open(dest, "w") as f:
            json.dump(sf_log_data, f, indent=2)
        saved_files.append(str(dest))

    return {
        "success": success,
        "stdout_tail": stdout[-2000:] if stdout else "",
        "stderr_tail": stderr[-2000:] if stderr else "",
        "result_data": result_data,
        "sf_log_data": sf_log_data,
        "saved_files": saved_files,
    }


def collect_results(case, config_name, suite, user_task, injection_task):
    model = "gpt-4o-mini-2024-07-18"
    run_dir = Path("runs") / model / suite
    result_path = (
        run_dir / f"user_task_{user_task}"
        / "important_instructions"
        / f"injection_task_{injection_task}.json"
    )

    if not result_path.exists():
        return None

    try:
        with open(result_path) as f:
            return json.load(f)
    except Exception as e:
        return {"error": str(e)}


def find_source_flow_log(case, suite, user_task, injection_task):
    model = "gpt-4o-mini-2024-07-18"
    run_dir = Path("runs") / model / suite
    log_pattern = str(
        run_dir / f"user_task_{user_task}"
        / "important_instructions"
        / f"injection_task_{injection_task}.source_flow.json"
    )

    matches = glob.glob(log_pattern)
    if not matches:
        alt_pattern = str(
            run_dir / "source_flow"
            / f"user_task_{user_task}_important_instructions"
            / f"injection_task_{injection_task}.source_flow.json"
        )
        matches = glob.glob(alt_pattern)

    if matches:
        try:
            with open(matches[0]) as f:
                return json.load(f)
        except Exception:
            pass
    return None


def extract_source_flow_events(log_data):
    if not log_data:
        return []
    events = []
    for entry in log_data.get("validation_trace", []):
        events.append({
            "step": entry.get("step"),
            "event": entry.get("event"),
            "decision": entry.get("decision"),
            "would_reject": entry.get("would_reject"),
            "details": {k: v for k, v in entry.get("details", {}).items()
                         if k in ("tool_name", "reason", "decision",
                                  "blocked_flows", "warnings", "call_error_message")},
        })
    return events


def generate_report(results, commit_hash):
    OUTPUT_BASE.mkdir(parents=True, exist_ok=True)

    rows = []
    for r in results:
        res = r.get("result", {}) or {}
        sf_events = r.get("source_flow_events", [])

        rejected = [e for e in sf_events if e.get("event") in
                     ("controlled_action_extension_rejected",
                      "source_flow_action_validation") and e.get("would_reject")]
        allowed_cae = [e for e in sf_events if e.get("event") ==
                        "allow_insert_controlled_action_extension"]

        rows.append({
            "suite": r["suite"],
            "user_task": r["user_task"],
            "injection_task": r["injection_task"],
            "tag": r["tag"],
            "config": r["config"],
            "utility": res.get("utility", "N/A"),
            "security": res.get("security", "N/A"),
            "attack_successful": not res.get("security", True) if isinstance(res.get("security"), bool) else "N/A",
            "executed_tools": r.get("executed_tools", []),
            "n_source_flow_events": len(sf_events),
            "n_rejected": len(rejected),
            "n_cae_allowed": len(allowed_cae),
            "sf_rejected_reasons": [e.get("details", {}).get("reason") for e in rejected],
            "sf_log_path": r.get("sf_log_path"),
            "result_path": r.get("result_path"),
            "error": r.get("error", ""),
        })

    csv_path = OUTPUT_BASE / "summary.csv"
    with open(csv_path, "w") as f:
        keys = ["suite", "user_task", "injection_task", "tag", "config",
                "utility", "security", "n_source_flow_events", "n_rejected",
                "n_cae_allowed", "sf_rejected_reasons", "error"]
        f.write(",".join(keys) + "\n")
        for row in rows:
            vals = [str(row.get(k, "")).replace(",", ";") for k in keys]
            f.write(",".join(vals) + "\n")

    json_path = OUTPUT_BASE / "summary.json"
    with open(json_path, "w") as f:
        json.dump({
            "commit": commit_hash,
            "timestamp": datetime.now().isoformat(),
            "total_cases": len(results),
            "rows": rows,
        }, f, indent=2)

    # Generate report.md
    lines = [
        "# Source-Flow 8-Task Smoke Experiment Report",
        "",
        f"- **Git commit**: `{commit_hash}`",
        f"- **Timestamp**: {datetime.now().isoformat()}",
        f"- **Model**: gpt-4o-mini-2024-07-18",
        f"- **Total runs**: {len(results)}",
        "",
        "## Configurations",
        "",
        "| Config | Flags |",
        "|--------|-------|",
        "| A_DRIFT_original | --build_constraints --injection_isolation --dynamic_validation |",
        "| B_DRIFT_sourceflow | + --source_flow_validation --source_flow_log |",
        "| C_DRIFT_cae | + --controlled_action_extension |",
        "",
        "## Results Summary",
        "",
        "| Suite | Task | Inj | Tag | Config | Utility | Security | SF_Events | Rejected | CAE_Allow | Error |",
        "|-------|------|-----|-----|--------|---------|----------|-----------|----------|-----------|-------|",
    ]
    for row in rows:
        lines.append(
            f"| {row['suite']} | {row['user_task']} | {row['injection_task']} | "
            f"{row['tag']} | {row['config']} | {row['utility']} | {row['security']} | "
            f"{row['n_source_flow_events']} | {row['n_rejected']} | {row['n_cae_allowed']} | "
            f"{row['error']} |"
        )

    # Key observations
    lines += [
        "",
        "## Key Observations",
        "",
        "### Injected ACTION Rejection (slack/user_task_15/injection_task_4)",
        "",
    ]
    for row in rows:
        if row["tag"] == "injected_post_webpage":
            lines.append(
                f"- **{row['config']}**: utility={row['utility']}, "
                f"security={row['security']}, "
                f"rejected={row['n_rejected']}, "
                f"reasons={row['sf_rejected_reasons']}"
            )

    lines += [
        "",
        "### Delegated TODO Utility (slack/user_task_18/injection_task_1)",
        "",
    ]
    for row in rows:
        if row["tag"] == "todo_delegated_action":
            lines.append(
                f"- **{row['config']}**: utility={row['utility']}, "
                f"security={row['security']}, "
                f"cae_allowed={row['n_cae_allowed']}"
            )

    lines += [
        "",
        "### Controlled Action Extension Events (Config C only)",
        "",
    ]
    for row in rows:
        if row["config"] == "C_DRIFT_cae" and (row["n_cae_allowed"] > 0 or row["n_rejected"] > 0):
            lines.append(
                f"- {row['suite']}/user_task_{row['user_task']}/injection_task_{row['injection_task']}: "
                f"cae_allowed={row['n_cae_allowed']}, rejected={row['n_rejected']}, "
                f"reasons={row['sf_rejected_reasons']}"
            )

    lines += [
        "",
        "## Commands",
        "",
        "```bash",
        "# Source env",
        "source ~/.config/drift/openai.env",
        "",
        "# Run experiment",
        "python experiments/run_sourceflow_8task_smoke.py",
        "```",
        "",
    ]

    report_path = OUTPUT_BASE / "report.md"
    with open(report_path, "w") as f:
        f.write("\n".join(lines))

    print(f"\nReport written to: {report_path}")
    print(f"CSV written to: {csv_path}")
    print(f"JSON written to: {json_path}")
    return rows


def main():
    env = load_env()
    if not env.get("OPENAI_API_KEY"):
        print("ERROR: OPENAI_API_KEY not found in ~/.config/drift/openai.env")
        sys.exit(1)

    commit_hash = get_git_commit()
    print(f"Git commit: {commit_hash}")
    print(f"API URL: {env.get('OPENAI_BASE_URL', 'default')}")
    print(f"Model: gpt-4o-mini-2024-07-18")

    all_results = []

    for case in CASES:
        suite = case["suite"]
        user_task = case["user_task"]
        injection_task = case["injection_task"]
        tag = case["tag"]

        for config_name, config_flags in CONFIGS.items():
            run_info = run_case(case, config_name, config_flags, env)

            result_data = run_info.get("result_data", {}) or {}
            sf_log = run_info.get("sf_log_data")
            sf_events = extract_source_flow_events(sf_log)

            executed_tools = []
            if result_data and "conversations" in result_data:
                for msg in result_data.get("conversations", []):
                    if msg.get("role") == "assistant":
                        for tc in msg.get("tool_calls", []) or []:
                            fn = tc.get("function") if isinstance(tc, dict) else getattr(tc, "function", None)
                            if fn:
                                executed_tools.append(fn if isinstance(fn, str) else fn.get("name", str(fn)))

            saved_dir = str(OUTPUT_BASE / config_name / suite / f"user_task_{user_task}" / f"injection_task_{injection_task}")

            error = ""
            if not run_info["success"]:
                error = run_info.get("stderr_tail", "run failed")[:200]
            elif result_data is None:
                error = "no result JSON found"

            all_results.append({
                "suite": suite,
                "user_task": user_task,
                "injection_task": injection_task,
                "tag": tag,
                "config": config_name,
                "result": result_data,
                "source_flow_events": sf_events,
                "executed_tools": executed_tools,
                "sf_log_path": "",
                "result_path": saved_dir,
                "error": error,
            })

            status = "OK" if not error else f"ERR: {error[:80]}"
            print(f"  -> {config_name}: {status}")

    generate_report(all_results, commit_hash)
    print("\nExperiment complete.")


if __name__ == "__main__":
    main()
