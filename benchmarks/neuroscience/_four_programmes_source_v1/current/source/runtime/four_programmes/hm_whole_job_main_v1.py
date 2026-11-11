"""Fixed complete C caller for the separately selected whole-job HM profile.

No arbitrary program callback, native execution on import, or success fallback.
Missing source/environment/isolation/pair evidence remains a real failure.
"""
from .common import need, closed, pin, encode
from .source_session import SourceSession
from .roots import BoundRoots
from .hm_main_metadata_v1 import captured_module
from .hm_whole_job_controller_v1 import HMWholeControllerCustodyV1
from .hm_whole_job_controller_budget_v1 import HMWholeControllerBudgetV1
from .hm_whole_job_stage_admission_v1 import admit_original_hm_whole_stage_v1
from .hm_whole_job_coordinator_v1 import HMWholeScientificCoordinatorV1
from .hm_whole_worker_contract_v1 import validate_request

_TOKEN = object()


class HMWholeMainV1:
    def __init__(self, token, *, session, budget, roots, selection_pin, custody):
        need(token is _TOKEN and type(session) is SourceSession and
             type(budget) is HMWholeControllerBudgetV1 and budget.session is session and
             type(custody) is HMWholeControllerCustodyV1 and not custody.is_endpoint and
             custody.session is session and custody.plan is budget.plan and type(roots) is BoundRoots,
             'same actual original C source, budget, roots and channel custody')
        need(getattr(session, '_hm_whole_main_v1', None) is None,
             'one original whole-job MAIN attempt, including first preparation failure')
        self.session = session;self.budget = budget;self.roots = roots;self.custody = custody
        self.selection_pin = selection_pin;self.selection = None;self.coordinator = None
        self.raw_first = None;self.secondaries = [];self.entered = False;self.closed = False
        self.publication = None;self.stage_requests = [];self.stages = [];self.pair_event = None
        self.report = None;self.final_event = None;session._hm_whole_main_v1 = self
        try:
            self.gm = captured_module(session, 'guard');self.cm = captured_module(session, 'coordinator')
            custody.require_original()
        except BaseException as error:
            self.retain(error, 'actual_MAIN_partial_owner_admission')
            self.close_once()
            raise self.raw_first

    def retain(self, error, site):
        if self.raw_first is None:self.raw_first = error
        elif error is not self.raw_first:self.secondaries.append((site, error))
        self.budget._own(error)

    def _document(self, descriptor):
        return self.cm['OriginalBudgetStore'](self.roots.roots['R'], self.budget).document(
            descriptor, self.budget.limits['read_bytes'])

    def _publish(self, name, body):
        raw = self.gm['encoded'](body);d = self.publication.write(name, raw)
        need(pin(encode(body)) == {k: d[k] for k in ('bytes', 'sha256')}, 'actual canonical publication return')
        return {'descriptor': d, 'body': body}

    def _prepare(self):
        self.budget.require_operation('prepare');selected = self._document(self.selection_pin)
        closed(selected, ('schema', 'profile', 'pair_id', 'scope', 'inputs', 'full_plan',
                          'submissions', 'original_authorities', 'qualifications'))
        need(selected['schema'] == 'hm_whole_fixed_main_selection_v1' and
             selected['profile'] == self.budget.plan.pin, 'distinct exact whole-job MAIN selection')
        closed(selected['submissions'], ('A', 'B'));closed(selected['qualifications'], ('A', 'B'))
        closed(selected['original_authorities'], ('reference', 'candidate:A', 'candidate:B'))
        for d in selected['original_authorities'].values():self.gm['descriptor'](d)
        scientific = {key: self._document(selected[key]) for key in ('scope', 'inputs', 'full_plan')}
        submissions = {arm: self._document(selected['submissions'][arm]) for arm in ('A', 'B')}
        self.selection = selected
        self.coordinator = HMWholeScientificCoordinatorV1(session=self.session, budget=self.budget,
            roots=self.roots, submissions=submissions, pair_id=selected['pair_id'], **scientific)
        self.publication = self.gm['Publisher'](
            self.roots.roots['R'] / 'central_output' / 'whole-control', self.budget)

    def _stage(self, sequence):
        c = self.coordinator;row = self.budget.plan.stage(sequence);selected = self.selection
        need(self.budget.sequence == sequence - 1 and len(self.stages) == sequence - 1,
             'full serial original reference/A/B sequence without replay')
        arm = None if sequence == 1 else ('A' if sequence == 2 else 'B')
        output = c.layout['reference_output' if arm is None else 'candidate_output_' + arm]
        request_body = validate_request({'schema': 'hm_whole_worker_scientific_request_v1',
            **{key: selected[key] for key in ('scope', 'inputs', 'full_plan')},
            'original_authority': selected['original_authorities'][row['stage']],
            'submission': None if arm is None else selected['submissions'][arm],
            'package': str(self.session.root / self.session.base), 'root': str(self.roots.roots['R']),
            'output': str(output), 'terminal_name': 'HM_WHOLE_WORKER_TERMINAL_' + str(sequence) + '.json'})
        request = self._publish('WORKER_REQUEST_' + str(sequence) + '.json', request_body)
        subject = self._publish('SUBJECT_' + str(sequence) + '.json', {
            'schema': 'hm_whole_stage_subject_v1', 'profile': self.budget.plan.pin,
            'sequence': sequence, 'stage': row['stage'],
            **{key: self.budget.plan.body[key] for key in ('source_manifest', 'environment', 'launch_policy')},
            **c.identities, 'submission': None if arm is None else pin(self.gm['encoded'](c.submissions[arm])),
            'original_authority': request_body['original_authority'], 'request': pin(encode(request_body))})
        dispatch = {'schema': 'hm_whole_stage_dispatch_request_v1', 'sequence': sequence,
            'profile': self.budget.plan.pin, 'subject': subject, 'scientific_request': request,
            'original_authority': request_body['original_authority']}
        self.stage_requests.append(dispatch)
        self.budget.suspend_for_stage_once(sequence)
        event = self.custody.channel.exchange('stage', dispatch)
        admission = admit_original_hm_whole_stage_v1(event, custody=self.custody, budget=self.budget,
            full_plan=c.plan, expected_subject=subject, expected_request=request,
            selected_submission=None if arm is None else c.submissions[arm])
        self.budget.consume_stage_once(admission);self.stages.append(admission)
        if arm is None:c.record_reference(admission)
        else:c.collect_candidate(arm, admission)

    def _final(self):
        c = self.coordinator;c.seal_both();c.open_reference()
        qualifications = {arm: self._document(self.selection['qualifications'][arm]) for arm in ('A', 'B')}
        self.pair_event = self.custody.channel.exchange('continuation', {
            'schema': 'hm_whole_matched_pair_request_v1', 'profile': self.budget.plan.pin,
            'pair_id': c.pair_id, **c.identities,
            'stage_returns': [s.record_pin for s in self.stages],
            'candidate_seals': {arm: c.seals[arm]['identity'] for arm in ('A', 'B')}})
        need(self.custody.channel.owns_completed_event(self.pair_event), 'actual original H pair response')
        # Original consumer deliberately refuses its genuinely absent native
        # isolation/common-input producer. This call cannot manufacture it.
        pair = self.cm['admit_matched_pair'](root_event=self.pair_event, source_session=self.session,
            reservation_plan=self.budget.plan, originals=c.candidates)
        self.report = c.score_and_compare(qualifications=qualifications, pair_admission=pair,
            report_output=self.roots.roots['R'] / 'central_output' / 'programme' / 'comparison')
        self.final_event = self.custody.channel.exchange('final_report', {
            'schema': 'hm_whole_original_C_final_request_v1', 'profile': self.budget.plan.pin,
            'report': self.report, 'stage_returns': [s.record_pin for s in self.stages],
            'original_budget': self.budget.snapshot(), 'later_original_whole_reconciliation_required': True})
        need(self.custody.channel.owns_completed_event(self.final_event) and
             self.final_event.body['status'] == 'observed', 'actual H prefix acknowledgement; outer closure still required')
        return self.final_event

    def close_once(self):
        if self.closed:return
        self.closed = True
        try:self.custody.close_once(primary=self.raw_first)
        except BaseException as error:self.retain(error, 'actual_C_channel_close')
        if self.session._hm_whole_main_v1 is self and not self.session.closed:
            try:self.session.close()
            except BaseException as error:self.retain(error, 'actual_C_source_close')

    def run_once(self):
        need(not self.entered, 'one complete original MAIN, including failure')
        self.entered = True;result = None
        try:
            self._prepare()
            for sequence in (1, 2, 3):self._stage(sequence)
            result = self._final()
        except BaseException as error:self.retain(error, 'original_full_whole_job_MAIN')
        finally:self.close_once()
        if self.raw_first is not None:
            try:BaseException.__setattr__(self.raw_first, 'four_original_hm_whole_main', self)
            except BaseException as later:self.secondaries.append(('failure_attachment', later))
            raise self.raw_first
        return result


def create_original_hm_whole_main_v1(*, session, budget, roots, selection_pin, custody):
    return HMWholeMainV1(_TOKEN, session=session, budget=budget, roots=roots,
                        selection_pin=selection_pin, custody=custody)
