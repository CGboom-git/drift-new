"""Read-only summary for the 67-case B2/B5 validation batch."""
import collections
import json
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
ARMS = {
    'B2_w/o_Binding': 'gpt-4o-mini-2024-07-18-rcvr_core_ablation_b2_wo_binding_20260911',
    'B5_w/o_Evidence_Isolation': 'gpt-4o-mini-2024-07-18-rcvr_core_ablation_b5_wo_evidence_isolation_20260911',
}
EVENT_NAMES = (
    'binding_verification', 'binding_verification_disabled', 'provenance_source_tracking',
    'evidence_bounded_recovery_proposal', 'evidence_bounded_recovery_read_response',
    'evidence_isolation_applied', 'evidence_isolation_disabled', 'candidate_stopped',
)


def pct(value, denominator):
    return round(100 * value / denominator, 1) if denominator else None


def main():
    summary = {}
    for label, tag in ARMS.items():
        records = [json.loads(path.read_text(encoding='utf-8'))
                   for path in (REPO / 'runs' / tag).rglob('*.json')]
        clean = [record for record in records if record['injection_task_id'] is None]
        attack = [record for record in records if record['injection_task_id'] is not None]
        event_tag = 'rcvr_core_ablation_' + tag.split('-rcvr_core_ablation_', 1)[1]
        event_files = list((REPO / 'reports' / 'rcvr_ablation_preflight' / 'online_events' / event_tag).rglob('*.json'))
        events = [event for path in event_files
                  for event in json.loads(path.read_text(encoding='utf-8'))['events']]
        counts = collections.Counter(event['event'] for event in events)
        summary[label] = {
            'records': len(records), 'event_files': len(event_files),
            'clean_utility': {'successes': sum(bool(x['utility']) for x in clean), 'n': len(clean),
                              'percent': pct(sum(bool(x['utility']) for x in clean), len(clean))},
            'attack_utility': {'successes': sum(bool(x['utility']) for x in attack), 'n': len(attack),
                               'percent': pct(sum(bool(x['utility']) for x in attack), len(attack))},
            'attack_success': {'successes': sum(bool(x['security']) for x in attack), 'n': len(attack),
                               'percent': pct(sum(bool(x['security']) for x in attack), len(attack))},
            'overall_utility': {'successes': sum(bool(x['utility']) for x in records), 'n': len(records),
                                'percent': pct(sum(bool(x['utility']) for x in records), len(records))},
            'avg_tokens': round(sum(x['total_tokens'] for x in records) / len(records), 1),
            'avg_duration_seconds': round(sum(x['duration'] for x in records) / len(records), 1),
            'events': {name: counts[name] for name in EVENT_NAMES},
        }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
