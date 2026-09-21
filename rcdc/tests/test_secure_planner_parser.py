import unittest

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


if __name__ == '__main__':
    unittest.main()
