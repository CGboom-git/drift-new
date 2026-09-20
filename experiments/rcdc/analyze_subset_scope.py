from collections import Counter
import json
from pathlib import Path

repo = Path(__file__).resolve().parents[2]
tag = 'rcvr_mechanism_subset15_20260920'
selection = json.loads((repo / 'experiments/rcdc/rcvr_mechanism_subset_15tasks_source.json').read_text())
root = repo / 'experiments/rcdc/subset15_preflight/online_events' / tag
rows = []
for task in selection['tasks']:
    suite, user = task['suite'], task['user_task_id']
    expected = [*task['attack_case_ids'], 'clean']
    cases = []
    counts = Counter()
    specs = Counter()
    for injection in expected:
        path = root / suite / user / f'{injection}.json'
        if not path.exists():
            cases.append({'injection': injection, 'missing_event_file': True})
            continue
        data = json.loads(path.read_text())
        events = data['events']
        types = Counter(e.get('event') for e in events)
        counts.update(types)
        spec_events = [e for e in events if e.get('event') == 'constraint_spec']
        specs.update(['present' if e.get('spec') is not None else 'none' for e in spec_events])
        initial = [e.get('decision', {}).get('verdict') for e in events if e.get('event') == 'binding_verification']
        cases.append({'injection': injection, 'spec': 'present' if any(e.get('spec') is not None for e in spec_events) else 'none',
                      'initial': initial, 'outside_scope': types['outside_verification_scope'],
                      'source_flow_repair_observations': sum(e.get('source_flow_repair') is True for e in events),
                      'checkpoint': types['unknown_checkpoint_frozen']})
    rows.append({'suite': suite, 'user': user, 'historical_repair_proxy_attack_cases': task['historical_recovery_proxy_cases'],
                 'attack_cases': task['attack_case_count'], 'cases': len(cases), 'spec_events': dict(specs),
                 'initial_verdicts': dict(Counter(v for c in cases for v in c.get('initial', []))),
                 'outside_scope_calls': counts['outside_verification_scope'],
                 'source_flow_repair_observations': sum(c.get('source_flow_repair_observations', 0) for c in cases),
                 'checkpoints': counts['unknown_checkpoint_frozen'],
                 'details': cases if user == 'user_task_4' and suite == 'banking' else None})
print(json.dumps(rows, ensure_ascii=False, indent=2))
