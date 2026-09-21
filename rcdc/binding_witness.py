"""Deterministic typed rules. SourceFlow labels are never verdicts."""
import json
from dataclasses import asdict
from decimal import Decimal, InvalidOperation
from .schema import Witness, Decision, canonical, digest


def number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError('numeric_type_required')
    result = Decimal(str(value))
    if not result.is_finite():
        raise ValueError('nonfinite_number')
    return result


def field(row, path):
    value = row
    for key in path.split('.') if path else []:
        if not isinstance(value, dict) or key not in value:
            raise ValueError('missing_field')
        value = value[key]
    return value


def equal(actual, expected, comparison='exact'):
    if comparison == 'number':
        return number(actual) == number(expected)
    if comparison == 'set_of_strings':
        if not isinstance(actual, list) or not isinstance(expected, list) or not all(isinstance(v, str) for v in actual + expected):
            raise ValueError('expected_string_list')
        # Explicit participant-set semantics only. Lists otherwise keep order.
        return set(actual) == set(expected)
    if comparison != 'exact':
        raise ValueError('unsupported_comparison')
    return canonical(actual) == canonical(expected)


def select(payload, rule):
    if not isinstance(payload, list):
        raise ValueError('missing_structured_collection')
    selected = []
    ids = set()
    for row in payload:
        # ``identity_field`` is planner metadata used only to detect duplicate
        # rows.  Tool input contracts rarely declare a response schema, so a
        # planner may name an unavailable identifier (for example
        # ``transaction_id`` when this particular backend exposes ``id``).
        # That must not discard an otherwise fully specified, uniquely
        # selected binding.  Fall back to the complete structured row, which
        # still detects literal duplicate records without inventing a value.
        try:
            identity = field(row, rule['identity_field']) if rule.get('identity_field') else row
        except ValueError as exc:
            if str(exc) != 'missing_field':
                raise
            identity = row
        key = canonical(identity)
        if key in ids:
            raise ValueError('ambiguous_record_identity')
        ids.add(key)
        fits = True
        for predicate in rule.get('predicates', []):
            value = field(row, predicate['field'])
            if predicate['operator'] == 'equals':
                # Runtime self is a contract-level identity relation, never a
                # task literal. Backends may expose it as a stable self alias.
                if predicate['value'] == '__RCVR_RUNTIME_SELF__':
                    fits &= isinstance(value, str) and value.strip().lower() in {'me', 'self', 'current_user'}
                else:
                    fits &= equal(value, predicate['value'])
            elif predicate['operator'] == 'prefix':
                if not isinstance(value, str):
                    raise ValueError('unknown_field_type')
                fits &= value.startswith(predicate['value'])
            elif predicate['operator'] == 'date':
                if not isinstance(value, str):
                    raise ValueError('unknown_date_representation')
                fits &= value[:10] == predicate['value']
            else:
                raise ValueError('unsupported_predicate')
        if fits:
            selected.append(row)
    if rule.get('selection') == 'max':
        scored = [(number(field(row, rule['selection_field'])), row) for row in selected]
        if scored:
            maximum = max(score for score, _ in scored)
            selected = [row for score, row in scored if score == maximum]
    if len(selected) != 1:
        raise ValueError('ambiguous_object' if selected else 'missing_object')
    return selected[0]


