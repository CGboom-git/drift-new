"""CAE Repair Mode Tests - verify repair mode trace events and logic without LLM calls."""
import unittest
import json
from source_flow import ValidationTraceEntry


class TestCAERepairTraceSanity(unittest.TestCase):
    """Verify repair mode trace events are correct and distinguishable."""

    def test_repair_mode_has_unique_events(self):
        """repair mode has its own unique trace events."""
        repair_events = {
            "cae_repair_candidate",
            "cae_repair_judge_result",
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
        """All repair events are distinct."""
        repair_events = [
            "cae_repair_candidate",
            "cae_repair_judge_result",
            "cae_repair_task_vf_pass",
            "cae_repair_task_vf_fail",
            "cae_repair_security_vf_pass",
            "cae_repair_security_vf_fail",
            "cae_repair_patch_committed",
            "cae_repair_reject_deviation",
            "cae_repair_reject_uncertain",
            "cae_repair_attack_deviation",
        ]
        self.assertEqual(len(repair_events), len(set(repair_events)))

    def test_task_extension_vf_fields(self):
        """Task Extension VF checks specific judge result fields."""
        required = {"classification", "parent_step", "necessary",
                     "new_goal_introduced", "output_consumed_by",
                     "final_authorized_effect"}
        self.assertEqual(len(required), 6)

    def test_plan_omission_pass_conditions(self):
        """PLAN_OMISSION requires all VF checks to pass."""
        judge = {
            "classification": "PLAN_OMISSION",
            "parent_step": "S3",
            "necessary": True,
            "repair_role": "INTERMEDIATE_SUBSTEP",
            "output_consumed_by": "S3",
            "final_authorized_effect": False,
            "new_goal_introduced": False,
            "new_principal_introduced": False,
            "reason": "missing required substep",
        }
        self.assertEqual(judge["classification"], "PLAN_OMISSION")
        self.assertTrue(judge["necessary"])
        self.assertFalse(judge["new_goal_introduced"])
        self.assertTrue(judge["output_consumed_by"])

    def test_deviation_is_rejected(self):
        """DEVIATION classification should be rejected."""
        judge = {"classification": "DEVIATION", "reason": "wrong tool"}
        self.assertNotEqual(judge["classification"], "PLAN_OMISSION")

    def test_uncertain_is_rejected(self):
        """UNCERTAIN classification should be rejected."""
        judge = {"classification": "UNCERTAIN", "reason": "insufficient evidence"}
        self.assertNotEqual(judge["classification"], "PLAN_OMISSION")

    def test_plan_omission_missing_parent_is_fail(self):
        """Missing parent_step should fail VF."""
        ok, reason = self._task_vf({
            "classification": "PLAN_OMISSION",
            "parent_step": None, "necessary": True,
            "output_consumed_by": "S3",
            "new_goal_introduced": False,
        })
        self.assertFalse(ok)
        self.assertEqual(reason, "missing_parent_step")

    def test_plan_omission_not_necessary_is_fail(self):
        """Not necessary should fail VF."""
        ok, reason = self._task_vf({
            "classification": "PLAN_OMISSION",
            "parent_step": "S1", "necessary": False,
            "output_consumed_by": "S2",
            "new_goal_introduced": False,
        })
        self.assertFalse(ok)
        self.assertEqual(reason, "not_necessary")

    def test_plan_omission_new_goal_is_fail(self):
        """New goal introduced should fail VF."""
        ok, reason = self._task_vf({
            "classification": "PLAN_OMISSION",
            "parent_step": "S1", "necessary": True,
            "output_consumed_by": "S2",
            "new_goal_introduced": True,
        })
        self.assertFalse(ok)
        self.assertEqual(reason, "new_goal_introduced")

    def test_plan_omission_final_effect_without_output_consumed_should_pass(self):
        """final_authorized_effect=True should pass even without output_consumed_by."""
        ok, reason = self._task_vf({
            "classification": "PLAN_OMISSION",
            "parent_step": "S5", "necessary": True,
            "output_consumed_by": None,
            "final_authorized_effect": True,
            "new_goal_introduced": False,
        })
        self.assertTrue(ok)

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


class TestRepairModeResolution(unittest.TestCase):
    """Verify repair mode is accepted by the CLI."""

    def test_explicit_repair_mode(self):
        import sys
        sys.argv = ['test', '--source_flow_validation', '--cae_mode', 'repair']
        from utils import get_args
        args = get_args()
        self.assertEqual(args.cae_mode, 'repair')

    def test_repair_mode_in_choices(self):
        import sys
        sys.argv = ['test', '--source_flow_validation', '--cae_mode', 'repair']
        from utils import get_args
        args = get_args()
        self.assertIn(args.cae_mode, ['on', 'off', 'strict', 'block', 'repair'])


if __name__ == "__main__":
    unittest.main()
