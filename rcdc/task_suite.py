"""Task-local RCVR wrapper for the untouched AgentDojo task suite.

The stock pipeline creates one executor before it knows which user task is
running.  RCVR constraints, evidence ledgers, and recovery budgets are instead
task-local.  This wrapper creates the experimental loop inside
``run_task_with_pipeline`` and leaves the stock suite and pipeline untouched.
"""
import json
import copy
from pathlib import Path

from DRIFTTaskSuite import DRIFTTaskSuite
from agentdojo.agent_pipeline import AgentPipeline, InitQuery
from .integration import components
from .task_planner import freeze_from_secure_plan
from .binding_ir import from_anchor


class RCVRTaskSuite(DRIFTTaskSuite):
    """An opt-in suite used only by ``experiments/rcdc/run_rcvr_online.py``."""

    _rcvr_config = None
    _rcvr_contracts = None
    _rcvr_events_root = None
    _rcvr_checkpoint_root = None

    @classmethod
    def configure_rcvr(cls, config, contracts, events_root, checkpoint_root=None):
        if config.get('method_name') != 'RCVR':
            raise ValueError('rcvr_config_method_name_required')
        if config.get('rcvr_mode') not in ('full', 'strict', 'allow', 'retry', 'shadow'):
            raise ValueError('rcvr_task_suite_requires_active_mode')
        if config.get('relation_mode') not in ('full', 'source_only'):
            raise ValueError('invalid_relation_mode')
        if not isinstance(config.get('enable_binding_verification'), bool):
            raise ValueError('invalid_binding_verification_flag')
        if not isinstance(config.get('enable_evidence_isolation'), bool):
            raise ValueError('invalid_evidence_isolation_flag')
        if config.get('constraint_source', 'task_anchor_v1') not in ('task_anchor_v1', 'legacy_regex_v1'):
            raise ValueError('invalid_constraint_source')
        cls._rcvr_config = dict(config)
        cls._rcvr_contracts = dict(contracts)
        cls._rcvr_events_root = Path(events_root)
        cls._rcvr_checkpoint_root = Path(checkpoint_root) if checkpoint_root else None

    @classmethod
    def clear_rcvr_configuration(cls):
        cls._rcvr_config = cls._rcvr_contracts = cls._rcvr_events_root = cls._rcvr_checkpoint_root = None

    def run_task_with_pipeline(self, agent_pipeline, user_task, injection_task,
                               injections, *args, **kwargs):
        config = self._rcvr_config
        if config is None or self._rcvr_contracts is None or self._rcvr_events_root is None:
            raise RuntimeError('RCVRTaskSuite_not_configured')
        elements = getattr(agent_pipeline, 'elements', ())
        # ``pipeline_main`` passes AgentPipeline([InitQuery(), llm, stock_loop])
        # rather than the loop directly.  Locate the actual DRIFT LLM by its
        # validation interface; the final element is the stock loop.
        if len(elements) < 2:
            raise ValueError('unexpected_stock_pipeline_shape')
        llms = [element for element in elements
                if callable(getattr(element, 'trajectory_constraint_validation', None))
                and hasattr(element, 'client')]
        if len(llms) != 1:
            raise ValueError('stock_pipeline_llm_not_unique')
        llm = llms[0]
        task_id = getattr(user_task, 'ID', None)
        prompt = getattr(user_task, 'PROMPT', None) or getattr(user_task, 'GOAL', None)
        if not isinstance(task_id, str) or not isinstance(prompt, str):
            raise ValueError('task_identity_or_prompt_missing')
        events = []
        constraint_source = config.get('constraint_source', 'task_anchor_v1')
        # The generic path retains the original APDE SourceFlow validator as
        # the runtime decision owner.  Legacy B1 regex runs preserve their
        # historical evidence-only composition for reproducibility.
        # SourceFlow supplies evidence to ExperimentalExecutor, which maps it
        # into the single RCVR three-valued decision provider.
        llm._rcvr_sourceflow_final = False
        # The generic anchor path owns the final verdict in RCVR.  Legacy
        # regex B1 keeps its historical DRIFT/TAER pre-dispatch path.
        llm._rcvr_unified_final_owner = constraint_source == 'task_anchor_v1'
        task_anchor = None
        if constraint_source == 'task_anchor_v1':
            # DRIFT calls this after its initial secure planner builds the
            # trajectory/checklist and TAER backbone, before any tool result.
            def freeze_anchor(initial_trajectory, initial_checklist, backbone, planner_complete):
                existing = getattr(llm, '_rcvr_task_anchor', None)
                if existing is not None:
                    events.append({'event': 'task_anchor_reuse_rejected',
                                   'reason': 'anchor_already_frozen',
                                   'anchor_id': existing.anchor_id})
                    return existing
                if not planner_complete:
                    events.append({'event': 'task_anchor_incomplete',
                                   'reason': 'secure_planner_missing_or_misaligned_checklist',
                                   'initial_trajectory': list(initial_trajectory or [])})
                    return None
                anchor = freeze_from_secure_plan(task_id, prompt, initial_trajectory,
                                                 initial_checklist, backbone, self._rcvr_contracts)
                llm._rcvr_task_anchor = anchor
                llm._rcvr_binding_ir = from_anchor(anchor)
                events.append({'event': 'task_anchor_frozen', 'anchor_id': anchor.anchor_id,
                               'planner_version': anchor.planner_version,
                               'planner_metadata': json.loads(anchor.planner_metadata)})
                return anchor
            llm._rcvr_task_anchor_callback = freeze_anchor
            llm._rcvr_task_anchor = None
        executor, loop = components(
            llm, task_id, prompt, self._rcvr_contracts,
            mode=config['rcvr_mode'], budget=config['recovery_read_calls_cap'],
            relation_mode=config['relation_mode'], emit=events.append,
            enable_binding_verification=config['enable_binding_verification'],
            enable_evidence_isolation=config['enable_evidence_isolation'],
            suite_name=self.name,
            constraint_source=constraint_source,
            task_anchor=task_anchor,
        )
        if self._rcvr_checkpoint_root is not None:
            injection_id = getattr(injection_task, 'ID', None) if injection_task is not None else 'clean'
            executor.checkpoint_root = self._rcvr_checkpoint_root
            executor.checkpoint_context = {
                'suite': self.name, 'task_id': task_id,
                'injection_task_id': injection_id or 'clean',
                'run_tag': getattr(self.args, 'run_tag', None) or 'untagged',
                'benchmark_version': self.args.benchmark_version,
                'config_id': config['config_id'],
                'recovery_budget': config['recovery_read_calls_cap'],
                'relation_mode': config['relation_mode'],
                'enable_binding_verification': config['enable_binding_verification'],
                'enable_evidence_isolation': config['enable_evidence_isolation'],
                'injections': copy.deepcopy(injections),
            }
        # Retain the stock InitialQuery -> LLM -> execution-loop sequence so
        # TaskSuite can invoke this pipeline with an empty message list.
        rcvr_pipeline = AgentPipeline([InitQuery(), llm, loop])
        if self._rcvr_checkpoint_root is not None:
            def capture_pre_environment(pre_environment):
                executor.checkpoint_context['pre_environment'] = pre_environment.model_copy(deep=True)
            self._capture_pre_environment_for_rcvr = capture_pre_environment
        try:
            result = super().run_task_with_pipeline(rcvr_pipeline, user_task, injection_task,
                                                    injections, *args, **kwargs)
        finally:
            for attr in ('_rcvr_task_anchor_callback', '_rcvr_task_anchor', '_rcvr_binding_ir', '_rcvr_unified_final_owner'):
                if hasattr(llm, attr):
                    delattr(llm, attr)
            if hasattr(self, '_capture_pre_environment_for_rcvr'):
                del self._capture_pre_environment_for_rcvr
        injection_id = getattr(injection_task, 'ID', None) if injection_task is not None else 'clean'
        event_path = self._rcvr_events_root / self.name / task_id / f'{injection_id or "clean"}.json'
        event_path.parent.mkdir(parents=True, exist_ok=True)
        event_path.write_text(json.dumps({
            'method_name': 'RCVR', 'config_id': config['config_id'],
            'contract_profile': config.get('contract_profile', 'agentdojo'),
            'contract_schema_hash': config.get('contract_schema_hash'),
            'task_id': task_id, 'injection_task_id': injection_id,
            'rcvr_mode': config['rcvr_mode'], 'relation_mode': config['relation_mode'],
            'enable_binding_verification': config['enable_binding_verification'],
            'enable_evidence_isolation': config['enable_evidence_isolation'],
            'constraint_source': config.get('constraint_source', 'task_anchor_v1'),
            'stopped': executor.stopped, 'events': events,
        }, ensure_ascii=False, indent=2, default=str) + '\n', encoding='utf-8')
        return result
