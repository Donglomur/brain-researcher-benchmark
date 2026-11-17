"""Full original HM C composition across the fixed C00--C05 reservations.

This connects original own-run receipts, both seals, the complete8223 reference
graph, original scoring and paired comparison. It never replaces a missing
qualified root issuer, original H stage producer, or independent private panel.
"""
from pathlib import Path
from .stage_budget import ExclusiveBudget
from .stage_closure import StageAdmission
from .reservations import ReservationPlan
from .guard import capture,strict,encoded,Publisher
from four_programmes.common import need,closed,pin,encode,failure,bounded_size,DependencyUnavailable
from four_programmes.source_session import SourceSession
from four_programmes.roots import BoundRoots
from four_programmes.hm_receipts import reference_submission,candidate_submission,seal_candidates,make_matched_pair

class OriginalBudgetStore:
    """One declared original Publisher base, with the same active HM Budget."""
    def __init__(self,root,budget):
        self.root=Path(root);self.budget=budget
    def document(self,d,cap):
        need(type(d) is dict and type(d.get('bytes')) is int and 0<=d['bytes']<=cap,
             'complete original descriptor extent before read/parse')
        self.budget.charge('work',d['bytes']*64+4096)
        return strict(capture(self.root,d,self.budget,cap=cap))

_PAIR=object()
class MatchedPairAdmission:
    __slots__=('complete','pair_id','submissions','common_inputs','budget_identity','record_pin','whole_costs','_token')
    def __init__(self,token,**values):
        need(token is _PAIR and set(values)==set(self.__slots__)-{'_token'},'fixed independent original pair admission')
        for name,value in values.items():setattr(self,name,value)
        self._token=token

def admit_matched_pair(*,root_event,source_session,reservation_plan,originals):
    # No existing selected source proves both fresh namespaces/cache exclusions
    # and own-run source/support identity from the original completed outputs.
    # A root JSON true flag or same score is not that missing native producer.
    raise DependencyUnavailable('HM_original_matched_pair_issuer',
        'exact source-owned independent fresh-workspace/cache/common-input/own-run admission producer remains unselected')

