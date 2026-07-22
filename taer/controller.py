"""TAER Controller - backbone init, matching, overlay lifecycle."""
import json
from .models import BackboneStep, RepairStep, TAERState


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
            obligation += " with " + ", ".join(str(k) for k in req_params)

        step = BackboneStep(
            step_id=step_id,
            original_index=i,
            tool_name=tool_name,
            obligation=obligation,
            required_parameters=req_params if isinstance(req_params, dict) else {},
            conditions=conditions if isinstance(conditions, dict) else {},
        )
        state.backbone_order.append(step_id)
        state.backbone_steps[step_id] = step

    state.initialized = True
    return state


def match_candidate_to_backbone(tool_name, tool_args, state):
    """Match candidate action to an unfinished backbone step. Returns step_id or None."""
    candidates = []
    for sid in state.backbone_order:
        step = state.backbone_steps[sid]
        if step.status in ("done", "failed"):
            continue
        if step.tool_name == tool_name:
            candidates.append(sid)

    if len(candidates) == 1:
        return candidates[0]
    if len(candidates) == 0:
        return None
    # Multiple matches - try to disambiguate by args match
    for sid in candidates:
        step = state.backbone_steps[sid]
        req = step.required_parameters or {}
        if req and tool_args:
            match_count = sum(1 for k in req if k in tool_args)
            if match_count >= len(req) * 0.5:
                return sid
    return None


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
    """Mark a repair as done."""
    if repair_id in state.repair_steps:
        state.repair_steps[repair_id].status = "done"
        state.repair_success_count += 1
        consumer_id = state.repair_steps[repair_id].consumer_step_id
        if consumer_id and consumer_id in state.backbone_steps:
            state.backbone_steps[consumer_id].status = "done"


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
