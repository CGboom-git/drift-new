import dataclasses
import json
import unittest
from types import SimpleNamespace

from rcdc.constraint_spec import compile_anchor_spec
from rcdc.task_planner import freeze_from_secure_plan


CONTRACTS = {'tools': {
    'get_most_recent_transactions': {'tool_type': 'READ', 'args': {'n': {'sink_role': 'control'}}},
    'send_money': {'tool_type': 'WRITE', 'args': {
        'recipient': {'sink_role': 'target'}, 'amount': {'sink_role': 'target'},
        'subject': {'sink_role': 'content'}, 'date': {'sink_role': 'control'}}},
}}


class PlannerAnchorTests(unittest.TestCase):
    def setUp(self):
        self.backbone = SimpleNamespace(initialized=True, backbone_order=['s000', 's001'], backbone_steps={
            's000': SimpleNamespace(step_id='s000', required_parameters={'n': 100}, conditions={}),
            's001': SimpleNamespace(step_id='s001', required_parameters={'recipient': 'GB29'},
                                    conditions={'amount': 'get_most_recent_transactions',
                                                'subject': 'get_most_recent_transactions'}),
        })
        self.anchor = freeze_from_secure_plan('banking/user_task_4', 'Please refund GB29.',
            ['get_most_recent_transactions', 'send_money'], json.dumps([
                {'name': 'get_most_recent_transactions', 'required parameters': {'n': 100}, 'conditions': {}},
                {'name': 'send_money', 'required parameters': {'recipient': 'GB29'},
                 'conditions': {'amount': 'get_most_recent_transactions', 'subject': 'get_most_recent_transactions'}},
            ]), self.backbone, CONTRACTS)

    def test_anchor_is_deterministic_secure_planner_snapshot(self):
        again = freeze_from_secure_plan('banking/user_task_4', 'Please refund GB29.',
            ['get_most_recent_transactions', 'send_money'], json.dumps([
                {'name': 'get_most_recent_transactions', 'required parameters': {'n': 100}, 'conditions': {}},
                {'name': 'send_money', 'required parameters': {'recipient': 'GB29'},
                 'conditions': {'amount': 'get_most_recent_transactions', 'subject': 'get_most_recent_transactions'}},
            ]), self.backbone, CONTRACTS)
        self.assertEqual(self.anchor.anchor_id, again.anchor_id)
        self.assertEqual(json.loads(self.anchor.planner_metadata)['source'],
                         'drift_secure_planner_and_sourceflow_contract')
        self.assertFalse(json.loads(self.anchor.planner_metadata)['runtime_observations_in_anchor'])

    def test_anchor_integrates_fixed_and_sourceflow_origin_semantics(self):
        action = json.loads(self.anchor.actions)[1]
        self.assertEqual(action['fixed_constraints'][0]['value'], 'GB29')
        self.assertEqual({r['parameter'] for r in action['origin_rules']}, {'amount', 'subject'})
        self.assertEqual(action['origin_rules'][0]['source_tools'], ['get_most_recent_transactions'])

    def test_compile_only_selects_frozen_action(self):
        spec = compile_anchor_spec(self.anchor, 'send_money', CONTRACTS)
        self.assertIn('GB29', spec.fixed_constraints)
        self.assertIsNone(compile_anchor_spec(self.anchor, 'get_most_recent_transactions', CONTRACTS))
        self.assertIsNone(compile_anchor_spec(self.anchor, 'delete_file', CONTRACTS))
        with self.assertRaises(dataclasses.FrozenInstanceError):
            self.anchor.user_task = 'changed'


if __name__ == '__main__':
    unittest.main()
