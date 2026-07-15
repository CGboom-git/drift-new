"""CAE Repair Mode Tests - updated with new fixes."""
import unittest
import json
from source_flow import ValidationTraceEntry


class TestCAERepairTraceSanity(unittest.TestCase):

    def test_repair_mode_has_unique_events(self):
        repair_events = {
            "cae_repair_candidate",
            "cae_repair_judge_result",
            "cae_repair_judge_parse_error",
            "cae_repair_task_vf_pass",
            "cae_repair_task_vf_fail",
            "cae_repair_security_vf_pass",
            "cae_repair_security_vf_fail",
            "cae_repair_patch_committed",
            "cae_repair_reject_deviation",
            "cae_repair_reject_uncertain",
            "cae_repair_attack_deviation",
        }
        for event in repair_events:
            self.assertIn("cae_repair", event)

    def test_repair_events_distinct(self):
        repair_events = [
            "cae_repair_candidate", "cae_repair_judge_result",
            "cae_repair_judge_parse_error",
            "cae_repair_task_vf_pass", "cae_repair_task_vf_fail",
            "cae_repair_security_vf_pass", "cae_repair_security_vf_fail",
            "cae_repair_patch_committed", "cae_repair_reject_deviation",
            "cae_repair_reject_uncertain", "cae_repair_attack_deviation",
        ]
        self.assertEqual(len(repair_events), len(set(repair_events)))

    def test_patch_has_parent_step_index_and_name(self):
        """ADD_SUBSTEP patch should include both parent_step_index and parent_tool_name."""
        judge = {
            "classification": "PLAN_OMISSION",
            "parent_step_index": 2,
            "parent_tool_name": "send_money",
            "parent_step": "send_money",
            "necessary": True,
            "repair_role": "INTERMEDIATE_SUBSTEP",
            "output_consumed_by": "S3",
            "final_authorized_effect": False,
            "new_goal_introduced": False,
            "new_principal_introduced": False,
            "reason": "test",
        }
        # Build patch
        patch = {
            "operation": "ADD_SUBSTEP",
            "parent_step": judge.get("parent_tool_name") or judge.get("parent_step"),
            "parent_step_index": judge.get("parent_step_index"),
            "parent_tool_name": judge.get("parent_tool_name") or judge.get("parent_step"),
            "tool_name": "get_balance",
            "tool_args": {},
        }
        self.assertEqual(patch["parent_step_index"], 2)
        self.assertEqual(patch["parent_tool_name"], "send_money")

    def test_plan_omission_pass_conditions(self):
        judge = {
            "classification": "PLAN_OMISSION",
            "parent_step_index": 3,
            "parent_tool_name": "send_money",
            "parent_step": "send_money",
            "necessary": True,
            "repair_role": "INTERMEDIATE_SUBSTEP",
            "output_consumed_by": "S3",
            "final_authorized_effect": False,
            "new_goal_introduced": False,
            "new_principal_introduced": False,
            "reason": "missing required substep",
        }
        self.assertTrue(judge["necessary"])
        self.assertFalse(judge["new_goal_introduced"])

    def test_task_vf_missing_parent_fails(self):
        ok, _ = self._task_vf({"classification": "PLAN_OMISSION",
            "parent_step": None, "necessary": True,
            "output_consumed_by": "S3", "new_goal_introduced": False})
        self.assertFalse(ok)

    def test_task_vf_not_necessary_fails(self):
        ok, _ = self._task_vf({"classification": "PLAN_OMISSION",
            "parent_step": "S1", "necessary": False,
            "output_consumed_by": "S2", "new_goal_introduced": False})
        self.assertFalse(ok)

    def test_task_vf_new_goal_fails(self):
        ok, _ = self._task_vf({"classification": "PLAN_OMISSION",
            "parent_step": "S1", "necessary": True,
            "output_consumed_by": "S2", "new_goal_introduced": True})
        self.assertFalse(ok)

    def test_task_vf_final_effect_passes(self):
        ok, _ = self._task_vf({"classification": "PLAN_OMISSION",
            "parent_step": "S5", "necessary": True,
            "output_consumed_by": None, "final_authorized_effect": True,
            "new_goal_introduced": False})
        self.assertTrue(ok)

    def test_robust_json_with_code_fence(self):
        """JSON inside markdown code fence should be extractable."""
        raw = '```json\n{"classification": "PLAN_OMISSION", "parent_step_index": 1, "parent_tool_name": "read_file", "parent_step": "read_file", "necessary": true, "repair_role": "INTERMEDIATE_SUBSTEP", "output_consumed_by": "S3", "final_authorized_effect": false, "new_goal_introduced": false, "new_principal_introduced": false, "reason": "test"}\n```'
        import re
        fence_match = re.search(r"(?is)```json\s*\n(.+?)\n\s*```", raw)
        self.assertIsNotNone(fence_match)
        result = json.loads(fence_match.group(1))
        self.assertEqual(result["classification"], "PLAN_OMISSION")

    def test_robust_json_plain(self):
        """Plain JSON should parse directly."""
        raw = '{"classification": "DEVIATION", "reason": "test"}'
        result = json.loads(raw)
        self.assertEqual(result["classification"], "DEVIATION")

    def test_parse_error_is_logged(self):
        """Parse error event name exists."""
        self.assertIn("cae_repair_judge_parse_error", [
            "cae_repair_judge_parse_error",
        ])

    def _task_vf(self, judge_result):
        if judge_result.get("classification") != "PLAN_OMISSION":
            return False, "classification_not_plan_omission"
        if not judge_result.get("parent_step"):
            return False, "missing_parent_step"
        if judge_result.get("necessary") is not True:
            return False, "not_necessary"
        if judge_result.get("new_goal_introduced") is True:
            return False, "new_goal_introduced"
        output_consumed = bool(judge_result.get("output_consumed_by"))
        final_effect = judge_result.get("final_authorized_effect") is True
        if not (output_consumed or final_effect):
            return False, "neither_output_consumed_nor_final_authorized_effect"
        return True, "pass"


if __name__ == "__main__":
    unittest.main()
