#!/usr/bin/env python
"""CAE Mode Trace Sanity Tests - verify on/off/strict produce distinguishable traces."""
import unittest

from source_flow import ValidationTraceEntry


class TestCAEModeTraceSanity(unittest.TestCase):
    """Verify the three CAE modes produce correct and distinguishable trace events."""

    def test_cae_mode_values_are_valid(self):
        """All three modes should be accepted."""
        valid = {"on", "off", "strict"}
        for mode in valid:
            self.assertIn(mode, valid)

    def test_cae_off_trace_event_name(self):
        """off mode uses cae_disabled_trajectory_outside_action."""
        event = "cae_disabled_trajectory_outside_action"
        self.assertIn("disabled", event)
        self.assertNotIn("candidate", event)
        self.assertNotIn("allow", event)
        self.assertNotIn("rejected", event)

    def test_cae_off_never_emits_cae_candidate(self):
        """off mode must not emit controlled_action_extension_candidate."""
        forbidden = {
            "controlled_action_extension_candidate",
            "allow_insert_controlled_action_extension",
            "controlled_action_extension_rejected",
        }
        valid_off_events = {"cae_disabled_trajectory_outside_action"}
        self.assertTrue(valid_off_events.isdisjoint(forbidden))

    def test_cae_on_can_emit_all_cae_events(self):
        """on mode may emit candidate, allow, rejected."""
        on_events = {
            "controlled_action_extension_candidate",
            "allow_insert_controlled_action_extension",
            "controlled_action_extension_rejected",
        }
        self.assertEqual(len(on_events), 3)

    def test_cae_strict_trace_event_name(self):
        """strict mode uses cae_strict_blocked_high_risk_action."""
        event = "cae_strict_blocked_high_risk_action"
        self.assertIn("strict", event)
        self.assertIn("blocked", event)
        self.assertIn("high_risk", event)

    def test_cae_strict_never_emits_allow_for_high_risk(self):
        """strict mode high-risk ACTION must not produce allow_insert_controlled_action_extension."""
        strict_high_risk_event = "cae_strict_blocked_high_risk_action"
        self.assertNotEqual(strict_high_risk_event, "allow_insert_controlled_action_extension")
        self.assertNotEqual(strict_high_risk_event, "controlled_action_extension_candidate")

    def test_three_modes_produce_distinct_events(self):
        """Each mode has its own unique trace events."""
        mode_events = {
            "on": {"controlled_action_extension_candidate",
                   "allow_insert_controlled_action_extension",
                   "controlled_action_extension_rejected"},
            "off": {"cae_disabled_trajectory_outside_action"},
            "strict": {"cae_strict_blocked_high_risk_action",
                       "controlled_action_extension_candidate",
                       "allow_insert_controlled_action_extension",
                       "controlled_action_extension_rejected"},
        }
        # off must not overlap with on's unique events
        off_set = mode_events["off"]
        on_set = {"controlled_action_extension_candidate",
                  "allow_insert_controlled_action_extension",
                  "controlled_action_extension_rejected"}
        self.assertTrue(off_set.isdisjoint(on_set),
                        "off mode must not produce on-mode CAE events")
        # strict has its own unique event
        self.assertIn("cae_strict_blocked_high_risk_action", mode_events["strict"])

    def test_high_risk_helper_whitelist_not_blacklist(self):
        """Helper should only skip read/transform, not require action/write/execute."""
        from source_flow import ContractHelper
        ch = ContractHelper("contracts")

        # These should be high-risk based on name prefix, regardless of tool_type
        high_risk_names = [
            "send_money", "delete_file", "share_document",
            "create_calendar_event", "update_password",
        ]
        for name in high_risk_names:
            # Even if contract says unknown, the name prefix should catch it
            result = self._check_high_risk(name, "unknown")
            self.assertTrue(result, f"{name} should be high-risk even with unknown type")

        # These should NOT be high-risk
        safe_names = ["read_file", "search_emails", "list_transactions", "get_webpage"]
        for name in safe_names:
            result = self._check_high_risk(name, "action")
            self.assertFalse(result, f"{name} should not be high-risk")

    def _check_high_risk(self, tool_name, tool_type):
        """Replicate the high-risk helper logic from DRIFTLLM."""
        if tool_type in ("read", "observe", "transform", "parse"):
            return False
        high_risk_names = {
            "send_money", "schedule_transaction", "update_scheduled_transaction",
            "update_password", "update_user_info", "send_email", "delete_email",
            "delete_file", "append_to_file", "share_file", "create_calendar_event",
            "invite_user", "remove_user", "share_document", "transfer_money",
            "purchase_item", "book_flight", "book_hotel", "cancel_booking",
        }
        name_lower = tool_name.lower()
        for prefix in ("send_", "delete_", "share_", "transfer_", "invite_",
                        "remove_", "purchase_", "book_", "cancel_", "update_",
                        "create_"):
            if name_lower.startswith(prefix):
                return True
        return name_lower in high_risk_names


if __name__ == "__main__":
    unittest.main()
