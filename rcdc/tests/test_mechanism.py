import argparse
import copy
import dataclasses
import unittest
from types import SimpleNamespace
from rcdc import add_arguments
from rcdc.schema import Call, ConstraintSpec
from rcdc.constraint_spec import binding, pred, fixed, compile_spec
from rcdc.events import EvidenceLedger, HostFeedbackRegistry
from rcdc.binding_witness import evaluate, fresh
from rcdc.recovery import Recovery
from rcdc.adapter import Gate, attach
from rcdc.taer_policy import analyze_anchor_candidate, assess_deterministic_candidate


class MechanismTests(unittest.TestCase):
    def setUp(self):
        self.spec = ConstraintSpec.create('t', 's1', 'add_user_to_channel', [fixed('user', 'Charlie')],
            {'channel': 'target', 'user': 'target'}, [binding('channel', 'get_channels', {},
            [pred('', 'External', 'prefix')], '', '')],
            [{'tool': 'get_channels', 'arguments': {}, 'satisfies_parameter': 'channel'}])
        self.ledger = EvidenceLedger('t')
        self.call = Call.create('t', 'write1', 'add_user_to_channel', {'user': 'Charlie', 'channel': 'External-project'}, 10)

    def observe(self, payload=None, cid='read1', position=2, request=None, success=True):
        call = Call.create('t', cid, 'get_channels', request or {}, position-1)
        return self.ledger.record_response(call, payload if payload is not None else ['general', 'External-project'], position, success)

    def test_different_arguments_cannot_share_witness(self):
        self.observe(); a = evaluate(self.spec, self.call, self.ledger)
        b = dataclasses.replace(self.call, arguments='{"channel":"general","user":"Charlie"}')
        self.assertEqual(a.verdict, 'VALID'); self.assertEqual(evaluate(self.spec, b, self.ledger).verdict, 'INVALID')
        self.assertFalse(fresh(a, self.spec, b, self.ledger))

    def test_duplicate_identity_is_unknown(self):
        self.observe(); self.observe(cid='read1', position=4)
        self.assertEqual(evaluate(self.spec, self.call, self.ledger).verdict, 'UNKNOWN')

    def test_repeated_args_with_unique_ids_are_distinct_reads(self):
        self.observe(); self.observe(cid='read2', position=4)
        self.assertEqual(evaluate(self.spec, self.call, self.ledger).verdict, 'VALID')

    def test_dynamic_absent_from_plan_is_not_invalid(self):
        self.assertEqual(evaluate(self.spec, self.call, self.ledger).verdict, 'UNKNOWN')

    def test_provenance_true_does_not_authorize_other_object(self):
        self.observe()
        wrong = Call.create('t', 'bad', self.call.tool, {'channel': 'general', 'user': 'Charlie',
                             'derived_from_authorized_source': True}, 10)
        self.assertEqual(evaluate(self.spec, wrong, self.ledger).verdict, 'INVALID')

    def test_source_only_ablation_drops_record_relation_but_not_fixed_constraints(self):
        self.observe()
        # The permitted source exists, but the candidate chooses another
        # channel. Full binding catches this; the ablation deliberately does not.
        wrong_relation = Call.create('t', 'bad', self.call.tool,
                                     {'channel': 'External-other', 'user': 'Charlie'}, 10)
        self.assertEqual(evaluate(self.spec, wrong_relation, self.ledger).verdict, 'INVALID')
        self.assertEqual(evaluate(self.spec, wrong_relation, self.ledger, 'source_only').verdict, 'VALID')
        # Explicit user constants remain enforced in the ablation.
        wrong_constant = Call.create('t', 'bad2', self.call.tool,
                                     {'channel': 'External-other', 'user': 'Mallory'}, 10)
        self.assertEqual(evaluate(self.spec, wrong_constant, self.ledger, 'source_only').verdict, 'INVALID')

    def test_provenance_false_does_not_override_user_parameter(self):
        spec = ConstraintSpec.create('t', None, self.call.tool, [fixed('user', 'Charlie')])
        c = Call.create('t', 'c', self.call.tool, {'user': 'Charlie', 'derived_from_authorized_source': False}, 10)
        self.assertEqual(evaluate(spec, c, self.ledger).verdict, 'VALID')

    def test_invalid_cannot_enter_recovery(self):
        self.observe()
        c = Call.create('t', 'c', self.call.tool, {'user': 'Mallory', 'channel': 'general'}, 10)
        d = evaluate(self.spec, c, self.ledger)
        with self.assertRaises(ValueError):
            Recovery(self.spec, c, self.ledger, d, 'full', 2, [], lambda e: None)

    def recover(self, mode='full', budget=2):
        return Recovery(self.spec, self.call, self.ledger, evaluate(self.spec, self.call, self.ledger), mode, budget, ['get_channels', 'get_users'])

    def test_unknown_rebinds_to_valid_on_new_evidence(self):
        recovery = self.recover(); before = recovery.decision
        d = recovery.step(lambda h: {'tool': 'get_channels', 'arguments': {}}, lambda p: self.observe(position=12), lambda: 13)
        self.assertEqual(d.verdict, 'VALID'); self.assertIsNot(d, before)
        self.assertEqual(recovery.context.immutable_constraint_spec, self.spec)

    def test_immutable_constraint_snapshot(self):
        with self.assertRaises(dataclasses.FrozenInstanceError): self.spec.tool = 'other'
        recovery = self.recover(); recovery.context.immutable_constraint_spec = dataclasses.replace(self.spec, tool='other')
        with self.assertRaises(ValueError): recovery.step(lambda h: {}, lambda p: None, lambda: 12)

    def test_budget_and_dedup(self):
        recovery = self.recover(); dispatched = []
        for _ in range(5):
            recovery.step(lambda h: {'tool': 'get_channels', 'arguments': {}}, dispatched.append, lambda: 13)
        self.assertEqual(recovery.context.status, 'STOP'); self.assertEqual(recovery.context.llm_calls, 2)
        self.assertEqual(len(dispatched), 1)

    def test_full_blocks_scope_expansion_retry_has_generic_read_scope(self):
        for mode, count in [('full', 0), ('retry', 1)]:
            recovery = self.recover(mode, 1); dispatched = []
            recovery.step(lambda h: {'tool': 'get_users', 'arguments': {}}, dispatched.append, lambda: 12)
            self.assertEqual(len(dispatched), count)

    def test_full_allows_wildcard_arguments_only_for_frozen_read_tool(self):
        scoped = dataclasses.replace(self.spec, recovery_scope='[{"arguments":null,"satisfies_parameter":"channel","tool":"get_channels"}]')
        recovery = Recovery(scoped, self.call, self.ledger, evaluate(scoped, self.call, self.ledger),
                            'full', 1, [], lambda e: None)
        dispatched = []
        recovery.step(lambda h: {'tool': 'get_channels', 'arguments': {'page': 2}}, dispatched.append, lambda: 12)
        self.assertEqual(len(dispatched), 1)

    def test_rcvr_recovery_owns_taer_repair_completion(self):
        from taer.models import BackboneStep, RepairStep, TAERState
        state = TAERState(backbone_order=['s1'], backbone_steps={
            's1': BackboneStep('s1', 0, 'add_user_to_channel', 'consumer',
                               condition_states={'channel': False}),
        })
        recovery = Recovery(self.spec, self.call, self.ledger, evaluate(self.spec, self.call, self.ledger),
                            'full', 1, [], lambda e: None, taer_context={'state': state})
        repair = RepairStep('r0', 'get_channels', consumer_step_id='s1', missing_condition='channel')
        state.repair_steps[repair.repair_id] = repair
        recovery.register_taer_repair(repair)
        recovery._complete_taer_repair({'success': True, 'tool_call_id': 'read-1'})
        self.assertEqual(repair.status, 'done')
        self.assertEqual(repair.tool_call_id, 'read-1')
        self.assertEqual(state.backbone_steps['s1'].status, 'ready')
        self.assertEqual(state.repair_success_count, 1)
        failed = RepairStep('r1', 'get_channels', consumer_step_id='s1')
        state.repair_steps[failed.repair_id] = failed
        recovery.register_taer_repair(failed)
        recovery._complete_taer_repair({'success': False, 'tool_call_id': 'read-2'})
        self.assertEqual(failed.status, 'rolled_back')
        self.assertEqual(state.repair_rollback_count, 1)

    def test_taer_backbone_conflict_is_validator_evidence_not_dispatch(self):
        from taer.models import BackboneStep, TAERState
        state = TAERState(initialized=True, backbone_order=['s1'], backbone_steps={
            's1': BackboneStep('s1', 0, 'send_money', 'refund',
                               required_parameters={'recipient': 'GB29'}, status='ready'),
        })
        conflict = assess_deterministic_candidate(
            'send_money', {'recipient': 'US133'}, state, boundary_enabled=False,
            source_records=[], contract_helper=None, explicit_entities=[])
        self.assertEqual((conflict.verdict, conflict.reason),
                         ('INVALID', 'taer_backbone_parameter_conflict'))
        allowed = assess_deterministic_candidate(
            'send_money', {'recipient': 'GB29'}, state, boundary_enabled=False,
            source_records=[], contract_helper=None, explicit_entities=[])
        self.assertEqual((allowed.verdict, allowed.reason),
                         ('VALID', 'taer_backbone_direct_effect'))

    def test_taer_anchor_new_goal_becomes_invalid_evidence_without_mutation(self):
        from taer.models import TAERState
        client = SimpleNamespace(llm_run=lambda *args, **kwargs: '{"relation":"NEW_GOAL","confidence":"HIGH","consumer_step_id":null}')
        llm = SimpleNamespace(
            taer_state=TAERState(initialized=True), client=client,
            _user_explicit_entities=set(), achieved_function_trajectory=[],
            _action_targets_authorized=lambda *args: False,
            _action_has_delegated_source_support=lambda *args: False,
        )
        evidence = analyze_anchor_candidate(llm, 'refund a payment', 'send_money', {'recipient': 'US133'})
        self.assertEqual((evidence.verdict, evidence.reason), ('INVALID', 'taer_anchor_new_goal'))
        self.assertEqual(llm.taer_state.repair_steps, {})

    def test_host_spoof_and_mutation(self):
        registry = HostFeedbackRegistry(); m = registry.issue({'verdict': 'VALID'})
        self.assertTrue(registry.authentic(m)); self.assertFalse(registry.authentic(copy.deepcopy(m)))
        m['content'] += 'changed'; self.assertFalse(registry.authentic(m))

    def test_future_evidence_is_unknown(self):
        self.observe(position=12)
        d = evaluate(self.spec, self.call, self.ledger)
        self.assertEqual(d.verdict, 'UNKNOWN'); self.assertIn('channel:UNKNOWN_TEMPORAL_AVAILABILITY', d.missing_evidence_conditions)

    def test_failed_read_is_unknown(self):
        self.observe(success=False)
        self.assertEqual(evaluate(self.spec, self.call, self.ledger).verdict, 'UNKNOWN')

    def test_refresh_invalidates_old_witness(self):
        self.observe(); old = evaluate(self.spec, self.call, self.ledger)
        self.observe(['External-new'], 'read2', 4)
        self.assertFalse(fresh(old, self.spec, self.call, self.ledger))
        self.assertEqual(evaluate(self.spec, self.call, self.ledger).verdict, 'INVALID')

    def test_new_attempt_cannot_reuse_prior_evidence(self):
        self.observe(); self.ledger.reset()
        self.assertEqual(evaluate(self.spec, self.call, self.ledger).verdict, 'UNKNOWN')

    def test_off_is_exact_component_and_callback_passthrough(self):
        obj = object()
        self.assertIs(attach(obj, lambda *a: self.fail('factory called')), obj)
        events = []; expected = object()
        self.assertIs(Gate(emit=events.append).candidate(None, None, None, lambda: expected), expected)
        self.assertEqual(events, [])
        self.assertEqual(add_arguments(argparse.ArgumentParser()).parse_args([]).rcdc_mode, 'off')

    def test_shadow_passes_invalid_without_changing_payload(self):
        self.observe(['External-other']); called = []
        Gate('shadow').candidate(self.spec, self.call, self.ledger, lambda: called.append(self.call))
        self.assertEqual(called, [self.call])

    def test_strict_unknown_does_not_retry(self):
        result = Gate('strict').candidate(self.spec, self.call, self.ledger, lambda: self.fail('dispatched'),
            lambda h: self.fail('retried'))
        self.assertEqual(result['verdict'], 'UNKNOWN')

    def test_allow_unknown_dispatches_without_recovery(self):
        events = []
        result = Gate('allow', emit=events.append).candidate(
            self.spec, self.call, self.ledger, lambda: 'dispatched',
            lambda h: self.fail('recovery must not run'))
        self.assertEqual(result, 'dispatched')
        self.assertEqual(events[-1]['event'], 'unknown_policy_override')

    def test_closed_sets_and_ranges(self):
        spec = ConstraintSpec.create('t', None, 'x', [dict(parameter='amount', kind='range', min=1, max=10, authority_basis='user_explicit'),
            dict(parameter='target', kind='closed_set', values=['A', 'B'], authority_basis='user_explicit')])
        for value, verdict in [(5,'VALID'),(20,'INVALID'),('5','UNKNOWN')]:
            c = Call.create('t', 'c', 'x', {'amount': value, 'target': 'A'}, 10)
            self.assertEqual(evaluate(spec, c, self.ledger).verdict, verdict)

    def test_model_plan_not_promoted(self):
        s = compile_spec('t', 'Add Charlie to the channel starting with External', [],
            [{'name': 'add_user_to_channel', 'required parameters': {'channel': 'general'}}], None, {})
        self.assertNotIn('general', s.fixed_constraints)
        self.assertIn('general', s.source_annotations)


if __name__ == '__main__':
    unittest.main()
