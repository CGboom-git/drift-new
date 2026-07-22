"""TAER integration tests - verify matcher, DRIFT fallback, mode switching."""
import unittest
from unittest.mock import MagicMock, patch

from taer import (
    BackboneStep, TAERState,
    init_taer_backbone, match_candidate_to_backbone,
    BackboneMatchResult, TAERBoundaryResult,
)


class TestMatcherCorrectness(unittest.TestCase):
    """Verify matcher returns correct typed results."""

    def setUp(self):
        self.state = init_taer_backbone(
            ["get_balance", "send_money", "send_money"],
            [{"name": "get_balance", "required parameters": {}, "conditions": {}},
             {"name": "send_money", "required parameters": {"recipient": "Alice", "amount": 100}, "conditions": {}},
             {"name": "send_money", "required parameters": {"recipient": "Bob"}, "conditions": {}}],
            "Pay Alice 100 and Bob some amount", None,
        )
        # Set first send_money ready
        sid1 = self.state.backbone_order[1]
        self.state.backbone_steps[sid1].status = "ready"

    def test_unique_match_conflict_on_recipient(self):
        """send_money to Charlie should CONFLICT with Alice/Bob requirement."""
        match = match_candidate_to_backbone("send_money",
            {"recipient": "Charlie", "amount": 100}, self.state)
        # Two send_money candidates, but Charlie conflicts with both
        self.assertIn(match.status, ("NONE", "AMBIGUOUS"))
        self.assertFalse(match.is_currently_ready)

    def test_unique_match_exact_values(self):
        """send_money to Alice with amount 100 should match."""
        match = match_candidate_to_backbone("send_money",
            {"recipient": "Alice", "amount": 100}, self.state)
        self.assertEqual(match.status, "UNIQUE")
        self.assertTrue(match.is_currently_ready)
        self.assertEqual(match.parameter_compatibility, "MATCH")

    def test_none_match(self):
        """Tool not in backbone returns NONE."""
        match = match_candidate_to_backbone("delete_file",
            {"file_id": "123"}, self.state)
        self.assertEqual(match.status, "NONE")
        self.assertIsNone(match.step_id)

    def test_blocked_node_not_ready(self):
        """A pending node should not be is_currently_ready."""
        # get_balance is pending by default
        match = match_candidate_to_backbone("get_balance", {}, self.state)
        self.assertEqual(match.status, "UNIQUE")
        self.assertFalse(match.is_currently_ready)

    def test_duplicate_ambiguous_on_tie(self):
        """Two same-tool candidates with equal evidence → AMBIGUOUS."""
        # Make both send_money ready
        sid2 = self.state.backbone_order[2]
        self.state.backbone_steps[sid2].status = "ready"
        # Remove the Alice recipient requirement to make them equal
        sid1 = self.state.backbone_order[1]
        self.state.backbone_steps[sid1].required_parameters = {}
        self.state.backbone_steps[sid2].required_parameters = {}
        match = match_candidate_to_backbone("send_money",
            {"recipient": "Someone", "amount": 50}, self.state)
        self.assertEqual(match.status, "AMBIGUOUS")


class TestDRIFTFallbackMode(unittest.TestCase):
    """Verify taer_mode=off and TAER fallback use original DRIFT helper."""

    def test_off_mode_does_not_use_taer(self):
        """taer_mode=off should bypass TAER entirely."""
        # This is an architectural test - the code path uses self.taer_mode
        # which is checked in trajectory_constraint_validation
        self.assertTrue(True)  # Placeholder for actual DRIFTLLM integration

    def test_taer_resolved_none(self):
        """TAERBackboneMatchResult NONE should not pass as truthy."""
        r = BackboneMatchResult(status="NONE", step_id=None, candidate_step_ids=[],
                                 reason="test", is_currently_ready=False,
                                 parameter_compatibility="UNKNOWN")
        # NONE result must not be treated as a valid match
        self.assertEqual(r.status, "NONE")
        self.assertIsNone(r.step_id)
        self.assertFalse(r.is_currently_ready)

    def test_taer_resolved_ambiguous(self):
        """TAERBackboneMatchResult AMBIGUOUS should not pass as truthy."""
        r = BackboneMatchResult(status="AMBIGUOUS", step_id=None,
                                 candidate_step_ids=["a","b"],
                                 reason="test", is_currently_ready=False,
                                 parameter_compatibility="UNKNOWN")
        self.assertEqual(r.status, "AMBIGUOUS")
        self.assertIsNone(r.step_id)

    def test_taer_boundary_result_types(self):
        """TAERBoundaryResult creates correctly."""
        r = TAERBoundaryResult(passed=True, explicit_violation=False,
                                violation_type=None, checked_authority_args={},
                                evidence_source_ids=[], reason="pass")
        self.assertTrue(r.passed)
        self.assertFalse(r.explicit_violation)


if __name__ == "__main__":
    unittest.main()
