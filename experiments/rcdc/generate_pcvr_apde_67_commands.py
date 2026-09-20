"""Generate the APDE-based 67-case PCVR B1--B5 validation matrix."""
import json
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
MANIFEST = REPO / 'experiments' / 'rcdc' / 'targeted_manifest.json'
OUT = REPO / 'reports' / 'rcvr_ablation_preflight' / 'run_pcvr_apde_67_b1_b5_t07_20260911.sh'
ARMS = ('B1_RCVR', 'B2_WO_BINDING', 'B3_UNKNOWN_STOP', 'B4_UNKNOWN_ALLOW', 'B5_WO_EVIDENCE_ISOLATION')
COMMON = (
    '--model gpt-4o-mini-2024-07-18 --temperature 0.7 --benchmark_version v1.2 '
    '--build_constraints --injection_isolation --dynamic_validation '
    '--taer_mode on --taer_variant full '
    '--source_flow_validation --source_flow_log source_flow --runtime_drift_trace'
)


def injection_number(injection_id):
    return injection_id.rsplit('_', 1)[1]


def command(arm, case):
    tag = f'pcvr_apde_67_{arm.lower()}_t07_20260911'
    base = (
        '"${CONDA_EXE:-/usr/local/miniconda3/bin/conda}" run --no-capture-output -n drift '
        f'python -B experiments/rcdc/run_rcvr_online.py run --config-id {arm} '
        f'--confirm-online-execution --suites {case["suite"]} '
        f'--target_user_tasks {case["task_id"].rsplit("_", 1)[1]} '
        f'--run_tag {tag} {COMMON}'
    )
    if case['attack']:
        return base + (' --do_attack --attack_type important_instructions '
                       f'--target_injection_tasks {injection_number(case["injection_task_id"])}')
    return base


def main():
    manifest = json.loads(MANIFEST.read_text(encoding='utf-8'))
    cases = manifest['cases']
    if manifest.get('case_count') != 67 or len(cases) != 67:
        raise ValueError('expected_frozen_67_case_manifest')
    lines = [
        '#!/usr/bin/env bash', 'set -euo pipefail',
        '# APDE (TAER + SourceFlow) PCVR validation; B0 is intentionally excluded.',
        'set -a; source /data/home/qyc/.config/drift/openai.env; set +a',
        ': "${OPENAI_API_KEY:?OPENAI_API_KEY is required}"', '',
    ]
    for arm in ARMS:
        lines.append(f'# {arm}')
        lines.extend(command(arm, case) for case in cases)
        lines.append('')
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text('\n'.join(lines), encoding='utf-8')
    print(json.dumps({'arms': ARMS, 'cases_per_arm': len(cases),
                      'commands': len(ARMS) * len(cases), 'path': str(OUT.relative_to(REPO))}))


if __name__ == '__main__':
    main()
