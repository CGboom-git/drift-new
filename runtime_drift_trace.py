"""Observational runtime-drift traces for offline experiment analysis.

This module deliberately does not participate in authorization or execution.
It only serializes state that the pipeline has already produced.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


SENSITIVE_ARG_NAMES = {
    "account", "account_id", "amount", "attachment", "attachments", "body",
    "channel", "destination", "email", "event_id", "file_id", "folder_id",
    "participants", "password", "path", "permission", "principal", "recipient",
    "recipients", "resource_id", "target", "url", "user", "user_id",
}
DRIFT_SOURCE_LABELS = {"injected_instruction", "unknown_origin", "model_generated"}


def _json_value(value: Any) -> Any:
    try:
        json.dumps(value)
        return value
    except (TypeError, ValueError):
        if hasattr(value, "model_dump"):
            return _json_value(value.model_dump())
        if hasattr(value, "dict"):
            return _json_value(value.dict())
        if hasattr(value, "__dict__"):
            return _json_value(vars(value))
        return repr(value)


def _parse_json(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return value


def _tool_call_parts(call: Any) -> tuple[str | None, dict, str | None]:
    if not isinstance(call, dict):
        call = _json_value(call)
    if not isinstance(call, dict):
        return None, {}, None
    function = call.get("function", {})
    call_id = call.get("id") or call.get("tool_call_id")
    if isinstance(function, dict):
        name = function.get("name")
        args = function.get("arguments", {})
    else:
        name = function
        args = call.get("args", call.get("arguments", {}))
    args = _parse_json(args)
    return name, args if isinstance(args, dict) else {"_raw": args}, call_id


def extract_runtime_actions(messages: list[dict]) -> list[dict]:
    actions: list[dict] = []
    by_id: dict[str, dict] = {}
    for message_index, message in enumerate(messages or []):
        if not isinstance(message, dict):
            continue
        if message.get("role") == "assistant":
            for call in message.get("tool_calls") or []:
                name, args, call_id = _tool_call_parts(call)
                if not name:
                    continue
                action = {
                    "step_index": len(actions),
                    "message_index": message_index,
                    "tool_call_id": call_id,
                    "tool_name": name,
                    "arguments": _json_value(args),
                    "execution_result": None,
                    "execution_error": None,
                }
                actions.append(action)
                if call_id:
                    by_id[str(call_id)] = action
        elif message.get("role") == "tool":
            call_id = message.get("tool_call_id") or message.get("id")
            action = by_id.get(str(call_id)) if call_id is not None else None
            if action is None:
                name, args, nested_id = _tool_call_parts(message.get("tool_call", {}))
                action = by_id.get(str(nested_id)) if nested_id is not None else None
                if action is None and name:
                    action = {
                        "step_index": len(actions), "message_index": message_index,
                        "tool_call_id": nested_id, "tool_name": name,
                        "arguments": _json_value(args), "execution_result": None,
                        "execution_error": None,
                    }
                    actions.append(action)
            if action is not None:
                action["execution_result"] = _json_value(message.get("content"))
                action["execution_error"] = _json_value(message.get("error"))
    for action in actions:
        action["executed"] = action["execution_result"] is not None and not action["execution_error"]
    return actions


def _validation_entries(llm: Any) -> list[dict]:
    store = getattr(llm, "source_label_store", None)
    entries = getattr(store, "validation_trace", []) if store is not None else []
    result = []
    for entry in entries:
        data = entry if isinstance(entry, dict) else vars(entry)
        if data.get("event") == "source_flow_action_validation":
            result.append(_json_value(data))
    return result


def _attach_provenance(actions: list[dict], entries: list[dict]) -> list[dict]:
    cursor = 0
    all_arguments = []
    for action in actions:
        match = None
        for index in range(cursor, len(entries)):
            details = entries[index].get("details", {})
            if details.get("tool_name") == action["tool_name"]:
                match, cursor = details, index + 1
                break
        validations = {v.get("arg_name"): v for v in (match or {}).get("arg_validations", [])}
        action_provenance = []
        for arg_name, value in action["arguments"].items():
            validation = validations.get(arg_name, {})
            sink_role = validation.get("sink_role")
            if arg_name.lower() not in SENSITIVE_ARG_NAMES and not sink_role:
                continue
            labels = validation.get("source_labels") or []
            entry = {
                "arg_name": arg_name,
                "value": _json_value(value),
                "sink_role": sink_role,
                "source_labels": labels,
                "origin_tools": validation.get("actual_origin_tools") or [],
                "origin_paths": validation.get("actual_origin_paths") or [],
                "derived_from_authorized_source": validation.get("derived_from_authorized_source"),
                "verification_decision": validation.get("decision") or (match or {}).get("decision"),
            }
            action_provenance.append(entry)
            all_arguments.append(entry)
        action["sensitive_argument_provenance"] = action_provenance
    return all_arguments


def build_runtime_drift_trace(llm: Any, messages: list[dict], case_id: dict) -> dict:
    plan = list(getattr(llm, "initial_function_trajectory", []) or [])
    actions = extract_runtime_actions(messages)
    for action in actions:
        index = action["step_index"]
        expected = plan[index] if index < len(plan) else None
        action["expected_tool_at_step"] = expected
        action["plan_match_status"] = "IN_PLAN_EXACT" if action["tool_name"] == expected else "OUT_OF_PLAN"
        action["tool_appears_elsewhere_in_plan"] = action["tool_name"] in plan

    provenance = _attach_provenance(actions, _validation_entries(llm))
    action_drift = any(a["plan_match_status"] == "OUT_OF_PLAN" for a in actions)
    provenance_drift = any(
        p["derived_from_authorized_source"] is False
        or bool(set(p["source_labels"]) & DRIFT_SOURCE_LABELS)
        for p in provenance
    )
    if action_drift and provenance_drift:
        drift_type = "MIXED_DRIFT"
    elif action_drift:
        drift_type = "OUT_OF_PLAN_DRIFT"
    elif provenance_drift:
        drift_type = "IN_PLAN_PROVENANCE_DRIFT"
    else:
        drift_type = "NO_DRIFT"

    summary = {
        "candidate_drift_type": drift_type,
        "classification_is_offline_heuristic": True,
        "planned_action_count": len(plan),
        "runtime_action_count": len(actions),
        "out_of_plan_action_count": sum(a["plan_match_status"] == "OUT_OF_PLAN" for a in actions),
        "sensitive_argument_count": len(provenance),
        "provenance_drift_count": sum(
            p["derived_from_authorized_source"] is False
            or bool(set(p["source_labels"]) & DRIFT_SOURCE_LABELS)
            for p in provenance
        ),
        "taer_decision_count": len(getattr(llm, "_runtime_drift_taer_events", []) or []),
    }
    return {
        "schema_version": "1.0",
        "record_type": "observational_runtime_drift_trace",
        "case_id": case_id,
        "initial_plan": {
            "tool_sequence": plan,
            "checklist": _json_value(_parse_json(getattr(llm, "initial_node_checklist", None))),
        },
        "runtime_actions": actions,
        "taer_runtime_decisions": _json_value(getattr(llm, "_runtime_drift_taer_events", []) or []),
        "summary": summary,
    }


def save_runtime_drift_trace(args: Any, llm: Any, result_file_path: Path,
                             messages: list[dict], case_id: dict, logger: Any):
    if not getattr(args, "runtime_drift_trace", False):
        return None, None
    trace = build_runtime_drift_trace(llm, messages, case_id)
    trace_dir = result_file_path.parent / "runtime_drift_trace"
    trace_dir.mkdir(parents=True, exist_ok=True)
    trace_path = trace_dir / f"{result_file_path.stem}.runtime_drift.json"
    with trace_path.open("w", encoding="utf-8") as file:
        json.dump(trace, file, ensure_ascii=False, indent=2)
    if logger:
        logger.info(f"Runtime-drift trace is saved at: {trace_path}")
    return str(trace_path), trace["summary"]
