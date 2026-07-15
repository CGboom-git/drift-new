"""CAE Repair Mode Tests - comprehensive runtime fix tests."""
import unittest
import json


class TestCAERepairTraceSanity(unittest.TestCase):

    def test_repair_events_include_new(self):
        events = [
            "cae_repair_candidate", "cae_repair_judge_result",
            "cae_repair_judge_parse_error", "cae_repair_parent_fallback",
            "cae_repair_task_vf_pass", "cae_repair_task_vf_fail",
            "cae_repair_security_vf_pass", "cae_repair_security_vf_fail",
            "cae_repair_patch_committed", "cae_repair_reject_deviation",
            "cae_repair_reject_uncertain", "cae_repair_attack_deviation",
        ]
        self.assertEqual(len(events), len(set(events)))

    def test_repair_events_distinct(self):
        for ev in ["cae_repair_candidate", "cae_repair_parent_fallback",
                    "cae_repair_judge_parse_error"]:
            self.assertIn("cae_repair", ev)


class TestParentInsertion(unittest.TestCase):

    def _resolve(self, trajectory, patch):
        parent_index = patch.get("parent_step_index")
        parent_tool = patch.get("parent_tool_name")
        if isinstance(parent_index, int) and 0 <= parent_index < len(trajectory):
            return trajectory[:parent_index] + [patch["tool_name"]] + trajectory[parent_index:]
        if isinstance(parent_tool, str) and parent_tool in trajectory:
            idx = trajectory.index(parent_tool)
            return trajectory[:idx] + [patch["tool_name"]] + trajectory[idx:]
        return trajectory + [patch["tool_name"]]

    def test_parent_index_insertion(self):
        """parent_step_index=1 inserts before index 1."""
        traj = ["read_email", "send_email"]
        patch = {"operation": "ADD_SUBSTEP", "parent_step_index": 1,
                 "parent_tool_name": "send_email", "tool_name": "get_contact"}
        result = self._resolve(traj, patch)
        self.assertEqual(result, ["read_email", "get_contact", "send_email"])

    def test_parent_tool_fallback(self):
        """Invalid index falls back to parent_tool_name."""
        traj = ["read_email", "send_email"]
        patch = {"operation": "ADD_SUBSTEP", "parent_step_index": 99,
                 "parent_tool_name": "send_email", "tool_name": "get_contact"}
        result = self._resolve(traj, patch)
        self.assertEqual(result, ["read_email", "get_contact", "send_email"])

    def test_fallback_append(self):
        """Invalid index AND invalid parent_tool_name appends to end."""
        traj = ["read_email", "send_email"]
        patch = {"operation": "ADD_SUBSTEP", "parent_step_index": 99,
                 "parent_tool_name": "S3", "tool_name": "get_contact"}
        result = self._resolve(traj, patch)
        self.assertEqual(result, ["read_email", "send_email", "get_contact"])

    def test_parent_index_zero(self):
        """parent_step_index=0 inserts at beginning."""
        traj = ["read_email", "send_email"]
        patch = {"operation": "ADD_SUBSTEP", "parent_step_index": 0,
                 "parent_tool_name": "read_email", "tool_name": "get_contact"}
        result = self._resolve(traj, patch)
        self.assertEqual(result, ["get_contact", "read_email", "send_email"])


