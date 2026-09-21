import unittest
from types import SimpleNamespace

from pydantic import BaseModel

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

    def test_action_constants_must_be_grounded_in_user_task(self):
        self.assertTrue(DRIFTLLM._planner_action_value_is_grounded('object-17', 'Apply to object-17.'))
        self.assertFalse(DRIFTLLM._planner_action_value_is_grounded(200, 'Refund what they sent me.'))

    def test_runtime_action_values_require_structured_relation(self):
        self.assertFalse(DRIFTLLM._is_structured_runtime_relation('lookup_record'))
        self.assertFalse(DRIFTLLM._is_structured_runtime_relation({
            'source_tool': 'lookup_record', 'request': {}, 'predicates': [], 'value_field': 'value'}))
        self.assertTrue(DRIFTLLM._is_structured_runtime_relation({
            'source_tool': 'lookup_record', 'request': {},
            'predicates': [{'field': 'target', 'value': 'object-17'}], 'value_field': 'value'}))

    def test_runtime_relation_uses_declared_return_fields(self):
        class Record(BaseModel):
            id: int
            sender: str
            amount: float

        schema = DRIFTLLM._tool_output_schema(SimpleNamespace(return_type=list[Record]))
        valid = {'source_tool': 'lookup_record', 'request': {},
                 'predicates': [{'field': 'sender', 'value': 'person'}],
                 'value_field': 'amount', 'identity_field': 'id'}
        invalid = {**valid, 'identity_field': 'transaction_id'}
        self.assertTrue(DRIFTLLM._structured_relation_matches_return_schema(valid, schema))
        self.assertFalse(DRIFTLLM._structured_relation_matches_return_schema(invalid, schema))

    def test_checklist_json_can_be_extracted_from_code_fence(self):
        text = '```json\n[{"name":"lookup","required parameters":{},"conditions":{}}]\n```'
        self.assertEqual(DRIFTLLM._extract_checklist_json(text),
                         '[{"name":"lookup","required parameters":{},"conditions":{}}]')


if __name__ == '__main__':
    unittest.main()
