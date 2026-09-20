"""Reproducible RCVR scope audit for two Full B1 runs and the 144-case subset.

Reads benchmark results, RCVR event streams, and SourceFlow logs. It never
executes benchmark cases or resumes checkpoints.
"""
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from agentdojo.task_suite.load_suites import get_suite
from rcdc.constraint_spec import query_constraints


OUT = REPO / 'reports/rcvr_scope_coverage_audit_20260920'
SUBSET = json.loads((REPO / 'experiments/rcdc/rcvr_mechanism_subset15_run_manifest.json').read_text())
SELECTION = json.loads((REPO / 'experiments/rcdc/rcvr_mechanism_subset_15tasks_source.json').read_text())
RUNS = [
    ('full_mini_0911', 'pcvr_apde_full_b1_v12_t07_20260911', 'gpt-4o-mini-2024-07-18',
     REPO / 'reports/rcvr_ablation_preflight/online_events', 1046),
    ('full_gpt4o_0919', 'pcvr_apde_full_b1_gpt4o_t07_20260919', 'gpt-4o',
     REPO / 'reports/rcvr_ablation_preflight/online_events', 1046),
    ('subset_mini_0920', 'rcvr_mechanism_subset15_20260920', 'gpt-4o-mini-2024-07-18',
     REPO / 'experiments/rcdc/subset15_preflight/online_events', 144),
]


def key(row):
    return row['suite_name'], row['user_task_id'], row['injection_task_id']


subset_keys = {key(row) for row in SUBSET['cases']}
assert len(subset_keys) == SUBSET['case_count'] == 144
full_keys = set()
static_tasks = []
static_case_keys = set()
for suite_name in ('banking', 'slack', 'travel', 'workspace'):
    suite = get_suite('v1.2', suite_name)
    for user, task in suite.user_tasks.items():
        full_keys.add((suite_name, user, None))
        for injection in suite.injection_tasks:
            full_keys.add((suite_name, user, injection))
        extracted = query_constraints(task.PROMPT)
        if extracted is not None:
            static_tasks.append({'suite': suite_name, 'user_task_id': user,
                                 'family': extracted[-1], 'cases': len(suite.injection_tasks) + 1})
            static_case_keys.add((suite_name, user, None))
            static_case_keys.update((suite_name, user, injection) for injection in suite.injection_tasks)
assert len(full_keys) == 1046 and subset_keys <= full_keys
assert len(static_tasks) == 6 and len(static_case_keys) == 67


