import unittest
from types import SimpleNamespace

from DRIFTLLM import DRIFTLLM


class SecurePlannerParserTests(unittest.TestCase):
    def test_python_style_checklist_is_normalized(self):
        parsed = DRIFTLLM._normalize_initial_checklist(
            "[{'name': 'commit_effect', 'required parameters': {'target': 'object-17', 'value': None}, "
            "'conditions': \"{'value': 'lookup_record'}\"}]"
        )
        self.assertEqual(parsed[0]['name'], 'commit_effect')
        self.assertEqual(parsed[0]['conditions'], {'value': 'lookup_record'})

    def test_invalid_checklist_is_rejected(self):
        self.assertIsNone(DRIFTLLM._normalize_initial_checklist('{"name": "commit_effect"}'))
        self.assertIsNone(DRIFTLLM._normalize_initial_checklist('[{"required parameters": {}}]'))

    def test_target_or_control_read_relation_requires_grounded_predicate(self):
        planner = object.__new__(DRIFTLLM)
        planner.initial_function_trajectory = ['lookup_record', 'commit_effect']
        planner.source_flow_contract_helper = SimpleNamespace(
            get_tool_type=lambda tool: 'READ' if tool == 'lookup_record' else 'WRITE',
            get_arg_role=lambda tool, parameter: 'target' if parameter in {'target', 'value'} else 'content',
        )
        planner.initial_node_checklist = (
            '[{"name":"lookup_record","required parameters":{},"conditions":{}},'
            '{"name":"commit_effect","required parameters":{"target":"object-17","value":null},'
            '"conditions":{"value":"lookup_record"}}]')
        self.assertFalse(planner._initial_plan_complete())
        self.assertEqual(planner.initial_planner_incomplete_reason,
                         'ungrounded_read_relation:commit_effect.value')
        planner.initial_node_checklist = (
            '[{"name":"lookup_record","required parameters":{},"conditions":{}},'
            '{"name":"commit_effect","required parameters":{"target":"object-17","value":null},'
            '"conditions":{"value":{"source_tool":"lookup_record","request":{},'
            '"predicates":[{"field":"target","value_from_parameter":"target"}],'
            '"value_field":"value","identity_field":"id"}}}]')
        self.assertTrue(planner._initial_plan_complete())


if __name__ == '__main__':
    unittest.main()