def evaluate(spec, call, ledger, relation_mode='full'):
    """Verify a candidate binding.

    ``source_only`` is an ablation: it retains the permitted read request and
    evidence availability checks but intentionally omits record-level value
    binding. It is never used by the Full RCVR configuration.
    """
    if relation_mode not in ('full', 'source_only'):
        raise ValueError('invalid_relation_mode')
    witnesses = []
    missing = []
    roles = json.loads(spec.parameter_roles)
    args = json.loads(call.arguments)

    def add(rule, parameter, verdict, reason, basis, relation, source=None, temporal=None):
        witnesses.append(Witness(call.call_id, call.tool, parameter, canonical(args.get(parameter)),
            spec.constraint_id, source.source_id if source else None,
            source.tool if source else basis, roles.get(parameter, 'unknown'), relation, temporal,
            verdict, reason, rule, basis, source.revision if source else None))
        if verdict == 'UNKNOWN':
            missing.append(f'{parameter}:{reason}')

    valid_identity = call.task_id == spec.task_id == ledger.task_id and call.epoch == ledger.epoch and call.tool == spec.tool
    if not valid_identity or not call.call_id or call.call_id in ledger.ambiguous_ids:
        add('IDENTITY', '*', 'UNKNOWN', 'ambiguous_or_cross_task_call', 'host', 'call_identity')
    else:
        for rule in json.loads(spec.fixed_constraints):
            p = rule['parameter']; basis = rule['authority_basis']; kind = rule['kind']
            try:
                if p not in args or args[p] is None:
                    raise ValueError('missing_parameter')
                if kind == 'equals':
                    matches = equal(args[p], rule['value'], rule.get('comparison', 'exact'))
                elif kind == 'closed_set':
                    matches = any(equal(args[p], x) for x in rule['values'])
                elif kind == 'range':
                    value = number(args[p]); matches = True
                    if 'min' in rule:
                        matches &= value >= number(rule['min'])
                    if 'max' in rule:
                        matches &= value <= number(rule['max'])
                else:
                    raise ValueError('unsupported_fixed_constraint')
                add('R1', p, 'VALID' if matches else 'INVALID', 'fixed_constraint_satisfied' if matches else 'fixed_constraint_conflict', basis, kind, temporal=True)
            except (ValueError, InvalidOperation):
                add('R1', p, 'UNKNOWN', 'missing_parameter_or_unknown_conversion', basis, kind)
        for rule in json.loads(spec.binding_rules):
            p = rule['parameter']; request = canonical(rule['request'])
            sources = [e for e in ledger.evidence() if e.task_id == call.task_id and e.epoch == call.epoch
                       and e.tool == rule['source_tool'] and e.request == request]
            prior = [e for e in sources if e.position < call.position]
            if not prior:
                reason = 'UNKNOWN_TEMPORAL_AVAILABILITY' if sources else 'missing_source'
                add(rule['rule_id'], p, 'UNKNOWN', reason, rule['authority_basis'], rule['relation_type'])
                continue
            source = max(prior, key=lambda e: e.revision)
            if source.call_id in ledger.ambiguous_ids or not source.success:
                add(rule['rule_id'], p, 'UNKNOWN', 'ambiguous_or_failed_source', rule['authority_basis'], rule['relation_type'], source, True)
                continue
            if relation_mode == 'source_only':
                add(rule['rule_id'], p, 'VALID', 'source_provenance_available',
                    rule['authority_basis'], 'source_provenance_only', source, True)
                continue
            try:
                selected = select(json.loads(source.payload), rule)
                expected = field(selected, rule['value_field'])
                if p not in args or args[p] is None:
                    raise ValueError('missing_parameter')
                matches = equal(args[p], expected, rule.get('comparison', 'exact'))
                add(rule['rule_id'], p, 'VALID' if matches else 'INVALID', 'object_field_relation_satisfied' if matches else 'object_field_relation_conflict',
                    rule['authority_basis'], rule['relation_type'], source, True)
            except (ValueError, TypeError, InvalidOperation) as exc:
                add(rule['rule_id'], p, 'UNKNOWN', str(exc), rule['authority_basis'], rule['relation_type'], source, True)
        if not witnesses:
            add('SCOPE', '*', 'UNKNOWN', 'missing_rule', 'unknown', 'unsupported')
    verdict = 'INVALID' if any(w.verdict == 'INVALID' for w in witnesses) else 'UNKNOWN' if any(w.verdict == 'UNKNOWN' for w in witnesses) else 'VALID'
    return Decision(verdict, tuple(witnesses), tuple(sorted(set(missing))), digest(asdict(call)), spec.constraint_id, ledger.revision)


def fresh(decision, spec, call, ledger):
    return (decision.call_fingerprint == digest(asdict(call)) and decision.constraint_id == spec.constraint_id
            and decision.evidence_revision == ledger.revision)