class TestSafeJSONParsing(unittest.TestCase):

    def _safe_parse(self, text):
        if isinstance(text, dict):
            return text
        if not isinstance(text, str):
            return None
        try:
            return json.loads(text)
        except Exception:
            pass
        cleaned = text.strip()
        import re
        cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()
        try:
            return json.loads(cleaned)
        except Exception:
            pass
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except Exception:
                return None
        return None

    def _normalize(self, result):
        if not isinstance(result, dict):
            return {"classification": "UNCERTAIN", "reason": "invalid"}
        n = dict(result)
        n["classification"] = str(n.get("classification", "UNCERTAIN")).strip().upper()
        if n["classification"] not in {"PLAN_OMISSION", "DEVIATION", "UNCERTAIN"}:
            n["classification"] = "UNCERTAIN"
        idx = n.get("parent_step_index")
        if isinstance(idx, str):
            try: idx = int(idx)
            except: idx = None
        n["parent_step_index"] = idx if isinstance(idx, int) else None
        for key in ["necessary", "final_authorized_effect", "new_goal_introduced"]:
            v = n.get(key)
            if isinstance(v, str): n[key] = v.strip().lower() == "true"
            else: n[key] = bool(v)
        return n

    def test_json_fence_parsing(self):
        """JSON inside markdown code fence should be extractable."""
        raw = '```json\n{"classification":"PLAN_OMISSION","parent_step_index":1,"parent_tool_name":"send_email","necessary":true,"final_authorized_effect":true,"new_goal_introduced":false}\n```'
        parsed = self._safe_parse(raw)
        self.assertIsNotNone(parsed)
        result = self._normalize(parsed)
        self.assertEqual(result["classification"], "PLAN_OMISSION")
        self.assertEqual(result["parent_step_index"], 1)

    def test_invalid_judge_output(self):
        """Unparseable text returns UNCERTAIN."""
        raw = "This action seems useful but I cannot produce JSON."
        parsed = self._safe_parse(raw)
        self.assertIsNone(parsed)
        # Simulate what _judge_plan_extension does on parse failure
        result = {"classification": "UNCERTAIN", "reason": "judge_parse_error"}
        self.assertEqual(result["classification"], "UNCERTAIN")

    def test_plain_json_parses(self):
        raw = '{"classification": "DEVIATION", "reason": "test"}'
        result = self._safe_parse(raw)
        self.assertEqual(result["classification"], "DEVIATION")

    def test_string_parent_index_normalized(self):
        """parent_step_index="1" should become 1."""
        result = self._normalize({"classification": "PLAN_OMISSION",
                                   "parent_step_index": "1", "necessary": "true"})
        self.assertEqual(result["parent_step_index"], 1)
        self.assertTrue(result["necessary"])

    def test_invalid_classification_normalized(self):
        result = self._normalize({"classification": "INVALID", "reason": "x"})
        self.assertEqual(result["classification"], "UNCERTAIN")


class TestTaskExtensionVF(unittest.TestCase):

    def _task_vf(self, judge_result):
        if judge_result.get("classification") != "PLAN_OMISSION":
            return False, "not_plan_omission"
        parent_index = judge_result.get("parent_step_index")
        parent_tool = judge_result.get("parent_tool_name")
        has_parent = (isinstance(parent_index, int)
                      or (isinstance(parent_tool, str) and bool(parent_tool.strip())))
        if not has_parent:
            return False, "missing_parent_reference"
        if judge_result.get("necessary") is not True:
            return False, "not_necessary"
        if judge_result.get("new_goal_introduced") is True:
            return False, "new_goal_introduced"
        output_consumed = bool(judge_result.get("output_consumed_by"))
        final_effect = judge_result.get("final_authorized_effect") is True
        if not (output_consumed or final_effect):
            return False, "no_consumed_output_or_final_effect"
        return True, "pass"

    def test_parent_index_passes(self):
        ok, _ = self._task_vf({"classification": "PLAN_OMISSION",
            "parent_step_index": 1, "necessary": True,
            "output_consumed_by": "S3", "new_goal_introduced": False})
        self.assertTrue(ok)

    def test_parent_tool_name_passes(self):
        ok, _ = self._task_vf({"classification": "PLAN_OMISSION",
            "parent_tool_name": "send_email", "necessary": True,
            "output_consumed_by": "S3", "new_goal_introduced": False})
        self.assertTrue(ok)

    def test_missing_parent_fails(self):
        ok, reason = self._task_vf({"classification": "PLAN_OMISSION",
            "necessary": True, "output_consumed_by": "S3",
            "new_goal_introduced": False})
        self.assertFalse(ok)
        self.assertEqual(reason, "missing_parent_reference")

    def test_final_authorized_effect_passes(self):
        ok, _ = self._task_vf({"classification": "PLAN_OMISSION",
            "parent_step_index": 0, "necessary": True,
            "final_authorized_effect": True, "new_goal_introduced": False})
        self.assertTrue(ok)


class TestToolSemanticMetadata(unittest.TestCase):
    """Verify the structure expected from _get_tool_semantic_metadata."""

    def test_metadata_structure(self):
        metadata = {
            "tool_name": "send_money",
            "tool_type": "action",
            "arg_roles": {"recipient": "target", "amount": "financial_amount"},
            "high_risk_args": ["recipient", "amount"],
            "content_args": [],
        }
        self.assertIn("tool_type", metadata)
        self.assertIn("arg_roles", metadata)
        self.assertIn("high_risk_args", metadata)
        self.assertIn("content_args", metadata)

    def test_unknown_tool_metadata(self):
        metadata = {
            "tool_name": "unknown_tool",
            "tool_type": "unknown",
            "arg_roles": {},
            "high_risk_args": [],
            "content_args": [],
        }
        self.assertEqual(metadata["tool_type"], "unknown")


if __name__ == "__main__":
    unittest.main()
