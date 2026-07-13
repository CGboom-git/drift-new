import unittest
from source_flow import (
    ContractHelper, FlowAwareValidator, FlowExpectationCompiler,
    SinkEvidenceResolver, SourceLabelStore, SinkSpec, FlowValidationDecision,
    ValidationTraceEntry,
)


class TestCAEHighRiskDetection(unittest.TestCase):
    def setUp(self):
        self.contracts = ContractHelper("contracts")
        self.validator = FlowAwareValidator()

    def _is_high_risk(self, tool_name, tool_type):
        if tool_type not in ("action", "write", "execute"):
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

    def test_send_money_is_high_risk(self):
        self.assertTrue(self._is_high_risk("send_money", "action"))

    def test_schedule_transaction_is_high_risk(self):
        self.assertTrue(self._is_high_risk("schedule_transaction", "action"))

    def test_create_calendar_event_is_high_risk(self):
        self.assertTrue(self._is_high_risk("create_calendar_event", "action"))

    def test_send_email_is_high_risk(self):
        self.assertTrue(self._is_high_risk("send_email", "action"))

    def test_delete_file_is_high_risk(self):
        self.assertTrue(self._is_high_risk("delete_file", "action"))

    def test_share_document_is_high_risk(self):
        self.assertTrue(self._is_high_risk("share_document", "action"))

    def test_read_file_is_not_high_risk(self):
        self.assertFalse(self._is_high_risk("read_file", "action"))

    def test_read_tool_is_not_high_risk(self):
        self.assertFalse(self._is_high_risk("search_emails", "read"))
        self.assertFalse(self._is_high_risk("get_webpage", "read"))

    def test_unknown_tool_is_not_high_risk(self):
        self.assertFalse(self._is_high_risk("unknown_tool", "unknown"))

    def test_transform_tool_is_not_high_risk(self):
        self.assertFalse(self._is_high_risk("parse_document", "transform"))


class TestCAEModeResolution(unittest.TestCase):
    def test_default_is_off(self):
        import sys
        sys.argv = ['test', '--source_flow_validation']
        from utils import get_args
        args = get_args()
        self.assertEqual(args.cae_mode, 'off')

    def test_controlled_action_extension_flag_sets_on(self):
        import sys
        sys.argv = ['test', '--source_flow_validation', '--controlled_action_extension']
        from utils import get_args
        args = get_args()
        self.assertEqual(args.cae_mode, 'on')

    def test_explicit_cae_mode_overrides(self):
        import sys
        sys.argv = ['test', '--source_flow_validation', '--controlled_action_extension', '--cae_mode', 'strict']
        from utils import get_args
        args = get_args()
        self.assertEqual(args.cae_mode, 'strict')

    def test_explicit_off(self):
        import sys
        sys.argv = ['test', '--source_flow_validation', '--cae_mode', 'off']
        from utils import get_args
        args = get_args()
        self.assertEqual(args.cae_mode, 'off')

    def test_explicit_on(self):
        import sys
        sys.argv = ['test', '--source_flow_validation', '--cae_mode', 'on']
        from utils import get_args
        args = get_args()
        self.assertEqual(args.cae_mode, 'on')

    def test_explicit_strict(self):
        import sys
        sys.argv = ['test', '--source_flow_validation', '--cae_mode', 'strict']
        from utils import get_args
        args = get_args()
        self.assertEqual(args.cae_mode, 'strict')

    def test_no_source_flow_validation_default(self):
        import sys
        sys.argv = ['test']
        from utils import get_args
        args = get_args()
        self.assertEqual(args.cae_mode, 'off')


if __name__ == "__main__":
    unittest.main()
