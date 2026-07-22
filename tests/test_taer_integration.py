import sys
import unittest
from unittest.mock import MagicMock, patch

from utils import get_args


def _mock_import_dependencies():
    import types

    def _mock_package(package_path, children):
        parts = package_path.split(".")
        for i in range(1, len(parts) + 1):
            parent_path = ".".join(parts[:i])
            if parent_path not in sys.modules:
                sys.modules[parent_path] = types.ModuleType(parent_path)
        for child in children:
            child_full = f"{package_path}.{child}"
            if child_full not in sys.modules:
                m = types.ModuleType(child_full)
                sys.modules[child_full] = m
            setattr(sys.modules[package_path], child, sys.modules[child_full])

    _mock_package("agentdojo", [
        "logging", "ast_utils", "types", "task_suite", "attacks",
        "agent_pipeline", "base_tasks", "functions_runtime", "yaml_loader",
    ])
    _mock_package("agentdojo.task_suite", ["load_suites", "task_suite"])
    _mock_package("agentdojo.attacks", ["attack_registry"])
    _mock_package("agentdojo.agent_pipeline", [
        "base_pipeline_element", "errors", "llms",
    ])
    _mock_package("agentdojo.agent_pipeline.llms", ["prompting_llm"])
    _mock_package("openai", ["types"])
    _mock_package("openai.types", ["chat"])
    _mock_package("google", ["genai"])
    _mock_package("google.genai", ["types"])

    for mod_name in ["source_flow", "json_repair"]:
        if mod_name not in sys.modules:
            sys.modules[mod_name] = types.ModuleType(mod_name)

    import openai.types.chat
    openai.types.chat.ChatCompletionMessageParam = MagicMock

    import agentdojo.logging
    agentdojo.logging.Logger = MagicMock
    import agentdojo.agent_pipeline.base_pipeline_element
    agentdojo.agent_pipeline.base_pipeline_element.BasePipelineElement = MagicMock
    import agentdojo.agent_pipeline.errors
    agentdojo.agent_pipeline.errors.AbortAgentError = type("AbortAgentError", (Exception,), {})
    import agentdojo.agent_pipeline.llms.prompting_llm
    agentdojo.agent_pipeline.llms.prompting_llm.PromptingLLM = MagicMock
    agentdojo.agent_pipeline.llms.prompting_llm.InvalidModelOutputError = type("InvalidModelOutputError", (Exception,), {})
    import agentdojo.functions_runtime
    agentdojo.functions_runtime.EmptyEnv = MagicMock
    agentdojo.functions_runtime.Env = MagicMock
    agentdojo.functions_runtime.Function = MagicMock
    agentdojo.functions_runtime.FunctionCall = MagicMock
    agentdojo.functions_runtime.FunctionsRuntime = MagicMock
    agentdojo.functions_runtime.TaskEnvironment = MagicMock
    import agentdojo.types
    agentdojo.types.ChatAssistantMessage = MagicMock
    agentdojo.types.ChatMessage = MagicMock
    agentdojo.types.MessageContentBlock = MagicMock
    agentdojo.types.get_text_content_as_str = MagicMock
    import agentdojo.ast_utils
    agentdojo.ast_utils.ASTParsingError = type("ASTParsingError", (Exception,), {})
    agentdojo.ast_utils.create_python_function_from_tool_call = MagicMock()
    agentdojo.ast_utils.parse_tool_calls_from_python_function = MagicMock()
    import agentdojo.task_suite.load_suites
    agentdojo.task_suite.load_suites.get_suite = MagicMock()
    agentdojo.task_suite.load_suites.get_suites = MagicMock()
    import agentdojo.task_suite.task_suite
    agentdojo.task_suite.task_suite.TaskSuite = MagicMock
    agentdojo.task_suite.task_suite.model_output_from_messages = MagicMock()
    agentdojo.task_suite.task_suite.functions_stack_trace_from_messages = MagicMock()
    import agentdojo.attacks.attack_registry
    agentdojo.attacks.attack_registry.ATTACKS = {}
    agentdojo.attacks.attack_registry.load_attack = MagicMock()
    import agentdojo.base_tasks
    agentdojo.base_tasks.BaseUserTask = MagicMock
    agentdojo.base_tasks.BaseInjectionTask = MagicMock
    import agentdojo.yaml_loader
    agentdojo.yaml_loader.ImportLoader = MagicMock
    import agentdojo.agent_pipeline
    agentdojo.agent_pipeline.AgentPipeline = MagicMock
    agentdojo.agent_pipeline.InitQuery = MagicMock
    agentdojo.agent_pipeline.PromptingLLM = MagicMock
    agentdojo.agent_pipeline.ToolsExecutionLoop = MagicMock
    agentdojo.agent_pipeline.ToolsExecutor = MagicMock

    import source_flow
    source_flow.ContractHelper = MagicMock
    source_flow.FlowAwareValidator = MagicMock
    source_flow.FlowExpectationCompiler = MagicMock
    source_flow.FlowValidationDecision = MagicMock
    source_flow.SinkEvidenceResolver = MagicMock
    source_flow.SourceLabelStore = MagicMock
    source_flow.ValidationTraceEntry = MagicMock

    import json_repair
    json_repair.repair_json = lambda x: x

    import taer
    import taer.models
    import taer.controller


