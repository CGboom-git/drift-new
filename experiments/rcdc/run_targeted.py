"""Prepare a fixed inventory and verify launch gates without changing legacy Full."""
import argparse
import collections
import hashlib
import inspect
import json
from pathlib import Path
import subprocess
import sys
from rcdc import add_arguments, VERSION
from rcdc.constraint_spec import query_constraints

REPO = Path(__file__).resolve().parents[2]
ROOT = Path(__file__).resolve().parent
REPORT = REPO / 'reports/rcdc_targeted'
TASKS = [('banking','user_task_4'), ('workspace','user_task_8'), ('workspace','user_task_9'),
         ('workspace','user_task_35'), ('slack','user_task_7'), ('slack','user_task_12')]
MODEL = 'gpt-4o-mini-2024-07-18'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')


def core_files():
    paths = [REPO / x for x in ['DRIFTLLM.py','DRIFTTaskSuite.py','DRIFTToolsExecutionLoop.py',
                              'client.py','pipeline_main.py','utils.py','prompts.py','runtime_drift_trace.py']]
    for folder in ['taer','source_flow','contracts']:
        paths.extend(p for p in (REPO/folder).iterdir() if p.suffix in ('.py','.json','.md'))
    return sorted(paths)


def prepare():
    from agentdojo.task_suite.load_suites import get_suite
    from agentdojo.attacks.attack_registry import load_attack
    from types import SimpleNamespace
    path = ROOT/'targeted_manifest.json'
    if path.exists():
        raise ValueError('manifest already exists; never overwrite or outcome-select')
    attack_run = list((REPO/'runs').glob('*full_attack_gpt4omini_runtime_trace_retry1_20260823'))
    clean_run = list((REPO/'runs').glob('*full_no_attack_gpt4omini_runtime_trace_retry1_20260824'))
    if len(attack_run) != 1 or len(clean_run) != 1:
        raise ValueError('ambiguous historical input directories')
    cases = []; issues = []
    for suite_name, task_id in TASKS:
        suite = get_suite('v1.2', suite_name); task = suite.get_user_task_by_id(task_id)
        rule = query_constraints(task.PROMPT)
        if rule is None:
            raise ValueError('unsupported task grammar')
        attack = load_attack('important_instructions', suite, SimpleNamespace(name='gpt-4o-2024-05-13'))
        inputs = [clean_run[0]/suite_name/task_id/'none/none.json']
        inputs += sorted((attack_run[0]/suite_name/task_id/'important_instructions').glob('injection_task_*.json'),
                         key=lambda p: int(p.stem.rsplit('_',1)[1]))
        for original in inputs:
            sf = original.parent/'source_flow'/(original.stem+'.source_flow.json')
            rt = original.parent/'runtime_drift_trace'/(original.stem+'.runtime_drift.json')
            if not all(p.is_file() for p in [original,sf,rt]):
                issues.append({'path':str(original),'reason':'incomplete_historical_logs'}); continue
            injection_id = None if original.stem == 'none' else original.stem
            payload = attack.attack(task, suite.get_injection_task_by_id(injection_id)) if injection_id else {}
            case_id = f'{suite_name}__{task_id}__{injection_id or "clean"}'
            pp = ROOT/'payloads'/(case_id+'.json');dump(pp,payload)
            cases.append({'case_id':case_id,'suite':suite_name,'task_id':task_id,'injection_task_id':injection_id,
                          'family':rule[3],'task_prompt':task.PROMPT,'attack':injection_id is not None,
                          'historical_files':{str(p.relative_to(REPO)):sha(p) for p in [original,sf,rt]},
                          'payload_file':str(pp.relative_to(REPO)),'payload_sha256':sha(pp),
                          'historical_payload_identity':'UNVERIFIED_TEMPLATE_RECONSTRUCTION',
                          'scenario_categories':[], 'category_assignment':'NOT_INFERRED_FROM_OUTCOMES'})
    smoke = []
    for suite_name, task_id in TASKS:
        subset = [c for c in cases if c['suite']==suite_name and c['task_id']==task_id]
        smoke += [c['case_id'] for c in subset[:2]]
    manifest = {'version':VERSION,'state':'FROZEN_NATURAL_CASE_INVENTORY_NOT_COMPLETE_SCENARIO_MANIFEST',
        'selection':'all complete-log clean/attack cases for six grammar-supported tasks; no utility/security selection',
        'model':MODEL,'benchmark':'v1.2','cases':cases,'smoke_case_ids':smoke,'issues':issues,
        'case_count':len(cases),'distinct_user_tasks':len(TASKS),
        'families':dict(collections.Counter(c['family'] for c in cases)),
        'required_scenario_coverage':{'A':'not yet certified','B':'not yet certified','C':'requires explicit recovery attack fixtures',
                                      'D':'requires evidence-refresh fixtures','E':'requires spoof fixtures','F':'requires unresolved fixtures'},
        'unit_tests_are_not_independent_online_cases':True,
        'freeze_rule':'do not add category labels or change selection after seeing online outcomes',
        'original_full_hashes':{str(p.relative_to(REPO)):sha(p) for p in core_files()},
        'git_head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip(),
        'git_status':subprocess.check_output(['git','status','--short'],cwd=REPO,text=True),
        'api_env':'/data/home/qyc/.config/drift/openai.env','proxy':'http://127.0.0.1:17890',
        'launch_blockers':['baseline_tests_not_all_passing','scenario_categories_not_certified','integration_protocol_review_pending']}
    dump(path,manifest)
    for name, mode, apde in [('C0','off',False),('C1','off',True),('C2','strict',True),('C3','retry',True),('C4','full',True),('shadow','shadow',True)]:
        dump(ROOT/'configs'/(name+'.json'),{'config':name,'rcdc_mode':mode,'model':MODEL,'apde':apde,
            'recovery_steps':2,'recovery_proposal_token_limit':512,'recovery_model_calls_cap':2,'recovery_read_calls_cap':2,
            'recovery_style':'generic_read_replanning' if mode=='retry' else 'condition_scoped_read_replanning' if mode=='full' else None,
            'additional_apde_validation_model_calls':'must be instrumented and included; pending protocol review',
            'original_drift_definition':'build_constraints+injection_isolation+dynamic_validation; taer off and source_flow_validation off' if name=='C0' else None})
    dump(REPORT/'preflight_inventory.json',{'cases':len(cases),'smoke_cases':len(smoke),'families':manifest['families'],
        'core_hashes':manifest['original_full_hashes'],'excluded_incomplete_audit':'audit_binding_witness/',
        'trusted_previous_audits':['authorization_audit_20260908/output_v1_1','authorization_audit_20260908/stage2/output_v2',
                                  'authorization_audit_20260908/host_feedback_pilot_20260909']})
    print(json.dumps({'cases':len(cases),'smoke_cases':len(smoke),'online_started':False}))


