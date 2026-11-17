"""Complete original scientific HM composition under the distinct whole profile.

The original compiler, receipts, candidate seals, scorer and arm comparison are
used intact. This is an additive lifecycle adapter, not a strict-V5 row alias.
"""
from .common import need, pin, encode, bounded_size, failure
from .source_session import SourceSession
from .roots import BoundRoots
from .hm_main_metadata_v1 import captured_module
from .hm_receipts import reference_submission, candidate_submission, seal_candidates, make_matched_pair
from .hm_whole_job_controller_budget_v1 import HMWholeControllerBudgetV1
from .hm_whole_job_stage_admission_v1 import HMWholeStageAdmissionV1


class HMWholeScientificCoordinatorV1:
    def __init__(self, *, session, budget, roots, scope, inputs, full_plan, submissions, pair_id):
        need(type(session) is SourceSession and type(budget) is HMWholeControllerBudgetV1 and
             budget.session is session and type(roots) is BoundRoots and
             set(roots.roots) == {'R'} and roots.relative_base == 'R',
             'actual original HM session/budget and one selected scientific root')
        budget.require_operation('prepare')
        need(type(pair_id) is str and 0 < len(pair_id) <= 256 and set(submissions) == {'A', 'B'},
             'one original full matched pair')
        self.session = session;self.budget = budget;self.roots = roots
        self.gm = captured_module(session, 'guard');self.cm = captured_module(session, 'coordinator')
        budget.charge('work', bounded_size([scope, inputs, full_plan, submissions]))
        need(type(full_plan) is dict and len(full_plan.get('jobs', [])) == 8223 and
             len({j['id'] for j in full_plan['jobs']}) == 8223,
             'whole original 8223-job plan, never a representative subset')
        compiled = session.module('scope').compile_jobs(scope, inputs)
        need(self.gm['encoded'](compiled) == self.gm['encoded'](full_plan),
             'actual complete original scientific compiler')
        need([i for i, j in enumerate(full_plan['jobs']) if j['kind'] == 'consume'] == [8221] and
             full_plan['jobs'][8221]['id'] == 'consume' and full_plan['jobs'][8222]['id'] == 'report',
             'unchanged original consume and report publisher ordinals')
        r = roots.roots['R'];out = r / 'central_output' / 'programme'
        self.layout = {'R': r, 'reference_output': out / 'reference',
                       'candidate_output_A': out / 'candidate-A', 'candidate_output_B': out / 'candidate-B'}
        self.scope = scope;self.inputs = inputs;self.plan = full_plan;self.submissions = submissions;self.pair_id = pair_id
        self.identities = {key: pin(self.gm['encoded'](value))
                           for key, value in (('scope', scope), ('inputs', inputs), ('full_plan', full_plan))}
        self.stages = [];self.candidates = {};self.seals = None;self.reference = None
        self.scores = {};self.paired = None;self.primary = None;self.failures = [];self.phase = 'reference_pending'
        self.report_publication = None;self.report_descriptor = None;self.report_raw = None;self.score_io = None

    def _own(self, error, operation):
        if self.primary is None:self.primary = error
        self.budget._own(error);self.phase = 'failed'
        self.failures.append({'operation': operation, 'original_failure': failure(error),
                              'same_original_primary': error is self.primary,
                              'original_budget': self.budget.snapshot()})

    def _closed_stage(self, stage, sequence):
        need(type(stage) is HMWholeStageAdmissionV1 and stage.plan is self.budget.plan and
             stage.complete and stage.eligible and stage.sequence == sequence and
             self.budget.sequence == sequence and self.budget.consumed.get(stage.return_key) is stage and
             self.budget.previous_return == stage.record_pin,
             'actual original H admission consumed once by this same original C writer')
        need(all(stage.record[key] == value for key, value in self.identities.items()) and
             stage.record['previous_return'] == (self.stages[-1].record_pin if self.stages else None),
             'same complete scope/inputs/plan and actual previous consumed stage')
        domain = [j['id'] for j in self.plan['jobs']] if sequence == 1 else [stage.record['submission']]
        need(stage.completion['ordered_domain'] == domain, 'full original reference or exact own-run candidate')

    def record_reference(self, stage):
        need(self.phase == 'reference_pending', 'one original reference before both candidates')
        try:
            self._closed_stage(stage, 1)
            need(stage.subject == 'reference' and stage.completion['result'] is not None,
                 'complete reference result descriptor; protected body remains unopened')
            self.stages.append(stage);self.phase = 'A_pending'
            return stage.completion['result']
        except BaseException as error:self._own(error, 'reference_descriptor_only');raise

    def collect_candidate(self, arm, stage):
        expected = {'A': ('A_pending', 2), 'B': ('B_pending', 3)}
        need(arm in expected and self.phase == expected[arm][0] and self.primary is None,
             'actual original A/B capture in declared order')
        try:
            self.budget.require_operation('capture_' + arm);self._closed_stage(stage, expected[arm][1])
            need(self.submissions[arm]['arm'] == arm and
                 stage.record['submission'] == pin(self.gm['encoded'](self.submissions[arm])) and
                 stage.candidate_receipt_pin == stage.completion['result'], 'same exact own-run candidate result')
            store = self.cm['OriginalBudgetStore'](self.layout['candidate_output_' + arm], self.budget)
            original = candidate_submission(stage.candidate_receipt_pin, store, self.submissions[arm],
                source_encode=self.gm['encoded'], process_admission=stage)
            self.candidates[arm] = original;self.stages.append(stage)
            self.phase = 'B_pending' if arm == 'A' else 'both_collected'
            return original
        except BaseException as error:self._own(error, 'candidate_' + arm + '_own_run_capture');raise

    def seal_both(self):
        need(self.phase == 'both_collected' and self.budget.sequence == 3 and self.primary is None,
             'both complete original own-run candidates before sealing')
        try:
            self.budget.require_operation('seal')
            self.budget.charge('work', bounded_size(self.candidates) * 64 + 4096)
            self.seals = seal_candidates(self.candidates, self.gm['encoded']);self.phase = 'both_sealed'
            return {arm: self.seals[arm]['identity'] for arm in ('A', 'B')}
        except BaseException as error:self._own(error, 'complete_paired_seal');raise

    def open_reference(self):
        need(self.phase == 'both_sealed' and self.primary is None,
             'both actual original seals precede protected reference body access')
        try:
            self.budget.require_operation('protected_reference')
            for arm in ('A', 'B'):
                self.budget.charge('work', bounded_size(self.candidates[arm]['document']) * 64 + 4096)
                need(self.gm['encoded'](self.candidates[arm]['document']) == self.seals[arm]['raw'],
                     'unchanged complete original own-run candidates at target barrier')
            root = self.layout['reference_output'];store = self.cm['OriginalBudgetStore']
            self.reference = reference_submission(self.plan, self.stages[0].completion['result'],
                store(root, self.budget), store(self.layout['R'], self.budget),
                store(root / 'work_08221', self.budget), source_encode=self.gm['encoded'],
                scope_identity=self.identities['scope'], inputs_identity=self.identities['inputs'])
            self.phase = 'reference_opened';return self.reference
        except BaseException as error:self._own(error, 'complete8223_reference_resolution');raise

    def score_and_compare(self, *, qualifications, pair_admission, report_output):
        need(self.phase == 'reference_opened' and self.primary is None, 'full protected reference before scoring')
        try:
            need(type(pair_admission) is self.cm['MatchedPairAdmission'] and pair_admission.complete and
                 pair_admission.pair_id == self.pair_id and set(qualifications) == {'A', 'B'},
                 'independent actual own-run matched-pair qualification remains required')
            self.score_io = self.budget.reserve_complete_score()
            for arm in ('A', 'B'):
                self.budget.require_operation('score')
                self.scores[arm] = self.session.api('hm_score')(
                    self.scope, self.candidates[arm]['document'], self.reference['document'], qualifications[arm])
                self.budget.check()
            pair = make_matched_pair(self.pair_id, self.scores, self.candidates, pair_admission)
            self.budget.require_operation('arms');self.paired = self.session.api('hm_arms')([pair]);self.budget.check()
            publication = self.gm['Publisher'](report_output, self.score_io)
            body = {'schema': 'hm_whole_original_comparison_v1', 'pair_id': self.pair_id,
                'full_original_jobs': 8223, 'plan': self.identities['full_plan'],
                'original_scores': self.scores, 'original_paired_comparison': self.paired,
                'candidate_seals': {arm: self.seals[arm]['identity'] for arm in ('A', 'B')},
                'original_stage_receipts': [s.record_pin for s in self.stages],
                'original_budget': self.budget.snapshot(), 'original_failures': self.failures,
                'improvement': {'status': 'required_unscorable', 'reason': 'independent private panel unavailable'},
                'original_C_H_exit_still_required': True, 'scientific_qualification': False, 'SOTA_claim': False}
            raw = self.gm['encoded'](body);descriptor_out = publication.write('REPORT.json', raw)
            self.report_publication = publication;self.report_descriptor = descriptor_out;self.report_raw = raw
            self.budget.check();self.phase = 'reported_provisional';return descriptor_out
        except BaseException as error:self._own(error, 'original_full_score_and_pair');raise
