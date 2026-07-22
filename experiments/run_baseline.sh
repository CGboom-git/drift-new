#!/bin/bash
# Run on old SourceFlow version (before triage/fallback)
source /home/cg/.config/drift/openai.env
export OPENAI_API_KEY OPENAI_BASE_URL
cd /home/cg/Code/DRIFT

exec /home/cg/anaconda3/envs/drift/bin/python -c "
import json, os, subprocess, sys
from pathlib import Path

CASES = [
    ('banking', '5,6,7,8,9'),
    ('travel', '5,6,7,8,9'),
    ('workspace', '5,6,7,8,9'),
    ('slack', '0,1,2,3,4'),
]

env = {}
with open(os.path.expanduser('~/.config/drift/openai.env')) as f:
    for line in f:
        line = line.strip()
        if not line or line.startswith('#'): continue
        if line.startswith('export '): line = line[7:]
        if '=' in line:
            k, _, v = line.partition('=')
            env[k.strip()] = v.strip().strip(\"'\").strip('\"')

run_env = os.environ.copy()
run_env.update(env)

for suite, tasks in CASES:
    inj_tasks = '1,2' if suite == 'slack' else '0,1'
    print(f'=== {suite} ===', flush=True)
    cmd = [sys.executable, 'pipeline_main.py',
           '--suites', suite, '--target_user_tasks', tasks,
           '--target_injection_tasks', inj_tasks,
           '--build_constraints', '--injection_isolation', '--dynamic_validation',
           '--source_flow_validation', '--controlled_action_extension', '--source_flow_log',
           '--do_attack', '--attack_type', 'important_instructions', '--force_rerun',
           '--model', 'gpt-4o-mini-2024-07-18', '--benchmark_version', 'v1.2']
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=3600, env=run_env)
    for line in (r.stdout + r.stderr).split('\n'):
        if any(k in line for k in ('Utility Success Ratio', 'Attack Success Ratio',
             'repair_required', 'recovery_exit', 'baseline_fallback',
             'EVIDENCE GAP', 'checklist_uncertainty', 'true_violation', 'locked_arg')):
            print(f'  {line.strip()[:200]}', flush=True)
    print(f'  DONE {suite}', flush=True)
print('ALL DONE', flush=True)
" > experiments/baseline_v1.log 2>&1
