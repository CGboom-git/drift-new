"""Create an offline authoring inventory for complete AgentDojo RCVR scope.

This script is deliberately not imported by the online runner. Ground-truth
tool calls are recorded only as an authoring reference for reviewers; runtime
constraint compilation must never read them.
"""
from __future__ import annotations

import hashlib
import inspect
import json
from pathlib import Path
import sys


REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from agentdojo.task_suite.load_suites import get_suite
from rcdc.constraint_spec import query_constraints


OUT = REPO / "experiments" / "rcdc" / "task_spec_inventory_v1.json"
SUITES = ("banking", "slack", "travel", "workspace")


def call_view(call):
    return {
        "tool": call.function,
        "arguments": call.args,
        "placeholder_arguments": getattr(call, "placeholder_args", None),
    }


def main():
    tasks = []
    for suite_name in SUITES:
        suite = get_suite("v1.2", suite_name)
        contracts = json.loads((REPO / "contracts" / "agentdojo_ifc_global_tool_contract_semantic_review_gpt55.json").read_text())
        base_environment = suite.load_and_inject_default_environment({})
        tools = {tool.name: tool.parameters.model_json_schema() for tool in suite.tools}
        for task_id, task in sorted(suite.user_tasks.items()):
            environment = task.init_environment(base_environment.model_copy(deep=True))
            reference_calls = [call_view(call) for call in task.ground_truth(environment)]
            action_tools = [call["tool"] for call in reference_calls
                            if not str(contracts["tools"].get(call["tool"], {}).get("tool_type", "")).startswith("READ")]
            existing = query_constraints(task.PROMPT)
            tasks.append({
                "suite": suite_name,
                "user_task_id": task_id,
                "prompt": task.PROMPT,
                "potential_case_count": len(suite.injection_tasks) + 1,
                "ground_truth_authoring_reference": reference_calls,
                "ground_truth_tool_sequence": [call["tool"] for call in reference_calls],
                "ground_truth_action_tool_sequence": action_tools,
                "current_compiler_family": existing[-1] if existing else None,
                "current_compiler_matches": existing is not None,
                "task_class_source": inspect.getsource(type(task)),
                "tool_schemas": {call["tool"]: tools[call["tool"]] for call in reference_calls},
                "spec_status": ("verified_existing" if existing else
                                "read_only_no_rcvr_gate" if not action_tools else "needs_semantic_spec"),
            })
    payload = {
        "version": 1,
        "purpose": "offline task-spec authoring inventory; never load from online RCVR runtime",
        "benchmark_version": "v1.2",
        "task_count": len(tasks),
        "potential_case_count": sum(task["potential_case_count"] for task in tasks),
        "tasks": tasks,
    }
    rendered = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    OUT.write_text(rendered, encoding="utf-8")
    print(json.dumps({
        "task_count": len(tasks),
        "potential_case_count": payload["potential_case_count"],
        "existing_compiler_tasks": sum(task["current_compiler_matches"] for task in tasks),
        "sha256": hashlib.sha256(rendered.encode()).hexdigest(),
        "output": str(OUT.relative_to(REPO)),
    }))


if __name__ == "__main__":
    main()
