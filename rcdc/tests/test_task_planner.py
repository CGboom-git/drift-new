import dataclasses
import json
import unittest
from types import SimpleNamespace

from rcdc.constraint_spec import compile_anchor_spec
from rcdc.task_planner import compile_relation_choices, freeze_from_secure_plan
from rcdc.binding_ir import from_anchor


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

    def test_binding_ir_contains_only_frozen_anchor_rules(self):
        nodes = json.loads(from_anchor(self.anchor))
        self.assertEqual([node['name'] for node in nodes], ['lookup_record', 'commit_effect'])
        self.assertEqual(nodes[1]['required parameters']['target'], 'object-17')
        self.assertNotIn('value', nodes[1]['conditions'])

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

    def test_unselected_read_is_not_promoted_to_record_binding(self):
        anchor = freeze_from_secure_plan('suite/user_task_x', 'Apply the requested effect to object-17.',
            ['lookup_record', 'commit_effect'], json.dumps([
                {'name': 'lookup_record', 'required parameters': {'limit': 1}, 'conditions': {}},
                {'name': 'commit_effect', 'required parameters': {'target': 'object-17'}, 'conditions': {
                    'value': {'source_tool': 'lookup_record', 'request': {'limit': 1},
                              'predicates': [], 'value_field': 'value', 'identity_field': 'id'}}},
            ]), self.backbone, CONTRACTS)
        action = json.loads(anchor.actions)[1]
        self.assertEqual(action['binding_rules'], [])

    def test_contract_constrained_choice_materializes_relation(self):
        contracts = {'tools': {
            'read_records': {'tool_type': 'READ', 'args': {}, 'output_semantics': {'fields': {
                'id': {'role': 'identity'}, 'owner': {'role': 'principal_owner'},
                'amount': {'role': 'financial_value'}}}},
            'commit_effect': {'tool_type': 'WRITE', 'args': {
                'amount': {'sink_role': 'control'}}},
        }, 'binding_capabilities': {
            'relation_types': ['unique_selected_record_field'],
            'parameter_role_compatibility': {'control': ['financial_value']},
        }}
        checklist = [
            {'name': 'read_records', 'required parameters': {}, 'conditions': {}},
            {'name': 'commit_effect', 'required parameters': {'amount': None}, 'conditions': {}},
        ]
        result = compile_relation_choices(checklist, ['read_records', 'commit_effect'], contracts, [{
            'action_tool': 'commit_effect', 'parameter': 'amount', 'source_tool': 'read_records',
            'relation': 'unique_selected_record_field', 'value_field': 'amount', 'identity_field': 'id',
            'selection': [{'field': 'owner', 'value': {'kind': 'user_literal', 'value': 'Alice'}}],
        }], 'Pay Alice the selected amount.')
        self.assertEqual(result[1]['conditions']['amount']['value_field'], 'amount')
        self.assertEqual(result[1]['conditions']['amount']['predicates'][0]['value'], 'Alice')

    def test_contract_constrained_choice_rejects_incompatible_target_field(self):
        contracts = {'tools': {
            'read_records': {'tool_type': 'READ', 'args': {}, 'output_semantics': {'fields': {
                'amount': {'role': 'financial_value'}}}},
            'commit_effect': {'tool_type': 'WRITE', 'args': {
                'target': {'sink_role': 'target'}}},
        }, 'binding_capabilities': {
            'relation_types': ['unique_selected_record_field'],
            'parameter_role_compatibility': {'target': ['principal']},
        }}
        checklist = [{'name': 'read_records', 'required parameters': {}, 'conditions': {}},
                     {'name': 'commit_effect', 'required parameters': {'target': None}, 'conditions': {}}]
        result = compile_relation_choices(checklist, ['read_records', 'commit_effect'], contracts, [{
            'action_tool': 'commit_effect', 'parameter': 'target', 'source_tool': 'read_records',
            'relation': 'unique_selected_record_field', 'value_field': 'amount', 'selection': [
                {'field': 'amount', 'value': {'kind': 'user_literal', 'value': '10'}}],
        }], 'Use 10.')
        self.assertIsNone(result)


if __name__ == '__main__':
    unittest.main()
