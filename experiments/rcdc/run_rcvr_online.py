"""Opt-in RCVR online worker with a dry-run default.

This runner is isolated from ``pipeline_main.py``.  It consumes one frozen
RCVR configuration and delegates the ordinary benchmark execution to the
existing pipeline only after an explicit command-line confirmation.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from utils import get_args, set_seed


PREFLIGHT = REPO / 'reports' / 'rcvr_ablation_preflight'
CONTRACTS_BY_PROFILE = {
    'agentdojo': REPO / 'contracts' / 'agentdojo_ifc_global_tool_contract_semantic_review_gpt55.json',
    'agentdyn': REPO / 'contracts' / 'agentdyn_ifc_global_tool_contract_semantic_review_v2_fixed.json',
}
EXPECTED = {
    'B0_APDE': ('off', 'full', False, True), 'B1_RCVR': ('full', 'full', True, True),
    'B2_WO_BINDING': ('full', 'full', False, True), 'B3_UNKNOWN_STOP': ('strict', 'full', True, True),
    'B4_UNKNOWN_ALLOW': ('allow', 'full', True, True),
    'B5_WO_EVIDENCE_ISOLATION': ('full', 'full', True, False),
}


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_config(config_id, preflight_root=PREFLIGHT):
    if config_id not in EXPECTED:
        raise ValueError('unknown_rcvr_config')
    path = Path(preflight_root) / 'configs' / f'{config_id}.json'
    if not path.is_file():
        raise ValueError('run_rcvr_ablation_prepare_first')
    config = json.loads(path.read_text(encoding='utf-8'))
    if config.get('method_name') != 'RCVR':
        raise ValueError('invalid_rcvr_config_method')
    if (config.get('rcvr_mode'), config.get('relation_mode'), config.get('enable_binding_verification'),
            config.get('enable_evidence_isolation')) != EXPECTED[config_id]:
        raise ValueError('rcvr_config_mapping_mismatch')
    manifest = REPO / Path(config['frozen_input_manifest'])
    if not manifest.is_file() or sha256(manifest) != config.get('frozen_input_manifest_sha256'):
        raise ValueError('frozen_input_manifest_changed')
    return config, manifest


def parse(argv=None):
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('command', choices=('dry-run', 'run'))
    parser.add_argument('--config-id', required=True, choices=tuple(EXPECTED))
    parser.add_argument('--confirm-online-execution', action='store_true')
    parser.add_argument(
        '--checkpoint-dir', type=Path, default=None,
        help='Opt-in private directory for pre-recovery UNKNOWN snapshots.',
    )
    parser.add_argument(
        '--preflight-root', type=Path, default=PREFLIGHT,
        help='Root containing the benchmark-specific frozen manifest and RCVR configs.',
    )
    known, remaining = parser.parse_known_args(argv)
    base_args = get_args(argv=remaining)
    return known, base_args


def contract_profile(base_args):
    profile = base_args.contract_profile
    if profile != 'auto':
        return profile
    suites = {item.strip().lower() for item in base_args.suites.split(',') if item.strip()}
    agentdyn_suites = {'shopping', 'github', 'dailylife'}
    return 'agentdyn' if suites and suites <= agentdyn_suites else 'agentdojo'


def load_contracts(base_args):
    profile = contract_profile(base_args)
    path = CONTRACTS_BY_PROFILE[profile]
    if not path.is_file():
        raise ValueError(f'contract_missing_for_profile:{profile}')
    contracts = json.loads(path.read_text(encoding='utf-8'))
    if contracts.get('benchmark') != profile or not contracts.get('contract_version'):
        raise ValueError(f'contract_profile_mismatch:{profile}')
    return profile, contracts


def normalized_task_ids(value, prefix):
    if value is None:
        return []
    return [item if item.startswith(prefix) else f'{prefix}{item}'
            for item in (part.strip() for part in value.split(',')) if item]


def validate_agentdyn_scope(config, manifest, base_args, profile):
    """Ensure an online pilot cannot diverge from its frozen target manifest."""
    if profile != 'agentdyn':
        return
    selection = manifest.get('selection', {})
    expected_suites = [selection.get('suite')]
    actual_suites = [item.strip() for item in base_args.suites.split(',') if item.strip()]
    if selection.get('mode') == 'all':
        if actual_suites != expected_suites or base_args.target_user_tasks is not None or base_args.target_injection_tasks is not None:
            raise ValueError('agentdyn_full_scope_differs_from_frozen_manifest')
        return
    actual_users = normalized_task_ids(base_args.target_user_tasks, 'user_task_')
    actual_injections = normalized_task_ids(base_args.target_injection_tasks, 'injection_task_')
    if (actual_suites != expected_suites
            or actual_users != selection.get('user_task_ids', [])
            or actual_injections != selection.get('injection_task_ids', [])):
        raise ValueError('agentdyn_target_scope_differs_from_frozen_manifest')


def dry_run(known, base_args):
    config, manifest_path = load_config(known.config_id, known.preflight_root)
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    profile, _ = load_contracts(base_args)
    if config.get('contract_profile', 'agentdojo') != profile:
        raise ValueError(f'config_contract_profile_mismatch:{profile}')
    validate_agentdyn_scope(config, manifest, base_args, profile)
    result = {
        'method_name': 'RCVR', 'online_started': False,
        'config_id': known.config_id, 'mode': config['rcvr_mode'],
        'relation_mode': config['relation_mode'], 'frozen_case_count': manifest['case_count'],
        'enable_binding_verification': config['enable_binding_verification'],
        'enable_evidence_isolation': config['enable_evidence_isolation'],
        'selected_suites': base_args.suites, 'selected_user_tasks': base_args.target_user_tasks,
        'selected_injection_tasks': base_args.target_injection_tasks,
        'contract_profile': profile,
        'b0_uses_stock_apde': known.config_id == 'B0_APDE',
        'active_arms_use_task_local_rcvr': known.config_id != 'B0_APDE',
    }
    print(json.dumps(result, ensure_ascii=False))


def run(known, base_args):
    if not known.confirm_online_execution:
        raise SystemExit('Refusing online execution: pass --confirm-online-execution after explicit review of the exact command.')
    config, manifest_path = load_config(known.config_id, known.preflight_root)
    if known.config_id == 'B0_APDE':
        import pipeline_main
        set_seed(base_args.seed)
        for suite in base_args.suites.split(','):
            pipeline_main.main(base_args, suite)
        return
    from rcdc.task_suite import RCVRTaskSuite
    profile, contracts = load_contracts(base_args)
    if config.get('contract_profile', 'agentdojo') != profile:
        raise ValueError(f'config_contract_profile_mismatch:{profile}')
    validate_agentdyn_scope(config, json.loads(manifest_path.read_text(encoding='utf-8')), base_args, profile)
    if config.get('contract_schema_hash') and config['contract_schema_hash'] != contracts.get('schema_hash'):
        raise ValueError('contract_schema_hash_changed')
    events_root = known.preflight_root / 'online_events' / base_args.run_tag
    RCVRTaskSuite.configure_rcvr(config, contracts, events_root,
                                  checkpoint_root=known.checkpoint_dir)
    import pipeline_main
    stock_suite = pipeline_main.DRIFTTaskSuite
    try:
        pipeline_main.DRIFTTaskSuite = RCVRTaskSuite
        set_seed(base_args.seed)
        for suite in base_args.suites.split(','):
            pipeline_main.main(base_args, suite)
    finally:
        pipeline_main.DRIFTTaskSuite = stock_suite
        RCVRTaskSuite.clear_rcvr_configuration()


if __name__ == '__main__':
    known, base_args = parse()
    {'dry-run': dry_run, 'run': run}[known.command](known, base_args)
