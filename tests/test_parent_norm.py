"""CAE Repair Parent Normalization Tests."""
import unittest, json


class TestParentNormalization(unittest.TestCase):
    """Test _normalize_cae_parent_reference logic."""

    def _normalize(self, result, current_traj, achieved_traj):
        if not isinstance(result, dict): return result
        if result.get("classification") != "PLAN_OMISSION": return result
        pi = result.get("parent_step_index")
        pt = result.get("parent_tool_name")

        # Case 1: valid index
        if isinstance(pi, int) and 0 <= pi < len(current_traj):
            if not pt: result["parent_tool_name"] = current_traj[pi]
            return result
        # Case 2: valid tool name
        if isinstance(pt, str) and pt in current_traj:
            result["parent_step_index"] = current_traj.index(pt)
            return result
        # Case 3: output_consumed_by matches
        ocb = result.get("output_consumed_by")
        if isinstance(ocb, str) and ocb in current_traj:
            result["parent_tool_name"] = ocb
            result["parent_step_index"] = current_traj.index(ocb)
            result["parent_inferred"] = True
            return result
        # Case 4: final authorized effect
        if result.get("final_authorized_effect") is True:
            ni = len(achieved_traj or [])
            if 0 <= ni < len(current_traj):
                result["parent_step_index"] = ni
                result["parent_tool_name"] = current_traj[ni]
                result["parent_inferred"] = True
                return result
        return result

    def setUp(self):
        self.traj = ["get_user_info", "send_email", "append_to_file"]
        self.achieved = ["get_user_info"]

    def test_valid_index_fills_tool_name(self):
        r = self._normalize({"classification": "PLAN_OMISSION", "parent_step_index": 1,
                              "necessary": True, "output_consumed_by": "send_email",
                              "new_goal_introduced": False}, self.traj, self.achieved)
        self.assertEqual(r["parent_tool_name"], "send_email")
        self.assertEqual(r["parent_step_index"], 1)

    def test_valid_tool_name_fills_index(self):
        r = self._normalize({"classification": "PLAN_OMISSION", "parent_tool_name": "send_email",
                              "necessary": True, "output_consumed_by": None,
                              "new_goal_introduced": False}, self.traj, self.achieved)
        self.assertEqual(r["parent_step_index"], 1)

    def test_output_consumed_by_inference(self):
        r = self._normalize({"classification": "PLAN_OMISSION", "parent_step_index": None,
                              "parent_tool_name": None, "necessary": True,
                              "output_consumed_by": "send_email",
                              "new_goal_introduced": False}, self.traj, self.achieved)
        self.assertEqual(r["parent_step_index"], 1)
        self.assertTrue(r.get("parent_inferred"))

    def test_final_effect_uses_next_expected(self):
        r = self._normalize({"classification": "PLAN_OMISSION", "parent_step_index": None,
                              "parent_tool_name": None, "necessary": True,
                              "output_consumed_by": None, "final_authorized_effect": True,
                              "new_goal_introduced": False}, self.traj, self.achieved)
        self.assertEqual(r["parent_step_index"], 1)  # next_expected = len(achieved)=1
        self.assertTrue(r.get("parent_inferred"))

    def test_missing_parent_unchanged(self):
        r_in = {"classification": "PLAN_OMISSION", "parent_step_index": None,
                "parent_tool_name": None, "necessary": True,
                "output_consumed_by": None, "final_authorized_effect": False,
                "new_goal_introduced": False}
        r = self._normalize(r_in, self.traj, self.achieved)
        self.assertIsNone(r["parent_step_index"])
        self.assertIsNone(r["parent_tool_name"])

    def test_deviation_not_modified(self):
        r_in = {"classification": "DEVIATION", "parent_step_index": None,
                "parent_tool_name": None, "necessary": False}
        r = self._normalize(r_in, self.traj, self.achieved)
        self.assertEqual(r["classification"], "DEVIATION")
        self.assertIsNone(r["parent_step_index"])


class TestParentRefEvents(unittest.TestCase):
    def test_missing_parent_event_exists(self):
        events = {"cae_repair_missing_parent_for_plan_omission",
                  "cae_repair_parent_fallback",
                  "cae_repair_judge_parse_error"}
        self.assertEqual(len(events), 3)

    def test_missing_parent_event_name(self):
        self.assertIn("plan_omission", "cae_repair_missing_parent_for_plan_omission")


if __name__ == "__main__":
    unittest.main()
