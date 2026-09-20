import dataclasses
import json
import unittest
from types import SimpleNamespace

from rcdc.constraint_spec import compile_anchor_spec
from rcdc.task_planner import freeze_from_secure_plan


CONTRACTS = {'tools': {
    'lookup_record': {'tool_type': 'READ', 'args': {'limit': {'sink_role': 'control'}}},
    'commit_effect': {'tool_type': 'WRITE', 'args': {
        'target': {'sink_role': 'target'}, 'value': {'sink_role': 'target'},
        'content': {'sink_role': 'content'}, 'when': {'sink_role': 'control'}}},
}}


class PlannerAnchorTests(unittest.TestCase):
    def setUp(self):
        self.backbone = SimpleNamespace(initialized=True, backbone_order=['s000', 's001'], backbone_steps={
            's000': SimpleNamespace(step_id='s000', required_parameters={'limit': 100}, conditions={}),
            's001': SimpleNamespace(step_id='s001', required_parameters={'target': 'object-17'},
                                    conditions={'value': 'lookup_record', 'content': 'lookup_record'}),
        })
        self.anchor = freeze_from_secure_plan('suite/user_task_x', 'Apply the requested effect to object-17.',
            ['lookup_record', 'commit_effect'], json.dumps([
                {'name': 'lookup_record', 'required parameters': {'limit': 100}, 'conditions': {}},
                {'name': 'commit_effect', 'required parameters': {'target': 'object-17'},
                 'conditions': {'value': 'lookup_record', 'content': 'lookup_record'}},
            ]), self.backbone, CONTRACTS)

    def test_anchor_is_deterministic_secure_planner_snapshot(self):
        again = freeze_from_secure_plan('suite/user_task_x', 'Apply the requested effect to object-17.',
            ['lookup_record', 'commit_effect'], json.dumps([
                {'name': 'lookup_record', 'required parameters': {'limit': 100}, 'conditions': {}},
                {'name': 'commit_effect', 'required parameters': {'target': 'object-17'},
                 'conditions': {'value': 'lookup_record', 'content': 'lookup_record'}},
            ]), self.backbone, CONTRACTS)
        self.assertEqual(self.anchor.anchor_id, again.anchor_id)
        self.assertEqual(json.loads(self.anchor.planner_metadata)['source'],
                         'drift_secure_planner_and_sourceflow_contract')
        self.assertFalse(json.loads(self.anchor.planner_metadata)['runtime_observations_in_anchor'])

    def test_anchor_integrates_fixed_and_sourceflow_origin_semantics(self):
        action = json.loads(self.anchor.actions)[1]
        self.assertEqual(action['fixed_constraints'][0]['value'], 'object-17')
        self.assertEqual({r['parameter'] for r in action['origin_rules']}, {'value', 'content'})
        self.assertEqual(action['origin_rules'][0]['source_tools'], ['lookup_record'])

    def test_compile_only_selects_frozen_action(self):
        spec = compile_anchor_spec(self.anchor, 'commit_effect', CONTRACTS)
        self.assertIn('object-17', spec.fixed_constraints)
        self.assertIsNone(compile_anchor_spec(self.anchor, 'lookup_record', CONTRACTS))
        self.assertIsNone(compile_anchor_spec(self.anchor, 'unplanned_effect', CONTRACTS))
        with self.assertRaises(dataclasses.FrozenInstanceError):
            self.anchor.user_task = 'changed'

    def test_structured_planner_relation_compiles_to_existing_witness_rule(self):
        anchor = freeze_from_secure_plan('suite/user_task_x', 'Apply the requested effect to object-17.',
            ['lookup_record', 'commit_effect'], json.dumps([
                {'name': 'lookup_record', 'required parameters': {'limit': 100}, 'conditions': {}},
                {'name': 'commit_effect', 'required parameters': {'target': 'object-17'}, 'conditions': {
                    'value': {'source_tool': 'lookup_record', 'request': {'limit': 100},
                              'predicates': [{'field': 'target', 'value_from_parameter': 'target'}],
                              'value_field': 'value', 'identity_field': 'id'}}},
            ]), self.backbone, CONTRACTS)
        action = json.loads(anchor.actions)[1]
        self.assertEqual(action['binding_rules'][0]['source_tool'], 'lookup_record')
        self.assertEqual(action['binding_rules'][0]['predicates'][0]['value'], 'object-17')
        spec = compile_anchor_spec(anchor, 'commit_effect', CONTRACTS)
        self.assertEqual(json.loads(spec.binding_rules)[0]['value_field'], 'value')


if __name__ == '__main__':
    unittest.main()
