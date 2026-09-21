"""Deterministic TAER facts exposed as RCVR validator evidence.

This module deliberately does not dispatch calls, mutate a trajectory, or
create repairs.  It translates immutable TAER-backbone facts into a small
three-valued contribution that the RCVR Runtime Validator can merge with
binding and SourceFlow witnesses.
"""
from dataclasses import dataclass

from taer import check_taer_boundary, match_candidate_to_backbone


@dataclass(frozen=True)
class TAERPolicyEvidence:
    verdict: str
    reason: str
    consumer_step_id: str | None = None


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
