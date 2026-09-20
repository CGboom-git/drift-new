import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from runtime_drift_trace import build_runtime_drift_trace, save_runtime_drift_trace
from utils import get_args


def validation(tool, arg, labels, authorized):
    return SimpleNamespace(
        event="source_flow_action_validation",
        details={
            "tool_name": tool,
            "decision": "allow" if authorized else "reject",
            "arg_validations": [{
                "arg_name": arg,
                "sink_role": "recipient",
                "source_labels": labels,
                "actual_origin_tools": ["read_contacts"],
                "actual_origin_paths": ["contacts[0].email"],
                "derived_from_authorized_source": authorized,
                "decision": "allow" if authorized else "reject",
            }],
        },
    )


def fake_llm(plan, traces=None):
    return SimpleNamespace(
        initial_function_trajectory=plan,
        initial_node_checklist='[{"name":"send_email"}]',
        source_label_store=SimpleNamespace(validation_trace=traces or []),
        _runtime_drift_taer_events=[],
    )


def messages(tool="send_email", recipient="safe@example.com"):
    return [
        {"role": "assistant", "tool_calls": [{
            "id": "c1", "function": tool, "args": {"recipients": [recipient], "body": "hello"},
        }]},
        {"role": "tool", "tool_call_id": "c1", "content": "ok", "error": None},
    ]


class RuntimeDriftTraceTests(unittest.TestCase):
    def test_default_flag_is_disabled(self):
        self.assertFalse(get_args(argv=[]).runtime_drift_trace)
        self.assertTrue(get_args(argv=["--runtime_drift_trace"]).runtime_drift_trace)

    def test_no_drift(self):
        trace = build_runtime_drift_trace(
            fake_llm(["send_email"], [validation("send_email", "recipients", ["user_explicit"], True)]),
            messages(), {"suite_name": "slack"},
        )
        self.assertEqual(trace["summary"]["candidate_drift_type"], "NO_DRIFT")
        self.assertTrue(trace["runtime_actions"][0]["executed"])

    def test_all_candidate_drift_classes(self):
        provenance = [validation("send_email", "recipients", ["injected_instruction"], False)]
        in_plan = build_runtime_drift_trace(fake_llm(["send_email"], provenance), messages(), {})
        out_plan = build_runtime_drift_trace(fake_llm(["share_file"]), messages(), {})
        mixed = build_runtime_drift_trace(fake_llm(["share_file"], provenance), messages(), {})
        self.assertEqual(in_plan["summary"]["candidate_drift_type"], "IN_PLAN_PROVENANCE_DRIFT")
        self.assertEqual(out_plan["summary"]["candidate_drift_type"], "OUT_OF_PLAN_DRIFT")
        self.assertEqual(mixed["summary"]["candidate_drift_type"], "MIXED_DRIFT")

    def test_disabled_writer_has_no_side_effect(self):
        with tempfile.TemporaryDirectory() as directory:
            result = Path(directory) / "none.json"
            path, summary = save_runtime_drift_trace(
                SimpleNamespace(runtime_drift_trace=False), fake_llm([]), result, [], {}, None,
            )
            self.assertIsNone(path)
            self.assertIsNone(summary)
            self.assertFalse((result.parent / "runtime_drift_trace").exists())

    def test_writer_uses_sibling_runtime_drift_trace_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            result = Path(directory) / "none" / "none.json"
            path, summary = save_runtime_drift_trace(
                SimpleNamespace(runtime_drift_trace=True), fake_llm([]), result, [], {}, None,
            )
            self.assertEqual(Path(path).parent.name, "runtime_drift_trace")
            self.assertEqual(Path(path).name, "none.runtime_drift.json")
            self.assertEqual(json.loads(Path(path).read_text(encoding="utf-8"))["summary"], summary)


if __name__ == "__main__":
    unittest.main()
