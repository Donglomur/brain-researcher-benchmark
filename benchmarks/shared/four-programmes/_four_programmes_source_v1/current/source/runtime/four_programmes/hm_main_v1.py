"""Fixed full HM C orchestration over original captured sources and owners.

No programme runs on import. This caller does not mint Context/native/issuer,
stage-host, matched-pair or scientific qualification. Every branch uses the
actual original complete source API; an unavailable real producer stays a failure.
"""
from .common import need, closed, pin, encode, failure, bounded_size
from .source_session import SourceSession
from .roots import BoundRoots
from .channel import RootChannel
from .hm_main_metadata_v1 import captured_module, reserve_original_hm_row_metadata_v1
from .hm_issuer_transport_v1 import HMChannelCustodyV1
from .hm_coordinator_terminal import send_original_hm_final_notice_v1

PROGRAMME = 'PAPER-paper-method-replacement-016'
_MAIN = object()
STAGES = ('reference', 'candidate:A', 'candidate:B')


class HMMainV1:
    def __init__(self, token, *, session, budget, roots, selection_pin,
                 issuer_custody, stage_custody):
        need(token is _MAIN and type(session) is SourceSession and
             session.programme == PROGRAMME and not session.closed,
             'fixed actual original HM MAIN and live captured source session')
        need(getattr(session, '_hm_main_owner_v1', None) is None,
             'one full original HM MAIN attempt, including failed preparation')
        self.session = session
        self.budget = budget
        self.budget_owned = False
        self.roots = roots
        self.selection_pin = selection_pin
        self.issuer = None
        self.stage_transport = None
        self.owned_custodies = []
        self.entered = False
        self.prepare_entered = False
        self.closed = False
        self.primary = None
        self.secondaries = []
        self.phase = 'registered'
        self.selection = None
        self.coordinator = None
        self.metadata_rows = []
        self.stages = []
        self.pair_event = None
        self.pair_admission = None
        self.report = None
        self.notice = None
        session._hm_main_owner_v1 = self
        try:
            self.bm = captured_module(session, 'stage_budget')
            self.cm = captured_module(session, 'coordinator')
            self.gm = captured_module(session, 'guard')
            self.im = captured_module(session, 'identity_contract')
            self.issuance = captured_module(session, 'issuance')
            self.closure = captured_module(session, 'stage_closure')
            self.tables = captured_module(session, 'fixed_tables')
            need(type(budget) is self.bm['ExclusiveBudget'] and budget.owner == 'C' and
                 budget.row == 'C00' and budget.generation == 0 and budget.active and
                 not budget.failed and budget.primary is None and budget.pending is None and
                 budget.guard is None and not budget.consumed and
                 type(roots) is BoundRoots and set(roots.roots) == {'R'} and roots.relative_base == 'R',
                 'same actual initial exclusive writer, full source plan and selected R')
            self.budget_owned = True
            for role, custody in (('issuer', issuer_custody), ('stage', stage_custody)):
                need(type(custody) is HMChannelCustodyV1 and custody.session is session and
                     custody.plan is budget.plan and custody.role == role,
                     'actual factory-owned original channel custody for this HM role/session/plan')
                custody.require_original()
                need(getattr(custody, '_hm_main_owner_v1', None) is None,
                     'original channel custody has not been transferred to another MAIN')
                custody._hm_main_owner_v1 = self
                self.owned_custodies.append(custody)
                if role == 'issuer':
                    self.issuer = custody
                else:
                    self.stage_transport = custody
            need(self.issuer is not self.stage_transport and
                 self.issuer.channel is not self.stage_transport.channel and
                 self.issuer.controller == self.stage_transport.controller and
                 self.issuer.channel.binding['launch'] == self.stage_transport.channel.binding['launch'],
                 'distinct original issuer/stage transports for one actually observed C launch')
            self.controller = self.issuer.controller
            self.gm['descriptor'](selection_pin)
            self.phase = 'admitted_source_owners'
        except BaseException as error:
            self.retain(error, 'MAIN_owner_admission')
            self.close_owned()
            raise self.primary

    def retain(self, error, site):
        if self.primary is None:
            self.primary = error
        elif error is not self.primary:
            self.secondaries.append((site, error))
        if self.budget_owned and self.budget.active:
            try:
                if self.coordinator is not None:
                    self.coordinator._own(error, site)
                else:
                    self.budget._own(error)
            except BaseException as later:
                if later is not self.primary:
                    self.secondaries.append((site + '_retention', later))
        self.phase = 'failed'

    def require_original(self):
        if self.primary is not None:
            raise self.primary
        need(self.session._hm_main_owner_v1 is self and not self.session.closed and not self.closed,
             'same original live MAIN owner and source session')
        for custody in self.owned_custodies:
            need(custody._hm_main_owner_v1 is self, 'same transferred original channel custody')
            custody.require_original()

    def _document(self, descriptor):
        self.gm['descriptor'](descriptor)
        # Existing programme row/global admission precedes actual whole reads.
        return self.cm['OriginalBudgetStore'](self.roots.roots['R'], self.budget).document(
            descriptor, self.budget.limits['read_bytes'])

    def prepare(self):
        if self.primary is not None:
            raise self.primary
        need(not self.prepare_entered, 'one original preparation including first-read failure')
        self.prepare_entered = True
        try:
            self.require_original()
            return self._prepare()
        except BaseException as error:
            self.retain(error, 'MAIN_original_input_preparation')
            self.close_owned()
            raise self.primary

    def _prepare(self):
        self.budget.require_operation('prepare')
        need(self.selection is None and self.coordinator is None,
             'one complete original metadata capture and scientific compiler')
        selected = self._document(self.selection_pin)
        closed(selected, ('schema', 'pair_id', 'scope', 'inputs', 'full_plan',
                          'submissions', 'stages', 'qualifications'))
        need(selected['schema'] == 'hundred_models_fixed_main_selection_v1' and
             type(selected['pair_id']) is str and 0 < len(selected['pair_id']) <= 256,
             'exact fixed ordinary MAIN input contract, not root/native authority')
        closed(selected['submissions'], ('A', 'B'))
        closed(selected['qualifications'], ('A', 'B'))
        need(type(selected['stages']) is list and len(selected['stages']) == 3,
             'all original reference/A/B stage selections')
        nonces = []
        for sequence, (stage, row) in enumerate(zip(STAGES, selected['stages']), 1):
            closed(row, ('sequence', 'stage', 'original_authority', 'profile',
                         'bootstrap_reservation', 'terminal_reservation', 'worker_nonce'))
            need(type(row['sequence']) is int and row['sequence'] == sequence and row['stage'] == stage,
                 'complete fixed original stage order')
            for key in ('original_authority', 'profile', 'bootstrap_reservation', 'terminal_reservation'):
                self.gm['descriptor'](row[key])
            nonce = row['worker_nonce']
            need(type(nonce) is str and 0 < len(nonce) <= 256 and nonce not in nonces,
                 'three distinct earlier selected original worker nonces')
            nonces.append(nonce)
        scope = self._document(selected['scope'])
        inputs = self._document(selected['inputs'])
        full_plan = self._document(selected['full_plan'])
        submissions = {arm: self._document(selected['submissions'][arm]) for arm in ('A', 'B')}
        # No reference/candidate result or protected target body is read here.
        self.selection = selected
        self.coordinator = self.cm['Coordinator'](session=self.session, budget=self.budget,
            roots=self.roots, scope=scope, inputs=inputs, full_plan=full_plan,
            submissions=submissions, pair_id=selected['pair_id'])
        self.phase = 'full_original_prepared'
        return self.coordinator

    def _invocation(self, sequence):
        coordinator = self.coordinator
        stage = self.budget.plan.stage(sequence)
        selected = self.selection['stages'][sequence - 1]
        invocation = {'campaign_id': self.budget.plan.body['campaign_id'],
            'stage': stage['stage'], 'sequence': sequence, 'reservation_plan': self.budget.plan.pin,
            'reservation_row': stage['row'], 'original_authority': selected['original_authority'],
            'source_manifest': self.budget.plan.body['source_manifest'],
            **coordinator.identities,
            'submission': None if sequence == 1 else pin(self.gm['encoded'](
                coordinator.submissions['A' if sequence == 2 else 'B'])),
            'root_issuer_source': self.budget.plan.body['root_issuer_source']}
        self.im['material'](invocation, self.budget.plan)
        return invocation

    def _stage(self, sequence):
        self.require_original()
        coordinator = self.coordinator
        stage = self.budget.plan.stage(sequence)
        selected = self.selection['stages'][sequence - 1]
        need(self.budget.row == stage['issue_from'] and self.budget.generation == sequence - 1 and
             len(self.stages) == sequence - 1,
             'each complete original reference/A/B stage once, with its restored predecessor')
        metadata = reserve_original_hm_row_metadata_v1(
            session=self.session, budget=self.budget, roots=self.roots)
        self.metadata_rows.append(metadata)
        invocation = self._invocation(sequence)
        subject = metadata.publish('SUBJECT.json', self.im['subject'](invocation, self.budget.plan))
        # All programme debits precede the immutable guard. The publication is
        # complete before arm_issuer forbids programme operations.
        state = self.budget._state('active_C')
        guard = metadata.publish('GUARD_STATE.json', state)
        armed = self.budget.arm_issuer()
        need(guard.raw == encode(armed) == self.budget.guard['snapshot'],
             'actual previously published original guard and unchanged C prefix')
        allocation = self.budget.guard['allocation']
        self.issuer.wait_until_original_ns(allocation['window']['start_ns'])
        self.budget.enter_issuer_wait()
        issued = self.issuance['exchange_issuer'](custody=self.issuer, budget=self.budget,
            invocation=invocation, subject_pin=subject.descriptor, guard_state_pin=guard.descriptor,
            controller=self.controller)
        need(type(issued) is self.issuance['IssuanceAdmission'] and issued.budget is self.budget and
             issued.plan is self.budget.plan and self.budget.guard['response'] is issued,
             'same actual completed issuer exchange and original guarded token')
        self.issuer.wait_until_original_ns(allocation['window']['stop_ns'])
        self.budget.finish_issuer_wait()
        base_body = self.budget.freeze_base()
        base = metadata.publish('BASE_STATE.json', base_body)
        lease_body = {'schema': self.tables['RECORD_VERSIONS']['HMLease'],
            **{key: value for key, value in invocation.items() if key != 'root_issuer_source'},
            'authority_subject': subject.descriptor, 'base_generation': self.budget.generation,
            'base_row': self.budget.row, 'base_state': base.descriptor,
            'bootstrap_reservation': selected['bootstrap_reservation'], 'controller': self.controller,
            'invocation_authority': issued.authority_pin,
            'original_deadline_ns': self.budget.deadline_ns,
            'previous_return': self.budget.previous_return, 'profile': selected['profile'],
            'terminal_reservation': selected['terminal_reservation'], 'worker_nonce': selected['worker_nonce']}
        self.bm['lease_scalars'](lease_body)
        lease = metadata.publish('LEASE.json', lease_body)
        arm = None if sequence == 1 else ('A' if sequence == 2 else 'B')
        output = coordinator.layout['reference_output' if arm is None else 'candidate_output_' + arm]
        request_body = {'schema': 'hundred_models_original_worker_request_v2',
            'lease': lease.descriptor, 'base_state': base.descriptor, 'subject': subject.descriptor,
            'root_selection': issued.selection_pin, 'invocation_authority': issued.authority_pin,
            'scope': self.selection['scope'], 'inputs': self.selection['inputs'],
            'full_plan': self.selection['full_plan'], 'original_authority': selected['original_authority'],
            'submission': None if arm is None else self.selection['submissions'][arm],
            'package': str(self.session.root / self.session.base), 'root': str(self.roots.roots['R']),
            'output': str(output), 'terminal_name': 'HM_WORKER_TERMINAL_' + str(sequence) + '.json'}
        request = metadata.publish('WORKER_REQUEST.json', request_body)
        self.budget.suspend(lease_body, lease.descriptor, base_body, base.descriptor)
        # One actual original H stage, never an in-process scientific shortcut.
        event = self.stage_transport.channel.exchange('stage', {
            'schema': 'hundred_models_original_stage_dispatch_v1',
            'worker_request': request.descriptor, 'worker_request_body': request_body,
            'lease': lease.descriptor, 'lease_body': lease_body,
            'base_state': base.descriptor, 'base_state_body': base_body})
        need(self.stage_transport.channel.owns_completed_event(event),
             'actual same original stage-channel event, not an equal supplied receipt')
        admission = self.closure['admit'](event, budget=self.budget, plan=self.budget.plan,
            full_plan=coordinator.plan, adapter_meter=self.stage_transport.channel.meter,
            selected_submission=None if arm is None else coordinator.submissions[arm])
        restored = self.budget.restore(admission)
        need(restored == {'already_consumed': False, 'state_mutated': True},
             'this MAIN consumes each actual original stage return exactly once')
        self.stages.append(admission)
        # H can finish inside its terminal row, before the restored C row starts.
        # Retain the consumed return first, then wait under the original bridge
        # owner; no early C capture, descriptor processing or scientific work.
        self.stage_transport.wait_until_original_ns(
            self.budget.plan.rows[self.budget.row]['window']['start_ns'])
        if arm is None:
            coordinator.record_reference(admission)
        else:
            coordinator.collect_candidate(arm, admission)
        return admission

    def _final_rows(self):
        coordinator = self.coordinator
        coordinator.seal_both()
        self.budget.advance_final_row('C04')
        self.stage_transport.wait_until_original_ns(self.budget.plan.rows['C04']['window']['start_ns'])
        coordinator.open_reference()
        self.budget.advance_final_row('C05')
        self.stage_transport.wait_until_original_ns(self.budget.plan.rows['C05']['window']['start_ns'])
        qualifications = {arm: self._document(self.selection['qualifications'][arm]) for arm in ('A', 'B')}
        # A genuine separate H pair producer must supply fresh namespace/cache,
        # common-input and own-run evidence. The existing consumer still refuses
        # while that producer is absent; no flag or score can replace it.
        self.pair_event = self.stage_transport.channel.exchange('continuation', {
            'schema': 'hundred_models_original_matched_pair_request_v1',
            'pair_id': coordinator.pair_id, 'scope': coordinator.identities['scope'],
            'inputs': coordinator.identities['inputs'], 'plan': coordinator.identities['plan'],
            'original_stage_receipts': [stage.record_pin for stage in self.stages],
            'candidate_seals': {arm: coordinator.seals[arm]['identity'] for arm in ('A', 'B')}})
        need(self.stage_transport.channel.owns_completed_event(self.pair_event),
             'actual original H pair response from this channel')
        self.pair_admission = self.cm['admit_matched_pair'](root_event=self.pair_event,
            source_session=self.session, reservation_plan=self.budget.plan,
            originals=coordinator.candidates)
        self.report = coordinator.score_and_compare(qualifications=qualifications,
            pair_admission=self.pair_admission,
            report_output=self.roots.roots['R'] / 'central_output' / 'programme' / 'comparison')
        self.notice = send_original_hm_final_notice_v1(
            coordinator=coordinator, channel=self.stage_transport.channel)
        self.phase = 'provisional_final_notice_sent'
        return self.notice

    def close_owned(self):
        if self.closed:
            return
        self.closed = True
        for custody in reversed(self.owned_custodies):
            if getattr(custody, '_hm_main_owner_v1', None) is not self:
                self.retain(RuntimeError('original MAIN channel custody changed'), 'MAIN_custody_loss')
                continue
            try:
                custody.close_owned_once(primary=self.primary)
            except BaseException as error:
                self.retain(error, 'MAIN_owned_channel_close')
        if getattr(self.session, '_hm_main_owner_v1', None) is not self:
            self.retain(RuntimeError('original MAIN source custody changed'), 'MAIN_source_custody_loss')
        elif not self.session.closed:
            try:
                self.session.close()
            except BaseException as error:
                self.retain(error, 'MAIN_owned_source_close')

    def run(self):
        if self.primary is not None:
            raise self.primary
        need(not self.entered, 'one complete original MAIN run, no failed replay')
        self.entered = True
        try:
            self.require_original()
            self.issuer.prepare_issuer_credits_once()
            self.prepare()
            for sequence in (1, 2, 3):
                self._stage(sequence)
            result = self._final_rows()
        except BaseException as error:
            self.retain(error, 'MAIN_original_full_campaign')
            result = None
        finally:
            self.close_owned()
        if self.primary is not None:
            # Actual owner and exact prefixes remain available even before a
            # Coordinator/report exists. No replacement successful report.
            try:
                BaseException.__setattr__(self.primary, 'four_original_hm_main', self)
            except BaseException as error:
                self.secondaries.append(('MAIN_failure_attachment', error))
            raise self.primary
        return result


def create_original_hm_main_v1(*, session, budget, roots, selection_pin,
                               issuer_custody, stage_custody):
    return HMMainV1(_MAIN, session=session, budget=budget, roots=roots,
        selection_pin=selection_pin, issuer_custody=issuer_custody, stage_custody=stage_custody)
