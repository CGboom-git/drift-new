"""TAER Controller - backbone init, matching, overlay lifecycle."""
import json
import re
from .models import BackboneStep, RepairStep, TAERState, BackboneMatchResult, TAERBoundaryResult, ConditionState


def init_taer_backbone(initial_function_trajectory, initial_node_checklist, query, contract_helper):
    """Initialize immutable authorization backbone from initial plan."""
    state = TAERState()
    traj = initial_function_trajectory or []
    state.backbone_order = []
    state.backbone_steps = {}
    step_counter = 0

    if isinstance(initial_node_checklist, str):
        try:
            checklist = json.loads(initial_node_checklist)
        except Exception:
            checklist = []
    elif isinstance(initial_node_checklist, list):
        checklist = list(initial_node_checklist)
    else:
        checklist = []

    for i, tool_name in enumerate(traj):
        step_id = f"s{step_counter:03d}"
        step_counter += 1

        entry = checklist[i] if i < len(checklist) else {}
        if isinstance(entry, dict):
            req_params = entry.get("required parameters") or {}
            conditions = entry.get("conditions") or {}
        else:
            req_params = {}
            conditions = {}

        obligation = f"{tool_name}"
        if req_params:
            param_vals = []
            for k, v in (req_params if isinstance(req_params, dict) else {}).items():
                param_vals.append(f"{k}={v}")
            if param_vals:
                obligation += " with " + ", ".join(param_vals)
            else:
                obligation += " with " + ", ".join(str(k) for k in req_params)

        # Build authorized_effect from params and query
        auth_effect = {"tool": tool_name}
        if isinstance(req_params, dict):
            for k, v in req_params.items():
                if v is not None and v != "":
                    auth_effect[k] = v
        if isinstance(query, str):
            auth_effect["_task_query"] = query[:200]

        step = BackboneStep(
            step_id=step_id,
            original_index=i,
            tool_name=tool_name,
            obligation=obligation,
            authorized_effect=auth_effect,
            required_parameters=req_params if isinstance(req_params, dict) else {},
            conditions=conditions if isinstance(conditions, dict) else {},
        )
        state.backbone_order.append(step_id)
        state.backbone_steps[step_id] = step

    state.initialized = True
    return state


def match_candidate_to_backbone(tool_name, tool_args, state):
    """Match candidate to unfinished backbone step. Returns dict: {status, step_id, reason}."""
    candidates = []
    for sid in state.backbone_order:
        step = state.backbone_steps[sid]
        if step.status in ("done", "failed"):
            continue
        if step.tool_name == tool_name:
            candidates.append(sid)

    if len(candidates) == 1:
        return BackboneMatchResult(status="UNIQUE", step_id=candidates[0], candidate_step_ids=candidates, reason="single_match", is_currently_ready=True)

    if len(candidates) == 0:
        return BackboneMatchResult(status="NONE", step_id=None, candidate_step_ids=[], reason="no_match")

    # Disambiguate by parameter value matching
    best_sid = None
    best_score = 0
    for sid in candidates:
        step = state.backbone_steps[sid]
        score = 0
        req = step.required_parameters or {}
        if req and tool_args:
            for k, req_val in req.items():
                if req_val is not None and k in tool_args:
                    if str(tool_args[k]) == str(req_val):
                        score += 2  # exact value match
                    else:
                        score += 1  # key match only
        # Check authorized_effect values
        auth = step.authorized_effect or {}
        for k, v in auth.items():
            if k.startswith("_"):
                continue
            if k in (tool_args or {}):
                if str(tool_args[k]) == str(v):
                    score += 2
        if score > best_score:
            best_score = score
            best_sid = sid

    if best_sid and best_score >= len(candidates):
        return BackboneMatchResult(status="UNIQUE", step_id=best_sid, candidate_step_ids=list(candidates), reason=f"value_match_score_{best_score}", is_currently_ready=True)

    return BackboneMatchResult(status="AMBIGUOUS", step_id=None, candidate_step_ids=list(candidates), reason=f"multiple_matches_{len(candidates)}")


