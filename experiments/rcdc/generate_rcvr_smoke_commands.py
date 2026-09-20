"""Write, but never execute, the exact 12-case RCVR smoke command matrix."""
import json
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
MANIFEST = REPO / 'experiments' / 'rcdc' / 'targeted_manifest.json'
OUT = REPO / 'reports' / 'rcvr_ablation_preflight' / 'run_rcvr_smoke_commands.sh'
ARMS = ('B0_APDE', 'B1_RCVR', 'B2_SOURCE_ONLY', 'B3_UNKNOWN_STOP', 'B4_UNKNOWN_ALLOW', 'B5_GENERIC_RECOVERY')
RUN_TAGS = {
    'B0_APDE': 'rcvr_smoke_b0_apde',
    # The first B1--B4 pass exposed a fenced-JSON parser defect before any
    # recovery read could execute.  Preserve those traces and write the valid
    # rerun to separate result directories.
    'B1_RCVR': 'rcvr_smoke_b1_rcvr_parsefix1',
    'B2_SOURCE_ONLY': 'rcvr_smoke_b2_source_only_parsefix1',
    'B3_UNKNOWN_STOP': 'rcvr_smoke_b3_unknown_stop_parsefix1',
    'B4_UNKNOWN_ALLOW': 'rcvr_smoke_b4_unknown_allow',
    'B5_GENERIC_RECOVERY': 'rcvr_smoke_b4_generic_recovery_parsefix1',
}
COMMON = ('--model gpt-4o-mini-2024-07-18 --benchmark_version v1.2 '
          '--build_constraints --injection_isolation --dynamic_validation --taer_mode off')


def injection_number(injection_id):
    return injection_id.rsplit('_', 1)[1]


def command(arm, case):
    tag = RUN_TAGS[arm]
    base = (f'"${{CONDA_EXE:-/usr/local/miniconda3/bin/conda}}" run --no-capture-output -n drift python -B experiments/rcdc/run_rcvr_online.py '
            f'run --config-id {arm} --confirm-online-execution --suites {case["suite"]} '
            f'--target_user_tasks {case["task_id"].rsplit("_", 1)[1]} --run_tag {tag} {COMMON}')
    if case['attack']:
        return base + f' --do_attack --attack_type important_instructions --target_injection_tasks {injection_number(case["injection_task_id"])}'
    return base


def main():
    manifest = json.loads(MANIFEST.read_text(encoding='utf-8'))
    cases = [case for case in manifest['cases'] if case['case_id'] in manifest['smoke_case_ids']]
    if len(cases) != 12:
        raise ValueError('expected_exactly_12_frozen_smoke_cases')
    if len({case['case_id'] for case in cases}) != len(cases):
        raise ValueError('duplicate_smoke_case')
    lines = [
        '#!/usr/bin/env bash', 'set -euo pipefail',
        '# Generated from the frozen RCVR manifest; intentionally not auto-started.',
        '# Base condition: APDE flags with TAER/source-flow disabled, as frozen by targeted_manifest.',
        '# Each command requires a separately reviewed --confirm-online-execution flag.',
        '# Load the server-side credential file without printing its contents.',
        'set -a; source /data/home/qyc/.config/drift/openai.env; set +a',
        ': "${OPENAI_API_KEY:?OPENAI_API_KEY is required for approved online smoke}"', '',
    ]
    for arm in ARMS:
        lines.append(f'# {arm}')
        lines.extend(command(arm, case) for case in cases)
        lines.append('')
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text('\n'.join(lines), encoding='utf-8')
    print(json.dumps({'method_name': 'RCVR', 'online_started': False, 'arms': len(ARMS),
                      'frozen_smoke_cases': len(cases), 'commands': len(ARMS) * len(cases),
                      'path': str(OUT.relative_to(REPO))}))


if __name__ == '__main__':
    main()
