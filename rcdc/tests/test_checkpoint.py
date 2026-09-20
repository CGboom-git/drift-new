"""Deterministic checkpoint capture and independent reload checks."""
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from agentdojo.functions_runtime import FunctionCall
from pydantic import BaseModel

from rcdc.binding_witness import evaluate
from rcdc.checkpoint import capture, load
from rcdc.events import EvidenceLedger
from rcdc.schema import Call, ConstraintSpec


class FakeEnvironment(BaseModel):
    balance: int = 100


class CheckpointTests(unittest.TestCase):
    def test_unknown_is_frozen_before_recovery_and_restored_independently(self):
        spec = ConstraintSpec.create(
            't', None, 'send_money', binding_rules=[{
                'parameter': 'amount', 'source_tool': 'get_most_recent_transactions',
                'request': {'n': 100}, 'predicates': [], 'value_field': 'amount',
                'identity_field': 'id', 'rule_id': 'R3', 'comparison': 'number',
                'relation_type': 'unique_object_field',
                'authority_basis': 'user_relation_plus_tool_schema',
            }], recovery_scope=[{
                'tool': 'get_most_recent_transactions', 'arguments': {'n': 100},
                'satisfies_parameter': 'amount',
            }],
        )
        call = Call.create('t', 'candidate-1', 'send_money', {'amount': 10}, 3)
        ledger = EvidenceLedger('t')
        ledger.observe_call(call)
        decision = evaluate(spec, call, ledger)
        self.assertEqual(decision.verdict, 'UNKNOWN')
        env = FakeEnvironment()
        context = {'run_tag': 'probe', 'suite': 'banking', 'task_id': 't',
                   'injection_task_id': 'clean', 'pre_environment': env.model_copy(deep=True)}
        llm = SimpleNamespace(client=SimpleNamespace(total_tokens=7), logger=None,
                              args=SimpleNamespace(model='test'), function_trajectory=['read'])
        executor = SimpleNamespace(ledger=ledger, clock=3)
        messages = [{'role': 'assistant', 'content': '', 'tool_calls': [
            FunctionCall(id='candidate-1', function='send_money', args={'amount': 10})]}]
        with tempfile.TemporaryDirectory() as directory:
            path = capture(directory, context, llm, executor, spec, call, decision,
                           env, messages, {})
            self.assertTrue(path.is_file())
            restored = load(path)
            self.assertEqual(evaluate(restored['spec'], restored['call'],
                                      restored['ledger']).json(), decision.json())
            self.assertEqual(restored['environment'].balance, 100)
            env.balance = 1
            restored['environment'].balance = 50
            self.assertEqual(load(path)['environment'].balance, 100)
            sidecar = json.loads(Path(path).with_suffix('.json').read_text())
            self.assertEqual(sidecar['initial_verdict'], 'UNKNOWN')
            self.assertEqual(sidecar['hashes']['spec'], spec.constraint_id)

    def test_checkpoint_rejects_multi_call_batch(self):
        spec = ConstraintSpec.create('t', None, 'send_money')
        call = Call.create('t', 'c1', 'send_money', {'amount': 10}, 1)
        ledger = EvidenceLedger('t')
        ledger.observe_call(call)
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, 'single_candidate'):
                capture(directory, {'run_tag': 'r', 'suite': 'banking',
                                    'injection_task_id': 'clean',
                                    'pre_environment': FakeEnvironment()},
                        SimpleNamespace(client=SimpleNamespace(), logger=None),
                        SimpleNamespace(ledger=ledger, clock=1),
                        spec, call, evaluate(spec, call, ledger), FakeEnvironment(),
                        [{'role': 'assistant', 'tool_calls': [
                            FunctionCall(id='c1', function='send_money', args={'amount': 10}),
                            FunctionCall(id='c2', function='send_money', args={'amount': 11})]}], {})


if __name__ == '__main__':
    unittest.main()
