"""Budgeted recovery. It does not execute tools or mutate an original spec."""
from dataclasses import dataclass, field, asdict
import json
from .binding_witness import evaluate
from .schema import Call, ConstraintSpec, canonical, digest


@dataclass
class RecoveryContext:
    original_call: Call
    immutable_constraint_spec: ConstraintSpec
    missing_conditions: tuple
    allowed_read_tools: tuple
    recovery_budget: int
    attempted_evidence: list = field(default_factory=list)
    status: str = 'PENDING'
    steps: int = 0
    llm_calls: int = 0
    tool_calls: int = 0
    # TAER is recovery policy, not a competing final-decision owner.
    taer_consumer_step_id: str | None = None
    taer_repair_id: str | None = None
    taer_authorization_lifetime: str | None = None
    taer_boundary_required: bool = False


class Recovery:
    def __init__(self, spec, call, ledger, decision, mode, budget, ordinary_read_tools,
                 emit=lambda e: None, relation_mode='full', decision_provider=None,
                 taer_context=None):
        if decision.verdict != 'UNKNOWN':
            raise ValueError('recovery_only_for_unknown')
        if mode not in ('retry', 'full') or not isinstance(budget, int) or budget < 0:
            raise ValueError('invalid_recovery_configuration')
        if relation_mode not in ('full', 'source_only'):
            raise ValueError('invalid_relation_mode')
        self.mode = mode
        self.ledger = ledger
        self.emit = emit
        self.spec = spec
        self.call = call
        self.fingerprint = spec.constraint_id
        self.requests = json.loads(spec.recovery_scope)
        self.relation_mode = relation_mode
        self.decision_provider = decision_provider
        # The TAER state remains immutable authorization input.  A repair
        # created while collecting RCVR evidence is owned here, rather than by
        # DRIFTLLM's legacy pending-repair map.
        self._taer_state = taer_context.get('state') if taer_context else None
        self._taer_repair = None
        allowed = tuple(sorted({x['tool'] for x in self.requests})) if mode == 'full' else tuple(sorted(ordinary_read_tools))
        taer_context = taer_context or {}
        self.context = RecoveryContext(call, spec, decision.missing_evidence_conditions, allowed, budget,
                                       taer_consumer_step_id=taer_context.get('consumer_step_id'),
                                       taer_repair_id=taer_context.get('repair_id'),
                                       taer_authorization_lifetime=taer_context.get('authorization_lifetime'),
                                       taer_boundary_required=bool(taer_context.get('boundary_required')))
        self.decision = decision

    def register_taer_repair(self, repair):
        """Attach a TAER repair created by an allowed recovery READ.

        The caller supplies the controller-created RepairStep, but this
        recovery instance controls its single completion transition.
        """
        if self._taer_repair is not None:
            raise ValueError('multiple_taer_repairs_in_one_recovery_step')
        if repair is None or not getattr(repair, 'repair_id', None):
            raise ValueError('invalid_taer_repair')
        self._taer_repair = repair
        self.context.taer_repair_id = repair.repair_id
        self.context.taer_consumer_step_id = getattr(repair, 'consumer_step_id', None)
        self.emit({'event': 'taer_repair_attached_to_rcvr_recovery',
                   'repair_id': repair.repair_id,
                   'consumer_step_id': self.context.taer_consumer_step_id})

    def _complete_taer_repair(self, result):
        if self._taer_repair is None or self._taer_state is None:
            return
        from taer import commit_repair, rollback_repair
        success = result is not False and (not isinstance(result, dict) or result.get('success', True))
        call_id = result.get('tool_call_id') if isinstance(result, dict) else None
        self._taer_repair.tool_call_id = call_id
        if success:
            commit_repair(self._taer_state, self._taer_repair.repair_id)
            outcome = 'committed'
        else:
            rollback_repair(self._taer_state, self._taer_repair.repair_id)
            outcome = 'rolled_back'
        self._taer_state.active_consumer_step_id = self._taer_repair.consumer_step_id
        self.emit({'event': 'taer_repair_completed_by_rcvr_recovery',
                   'repair_id': self._taer_repair.repair_id, 'outcome': outcome,
                   'tool_call_id': call_id})
        self._taer_repair = None

    def step(self, propose_read, execute_read, position):
        ctx = self.context
        if ctx.immutable_constraint_spec != self.spec or self.spec.constraint_id != self.fingerprint or ctx.original_call != self.call:
            ctx.status = 'STOP'
            raise ValueError('immutable_recovery_context_changed')
        if ctx.status in ('VALID', 'INVALID', 'STOP'):
            return self.decision
        if ctx.steps >= ctx.recovery_budget:
            ctx.status = 'STOP'
            self.emit({'event': 'evidence_bounded_recovery_exhausted', 'context': asdict(ctx)})
            return self.decision
        ctx.steps += 1
        ctx.llm_calls += 1
        # Same model invocation cap in retry/full. Only full exposes missing
        # conditions and the exact evidence acquisition scope to the proposer.
        hint = {'mode': self.mode, 'original_call': asdict(self.call),
                'attempted_evidence': list(ctx.attempted_evidence)}
        if self.mode == 'full':
            hint.update(missing_conditions=ctx.missing_conditions, allowed_requests=self.requests)
        proposal = propose_read(hint)
        self.emit({'event': 'evidence_bounded_recovery_proposal', 'step': ctx.steps, 'proposal': proposal})
        if not isinstance(proposal, dict) or not isinstance(proposal.get('arguments'), dict):
            allowed = False
        else:
            allowed = proposal.get('tool') in ctx.allowed_read_tools
            if self.mode == 'full':
                allowed &= any(proposal['tool'] == r['tool']
                               and (r.get('arguments') is None or canonical(proposal['arguments']) == canonical(r['arguments']))
                               and any(m.startswith(r['satisfies_parameter'] + ':') for m in ctx.missing_conditions) for r in self.requests)
        request_key = digest(proposal)
        duplicate = request_key in ctx.attempted_evidence
        if allowed and not duplicate:
            ctx.attempted_evidence.append(request_key)
            ctx.tool_calls += 1
            result = execute_read(proposal)
            self._complete_taer_repair(result)
        else:
            self.emit({'event': 'evidence_bounded_recovery_read_rejected', 'reason': 'duplicate_read' if duplicate else 'outside_scope'})
        # Always construct a new call-time witness, including after failed reads.
        rebound = Call(self.call.task_id, self.call.call_id, self.call.tool, self.call.arguments, position(), self.call.epoch)
        self.decision = (self.decision_provider(rebound) if self.decision_provider is not None
                         else evaluate(self.spec, rebound, self.ledger, self.relation_mode))
        ctx.missing_conditions = self.decision.missing_evidence_conditions
        ctx.status = self.decision.verdict if self.decision.verdict != 'UNKNOWN' else 'STOP' if ctx.steps >= ctx.recovery_budget else 'PENDING'
        self.emit({'event': 'binding_reverification', 'step': ctx.steps, 'decision': self.decision.json(), 'status': ctx.status,
                   'spec_id': self.spec.constraint_id, 'tool_calls': ctx.tool_calls, 'llm_calls': ctx.llm_calls})
        return self.decision
