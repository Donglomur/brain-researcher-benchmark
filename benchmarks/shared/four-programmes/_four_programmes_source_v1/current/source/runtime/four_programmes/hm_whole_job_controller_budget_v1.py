"""Original scientific C budget under a distinct predeclared whole-job share."""
from .common import need, integer
from .source_session import SourceSession
from .hm_whole_job_profile_v1 import HMWholeJobPlanV1, PROGRAMME, LOGICAL

_TOKEN = object()


class HMWholeControllerBudgetV1:
    def __init__(self, token, *, session, plan):
        need(token is _TOKEN and type(session) is SourceSession and not session.closed and
             session.programme == PROGRAMME and type(plan) is HMWholeJobPlanV1,
             'original admitted source and distinct whole-job controller selection')
        need(getattr(session, '_hm_whole_controller_budget_v1', None) is None,
             'one source-owned C logical budget, including failed initialization')
        self.session = session;self.plan = plan;self.original = None
        self.primary = None;self.secondary = [];self.active = True
        self.sequence = 0;self.pending_sequence = None;self.consumed = {};self.previous_return = None
        self.score_hold = None;self.closed = False;self.owner = 'C'
        session._hm_whole_controller_budget_v1 = self
        try:
            plan.require_original()
            guard = session.module('guard')
            self.original = guard.Budget(**plan.body['controller'], deadline_ns=plan.run_deadline_ns)
        except BaseException as error:self._own(error);raise self.primary

    @property
    def limits(self):return self.original.limits
    @property
    def used(self):return self.original.used
    @property
    def deadline_ns(self):return self.original.deadline_ns
    @property
    def failed(self):return self.primary is not None or self.original.failed

    def _own(self, error):
        if self.primary is None:self.primary = error
        elif error is not self.primary:self.secondary.append(error)
        if self.original is not None:self.original.failed = True

    def check(self):
        if self.primary is not None:raise self.primary
        need(not self.closed and self.session._hm_whole_controller_budget_v1 is self,
             'same original open C logical budget')
        self.plan.require_original()
        try:self.original.check()
        except BaseException as error:self._own(error);raise self.primary

    def require_operation(self, operation):
        self.check()
        need(self.active and self.pending_sequence is None and operation in
             ('prepare', 'capture_A', 'capture_B', 'seal', 'protected_reference', 'score', 'arms'),
             'C scientific work only while original W writer is inactive')

    def charge(self, kind, amount):
        self.check();need(self.active, 'original C logical writer inactive during W')
        integer(amount);need(kind in LOGICAL, 'original scientific logical dimension')
        try:self.original.charge(kind, amount)
        except BaseException as error:self._own(error);raise self.primary

    def suspend_for_stage_once(self, sequence):
        self.check();integer(sequence, 1)
        need(self.active and self.pending_sequence is None and sequence == self.sequence + 1 and
             sequence <= 3, 'one next original full stage, without replay')
        self.pending_sequence = sequence;self.active = False

    def consume_stage_once(self, admission):
        if self.primary is not None:raise self.primary
        from .hm_whole_job_stage_admission_v1 import HMWholeStageAdmissionV1
        need(type(admission) is HMWholeStageAdmissionV1 and admission.plan is self.plan and
             admission.complete and admission.eligible and admission.sequence == self.pending_sequence and
             admission.previous_return == self.previous_return and
             admission.return_key not in self.consumed and not self.active,
             'actual next original H return while this C writer is inactive')
        # Latch the exact consumed original before later clock checks.
        self.consumed[admission.return_key] = admission
        self.sequence = admission.sequence;self.previous_return = admission.record_pin
        self.pending_sequence = None;self.active = True
        self.check()
        return admission

    def reserve_complete_score(self):
        self.require_operation('score')
        need(self.sequence == 3 and self.score_hold is None, 'one complete terminal score reservation')
        amounts = {k:self.limits[k] - self.used[k] for k in LOGICAL}
        hold = HMWholeScoreHoldV1(_TOKEN, self, amounts);self.score_hold = hold
        try:
            for key in LOGICAL:self.charge(key, amounts[key])
            hold.admitted = True;return hold
        except BaseException as error:self._own(error);raise self.primary

    def snapshot(self):
        return {'schema':'hm_whole_controller_logical_prefix_v1',
            'original':None if self.original is None else self.original.snapshot(),
            'profile':self.plan.pin, 'sequence':self.sequence, 'pending_sequence':self.pending_sequence,
            'active':self.active, 'whole_physical_cost_requires_H_observation':True,
            'whole_physical_cost_known_here':False, 'full_reserved_capacity_retained':True,
            'terminal_hold':None if self.score_hold is None else self.score_hold.record()}


class HMWholeScoreHoldV1:
    def __init__(self, token, owner, limits):
        need(token is _TOKEN, 'source-owned pre-reserved terminal score hold')
        self.owner = owner;self.limits = dict(limits);self.used = dict.fromkeys(LOGICAL, 0)
        self.admitted = False

    def check(self):
        need(self.owner.score_hold is self and self.admitted,
             'same original fully reserved score/output hold')
        self.owner.check()

    def charge(self, kind, amount):
        self.check();integer(amount);need(kind in LOGICAL, 'original score/output category')
        self.used[kind] += amount
        try:need(self.used[kind] <= self.limits[kind], 'earlier complete score hold exceeded; no refill')
        except BaseException as error:self.owner._own(error);raise self.owner.primary

    def snapshot(self):return self.record()
    def record(self):
        return {'reserved':dict(self.limits),'used':dict(self.used),'admitted':self.admitted,
                'already_charged_to_original_C_budget':True,'new_allowance':False}


def create_original_hm_whole_controller_budget_v1(*, session, plan):
    return HMWholeControllerBudgetV1(_TOKEN, session=session, plan=plan)
