"""Policy adapter with exact pass-through for off; execution is a host callback."""
import json
from . import MODES
from .binding_witness import evaluate
from .recovery import Recovery


def attach(original, factory, mode='off'):
    if mode not in MODES:
        raise ValueError('invalid_rcdc_mode')
    return original if mode == 'off' else factory(original, mode)


class Gate:
    def __init__(self, mode='off', budget=2, relation_mode='full', emit=lambda e: None,
                 enable_binding_verification=True):
        if mode not in MODES or relation_mode not in ('full', 'source_only') or not isinstance(budget, int) or budget < 0:
            raise ValueError('invalid_rcdc_configuration')
        if not isinstance(enable_binding_verification, bool):
            raise ValueError('invalid_binding_verification_flag')
        self.mode, self.budget, self.relation_mode, self.emit = mode, budget, relation_mode, emit
        self.enable_binding_verification = enable_binding_verification

    def candidate(self, spec, call, ledger, continue_original, propose_read=None,
                  execute_read=None, position=None, ordinary_read_tools=(), on_unknown=None,
                  decision_provider=None):
        if self.mode == 'off':
            return continue_original()
        if spec is None:
            self.emit({'event': 'outside_verification_scope', 'call_id': call.call_id})
            return continue_original()
        ledger.observe_call(call)
        # B2 deliberately retains the host-owned provenance ledger and the
        # original DRIFT callback, but no RCVR constraint-specific verdict is
        # allowed to decide dispatch, stopping, or recovery.
        if not self.enable_binding_verification:
            self.emit({'event': 'provenance_source_tracking', 'call_id': call.call_id,
                       'constraint_id': spec.constraint_id,
                       'binding_rule_count': len(json.loads(spec.binding_rules))})
            self.emit({'event': 'binding_verification_disabled', 'call_id': call.call_id})
            return continue_original()
        decision = (decision_provider(call) if decision_provider is not None
                    else evaluate(spec, call, ledger, self.relation_mode))
        self.emit({'event': 'binding_verification', 'decision': decision.json(), 'mode': self.mode,
                   'relation_mode': self.relation_mode})
        if decision.verdict == 'UNKNOWN' and on_unknown is not None:
            # The callback runs before any recovery proposal or tool effect.
            on_unknown(decision)
        if self.mode == 'shadow':
            return continue_original()
        # UNKNOWN is not INVALID.  This ablation deliberately treats it as a
        # permissive decision, while preserving every other verifier and
        # provenance check.  Full RCVR never takes this branch.
        if decision.verdict == 'UNKNOWN' and self.mode == 'allow':
            self.emit({'event': 'unknown_policy_override', 'policy': 'allow',
                       'call_id': call.call_id, 'original_verdict': 'UNKNOWN'})
            return continue_original()
        if decision.verdict == 'UNKNOWN' and self.mode in ('retry', 'full'):
            recovery = Recovery(spec, call, ledger, decision, self.mode, self.budget, ordinary_read_tools,
                                self.emit, self.relation_mode, decision_provider)
            while recovery.context.status not in ('VALID', 'INVALID', 'STOP'):
                decision = recovery.step(propose_read, execute_read, position)
        if decision.verdict == 'VALID':
            return continue_original()
        self.emit({'event': 'candidate_stopped', 'call_id': call.call_id, 'verdict': decision.verdict})
        return {'rcvr_stopped': True, 'verdict': decision.verdict, 'decision': decision.json()}
