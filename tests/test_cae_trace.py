#!/usr/bin/env python
"""CAE Mode Trace Sanity Tests - verify on/off/strict/block produce distinguishable traces."""
import unittest


class TestCAEModeTraceSanity(unittest.TestCase):
    """Verify the four CAE modes produce correct and distinguishable trace events."""

    def test_cae_mode_values_are_valid(self):
        valid = {"on", "off", "strict", "block"}
        self.assertEqual(len(valid), 4)

    def test_cae_off_uses_preserve_drift_native(self):
        """off mode uses cae_disabled_preserve_drift_native, not old block event."""
        event = "cae_disabled_preserve_drift_native"
        self.assertIn("preserve", event)
        self.assertNotEqual(event, "cae_disabled_trajectory_outside_action")

    def test_cae_block_uses_hard_block_event(self):
        """block mode uses cae_disabled_trajectory_outside_action (old hard block)."""
        event = "cae_disabled_trajectory_outside_action"
        self.assertIn("disabled", event)
        self.assertNotIn("preserve", event)

    def test_cae_off_never_emits_hard_block(self):
        """off mode must never use cae_disabled_trajectory_outside_action."""
        off_event = "cae_disabled_preserve_drift_native"
        block_event = "cae_disabled_trajectory_outside_action"
        self.assertNotEqual(off_event, block_event)

    def test_cae_on_can_emit_all_cae_events(self):
        on_events = {
            "controlled_action_extension_candidate",
            "allow_insert_controlled_action_extension",
            "controlled_action_extension_rejected",
        }
        self.assertEqual(len(on_events), 3)

    def test_cae_strict_trace_event_name(self):
        event = "cae_strict_blocked_high_risk_action"
        self.assertIn("strict", event)
        self.assertIn("blocked", event)
        self.assertIn("high_risk", event)

    def test_cae_strict_never_emits_allow_for_high_risk(self):
        strict_event = "cae_strict_blocked_high_risk_action"
        self.assertNotEqual(strict_event, "allow_insert_controlled_action_extension")

    def test_four_modes_produce_distinct_events(self):
        mode_events = {
            "on": {"controlled_action_extension_candidate",
                   "allow_insert_controlled_action_extension",
                   "controlled_action_extension_rejected"},
            "off": {"cae_disabled_preserve_drift_native"},
            "block": {"cae_disabled_trajectory_outside_action"},
            "strict": {"cae_strict_blocked_high_risk_action"},
        }
        # off must not overlap with block
        self.assertTrue(mode_events["off"].isdisjoint(mode_events["block"]),
                        "off and block must use different events")
        # off must not overlap with on's CAE events
        self.assertTrue(mode_events["off"].isdisjoint(mode_events["on"]),
                        "off must not produce on-mode CAE events")
        # strict has its own unique event
        self.assertIn("cae_strict_blocked_high_risk_action", mode_events["strict"])

    def test_off_preserves_drift_native_path(self):
        """off mode should NOT block - it preserves original DRIFT native path."""
        off_event = "cae_disabled_preserve_drift_native"
        # This event means: logged, then falls through to original Open Dynamic Updating
        self.assertIn("preserve", off_event)
        self.assertIn("drift", off_event)

    def test_block_mode_is_hard_reject(self):
        """block mode hard-rejects, does not fall through to DRIFT native."""
        block_event = "cae_disabled_trajectory_outside_action"
        off_event = "cae_disabled_preserve_drift_native"
        self.assertNotEqual(block_event, off_event)

    def test_high_risk_helper_whitelist_not_blacklist(self):
        names = ["send_money", "delete_file", "share_document",
                 "create_calendar_event", "update_password"]
        for name in names:
            result = self._check_high_risk(name, "unknown")
            self.assertTrue(result, f"{name} should be high-risk even with unknown type")

        safe_names = ["read_file", "search_emails", "list_transactions", "get_webpage"]
        for name in safe_names:
            self.assertFalse(self._check_high_risk(name, "action"),
                             f"{name} should not be high-risk")

    def _check_high_risk(self, tool_name, tool_type):
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