def test():
    REPORT.mkdir(parents=True,exist_ok=True)
    suites = [('legacy_tests', ['-m','pytest','tests','-q','-p','no:cacheprovider','--tb=short']),
              ('rcdc_unit_tests', ['-m','unittest','rcdc.tests.test_mechanism','-v']),
              ('rcdc_integration_tests', ['-m','unittest','rcdc.tests.test_integration','-v'])]
    results = {}
    for name, args in suites:
        result = subprocess.run([sys.executable,'-B',*args],cwd=REPO,capture_output=True,text=True,timeout=120)
        (REPORT/(name+'.txt')).write_text(result.stdout+result.stderr)
        results[name]={'returncode':result.returncode,'log':name+'.txt'}
    plan=json.loads((ROOT/'targeted_manifest.json').read_text())
    results['original_files_unchanged']=all(sha(REPO/p)==h for p,h in plan['original_full_hashes'].items())
    results['historical_inputs_unchanged']=all(sha(REPO/p)==h for c in plan['cases'] for p,h in c['historical_files'].items())
    results['online_launch_allowed']=False
    dump(REPORT/'preflight_tests.json',results)
    print(json.dumps(results))


def launch():
    raise SystemExit('Online launch blocked: legacy tests fail and A-F scenario/protocol certification is incomplete. No API request issued.')


if __name__ == '__main__':
    p=add_arguments(argparse.ArgumentParser());p.add_argument('command',choices=['prepare','test','launch'])
    a=p.parse_args()
    {'prepare':prepare,'test':test,'launch':launch}[a.command]()
