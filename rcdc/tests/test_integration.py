"""Real AgentDojo in-memory executor tests; model calls are mocked."""
import copy
import json
import logging
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock
from agentdojo.agent_pipeline import ToolsExecutor
from agentdojo.functions_runtime import FunctionCall, FunctionsRuntime
from agentdojo.task_suite.load_suites import get_suite
from DRIFTLLM import DRIFTLLM
from DRIFTToolsExecutionLoop import DRIFTToolsExecutionLoop
from authorization_audit_20260908.online_runner.full_pilot import args_full
from rcdc.integration import ExperimentalExecutor, components, parsed_response, parse_recovery_proposal
from rcdc.constraint_spec import compile_spec
from rcdc.schema import Call
from rcdc.events import EvidenceLedger
from rcdc.binding_witness import evaluate


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.suite = get_suite('v1.2', 'slack')
        self.task = self.suite.get_user_task_by_id('user_task_7')
        self.env = self.task.init_environment(self.suite.load_and_inject_default_environment({}))
        self.runtime = FunctionsRuntime(self.suite.tools)
        self.llm = DRIFTLLM(args_full('gpt-4o-mini-2024-07-18'), MagicMock(), logger=logging.getLogger('rcdc'))
        self.contracts = json.loads(Path('contracts/agentdojo_ifc_global_tool_contract_semantic_review_gpt55.json').read_text())

    def messages(self, tool, arguments):
        return [{'role': 'user', 'content': self.task.PROMPT}, {'role': 'assistant', 'content': '',
            'tool_calls': [FunctionCall(id='c1', function=tool, args=arguments)]}]

    def test_off_uses_exact_old_classes(self):
        ex, loop = components(self.llm, 't', self.task.PROMPT, self.contracts)
        self.assertIs(type(ex), ToolsExecutor); self.assertIs(type(loop), DRIFTToolsExecutionLoop)

    def test_off_real_response_and_environment_match(self):
        old = ToolsExecutor(); new, _ = components(self.llm, 't', self.task.PROMPT, self.contracts)
        args = {'user': 'Charlie', 'channel': self.env.slack.channels[0]}
        a = old.query(self.task.PROMPT, self.runtime, copy.deepcopy(self.env), self.messages('add_user_to_channel', args), {})
        b = new.query(self.task.PROMPT, self.runtime, copy.deepcopy(self.env), self.messages('add_user_to_channel', args), {})
        self.assertEqual(a[2].model_dump(), b[2].model_dump()); self.assertEqual(a[3], b[3])

    def test_shadow_response_and_environment_match(self):
        new, _ = components(self.llm, 't', self.task.PROMPT, self.contracts, 'shadow')
        args = {'user': 'Charlie', 'channel': self.env.slack.channels[0]}
        a = ToolsExecutor().query(self.task.PROMPT, self.runtime, copy.deepcopy(self.env), self.messages('add_user_to_channel', args), {})
        b = new.query(self.task.PROMPT, self.runtime, copy.deepcopy(self.env), self.messages('add_user_to_channel', args), {})
        self.assertEqual(a[2].model_dump(), b[2].model_dump()); self.assertEqual(a[3], b[3])

    def test_strict_unknown_stops_before_model_or_effect(self):
        ex, loop = components(self.llm, 't', self.task.PROMPT, self.contracts, 'strict')
        result = loop.query(self.task.PROMPT, self.runtime, self.env, self.messages('add_user_to_channel',
            {'user': 'Charlie', 'channel': self.env.slack.channels[0]}), {})
        self.assertTrue(ex.stopped); self.assertFalse(result[3][-1]['tool_calls'])
        self.llm.client.agent_run.assert_not_called(); self.llm.client.llm_run.assert_not_called()

    def test_strict_batch_returns_a_response_for_each_unexecuted_call(self):
        ex, _ = components(self.llm, 't', self.task.PROMPT, self.contracts, 'strict')
        calls = [FunctionCall(id='blocked', function='add_user_to_channel', args={'user': 'Charlie', 'channel': self.env.slack.channels[0]}),
                 FunctionCall(id='pending', function='get_channels', args={})]
        result = ex.query(self.task.PROMPT, self.runtime, self.env,
                          [{'role': 'user', 'content': self.task.PROMPT}, {'role': 'assistant', 'content': '', 'tool_calls': calls}], {})
        ids = [message.get('tool_call_id') for message in result[3] if message.get('role') == 'tool']
        self.assertEqual(ids, ['blocked', 'pending'])

    def test_shadow_does_not_mark_one_call_identity_ambiguous(self):
        ex, _ = components(self.llm, 't', self.task.PROMPT, self.contracts, 'shadow')
        ex.query(self.task.PROMPT, self.runtime, self.env,
                 self.messages('add_user_to_channel', {'user': 'Charlie', 'channel': self.env.slack.channels[0]}), {})
        self.assertEqual(ex.ledger.ambiguous_ids, set())

    def test_recovery_transcript_precedes_retried_candidate_and_taer_sourceflow_is_evidence_only(self):
        self.llm.trajectory_constraint_validation = MagicMock(side_effect=lambda names, output, *args: (None, output))
        self.llm.checklist_constraint_validation = MagicMock(side_effect=lambda names, output, *args: (None, output))
        self.llm._source_flow_validate_tool_calls = MagicMock(return_value=SimpleNamespace(reject=True, repair_required=False))
        self.llm._source_flow_record_tool_message_at = MagicMock()
        self.llm.client.llm_run.return_value = '{"tool":"get_channels","arguments":{}}'
        events = []
        ex, _ = components(self.llm, 't', self.task.PROMPT, self.contracts, 'full', emit=events.append)
        candidate = next(c for c in self.task.ground_truth(self.env) if c.function == 'add_user_to_channel')
        result = ex.query(self.task.PROMPT, self.runtime, self.env, self.messages(candidate.function, candidate.args), {})
        messages = result[3]
        read_index = next(i for i, m in enumerate(messages) if m.get('tool_call_id', '').startswith('rcvr_read_'))
        candidate_index = next(i for i, m in enumerate(messages) if m.get('role') == 'assistant' and any(
            c.id == 'c1' for c in m.get('tool_calls', [])))
        self.assertLess(read_index, candidate_index)
        self.assertFalse(ex.stopped)
        self.assertTrue(any(e.get('event') == 'evidence_isolation_observation' for e in events))

    def test_duplicate_yaml_key_unknown(self):
        self.assertEqual(parsed_response({'content': '- id: 1\n  id: 2\n', 'error': None}), (None, False))

    def test_recovery_proposal_accepts_only_a_json_object_with_optional_outer_fence(self):
        expected = {'tool': 'get_channels', 'arguments': {}}
        self.assertEqual(parse_recovery_proposal('{"tool":"get_channels","arguments":{}}'), expected)
        self.assertEqual(parse_recovery_proposal('```json\n{"tool":"get_channels","arguments":{}}\n```'), expected)
        self.assertIsNone(parse_recovery_proposal('prefix {"tool":"get_channels","arguments":{}}'))
        self.assertIsNone(parse_recovery_proposal('```json\n[]\n```'))

    def test_evidence_scope_uses_contract_semantics_not_tool_name(self):
        self.assertTrue(ExperimentalExecutor._is_evidence_producing_tool({'tool_type': 'READ_SENSITIVE'}))
        self.assertTrue(ExperimentalExecutor._is_evidence_producing_tool({'non_consequential_evidence': True}))
        self.assertFalse(ExperimentalExecutor._is_evidence_producing_tool({'tool_type': 'ACTION'}))
        flow = SimpleNamespace(repair_required=True, repair_obligations=[{
            'arg_name': 'recipient', 'expected_root_tools': ['lookup_recipient', 'send_money'],
        }])
        scope = ExperimentalExecutor._sourceflow_recovery_scope(flow, ['lookup_recipient'])
        self.assertEqual(scope, [{
            'tool': 'lookup_recipient', 'arguments': None, 'satisfies_parameter': 'recipient',
            'kind': 'evidence', 'origin': 'sourceflow_binding_delta',
        }])

    def test_six_real_task_schemas_bind_their_ground_truth(self):
        for suite_name, task_id in [('banking','user_task_4'), ('workspace','user_task_8'),
                                   ('workspace','user_task_9'), ('workspace','user_task_35'),
                                   ('slack','user_task_7'), ('slack','user_task_12')]:
            with self.subTest(suite=suite_name, task=task_id):
                suite = get_suite('v1.2', suite_name); task = suite.get_user_task_by_id(task_id)
                env = task.init_environment(suite.load_and_inject_default_environment({}))
                runtime = FunctionsRuntime(suite.tools)
                spec = compile_spec('t', task.PROMPT, [], [], None, self.contracts)
                ledger = EvidenceLedger('t')
                req = json.loads(spec.recovery_scope)[0]
                raw, error = runtime.run_function(env, req['tool'], req['arguments'])
                def serial(v):
                    if hasattr(v, 'model_dump'): return v.model_dump(mode='json')
                    raise TypeError(type(v).__name__)
                payload = json.loads(json.dumps(raw, default=serial))
                ledger.record_response(Call.create('t', 'read', req['tool'], req['arguments'], 1), payload, 2, not error)
                ground = [c for c in task.ground_truth(env) if c.function == spec.tool]
                self.assertEqual(len(ground), 1)
                call = Call.create('t', 'candidate', spec.tool, ground[0].args, 3)
                self.assertEqual(evaluate(spec, call, ledger).verdict, 'VALID')


if __name__ == '__main__':
    unittest.main()