def read_case(run_root, event_root, case_key):
    suite, user, injection = case_key
    attack = 'important_instructions' if injection is not None else 'none'
    result_path = run_root / suite / user / attack / f'{injection or "none"}.json'
    event_path = event_root / suite / user / f'{injection or "clean"}.json'
    errors = []
    if not result_path.exists():
        errors.append(f'missing_result:{result_path.relative_to(REPO)}')
        return {'key': case_key, 'errors': errors}
    if not event_path.exists():
        errors.append(f'missing_event:{event_path.relative_to(REPO)}')
        return {'key': case_key, 'errors': errors}
    result = json.loads(result_path.read_text())
    event_data = json.loads(event_path.read_text())
    events = event_data.get('events', [])
    conversations = result.get('conversations') or []
    api_error_messages = [m for m in conversations if isinstance(m, dict)
                          and m.get('role') == 'assistant'
                          and 'API_ERROR' in str(m.get('content', ''))]
    assistant_messages = [m for m in conversations if isinstance(m, dict) and m.get('role') == 'assistant']
    if not isinstance(events, list):
        errors.append('invalid_events_type')
        events = []
    expected_injection = injection if injection is not None else 'clean'
    if (result.get('suite_name'), result.get('user_task_id'), result.get('injection_task_id')) != (suite, user, injection):
        # Stock clean results may represent a missing injection as the string "None".
        if not (injection is None and str(result.get('injection_task_id')).lower() in ('none', 'null')
                and result.get('suite_name') == suite and result.get('user_task_id') == user):
            errors.append('result_identity_mismatch')
    if event_data.get('task_id') != user or event_data.get('injection_task_id') != expected_injection:
        errors.append('event_identity_mismatch')
    expected_flags = {'method_name': 'RCVR', 'config_id': 'B1_RCVR', 'rcvr_mode': 'full',
                      'relation_mode': 'full', 'enable_binding_verification': True,
                      'enable_evidence_isolation': True}
    for field, value in expected_flags.items():
        if event_data.get(field) != value:
            errors.append(f'event_config_mismatch:{field}')
    if 'utility' not in result or 'security' not in result:
        errors.append('result_not_scoreable')
    spec_events = [e for e in events if e.get('event') == 'constraint_spec']
    binding = [e for e in events if e.get('event') == 'binding_verification']
    verdicts = [e.get('decision', {}).get('verdict') for e in binding]
    if any(v not in ('VALID', 'INVALID', 'UNKNOWN') for v in verdicts):
        errors.append('invalid_binding_verdict')
    event_counts = Counter(e.get('event') for e in events)
    source_flow_path = result.get('source_flow_log_path')
    source_flow_repair_events = None
    if source_flow_path:
        source_flow_file = Path(source_flow_path)
        if not source_flow_file.is_absolute():
            source_flow_file = REPO / source_flow_file
        if source_flow_file.exists():
            source_flow = json.loads(source_flow_file.read_text())
            source_flow_repair_events = sum(trace.get('decision') == 'repair_required'
                                            for trace in source_flow.get('validation_trace', []))
        else:
            errors.append('missing_source_flow_log')
    else:
        errors.append('source_flow_path_absent')
    return {
        'key': case_key, 'errors': errors,
        'model': result.get('pipeline_name'), 'temperature_metadata': result.get('temperature'),
        'benchmark_version': result.get('benchmark_version'),
        'api_error_case': bool(api_error_messages),
        'api_error_messages': len(api_error_messages),
        'first_assistant_api_error': bool(assistant_messages and
                                          'API_ERROR' in str(assistant_messages[0].get('content', ''))),
        'event_count': len(events), 'spec_event_count': len(spec_events),
        'spec_present': any(e.get('spec') is not None for e in spec_events),
        'spec_none': any(e.get('spec') is None for e in spec_events),
        'binding_verdicts': verdicts, 'outside_scope_calls': event_counts['outside_verification_scope'],
        'checkpoint_events': event_counts['unknown_checkpoint_frozen'],
        'checkpoint_unsupported': event_counts['unknown_checkpoint_unsupported'],
        'recovery_proposals': event_counts['evidence_bounded_recovery_proposal'],
        'recovery_read_responses': event_counts['evidence_bounded_recovery_read_response'],
        'binding_reverifications': event_counts['binding_reverification'],
        'candidate_stops': event_counts['candidate_stopped'],
        'source_flow_repair_events': source_flow_repair_events,
    }


def summarize(rows):
    good = [row for row in rows if 'event_count' in row]
    counts = Counter()
    verdict_events = Counter()
    by_suite = defaultdict(Counter)
    for row in good:
        suite = row['key'][0]
        for bucket in (counts, by_suite[suite]):
            bucket['cases'] += 1
            bucket['api_error_cases'] += row['api_error_case']
            bucket['api_error_messages'] += row['api_error_messages']
            bucket['first_assistant_api_error_cases'] += row['first_assistant_api_error']
            bucket['valid_without_api_error'] += not row['api_error_case']
            bucket['spec_cases'] += row['spec_present']
            bucket['spec_cases_without_api_error'] += row['spec_present'] and not row['api_error_case']
            bucket['spec_none_cases'] += row['spec_none'] and not row['spec_present']
            bucket['no_spec_event_cases'] += row['spec_event_count'] == 0
            bucket['binding_cases'] += bool(row['binding_verdicts'])
            bucket['binding_cases_without_api_error'] += bool(row['binding_verdicts']) and not row['api_error_case']
            bucket['unknown_cases'] += 'UNKNOWN' in row['binding_verdicts']
            bucket['invalid_cases'] += 'INVALID' in row['binding_verdicts']
            bucket['valid_cases'] += 'VALID' in row['binding_verdicts']
            bucket['outside_scope_cases'] += row['outside_scope_calls'] > 0
            bucket['outside_scope_calls'] += row['outside_scope_calls']
            bucket['binding_events'] += len(row['binding_verdicts'])
            bucket['checkpoint_events'] += row['checkpoint_events']
            bucket['checkpoint_unsupported'] += row['checkpoint_unsupported']
            bucket['recovery_proposals'] += row['recovery_proposals']
            bucket['recovery_read_responses'] += row['recovery_read_responses']
            bucket['binding_reverifications'] += row['binding_reverifications']
            bucket['candidate_stops'] += row['candidate_stops']
            bucket['source_flow_repair_cases'] += bool(row['source_flow_repair_events'])
            bucket['source_flow_repair_events'] += row['source_flow_repair_events'] or 0
            bucket['missing_source_flow_logs'] += row['source_flow_repair_events'] is None
        verdict_events.update(row['binding_verdicts'])
    counts['missing_result_or_event'] = len(rows) - len(good)
    counts['cases_with_errors'] = sum(bool(row['errors']) for row in rows)
    counts['attack_cases'] = sum(row['key'][2] is not None for row in good)
    counts['clean_cases'] = sum(row['key'][2] is None for row in good)
    counts['static_eligible_cases'] = sum(tuple(row['key']) in static_case_keys for row in good)
    counts['static_eligible_with_api_error'] = sum(tuple(row['key']) in static_case_keys and row['api_error_case'] for row in good)
    counts['static_eligible_without_api_error'] = sum(tuple(row['key']) in static_case_keys and not row['api_error_case'] for row in good)
    counts['static_eligible_spec_cases'] = sum(tuple(row['key']) in static_case_keys and row['spec_present'] for row in good)
    counts['static_eligible_binding_cases'] = sum(tuple(row['key']) in static_case_keys and bool(row['binding_verdicts']) for row in good)
    counts['static_ineligible_spec_cases'] = sum(tuple(row['key']) not in static_case_keys and row['spec_present'] for row in good)
    return {'counts': dict(counts), 'verdict_events': dict(verdict_events),
            'by_suite': {k: dict(v) for k, v in sorted(by_suite.items())}}


