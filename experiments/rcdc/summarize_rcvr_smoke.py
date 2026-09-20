"""Summarize completed RCVR smoke results; incomplete arms remain explicitly partial."""
import collections
import json
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
ROOT = REPO / 'runs'
OUT = REPO / 'reports' / 'rcvr_ablation_preflight' / 'smoke_progress.json'
RUN_TAGS = {
    'b0_apde': 'b0_apde',
    'b1_rcvr': 'b1_rcvr_parsefix1',
    'b2_source_only': 'b2_source_only_parsefix1',
    'b3_unknown_stop': 'b3_unknown_stop_parsefix1',
    'b4_unknown_allow': 'b4_unknown_allow',
    'b5_generic_recovery': 'b4_generic_recovery_parsefix1',
}


def rate(rows, field):
    return None if not rows else round(100 * sum(bool(row.get(field)) for row in rows) / len(rows), 1)


def main():
    groups = collections.defaultdict(list)
    for path in ROOT.glob('gpt-4o-mini-2024-07-18-rcvr_smoke_*/*/user_task_*/*/*.json'):
        try:
            row = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError):
            continue
        if 'utility' not in row:
            continue
        name = path.parents[3].name.split('rcvr_smoke_', 1)[-1]
        groups[name].append(row)
    summary = {'method_name': 'RCVR', 'expected_per_arm': 12, 'arms': {}}
    for arm, run_tag in RUN_TAGS.items():
        rows = groups[run_tag]
        clean = [row for row in rows if row.get('injection_task_id') is None]
        attack = [row for row in rows if row.get('injection_task_id') is not None]
        summary['arms'][arm] = {
            'completed': len(rows), 'status': 'COMPLETE' if len(rows) == 12 else 'PARTIAL' if rows else 'NOT_STARTED',
            'clean_cases': len(clean), 'attack_cases': len(attack),
            'clean_utility_pct': rate(clean, 'utility'),
            'attack_utility_pct': rate(attack, 'utility'),
            'attack_success_rate_pct': rate(attack, 'security'),
        }
    OUT.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == '__main__':
    main()
