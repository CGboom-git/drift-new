"""Deterministic TAER facts exposed as RCVR validator evidence.

This module deliberately does not dispatch calls, mutate a trajectory, or
create repairs.  It translates immutable TAER-backbone facts into a small
three-valued contribution that the RCVR Runtime Validator can merge with
binding and SourceFlow witnesses.
"""
from dataclasses import dataclass, field
import json

from taer import check_taer_boundary, match_candidate_to_backbone
from taer import check_params_against_consumer
from prompts import TAER_ANCHOR_PROMPT


@dataclass(frozen=True)
class TAERPolicyEvidence:
    verdict: str
    reason: str
    consumer_step_id: str | None = None
    anchor: dict = field(default_factory=dict)


def assess_deterministic_candidate(tool_name, tool_args, state, *, boundary_enabled,
                                   source_records, contract_helper, explicit_entities):
    """Return only facts established by the immutable TAER backbone.

    ``None`` means that relation classification still needs the later TAER
    anchor analysis; it must not be treated as a negative authorization.
    """
    if state is None or not getattr(state, 'initialized', False):
        return None
    match = match_candidate_to_backbone(tool_name, tool_args, state)
    if match.parameter_compatibility == 'CONFLICT':
        return TAERPolicyEvidence('INVALID', 'taer_backbone_parameter_conflict', match.step_id)
    if (match.status == 'UNIQUE' and match.is_currently_ready
            and match.parameter_compatibility == 'MATCH'):
        return TAERPolicyEvidence('VALID', 'taer_backbone_direct_effect', match.step_id)
    # A boundary check is meaningful only when the tool is related to a known
    # consumer.  It is an explicit conflict, never an evidence-gap repair.
    if boundary_enabled and match.step_id:
        anchor = {'scope_delta': 'NONE', 'consumer_step_id': match.step_id}
        boundary = check_taer_boundary(tool_name, tool_args, anchor, match.step_id,
                                       source_records, contract_helper, explicit_entities)
        if not boundary.passed:
            return TAERPolicyEvidence('INVALID', f'taer_boundary:{boundary.reason}', match.step_id)
    return None


def analyze_anchor_candidate(llm, query, tool_name, tool_args):
    """Classify an out-of-plan candidate without changing execution state.

    This is the migration seam for TAER's former final-decision branch.  The
    returned fact is consumed by RCVR; no authorization, trajectory extension,
    pending repair, or tool execution happens here.
    """
    state = getattr(llm, 'taer_state', None)
    if state is None or not getattr(state, 'initialized', False):
        return None
    match = match_candidate_to_backbone(tool_name, tool_args, state)
    context = {
        'user_query': str(query)[:500],
        'backbone_steps': [
            {'step_id': sid, 'tool_name': step.tool_name, 'obligation': step.obligation}
            for sid in state.backbone_order
            for step in [state.backbone_steps.get(sid)]
            if step and step.status not in ('done', 'failed')
        ],
        'candidate_tool': tool_name,
        'candidate_args': dict(tool_args or {}),
        'backbone_match': {
            'status': match.status, 'step_id': match.step_id,
            'candidate_step_ids': match.candidate_step_ids,
            'parameter_compatibility': match.parameter_compatibility,
        },
        'achieved_trajectory': list(getattr(llm, 'achieved_function_trajectory', []) or []),
    }
    try:
        raw = llm.client.llm_run(TAER_ANCHOR_PROMPT, json.dumps(context, sort_keys=True),
                                 max_tokens=1024, enable_thinking=False)
        anchor = json.loads(raw)
    except (TypeError, ValueError, AttributeError):
        return TAERPolicyEvidence('UNKNOWN', 'taer_anchor_unavailable')
    if not isinstance(anchor, dict):
        return TAERPolicyEvidence('UNKNOWN', 'taer_anchor_malformed')
    relation = str(anchor.get('relation', 'AMBIGUOUS'))
    confidence = str(anchor.get('confidence', 'LOW'))
    if relation not in {'DIRECT_EFFECT', 'REPAIR', 'NEW_GOAL', 'AMBIGUOUS'} or confidence != 'HIGH':
        return TAERPolicyEvidence('UNKNOWN', 'taer_anchor_unresolved', anchor=anchor)
    if relation == 'NEW_GOAL':
        targets_authorized = getattr(llm, '_action_targets_authorized', lambda *_: False)(
            tool_args, getattr(llm, '_user_explicit_entities', []))
        delegated = getattr(llm, '_action_has_delegated_source_support', lambda *_: False)(tool_name, tool_args)
        if not (targets_authorized or delegated):
            return TAERPolicyEvidence('INVALID', 'taer_anchor_new_goal', anchor.get('consumer_step_id'), anchor)
        return TAERPolicyEvidence('UNKNOWN', 'taer_anchor_new_goal_with_external_support',
                                  anchor.get('consumer_step_id'), anchor)
    if relation == 'AMBIGUOUS':
        return TAERPolicyEvidence('UNKNOWN', 'taer_anchor_ambiguous', anchor.get('consumer_step_id'), anchor)
    boundary_enabled = bool(getattr(llm, 'taer_boundary_enabled', lambda: False)())
    if boundary_enabled:
        param_result, param_reason = check_params_against_consumer(tool_name, tool_args, anchor, state)
        if param_result == 'block':
            return TAERPolicyEvidence('INVALID', f'taer_anchor_parameter:{param_reason}',
                                      anchor.get('consumer_step_id'), anchor)
        if param_result == 'fallback':
            return TAERPolicyEvidence('UNKNOWN', f'taer_anchor_consumer_unresolved:{param_reason}',
                                      anchor.get('consumer_step_id'), anchor)
        boundary = check_taer_boundary(
            tool_name, tool_args, anchor, anchor.get('consumer_step_id'),
            list(getattr(getattr(llm, 'source_label_store', None), 'records', []) or []),
            getattr(llm, 'source_flow_contract_helper', None),
            getattr(llm, '_user_explicit_entities', []),
        )
        if not boundary.passed:
            return TAERPolicyEvidence('INVALID', f'taer_anchor_boundary:{boundary.reason}',
                                      anchor.get('consumer_step_id'), anchor)
    return TAERPolicyEvidence('VALID', f'taer_anchor_{relation.lower()}',
                              anchor.get('consumer_step_id'), anchor)
