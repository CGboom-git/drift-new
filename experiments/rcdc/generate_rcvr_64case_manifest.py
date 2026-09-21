"""Create the user-specified four-suite 64-case RCVR pilot manifest."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'experiments/rcdc/rcvr_structural_64case_manifest.json'
SUITES = ('banking', 'workspace', 'slack', 'travel')
TASKS = tuple(f'user_task_{i}' for i in range(8))
ATTACKS = tuple(f'injection_task_{i}' for i in range(2))

cases = [
    {'suite_name': suite, 'attack_type': 'important_instructions',
     'user_task_id': task, 'injection_task_id': attack}
    for suite in SUITES for task in TASKS for attack in ATTACKS
]
manifest = {
    'purpose': 'Structural BindingIR RCVR pilot; user-specified stratified scope',
    'selection': {'suites': list(SUITES), 'user_task_ids': list(TASKS),
                  'injection_task_ids': list(ATTACKS), 'attack_type': 'important_instructions'},
    'task_count': len(SUITES) * len(TASKS), 'attack_cases_per_task': len(ATTACKS),
    'case_count': len(cases), 'cases': cases,
}
OUT.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'path': str(OUT), 'case_count': len(cases),
                  'sha256': hashlib.sha256(OUT.read_bytes()).hexdigest()}))
