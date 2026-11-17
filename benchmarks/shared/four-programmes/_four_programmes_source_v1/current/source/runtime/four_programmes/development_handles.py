"""Source-owned original H development handles and final pair capability.

This module defines the fixed owners before the native route is entered. Wire
records cannot construct them. Native launch/admission is a separate actual
producer; unfinished owners remain retained and never count as completion.
"""
from .common import need
from .early_resources import EarlyResources
from .backend_capture import CapturedRecord
from .development_preparation import PreparationHandle
from .precommit_records import CONDITIONS

_ATTEMPT=object()
_PAIR_COMPLETE=object()

class DevelopmentAttemptHandle:
    __slots__=('pair','condition','host','arm','process','streams','selector','started_ns','run_deadline_ns',
               'evidence_deadline_ns','prefix_capture','process_capture','group_capture','launch_ack',
               'native_launch_admission','raw_first','raw_secondaries','spawn_state','spawn_entered',
               'finish_attempted','wait_consumed','wait_result','process_observation','complete_stream_capture',
               'cost_observation','descendant_workspace_closure','backend','source_closed','worker_kernel','evidence_capture',
               'native_channel','native_observations','whole_arm_capture','output_finalization','host_terminal_custody','start_observation','launch_group_owner','bootstrap_carrier','native_control_plan','native_launch_pipeline','_token')
    def __init__(self,token,pair,condition,host):
        need(token is _ATTEMPT,'actual fixed H original development attempt')
        need(type(pair) is PreparationHandle and pair.promotion is pair and
             type(pair.outcome) is CapturedRecord and pair.outcome.kind=='PreparationSuccess',
             'same fully prepared original pair before worker registration')
        need(condition in CONDITIONS,'fixed original condition')
        self._token=token;self.pair=pair;self.condition=condition;self.host=host;self.arm=pair.arms[condition]
        self.process=None;self.streams=None;self.selector=None
        self.started_ns=None;self.run_deadline_ns=self.arm.launch.body['run_deadline_ns']
        self.evidence_deadline_ns=self.arm.launch.body['evidence_deadline_ns']
        self.prefix_capture=None;self.process_capture=None;self.group_capture=None;self.launch_ack=None
        self.native_launch_admission=None;self.raw_first=None;self.raw_secondaries=[]
        self.spawn_state='not_attempted';self.spawn_entered=False;self.finish_attempted=False
        self.wait_consumed=False;self.wait_result=None;self.process_observation=None
        self.complete_stream_capture=None;self.cost_observation=None;self.descendant_workspace_closure=None
        self.backend=None;self.source_closed=False;self.worker_kernel=None;self.evidence_capture=None
        self.native_channel=None;self.native_observations=None;self.whole_arm_capture=None
        self.output_finalization=None
        self.host_terminal_custody=None
        self.start_observation=None;self.launch_group_owner=None;self.bootstrap_carrier=None
        self.native_control_plan=None;self.native_launch_pipeline=None
    @property
    def owner(self):return self.pair.owner
    def retain(self,error,site,unknown=None):
        if self.raw_first is None:self.raw_first=error
        elif error is not self.raw_first:self.raw_secondaries.append(error)
        try:self.owner.parent.retain(error,'development_observe','unknown_failure',site,unknown)
        except BaseException as later:self.raw_secondaries.append(later)
    def require_live_original(self):
        need(self._token is _ATTEMPT and self.owner.parent.preparation is self.pair and
             self.pair.launches.get(self.condition) is self,'actual same registered original H attempt')
    @property
    def complete(self):
        from .observer import OriginalProcessObservation
        observed=self.process_observation
        return (self.raw_first is None and self.finish_attempted and self.source_closed and
                type(observed) is OriginalProcessObservation and observed.success and
                all(type(x) is CapturedRecord for x in
                    (self.prefix_capture,self.process_capture,self.group_capture,self.launch_ack,
                     self.complete_stream_capture,self.cost_observation,self.descendant_workspace_closure)))

class PairCompletionHandle:
    __slots__=('pair','attempts','completions','closure','raw_first','raw_secondaries','attempted','_token','backend_views')
    def __init__(self,token,pair):
        need(token is _PAIR_COMPLETE and type(pair) is PreparationHandle and pair.promotion is pair,
             'actual fixed original pair completion producer')
        self._token=token;self.pair=pair;self.attempts={}
        self.completions={};self.closure=None;self.raw_first=None;self.raw_secondaries=[];self.attempted=False
        self.backend_views={}
    @property
    def owner(self):return self.pair.owner
    def retain(self,error,site):
        # An actual worker/receiver may already have failed under this same
        # original parent before the pair producer enters its terminal loop.
        # A later incomplete-view diagnostic must not replace that raw first.
        first=self.owner.parent.first_raw
        if self.raw_first is None:self.raw_first=error if first is None else first
        if error is not self.raw_first:self.raw_secondaries.append(error)
        try:self.owner.parent.retain(error,'development_observe','unknown_failure',site)
        except BaseException as later:self.raw_secondaries.append(later)
    def require_original(self):
        need(self._token is _PAIR_COMPLETE and getattr(self.pair,'backend_completion',None) is self and
             self.owner.parent.preparation is self.pair and self.pair.promotion is self.pair,
             'same source-owned registered completion; no decoded replacement')
        need(self.raw_first is None and self.owner.parent.first_raw is None,
             'no success after any retained original owner failure')
        need(set(self.attempts)==set(CONDITIONS) and set(self.completions)==set(CONDITIONS),
             'both complete original attempts and v3 completion captures')
        for condition in CONDITIONS:
            attempt=self.attempts[condition];completion=self.completions[condition]
            need(type(attempt) is DevelopmentAttemptHandle and attempt.pair is self.pair and
                 attempt.condition==condition and self.pair.launches.get(condition) is attempt and attempt.complete,
                 'actual completed original same-arm H lifecycle')
            need(type(completion) is CapturedRecord and completion.owner is self.owner and
                 completion.kind=='DevelopmentCompletion' and
                 completion.body['schema']=='ci_developmentcompletion_v3' and
                 completion.body['condition']==condition and
                 completion.body['pair_plan']==self.pair.pair_plan.pin and
                 completion.body['original_attempt']==attempt.prefix_capture.pin,
                 'exact complete v3 capture bound to original H attempt')
            from .development_targets import require_completion_targets
            require_completion_targets(attempt,completion)
        need(type(self.closure) is CapturedRecord and self.closure.owner is self.owner and
             self.closure.kind=='DevelopmentPairClosure','actual completed original pair closure capture')
        body=self.closure.body
        need(body['schema']=='ci_developmentpairclosure_v3' and body['pair_plan']==self.pair.pair_plan.pin and
             body['same_owner_binding']==self.owner.parent.binding_pin and
             body['completion_by_condition']=={c:self.completions[c].pin for c in CONDITIONS},
             'full v3 pair closure and both exact completed identities')
        from .development_completion import require_original_pair_outputs
        return require_original_pair_outputs(self)
    @property
    def complete(self):
        try:self.require_original();return True
        except BaseException:return False

