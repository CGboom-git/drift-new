"""Generate, but never start, the frozen RCVR core-ablation command matrix.

The output covers the five primary arms from the execution checklist.  It is
kept separate from the smoke matrix and refuses to infer cases outside the
frozen targeted manifest.
"""
import argparse
import json
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
MANIFEST = REPO / 'experiments' / 'rcdc' / 'targeted_manifest.json'
OUT = REPO / 'reports' / 'rcvr_ablation_preflight' / 'run_rcvr_core_ablation.sh'
CORE_ARMS = ('B0_APDE', 'B1_RCVR', 'B2_WO_BINDING', 'B3_UNKNOWN_STOP', 'B4_UNKNOWN_ALLOW', 'B5_WO_EVIDENCE_ISOLATION')
RUN_TAGS = {arm: f'rcvr_core_ablation_{arm.lower()}_20260911' for arm in CORE_ARMS}
COMMON = ('--model gpt-4o-mini-2024-07-18 --benchmark_version v1.2 '
          '--build_constraints --injection_isolation --dynamic_validation --taer_mode off')


def injection_number(injection_id):
    return injection_id.rsplit('_', 1)[1]


def command(arm, case):
    base = (f'"${{CONDA_EXE:-/usr/local/miniconda3/bin/conda}}" run --no-capture-output -n drift '
            f'python -B experiments/rcdc/run_rcvr_online.py run --config-id {arm} '
            f'--confirm-online-execution --suites {case["suite"]} '
            f'--target_user_tasks {case["task_id"].rsplit("_", 1)[1]} '
            f'--run_tag {RUN_TAGS[arm]} {COMMON}')
    if case['attack']:
        return base + (' --do_attack --attack_type important_instructions '
                       f'--target_injection_tasks {injection_number(case["injection_task_id"])}')
    return base


def main(arms=None, output_name='run_rcvr_core_ablation.sh'):
    manifest = json.loads(MANIFEST.read_text(encoding='utf-8'))
    cases = manifest['cases']
    if manifest.get('case_count') != len(cases) or len({case['case_id'] for case in cases}) != len(cases):
        raise ValueError('invalid_frozen_case_manifest')
    lines = [
        '#!/usr/bin/env bash', 'set -euo pipefail',
        '# Generated from the frozen RCVR core-ablation manifest; never auto-started.',
        '# Each command uses the unchanged benchmark and evaluator through the opt-in RCVR runner.',
        'set -a; source /data/home/qyc/.config/drift/openai.env; set +a',
        ': "${OPENAI_API_KEY:?OPENAI_API_KEY is required for approved online execution}"', '',
    ]
    selected_arms = CORE_ARMS if arms is None else tuple(arms)
    if not selected_arms or any(arm not in CORE_ARMS for arm in selected_arms):
        raise ValueError('invalid_core_ablation_arm_selection')
    for arm in selected_arms:
        lines.append(f'# {arm}')
        lines.extend(command(arm, case) for case in cases)
        lines.append('')
    output = OUT.parent / output_name
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text('\n'.join(lines), encoding='utf-8')
    print(json.dumps({'method_name': 'RCVR', 'arms': list(selected_arms),
                      'frozen_cases_per_arm': len(cases),
                      'commands': len(selected_arms) * len(cases),
                      'path': str(output.relative_to(REPO))}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--arms', nargs='+', choices=CORE_ARMS)
    parser.add_argument('--output-name', default='run_rcvr_core_ablation.sh')
    args = parser.parse_args()
    main(args.arms, args.output_name)