def display_table(headers, rows):
    def safe(value):
        return str(value).replace('|', '\\|')
    return ['| ' + ' | '.join(map(safe, headers)) + ' |',
            '| ' + ' | '.join(['---'] * len(headers)) + ' |',
            *['| ' + ' | '.join(map(safe, row)) + ' |' for row in rows]]


def run():
    OUT.mkdir(parents=True, exist_ok=True)
    data = {'generated_at_utc': datetime.now(timezone.utc).isoformat(),
            'case_key': ['suite', 'user_task_id', 'injection_task_id_or_null'],
            'static_compiler_scope': static_tasks,
            'subset_manifest_sha256': hashlib.sha256((REPO / 'experiments/rcdc/rcvr_mechanism_subset15_run_manifest.json').read_bytes()).hexdigest(),
            'runs': {}, 'selected_task_comparison': [], 'subset_repair_unknown_cross_tab': {}}
    for label, tag, model, events_base, expected_count in RUNS:
        expected = subset_keys if expected_count == 144 else full_keys
        run_root = REPO / 'runs' / f'{model}-{tag}'
        event_root = events_base / tag
        rows = [read_case(run_root, event_root, case_key) for case_key in sorted(expected, key=str)]
        event_files = list(event_root.glob('*/*/*.json'))
        result_files = [p for p in run_root.glob('*/user_task_*/*/*.json')
                        if p.parent.name in ('none', 'important_instructions') and not p.name.endswith('.failed.json')]
        event_keys = {(p.parts[-3], p.parts[-2], None if p.stem == 'clean' else p.stem)
                      for p in event_files}
        result_keys = {(p.parts[-4], p.parts[-3], None if p.stem == 'none' else p.stem)
                       for p in result_files}
        summary = summarize(rows)
        summary.update({'tag': tag, 'model': model, 'expected_cases': len(expected),
                        'event_file_count': len(event_files), 'result_file_count': len(result_files),
                        'unexpected_event_keys': sorted(event_keys - expected, key=str),
                        'missing_event_keys': sorted(expected - event_keys, key=str),
                        'unexpected_result_keys': sorted(result_keys - expected, key=str),
                        'missing_result_keys': sorted(expected - result_keys, key=str),
                        'models_in_results': dict(Counter(row['model'] for row in rows if 'model' in row)),
                        'temperatures_in_results': dict(Counter(str(row['temperature_metadata']) for row in rows if 'temperature_metadata' in row)),
                        'benchmark_versions': dict(Counter(row['benchmark_version'] for row in rows if 'benchmark_version' in row)),
                        'case_errors': [{'key': row['key'], 'errors': row['errors']} for row in rows if row['errors']]})
        data['runs'][label] = {'summary': summary, 'cases': rows}
        print(label, summary['counts'], summary['verdict_events'], flush=True)

    for task in SELECTION['tasks']:
        suite, user = task['suite'], task['user_task_id']
        comparison = {'suite': suite, 'user_task_id': user,
                      'historical_repair_proxy_attack_cases': task['historical_recovery_proxy_cases'],
                      'attack_cases': task['attack_case_count'], 'runs': {}}
        for label, *_ in RUNS:
            rows = [r for r in data['runs'][label]['cases'] if r['key'][:2] == (suite, user)]
            comparison['runs'][label] = summarize(rows)['counts']
        data['selected_task_comparison'].append(comparison)

    current = data['runs']['subset_mini_0920']['cases']
    cross = Counter()
    for row in current:
        if 'event_count' not in row:
            continue
        cross[('attack' if row['key'][2] else 'clean', bool(row['source_flow_repair_events']),
               'UNKNOWN' in row['binding_verdicts'])] += 1
    data['subset_repair_unknown_cross_tab'] = {'/'.join(map(str, k)): v for k, v in sorted(cross.items(), key=str)}

    checkpoint_dir = REPO / 'reports/rcvr_mechanism_subset15_20260920/checkpoints/rcvr_mechanism_subset15_20260920'
    checkpoint_files = list(checkpoint_dir.rglob('*.pkl'))
    checkpoint_errors = []
    for path in checkpoint_files:
        sidecar = path.with_suffix('.json')
        if not sidecar.exists():
            checkpoint_errors.append(f'missing_sidecar:{path.relative_to(REPO)}')
            continue
        payload = json.loads(sidecar.read_text())
        if hashlib.sha256(path.read_bytes()).hexdigest() != payload.get('sha256'):
            checkpoint_errors.append(f'hash_mismatch:{path.relative_to(REPO)}')
    data['checkpoint_integrity'] = {'files': len(checkpoint_files), 'errors': checkpoint_errors}
    recorded_paths = set()
    # Event paths are relative to the repo in this run. Compare them against
    # physical checkpoint files as well as checking the sidecar hashes.
    for case_key in subset_keys:
        suite, user, injection = case_key
        event_file = (REPO / 'experiments/rcdc/subset15_preflight/online_events/rcvr_mechanism_subset15_20260920'
                      / suite / user / f'{injection or "clean"}.json')
        for event in json.loads(event_file.read_text())['events']:
            if event.get('event') == 'unknown_checkpoint_frozen':
                recorded_paths.add(Path(event['path']))
    actual_paths = {p.relative_to(REPO) for p in checkpoint_files}
    data['checkpoint_integrity']['event_path_mismatch'] = {
        'event_without_file': sorted(map(str, recorded_paths - actual_paths)),
        'file_without_event': sorted(map(str, actual_paths - recorded_paths)),
    }

    (OUT / 'audit.json').write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    write_report(data)


