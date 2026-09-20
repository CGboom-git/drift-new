import json
import unittest
from types import SimpleNamespace

from rcdc.constraint_spec import compile_anchor_spec
from rcdc.task_planner import TaskAnchor, create_anchor, planner_prompt, validate_actions


CONTRACTS = {
    'tools': {
        'send_money': {'tool_type': 'WRITE', 'args': {'recipient': {'sink_role': 'target'}, 'amount': {'sink_role': 'target'}}},
        'get_most_recent_transactions': {'tool_type': 'READ', 'args': {'n': {'sink_role': 'control'}}},
        'delete_file': {'tool_type': 'WRITE', 'args': {'file_id': {'sink_role': 'target'}}},
    }
}


class PlannerTests(unittest.TestCase):
    def test_prompt_contains_only_task_and_contract_snapshot(self):
        system, prompt = planner_prompt('banking/user_task_4', 'Refund AB12.', CONTRACTS)
        self.assertIn('ORIGINAL_USER_TASK', prompt)
        self.assertIn('TOOL_CONTRACTS', prompt)
        self.assertNotIn('runtime', prompt.lower())
        self.assertIn('trusted task planner', system)

    def test_contract_validation_drops_unknown_tools_and_arguments(self):
        raw = {'actions': [
            {'tool': 'unknown', 'fixed_constraints': [{'parameter': 'x', 'value': 1}]},
            {'tool': 'send_money', 'fixed_constraints': [
                {'parameter': 'recipient', 'value': 'AB12'}, {'parameter': 'attacker', 'value': 'x'}],
             'binding_rules': [
                {'parameter': 'amount', 'source_tool': 'get_most_recent_transactions', 'request': {'n': 100},
                 'predicates': [{'field': 'sender', 'value': 'AB12'}], 'value_field': 'amount', 'identity_field': 'id'},
                {'parameter': 'amount', 'source_tool': 'send_money', 'request': {}, 'predicates': []}]},
        ]}
        actions = validate_actions(raw, CONTRACTS)
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0]['fixed_constraints'][0]['parameter'], 'recipient')
        self.assertEqual(len(actions[0]['binding_rules']), 1)

    def test_anchor_compilation_cannot_be_changed_by_candidate_data(self):
        anchor = TaskAnchor.create('t', 'Refund AB12.', [{
            'tool': 'send_money', 'fixed_constraints': [{'parameter': 'recipient', 'kind': 'equals', 'value': 'AB12',
                                                          'comparison': 'exact', 'authority_basis': 'task_anchor_user_requirement'}],
            'binding_rules': [],
        }])
        spec = compile_anchor_spec(anchor, 'send_money', CONTRACTS)
        self.assertIn('AB12', spec.fixed_constraints)
        self.assertNotIn('EVIL', spec.fixed_constraints)
        with self.assertRaises(Exception):
            anchor.user_task = 'changed'
        self.assertIsNone(compile_anchor_spec(anchor, 'delete_file', CONTRACTS))

    def test_create_anchor_never_passes_runtime_data_to_model(self):
        client = SimpleNamespace(llm_run=lambda system, prompt, **kwargs: json.dumps({'actions': [{
            'tool': 'send_money', 'fixed_constraints': [{'parameter': 'recipient', 'value': 'AB12'}],
            'binding_rules': [],
        }]}))
        anchor = create_anchor(SimpleNamespace(client=client), 't', 'Refund AB12.', CONTRACTS)
        self.assertEqual(json.loads(anchor.actions)[0]['tool'], 'send_money')
        self.assertEqual(json.loads(anchor.planner_metadata)['runtime_observations_in_prompt'], False)


if __name__ == '__main__':
    unittest.main()