class Coordinator:
    def __init__(self,*,session,budget,roots,scope,inputs,full_plan,submissions,pair_id):
        need(type(session) is SourceSession and session.programme=='PAPER-paper-method-replacement-016' and
             type(budget) is ExclusiveBudget and budget.owner=='C' and budget.row=='C00' and
             type(roots) is BoundRoots and type(budget.plan) is ReservationPlan,
             'actual original source session, root namespaces and initial one C Budget')
        budget.require_operation('prepare')
        need(set(roots.roots)=={'R'} and roots.relative_base=='R',
             'one existing independently selected R; future fresh Publisher roots are not precreated')
        r=roots.roots['R'];out=r/'central_output'/'programme'
        self.layout={'R':r,'reference_output':out/'reference',
                     'candidate_output_A':out/'candidate-A','candidate_output_B':out/'candidate-B'}
        need(type(pair_id) is str and 0<len(pair_id)<=256 and set(submissions)=={'A','B'},
             'one original selected attempt and both distinct own-run submissions')
        need(type(full_plan) is dict and len(full_plan.get('jobs',[]))==8223 and
             len({j['id'] for j in full_plan['jobs']})==8223,'entire original8223 graph, never a representative subset')
        budget.charge('work',bounded_size([scope,inputs,full_plan,submissions]))
        compiled=session.module('scope').compile_jobs(scope,inputs)
        need(encoded(compiled)==encoded(full_plan),'actual complete original compiler equals full immutable plan')
        need([i for i,j in enumerate(full_plan['jobs']) if j['kind']=='consume']==[8221] and
             full_plan['jobs'][8221]['id']=='consume' and full_plan['jobs'][8222]['id']=='report',
             'original full source order and declared consume Publisher ordinal')
        self.session=session;self.budget=budget;self.roots=roots;self.scope=scope;self.inputs=inputs
        self.plan=full_plan;self.submissions=submissions;self.pair_id=pair_id
        self.identities={'scope':pin(encoded(scope)),'inputs':pin(encoded(inputs)),'plan':pin(encoded(full_plan))}
        self.stages=[];self.candidates={};self.seals=None;self.reference=None;self.scores={};self.paired=None
        self.primary=None;self.failures=[];self.phase='reference_pending';self.score_io=None
        # Actual original publication return and one terminal attempt are retained.
        self.report_publication=None;self.report_descriptor=None;self.report_raw=None
        self.final_terminal_raw=None;self.final_notice_attempted=False;self.final_notice_pin=None

    def _own(self,error,operation):
        if self.primary is None:self.primary=error
        self.budget._own(error);self.phase='failed'
        self.failures.append({'operation':operation,'original_failure':failure(error),
                              'same_original_primary':error is self.primary,'original_budget':self.budget.snapshot()})

    def _closed_stage(self,stage,sequence):
        need(type(stage) is StageAdmission and stage.plan is self.budget.plan and stage.complete and stage.eligible and
             self.budget.consumed.get(encode(stage.return_pin)) is stage and
             self.budget.previous_return==stage.return_pin and self.budget.generation==sequence,
             'actual original H admission already restored into this same C writer')
        lease=stage.lease
        need(lease['sequence']==sequence and lease['stage']==('reference' if sequence==1 else 'candidate:'+('A' if sequence==2 else 'B')) and
             all(lease[k]==v for k,v in self.identities.items()),'same original full scope/inputs/8223 plan')
        # The original reference executes the entire 8,223-job graph. Each
        # candidate is one independently isolated submission whose *result*
        # must cover the whole scientific support. Its process domain is the
        # exact submission identity, as already enforced by stage_closure.
        need(type(sequence) is int and sequence in (1,2,3),
             'only the original reference and two candidate stages')
        domain=([j['id'] for j in self.plan['jobs']] if sequence==1
                else [lease['submission']])
        need(stage.completion['ordered_domain']==domain,
             'whole reference graph or exact original own-run candidate domain')
        if self.stages:
            need(lease['previous_return']==self.stages[-1].return_pin,'same actually consumed predecessor')
        else:need(lease['previous_return'] is None,'original first-stage predecessor')

    def record_reference(self,stage):
        need(self.phase=='reference_pending' and self.budget.row=='C01','reference closure precedes candidateA')
        try:
            self._closed_stage(stage,1)
            need(stage.subject=='reference' and stage.completion['result'] is not None,'original complete reference result descriptor')
            self.stages.append(stage);self.phase='A_pending'
            # Deliberately no R00/R01/R02/R03 body traversal while either
            # candidate still has access to its isolated source/data view.
            return stage.completion['result']
        except BaseException as error:self._own(error,'reference_descriptor_only');raise

    def collect_candidate(self,arm,stage):
        expected={'A':('A_pending','C02',2),'B':('B_pending','C03',3)}
        need(arm in expected and (self.phase,self.budget.row)==expected[arm][:2] and self.primary is None,
             'actual same-budget candidate capture in its exact original row')
        try:
            self.budget.require_operation('capture_'+arm);self._closed_stage(stage,expected[arm][2])
            need(stage.lease['submission']==pin(encoded(self.submissions[arm])) and
                 self.submissions[arm]['arm']==arm and stage.candidate_receipt_pin==stage.completion['result'],
                 'separate exact original own-run candidate identity')
            store=OriginalBudgetStore(self.layout['candidate_output_'+arm],self.budget)
            original=candidate_submission(stage.candidate_receipt_pin,store,self.submissions[arm],
                                          source_encode=encoded,process_admission=stage)
            self.candidates[arm]=original;self.stages.append(stage)
            self.phase='B_pending' if arm=='A' else 'both_collected'
            return original
        except BaseException as error:self._own(error,'candidate_'+arm+'_own_run_capture');raise

    def seal_both(self):
        need(self.phase=='both_collected' and self.budget.row=='C03' and self.primary is None,
             'both entire original candidate documents captured before sealing')
        try:
            self.budget.require_operation('seal')
            self.budget.charge('work',bounded_size(self.candidates)*64+4096)
            self.seals=seal_candidates(self.candidates,encoded);self.phase='both_sealed'
            return {arm:self.seals[arm]['identity']for arm in ('A','B')}
        except BaseException as error:self._own(error,'complete_paired_seal');raise

    def open_reference(self):
        need(self.phase=='both_sealed' and self.budget.row=='C04' and self.primary is None,
             'both original seals and fixed C04 precede any protected reference body')
        try:
            self.budget.require_operation('protected_reference')
            for arm in ('A','B'):
                self.budget.charge('work',bounded_size(self.candidates[arm]['document'])*64+4096)
                need(encoded(self.candidates[arm]['document'])==self.seals[arm]['raw'],
                     'same complete original own-run candidate after both seals')
            root=self.layout['reference_output'];consume_root=root/'work_08221'
            self.reference=reference_submission(self.plan,self.stages[0].completion['result'],
                OriginalBudgetStore(root,self.budget),OriginalBudgetStore(self.layout['R'],self.budget),
                OriginalBudgetStore(consume_root,self.budget),source_encode=encoded,
                scope_identity=self.identities['scope'],inputs_identity=self.identities['inputs'])
            self.phase='reference_opened';return self.reference
        except BaseException as error:self._own(error,'complete8223_reference_resolution');raise

    def score_and_compare(self,*,qualifications,pair_admission,report_output):
        need(self.phase=='reference_opened' and self.budget.row=='C05' and self.primary is None,
             'complete protected reference followed by original final C05 row')
        try:
            need(type(pair_admission) is MatchedPairAdmission and pair_admission.complete and
                 pair_admission.pair_id==self.pair_id and set(qualifications)=={'A','B'},
                 'independently produced complete own-run pair qualification, not source strings or flags')
            self.score_io=self.budget.reserve_complete_score()
            # Original score and arms APIs have no budget argument. The full
            # earlier C05 share is reserved before either enters; original
            # hard physical/clock enforcement remains an external prerequisite.
            for arm in ('A','B'):
                self.budget.require_operation('score')
                self.scores[arm]=self.session.api('hm_score')(self.scope,self.candidates[arm]['document'],
                                                            self.reference['document'],qualifications[arm])
                self.budget.check()
            pair=make_matched_pair(self.pair_id,self.scores,self.candidates,pair_admission)
            self.budget.require_operation('arms')
            self.paired=self.session.api('hm_arms')([pair]);self.budget.check()
            publication=Publisher(report_output,self.score_io)
            body={'schema':'four_hundred_models_complete_original_comparison_v1','pair_id':self.pair_id,
                  'full_original_jobs':8223,'plan':self.identities['plan'],'original_scores':self.scores,
                  'original_paired_comparison':self.paired,'candidate_seals':{a:self.seals[a]['identity']for a in ('A','B')},
                  'original_stage_receipts':[s.record_pin for s in self.stages],
                  'original_budget':self.budget.snapshot(),'original_failures':self.failures,
                  'improvement':{'status':'required_unscorable','reason':'independent private-panel producer not selected'},
                  'original_C_exit_still_required':True,'scientific_qualification':False,'SOTA_claim':False}
            raw=encoded(body)
            descriptor=publication.write('REPORT.json',raw)
            # Retain the actual complete write before the later clock can fail.
            self.report_publication=publication;self.report_descriptor=descriptor;self.report_raw=raw
            self.budget.check()
            self.phase='reported_provisional';return descriptor
        except BaseException as error:self._own(error,'original_full_score_and_pair');raise

    def unavailable_pair(self):
        """Outer failure evidence keeps the selected pair without fake scores."""
        return {'pair_id':self.pair_id,'status':'operator_unavailable','original_failures':list(self.failures),
                'candidate_originals':self.candidates,'original_scores':self.scores,
                'original_stage_receipts':[s.record_pin for s in self.stages],
                'full_original_jobs':8223,'original_plan':self.identities['plan'],
                'paired_comparison':None,'original_budget':self.budget.snapshot(),
                'full_outstanding_reservations_retained':True,'scientific_qualification':False}
