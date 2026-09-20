"""Deterministic diagnostics for the two RCVR core mechanisms.

These are mechanism tests, not benchmark outcomes and do not invoke an LLM.
"""
import dataclasses
import unittest

from rcdc.binding_witness import evaluate
from rcdc.constraint_spec import binding, fixed, pred
from rcdc.events import EvidenceLedger
from rcdc.recovery import Recovery
from rcdc.schema import Call, ConstraintSpec


def refund_spec():
    return ConstraintSpec.create(
        'task', 'consumer', 'send_money', [fixed('recipient', 'Alice')],
        {'recipient': 'target', 'amount': 'target'},
        [binding('amount', 'get_transactions', {'n': 10},
                 [pred('sender', 'Alice'), pred('recipient', 'me')], 'amount', 'id', 'R3', 'number')],
        [{'tool': 'get_transactions', 'arguments': {'n': 10}, 'satisfies_parameter': 'amount'}])


def candidate(amount=10, position=10):
    return Call.create('task', 'effect', 'send_money', {'recipient': 'Alice', 'amount': amount}, position)


def evidence(ledger, payload, position=2, success=True):
    read = Call.create('task', 'read', 'get_transactions', {'n': 10}, position - 1)
    return ledger.record_response(read, payload, position, success)


class RCVRDiagnostics(unittest.TestCase):
    def setUp(self):
        self.spec = refund_spec()
        self.ledger = EvidenceLedger('task')

    def test_trivalent_binding_matrix(self):
        correct = [{'id': 't1', 'sender': 'Alice', 'recipient': 'me', 'amount': 10}]
        evidence(self.ledger, correct)
        self.assertEqual(evaluate(self.spec, candidate(), self.ledger).verdict, 'VALID')
        self.assertEqual(evaluate(self.spec, candidate(11), self.ledger).verdict, 'INVALID')

    def test_missing_and_ambiguous_evidence_are_unknown_not_invalid(self):
        self.assertEqual(evaluate(self.spec, candidate(), self.ledger).verdict, 'UNKNOWN')
        ambiguous = [
            {'id': 't1', 'sender': 'Alice', 'recipient': 'me', 'amount': 10},
            {'id': 't2', 'sender': 'Alice', 'recipient': 'me', 'amount': 10},
        ]
        evidence(self.ledger, ambiguous)
        self.assertEqual(evaluate(self.spec, candidate(), self.ledger).verdict, 'UNKNOWN')

    def test_temporal_and_attempt_boundaries_are_unknown(self):
        evidence(self.ledger, [{'id': 't1', 'sender': 'Alice', 'recipient': 'me', 'amount': 10}], position=12)
        self.assertEqual(evaluate(self.spec, candidate(), self.ledger).verdict, 'UNKNOWN')
        self.ledger.reset()
        self.assertEqual(evaluate(self.spec, candidate(), self.ledger).verdict, 'UNKNOWN')

    def test_recovery_preserves_spec_and_candidate_arguments(self):
        initial = evaluate(self.spec, candidate(), self.ledger)
        recovery = Recovery(self.spec, candidate(), self.ledger, initial, 'full', 1, ['get_transactions'])
        original = recovery.context.original_call
        recovery.step(lambda _: {'tool': 'get_transactions', 'arguments': {'n': 10}},
                      lambda _: evidence(self.ledger, [{'id': 't1', 'sender': 'Alice', 'recipient': 'me', 'amount': 10}], 12),
                      lambda: 13)
        self.assertEqual(recovery.decision.verdict, 'VALID')
        self.assertEqual(recovery.context.original_call, original)
        self.assertEqual(recovery.context.immutable_constraint_spec, self.spec)

    def test_recovery_rejects_side_effect_scope_and_budget_overrun(self):
        initial = evaluate(self.spec, candidate(), self.ledger)
        recovery = Recovery(self.spec, candidate(), self.ledger, initial, 'full', 1, ['get_transactions'])
        dispatched = []
        recovery.step(lambda _: {'tool': 'send_money', 'arguments': {'recipient': 'Mallory', 'amount': 1}},
                      dispatched.append, lambda: 12)
        self.assertEqual(dispatched, [])
        self.assertEqual(recovery.context.tool_calls, 0)
        self.assertEqual(recovery.context.status, 'STOP')

    def test_mutated_constraint_context_fails_closed(self):
        initial = evaluate(self.spec, candidate(), self.ledger)
        recovery = Recovery(self.spec, candidate(), self.ledger, initial, 'full', 1, ['get_transactions'])
        recovery.context.immutable_constraint_spec = dataclasses.replace(self.spec, tool='other')
        with self.assertRaises(ValueError):
            recovery.step(lambda _: {}, lambda _: None, lambda: 12)


if __name__ == '__main__':
    unittest.main()