def write_report(data):
    lines = ['# RCVR scope coverage audit', '',
             'Runs audited: two Full B1 AgentDojo v1.2 runs (2026-09-11 and 2026-09-19) and the exact 144-case subset (2026-09-20).',
             'This is a scope and event audit, not a causal comparison across model versions or independently sampled trajectories.', '',
             '## Input and completeness', '',
             'A case is one `(suite, user_task_id, injection_task_id)` tuple; `null` injection is clean. ',
             'The Full universe is constructed from the installed AgentDojo v1.2 suites: all user tasks crossed with all injection tasks, plus one clean case per user task. ',
             'The subset comes from the frozen 144-case manifest. Only top-level result JSONs and per-case RCVR event JSONs are counted.', '']
    rows = []
    for label, *_ in RUNS:
        s = data['runs'][label]['summary']
        rows.append([label, s['model'], s['expected_cases'], s['result_file_count'], s['event_file_count'],
                     s['counts']['cases_with_errors'], s['temperatures_in_results']])
    lines += display_table(['Run', 'Model', 'Expected', 'Results', 'Event files', 'Structural errors', 'Stored temperature'], rows)
    lines += ['', 'The launch scripts specify temperature 0.7 for both historical runs; the 2026-09-11 result JSONs store `temperature: null`, so the audit preserves this metadata discrepancy. ',
              'The 2026-09-19 Full run uses `gpt-4o`; the other two use `gpt-4o-mini-2024-07-18`.', '',
              '### API_ERROR contamination', '',
              'A result file and event file can exist even when an assistant message says `API_ERROR: Generation failed.`. ',
              'These cases are file-complete but should not be treated as successful model executions. ',
              'The audit counts any such assistant message, including errors after earlier tool calls.', '']
    rows = []
    for label, *_ in RUNS:
        c = data['runs'][label]['summary']['counts']
        rows.append([label, c['cases'], c['api_error_cases'], c['first_assistant_api_error_cases'],
                     c['valid_without_api_error'], c['spec_cases_without_api_error'],
                     c['binding_cases_without_api_error'], c['no_spec_event_cases']])
    lines += display_table(['Run', 'Files', 'API_ERROR cases', 'Error on first assistant reply',
                            'No API_ERROR', 'Spec among no-error', 'Binding among no-error',
                            'No spec event'], rows)
    lines += ['', 'The GPT-4o Full run has extensive API_ERROR contamination, so its low observed gate activity is partly censored by failed generations. ',
              'It should not be used as a clean coverage-rate comparator against the two GPT-4o-mini runs.', '']
    lines += ['## Static compiler scope', '',
              '`query_constraints` recognizes six exact user prompts in the installed AgentDojo v1.2 benchmark, spanning 67 potential cases out of 1046. ',
              'This is a ceiling for RCVR binding evaluation before model behavior is considered. The other 91 user tasks cannot produce an RCVR binding verdict under the current compiler.', '']
    rows = [[r['suite'], r['user_task_id'], r['family'], r['cases']] for r in data['static_compiler_scope']]
    lines += display_table(['Suite', 'Task', 'Rule family', 'Potential cases'], rows)
    lines += ['', '### Static-to-dynamic funnel', '']
    rows = []
    for label, *_ in RUNS:
        c = data['runs'][label]['summary']['counts']
        rows.append([label, c['static_eligible_cases'], c['static_eligible_with_api_error'],
                     c['static_eligible_without_api_error'], c['static_eligible_spec_cases'],
                     c['static_eligible_binding_cases'], c['static_ineligible_spec_cases']])
    lines += display_table(['Run', 'Statically eligible', 'Eligible with API_ERROR', 'Eligible without API_ERROR',
                            'Spec observed', 'Binding observed', 'Spec outside static scope'], rows)
    lines += ['', 'In the GPT-4o Full run, 37 of 67 statically eligible cases have an API_ERROR and no specification event; the other two API-error cases had already produced a specification. ',
              'All 28 eligible cases without API_ERROR produced a specification.', '']
    lines += ['## Scope funnel (case level)', '',
              '`spec` means at least one non-null `constraint_spec` event; `binding` means at least one `binding_verification` event. ',
              'A case may have both binding and outside-scope calls. UNKNOWN, INVALID, and VALID are initial binding verdicts and may overlap within a case with multiple candidates.', '']
    rows = []
    for label, *_ in RUNS:
        c = data['runs'][label]['summary']['counts']
        rows.append([label, c['cases'], c['spec_cases'], c['binding_cases'], c['unknown_cases'],
                     c['invalid_cases'], c['valid_cases'], c['source_flow_repair_cases'],
                     c['outside_scope_cases'], c['checkpoint_events']])
    lines += display_table(['Run', 'Cases', 'Spec', 'Binding', 'UNKNOWN', 'INVALID', 'VALID',
                            'SourceFlow repair', 'Outside scope', 'Checkpoint events'], rows)
    lines += ['', '### Event-level counts', '']
    rows = []
    for label, *_ in RUNS:
        s = data['runs'][label]['summary']
        c = s['counts']; v = s['verdict_events']
        rows.append([label, c['binding_events'], v.get('UNKNOWN', 0), v.get('INVALID', 0), v.get('VALID', 0),
                     c['outside_scope_calls'], c['recovery_proposals'], c['recovery_read_responses'],
                     c['binding_reverifications'], c['candidate_stops'], c['checkpoint_unsupported']])
    lines += display_table(['Run', 'Binding events', 'UNKNOWN', 'INVALID', 'VALID', 'Outside calls',
                            'Recovery proposals', 'Recovery reads', 'Reverifications', 'Stops', 'Unsupported checkpoints'], rows)
    lines += ['', '## Current subset: 15 selected tasks on the same case keys', '',
              'Cells are `spec / binding / UNKNOWN` case counts. Historical selection used SourceFlow `repair_required` as a proxy; the last column is its manifest count among attacked cases.', '']
    rows = []
    for task in data['selected_task_comparison']:
        cells = []
        for label, *_ in RUNS:
            c = task['runs'][label]
            cells.append(f"{c['spec_cases']}/{c['binding_cases']}/{c['unknown_cases']}")
        rows.append([task['suite'], task['user_task_id'], task['attack_cases'] + 1,
                     *cells, task['runs']['full_gpt4o_0919']['api_error_cases'],
                     task['historical_repair_proxy_attack_cases']])
    lines += display_table(['Suite', 'Task', 'Cases', 'Full mini 09-11', 'Full GPT-4o 09-19',
                            'Subset mini 09-20', 'GPT-4o API_ERROR cases', 'Historical repair proxy'], rows)
    lines += ['', '### Same 129 attacked case keys', '']
    rows = []
    for label, *_ in RUNS:
        selected = [r for r in data['runs'][label]['cases']
                    if tuple(r['key']) in subset_keys and r['key'][2] is not None]
        rows.append([label, len(selected), sum(r['api_error_case'] for r in selected),
                     sum(bool(r['source_flow_repair_events']) for r in selected),
                     sum('UNKNOWN' in r['binding_verdicts'] for r in selected)])
    lines += display_table(['Run', 'Attacked cases', 'API_ERROR', 'SourceFlow repair', 'RCVR UNKNOWN'], rows)
    lines += ['', 'The manifest historical proxy count of 74/129 reproduces exactly from the 2026-09-11 Full B1 SourceFlow logs. ',
              'It does not represent 74 RCVR UNKNOWN cases.', '']
    lines += ['', '## SourceFlow proxy versus RCVR UNKNOWN in the current subset', '',
              'SourceFlow repair means at least one `validation_trace` entry with `decision=repair_required`. ',
              'RCVR UNKNOWN means at least one initial `binding_verification` with `verdict=UNKNOWN`. ',
              'These are different detectors with different scopes.', '']
    rows = [[k, v] for k, v in data['subset_repair_unknown_cross_tab'].items()]
    lines += display_table(['attack-or-clean / SourceFlow repair / RCVR UNKNOWN', 'Cases'], rows)
    lines += ['', '## Interpretation', '',
              '1. The 15-task selection was made from historical SourceFlow repair frequency, not observed RCVR UNKNOWN frequency. Its own manifest explicitly calls this a proxy.',
              '2. The trusted-query compiler recognizes only `banking/user_task_4` among these 15 selected prompts. For the other 14 tasks, `compile_spec` returns `None`; `Gate.candidate` emits `outside_verification_scope` and passes through. This is structural coverage, not an occasional sampling miss.',
              '3. The current subset produced 7 initial UNKNOWN verdicts and 7 checkpoints, all on `banking/user_task_4`. All seven checkpoint files have matching SHA-256 sidecars; no unsupported checkpoint event was observed.',
              '4. The 2026-09-19 GPT-4o run has many scoreable JSON files containing assistant `API_ERROR`. Its gate counts are censored and are not a clean replication. The runs also differ in model and/or sampled trajectories. Changes in UNKNOWN counts are descriptive, not a causal estimate of RCVR behavior.',
              '5. A 15-task mechanism analysis requires trusted constraints and source bindings for the other task families, followed by a new instrumented run; existing out-of-scope trajectories cannot be retroactively forked at an RCVR UNKNOWN.', '',
              '## Artifact checks', '',
              f"- Frozen subset manifest SHA-256: `{data['subset_manifest_sha256']}`",
              f"- Checkpoint files: {data['checkpoint_integrity']['files']}; integrity errors: {len(data['checkpoint_integrity']['errors'])}; event/file path discrepancies: {sum(len(v) for v in data['checkpoint_integrity']['event_path_mismatch'].values())}.",
              '- Machine-readable per-case rows and completeness errors: `audit.json`.',
              '- Code: `experiments/rcdc/audit_scope_coverage.py`.', '']
    (OUT / 'report.md').write_text('\n'.join(lines) + '\n')


if __name__ == '__main__':
    run()