_mock_import_dependencies()

from taer.models import BackboneMatchResult, TAERBoundaryResult, TAERState


class TestCLIParsing(unittest.TestCase):
    def test_taer_mode_off_default(self):
        args = get_args(argv=[])
        self.assertEqual(args.taer_mode, "off")

    def test_taer_mode_on(self):
        args = get_args(argv=["--taer_mode", "on"])
        self.assertEqual(args.taer_mode, "on")

    def test_taer_mode_off_explicit(self):
        args = get_args(argv=["--taer_mode", "off"])
        self.assertEqual(args.taer_mode, "off")

    def test_taer_mode_invalid_rejected(self):
        with self.assertRaises(SystemExit):
            get_args(argv=["--taer_mode", "invalid"])


class TestTaerRouting(unittest.TestCase):
    def _make_llm(self, taer_mode):
        mock_args = MagicMock()
        mock_args.taer_mode = taer_mode
        mock_args.dynamic_validation = True
        mock_args.build_constraints = False
        mock_args.injection_isolation = False
        mock_args.adaptive_attack = False
        mock_args.source_flow_log = None
        mock_args.source_flow_validation = False
        mock_args.seed = 98
        mock_args.benchmark_version = "v1.2"
        mock_args.suites = "banking"
        mock_args.model = "gpt-4o-mini-2024-07-18"

        mock_client = MagicMock()
        mock_client.total_tokens = 0
        mock_client.llm_run = MagicMock(return_value='{"relation": "NEW_GOAL", "consumer_step_id": null, "missing_condition": null, "provides": "", "expected_effect": null, "control_sources": [], "argument_sources": {}, "scope_delta": "NONE", "risk": "READ_ONLY", "confidence": "LOW", "reason": "test"}')

        mock_store = MagicMock()
        mock_store.records = []

        mock_contracts = MagicMock()

        llm = MagicMock()
        llm.args = mock_args
        llm.client = mock_client
        llm.logger = MagicMock()
        llm.function_trajectory = ["read_file"]
        llm.achieved_function_trajectory = []
        llm.node_checklist = "[]"
        llm.tool_permissions = {}
        llm._MAX_ATTEMPTS = 3
        llm.source_label_store = mock_store
        llm.source_flow_contract_helper = mock_contracts
        llm.taer_mode_enabled = MagicMock(return_value=(taer_mode == "on"))
        llm.taer_state = TAERState() if taer_mode == "on" else None

        llm._run_original_drift_deviation_validation = MagicMock(
            return_value=(None, {"role": "assistant", "content": "", "tool_calls": []})
        )
        llm._is_action_tool = MagicMock(return_value=True)
        llm._is_read_tool = MagicMock(return_value=False)
        llm._source_flow_sanitize_rejected_output = MagicMock()
        llm._tool_call_to_str = MagicMock(
            return_value={
                "id": "call_1",
                "type": "function",
                "function": {"name": "send_money", "arguments": '{"amount": 100}'},
            }
        )
        llm.user_approval_request = MagicMock(return_value=False)

        if taer_mode == "on":
            step = MagicMock()
            step.tool_name = "send_money"
            step.status = "ready"
            step.required_parameters = {"amount": 100}
            step.obligation = "send_money with amount=100"
            llm.taer_state.backbone_order = ["s000"]
            llm.taer_state.backbone_steps = {"s000": step}
            llm.taer_state.initialized = True

        return llm

    def _make_output(self, function_name="send_money", args=None):
        if args is None:
            args = {"amount": 100}
        mock_tc = MagicMock()
        mock_tc.function = function_name
        mock_tc.args = args
        return {
            "role": "assistant",
            "content": f"<function_thought>test</function_thought>\n<function_call>[{function_name}(amount=100)]</function_call>",
            "tool_calls": [mock_tc],
        }

    @patch("DRIFTLLM.match_candidate_to_backbone")
    @patch("DRIFTLLM.check_taer_boundary")
    def test_taer_mode_off_skips_match_and_boundary(self, mock_boundary, mock_matcher):
        from DRIFTLLM import DRIFTLLM
        llm = self._make_llm("off")
        llm._is_action_tool.return_value = True

        DRIFTLLM.trajectory_constraint_validation(
            llm, ["send_money"], self._make_output(), "Send $100", [{"role": "user", "content": "Send $100"}]
        )

        mock_matcher.assert_not_called()
        mock_boundary.assert_not_called()
        llm._run_original_drift_deviation_validation.assert_called_once()

    @patch("DRIFTLLM.match_candidate_to_backbone")
    @patch("DRIFTLLM.check_taer_boundary")
    def test_taer_unique_ready_match_calls_matcher_not_boundary(self, mock_boundary, mock_matcher):
        from DRIFTLLM import DRIFTLLM
        llm = self._make_llm("on")
        llm._is_action_tool.return_value = True
        mock_matcher.return_value = BackboneMatchResult(
            status="UNIQUE", step_id="s000", candidate_step_ids=["s000"],
            reason="single_match", is_currently_ready=True,
            parameter_compatibility="MATCH",
        )

        DRIFTLLM.trajectory_constraint_validation(
            llm, ["send_money"], self._make_output(), "Send $100", [{"role": "user", "content": "Send $100"}]
        )

        mock_matcher.assert_called_once()
        mock_boundary.assert_not_called()
        llm._run_original_drift_deviation_validation.assert_not_called()

    @patch("DRIFTLLM.match_candidate_to_backbone")
    @patch("DRIFTLLM.check_taer_boundary")
    def test_taer_non_match_enters_anchor_analyzer(self, mock_boundary, mock_matcher):
        from DRIFTLLM import DRIFTLLM
        llm = self._make_llm("on")
        llm._is_action_tool.return_value = True
        mock_matcher.return_value = BackboneMatchResult(
            status="NONE", step_id=None, candidate_step_ids=[],
            reason="no_match", is_currently_ready=False,
            parameter_compatibility="UNKNOWN",
        )

        DRIFTLLM.trajectory_constraint_validation(
            llm, ["send_money"], self._make_output(), "Send $100", [{"role": "user", "content": "Send $100"}]
        )

        mock_matcher.assert_called_once()
        self.assertTrue(llm.client.llm_run.called, "TAER anchor analyzer should call LLM")

    @patch("DRIFTLLM.match_candidate_to_backbone")
    @patch("DRIFTLLM.check_taer_boundary")
    def test_taer_boundary_guard_called_before_allow(self, mock_boundary, mock_matcher):
        from DRIFTLLM import DRIFTLLM
        llm = self._make_llm("on")
        llm._is_action_tool.return_value = True
        mock_matcher.return_value = BackboneMatchResult(
            status="NONE", step_id=None, candidate_step_ids=[],
            reason="no_match", is_currently_ready=False,
            parameter_compatibility="UNKNOWN",
        )
        llm.client.llm_run.return_value = json.dumps({
            "relation": "REPAIR",
            "consumer_step_id": "s000",
            "missing_condition": "account_id",
            "provides": "repair",
            "expected_effect": "read account",
            "control_sources": ["get_webpage"],
            "argument_sources": {"amount": ["read_file"]},
            "scope_delta": "NONE",
            "risk": "READ_ONLY",
            "confidence": "MEDIUM",
            "reason": "repair test",
        })
        mock_boundary.return_value = TAERBoundaryResult(
            passed=True, explicit_violation=False, violation_type=None,
            checked_authority_args={}, evidence_source_ids=[], reason="boundary_pass",
        )

        DRIFTLLM.trajectory_constraint_validation(
            llm, ["send_money"], self._make_output(), "Send $100", [{"role": "user", "content": "Send $100"}]
        )

        mock_matcher.assert_called_once()
        mock_boundary.assert_called_once()
        llm._run_original_drift_deviation_validation.assert_not_called()

    @patch("DRIFTLLM.match_candidate_to_backbone")
    @patch("DRIFTLLM.check_taer_boundary")
    def test_taer_new_goal_rejected_without_boundary(self, mock_boundary, mock_matcher):
        from DRIFTLLM import DRIFTLLM
        llm = self._make_llm("on")
        llm._is_action_tool.return_value = True
        mock_matcher.return_value = BackboneMatchResult(
            status="NONE", step_id=None, candidate_step_ids=[],
            reason="no_match", is_currently_ready=False,
            parameter_compatibility="UNKNOWN",
        )

        result = DRIFTLLM.trajectory_constraint_validation(
            llm, ["send_money"], self._make_output(), "Send $100", [{"role": "user", "content": "Send $100"}]
        )

        mock_matcher.assert_called_once()
        mock_boundary.assert_not_called()
        llm._run_original_drift_deviation_validation.assert_not_called()
        self.assertIsNotNone(result)

    @patch("DRIFTLLM.match_candidate_to_backbone")
    @patch("DRIFTLLM.check_taer_boundary")
    def test_taer_boundary_block_falls_back_to_drift(self, mock_boundary, mock_matcher):
        from DRIFTLLM import DRIFTLLM
        llm = self._make_llm("on")
        llm._is_action_tool.return_value = True
        mock_matcher.return_value = BackboneMatchResult(
            status="NONE", step_id=None, candidate_step_ids=[],
            reason="no_match", is_currently_ready=False,
            parameter_compatibility="UNKNOWN",
        )
        llm.client.llm_run.return_value = json.dumps({
            "relation": "REPAIR",
            "consumer_step_id": "s000",
            "missing_condition": "account_id",
            "provides": "repair",
            "expected_effect": "read account",
            "control_sources": [],
            "argument_sources": {},
            "scope_delta": "NONE",
            "risk": "READ_ONLY",
            "confidence": "LOW",
            "reason": "repair",
        })
        mock_boundary.return_value = TAERBoundaryResult(
            passed=False, explicit_violation=True,
            violation_type="injected_control_arg",
            checked_authority_args={}, evidence_source_ids=[], reason="blocked",
        )

        result = DRIFTLLM.trajectory_constraint_validation(
            llm, ["send_money"], self._make_output(), "Send $100", [{"role": "user", "content": "Send $100"}]
        )

        mock_matcher.assert_called_once()
        mock_boundary.assert_called_once()
        llm._run_original_drift_deviation_validation.assert_not_called()
        self.assertIsNotNone(result)

    @patch("DRIFTLLM.match_candidate_to_backbone")
    def test_taer_ambiguous_falls_back_to_drift(self, mock_matcher):
        from DRIFTLLM import DRIFTLLM
        llm = self._make_llm("on")
        llm._is_action_tool.return_value = True
        mock_matcher.return_value = BackboneMatchResult(
            status="NONE", step_id=None, candidate_step_ids=[],
            reason="no_match", is_currently_ready=False,
            parameter_compatibility="UNKNOWN",
        )
        llm.client.llm_run.return_value = json.dumps({
            "relation": "AMBIGUOUS",
            "consumer_step_id": None,
            "missing_condition": None,
            "provides": "",
            "expected_effect": None,
            "control_sources": [],
            "argument_sources": {},
            "scope_delta": "NONE",
            "risk": "READ_ONLY",
            "confidence": "LOW",
            "reason": "ambiguous test",
        })

        DRIFTLLM.trajectory_constraint_validation(
            llm, ["send_money"], self._make_output(), "Send $100", [{"role": "user", "content": "Send $100"}]
        )

        mock_matcher.assert_called_once()
        llm._run_original_drift_deviation_validation.assert_called_once()


import json


if __name__ == "__main__":
    unittest.main()
