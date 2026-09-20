"""Task-local RCVR wrapper for the untouched AgentDojo task suite.

The stock pipeline creates one executor before it knows which user task is
running.  RCVR constraints, evidence ledgers, and recovery budgets are instead
task-local.  This wrapper creates the experimental loop inside
``run_task_with_pipeline`` and leaves the stock suite and pipeline untouched.
"""
import json
from pathlib import Path

from DRIFTTaskSuite import DRIFTTaskSuite
from agentdojo.agent_pipeline import AgentPipeline, InitQuery
from .integration import components


class RCVRTaskSuite(DRIFTTaskSuite):
    """An opt-in suite used only by ``experiments/rcdc/run_rcvr_online.py``."""

    _rcvr_config = None
    _rcvr_contracts = None
    _rcvr_events_root = None

    @classmethod
    def configure_rcvr(cls, config, contracts, events_root):
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
        cls._rcvr_config = dict(config)
        cls._rcvr_contracts = dict(contracts)
        cls._rcvr_events_root = Path(events_root)

    @classmethod
    def clear_rcvr_configuration(cls):
        cls._rcvr_config = cls._rcvr_contracts = cls._rcvr_events_root = None

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
        executor, loop = components(
            llm, task_id, prompt, self._rcvr_contracts,
            mode=config['rcvr_mode'], budget=config['recovery_read_calls_cap'],
            relation_mode=config['relation_mode'], emit=events.append,
            enable_binding_verification=config['enable_binding_verification'],
            enable_evidence_isolation=config['enable_evidence_isolation'],
        )
        # Retain the stock InitialQuery -> LLM -> execution-loop sequence so
        # TaskSuite can invoke this pipeline with an empty message list.
        rcvr_pipeline = AgentPipeline([InitQuery(), llm, loop])
        result = super().run_task_with_pipeline(rcvr_pipeline, user_task, injection_task,
                                                injections, *args, **kwargs)
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
            'stopped': executor.stopped, 'events': events,
        }, ensure_ascii=False, indent=2, default=str) + '\n', encoding='utf-8')
        return result