def create_repair_step(state, tool_name, tool_args, anchor_result):
    """Create a RepairStep from TAER anchor result."""
    rid = f"r{len(state.repair_steps):03d}"
    repair = RepairStep(
        repair_id=rid,
        tool_name=tool_name,
        tool_args=tool_args or {},
        relation=anchor_result.get("relation", "REPAIR"),
        consumer_step_id=anchor_result.get("consumer_step_id"),
        missing_condition=anchor_result.get("missing_condition"),
        provides=anchor_result.get("provides", ""),
        control_sources=anchor_result.get("control_sources", []),
        argument_sources=anchor_result.get("argument_sources", {}),
        scope_delta=anchor_result.get("scope_delta", "NONE"),
        risk=anchor_result.get("risk", "READ_ONLY"),
        confidence=anchor_result.get("confidence", "LOW"),
        expected_effect=anchor_result.get("expected_effect"),
    )
    state.repair_steps[rid] = repair
    return repair


def rollback_repair(state, repair_id):
    """Roll back a failed repair."""
    if repair_id in state.repair_steps:
        state.repair_steps[repair_id].status = "rolled_back"
        state.repair_rollback_count += 1


def commit_repair(state, repair_id):
    """Mark a repair as done. Satisfies a missing condition, does NOT complete the consumer."""
    if repair_id in state.repair_steps:
        repair = state.repair_steps[repair_id]
        repair.status = "done"
        state.repair_success_count += 1
        consumer_id = repair.consumer_step_id
        if consumer_id and consumer_id in state.backbone_steps:
            consumer = state.backbone_steps[consumer_id]
            # Mark condition satisfied
            if repair.missing_condition:
                consumer.condition_states[repair.missing_condition] = True
            # Set consumer ready only if all conditions satisfied
            if all(consumer.condition_states.values()) if consumer.condition_states else True:
                consumer.status = "ready"


def get_taer_metrics(state):
    """Return compact metrics dict."""
    return {
        "candidate_count": state.candidate_count,
        "direct_effect_count": state.direct_effect_count,
        "repair_count": state.repair_count,
        "probe_count": state.probe_count,
        "new_goal_count": state.new_goal_count,
        "ambiguous_count": state.ambiguous_count,
        "boundary_block_count": state.boundary_block_count,
        "fallback_count": state.fallback_count,
        "repair_success_count": state.repair_success_count,
        "repair_rollback_count": state.repair_rollback_count,
    }

def check_taer_boundary(tool_name, tool_args, anchor, consumer_step, source_records, contract_helper):
    """Minimal evidence boundary guard. Returns {passed, explicit_violation, violation_type, reason}."""
    authority_args = {"recipient", "recipients", "principal", "user", "account", "account_id",
                       "amount", "destination", "url", "file_id", "path", "resource_id",
                       "event_id", "channel", "participants", "target", "password"}
    non_authority = {"limit", "page", "sort", "order", "format", "count", "query", "syntax"}

    for arg_name, arg_val in (tool_args or {}).items():
        name_lower = arg_name.lower()
        if any(kw in name_lower for kw in non_authority):
            continue
        if any(kw in name_lower for kw in authority_args):
            # Check injected source
            for rec in (source_records or []):
                labels = set(getattr(rec, "source_labels", []) or [])
                if "injected_instruction" in labels:
                    rec_val = str(getattr(rec, "value", "") or "")
                    if rec_val and str(arg_val) in rec_val:
                        return TAERBoundaryResult(passed=False, explicit_violation=True,
                                 violation_type="injected_control_arg", checked_authority_args={arg_name: str(arg_val)}, evidence_source_ids=[], reason=f"{arg_name} sourced from injected instruction")

    # Check scope_delta against relation
    scope = anchor.get("scope_delta", "NONE")
    if scope in ("NEW_PRINCIPAL", "NEW_DESTINATION", "NEW_EFFECT"):
        return TAERBoundaryResult(passed=False, explicit_violation=True,
                 violation_type=f"scope_delta_{scope.lower()}",
                 checked_authority_args={},
                 evidence_source_ids=[],
                 reason=f"unauthorized {scope}")

    return TAERBoundaryResult(passed=True, explicit_violation=False, violation_type=None, checked_authority_args={}, evidence_source_ids=[], reason="boundary_pass")

