"""Actual original H start owner, before carrier publication and Popen.

This is a fixed source producer, not a supplied time/capture constructor. The
private source/root qualifier remains upstream; this module grants none.
"""
import time
from .common import need,same,bounded_size
from .backend_capture import CanonicalPublisher,CapturedRecord
from .development_handles import DevelopmentAttemptHandle


class HWorkerStartOwnerV3:
    def __init__(self,kernel):
        from .development_worker_io import DevelopmentWorkerKernel
        from .development_native_observations import DevelopmentNativeObservation
        need(type(kernel)is DevelopmentWorkerKernel,'actual fixed H worker kernel')
        a=kernel.attempt
        need(type(a)is DevelopmentAttemptHandle,'actual original attempt');a.require_live_original()
        o=kernel.native_observations
        need(a.worker_kernel is kernel and type(o)is DevelopmentNativeObservation and
             a.native_observations is o and o.kernel is kernel and o.prefix_complete and
             type(a.prefix_capture)is CapturedRecord and a.prefix_capture.owner is a.owner and
             a.prefix_capture.kind=='DevelopmentAttempt','same actual completed prestart prefix')
        need(a.start_observation is None and a.started_ns is None and not kernel.spawn_entered and
             not a.spawn_entered,'one original start owner before any spawn')
        self.kernel=kernel;self.attempt=a;self.observer=o;self.publisher=o.publisher
        self.capture=None;self.raw_first=None;self.secondaries=[];self.entered=False;self.complete=False
        self.original_upper_R=a.run_deadline_ns;self.schedule=None;self.S=self.R=self.G=self.J=None
        self.E=a.evidence_deadline_ns;self.raw_clock=None;self.body=None
        a.start_observation=self

    def retain(self,error,site):
        if self.raw_first is None:self.raw_first=error
        elif error is not self.raw_first:self.secondaries.append(error)
        self.kernel.retain(error,'original_start_'+site)

    def capture_before_carrier_v3(self):
        need(not self.entered,'original start including failed attempt is never retried')
        self.entered=True
        try:
            a=self.attempt;k=self.kernel;o=self.observer;p=self.publisher
            a.require_live_original()
            need(type(p)is CanonicalPublisher and p.owner is a.owner and p.condition is None and
                 a.start_observation is self and a.native_observations is o and o.kernel is k,
                 'same actual original H publisher and registered start owner')
            # Actual publisher-source binding, not its old hash or a wire Pin.
            p.require_native_source_v3()
            prefix=o._capture_body(a.prefix_capture,'DevelopmentAttempt')
            request=o._capture_body(a.arm.request,'DevelopmentRequest')
            launch=o._capture_body(a.arm.launch,'DevelopmentLaunchRequest')
            need(prefix['original_start_ns'] is None and prefix['start_observation_ns'] is None and
                 prefix['spawn_state']=='not_attempted' and prefix['run_deadline_ns']==self.original_upper_R and
                 prefix['launch_request']==a.arm.launch.pin and launch['request']==a.arm.request.pin,
                 'immutable prestart record is earlier evidence, not rewritten actual S/R')
            need(k.running is a.process and k.running.child is None and not k.spawn_entered and
                 not k.running.record['spawn_attempted'] and a.started_ns is None,
                 'no carrier/spawn may precede original start capture')
            schedule=request['schedule'];self.schedule=schedule
            limits=a.pair.contract.backend['limits']
            p.meter.charge('retained_bytes',bounded_size(schedule)+8192)
            p.meter.charge('work_units',bounded_size(schedule)*64+8192)
            # Retain the actual return before deriving or checking any value.
            a.owner.check();self.raw_clock=time.monotonic_ns();self.S=self.raw_clock
            need(type(self.S)is int and a.owner.parent.original_origin<=self.S<self.original_upper_R and
                 schedule['earliest_launch_ns']<=self.S<=schedule['latest_launch_ns'],
                 'same actual original S in matched launch window')
            need(o.last_time is None or self.S>=o.last_time,'same original nondecreasing prefix/start clock')
            o.last_time=self.S
            self.R=self.S+schedule['duration_ns']
            self.G=self.R-limits['shutdown_duration_ns']
            self.J=min(self.S+limits['initialization_duration_ns'],self.G)
            need(self.S<self.J<=self.G<self.R<=self.original_upper_R and
                 self.R<=schedule['common_cutoff_ns'] and self.E==a.evidence_deadline_ns,
                 'exact original S+D, R-Q, min(S+I,G), unchanged E')
            # These actual returned/derived values survive later capture failure.
            # The immutable prefix remains unchanged. No later retry chooses S.
            a.started_ns=self.S;a.run_deadline_ns=self.R
            k.running.spec['run_deadline_ns']=self.R
            profile=a.pair.contract.profile
            need(profile['clock_mapping']==a.owner.parent.clock['mapping_source'] and
                 same(a.host.mapping['source'],profile['clock_mapping']),
                 'same actual original clock mapping and source')
            self.body={'schema':'four_worker_start_observation_v1',
                'original_attempt':a.prefix_capture.pin,'condition':a.condition,
                'launch_request':a.arm.launch.pin,'owner_binding':a.owner.parent.binding_pin,
                'schedule':schedule,'host':a.owner.parent.identity,
                'clock_mapping':profile['clock_mapping'],'source':profile['observer_source'],
                'original_S_ns':self.S,'R_ns':self.R,'G_ns':self.G,'J_ns':self.J,'E_ns':self.E,
                'observed_ns':o._now(self.R),'cost_prefix':a.owner.cost_prefix()}
            self.capture=p.capture(o._prefix()+'_WORKER_START.json','WorkerStartObservationV1',self.body)
            self.require_original_capture_v3();self.complete=True;return self
        except BaseException as error:self.retain(error,'capture');raise

    def require_original_capture_v3(self):
        a=self.attempt;a.require_live_original()
        need(a.start_observation is self and a.worker_kernel is self.kernel and self.entered and
             self.raw_first is None and type(self.capture)is CapturedRecord and
             self.capture.owner is a.owner and self.capture.kind=='WorkerStartObservationV1' and
             self.capture._attempt.complete is self.capture,'actual completed original start producer')
        body=self.capture.body
        need(same(body,self.body) and body['original_attempt']==a.prefix_capture.pin and
             body['launch_request']==a.arm.launch.pin and body['owner_binding']==a.owner.parent.binding_pin and
             body['original_S_ns']==a.started_ns==self.S and body['R_ns']==a.run_deadline_ns==self.R and
             body['E_ns']==a.evidence_deadline_ns==self.E,
             'same exact original capture/time/owner/attempt, no future or borrowed Pin')
        return self.capture

    def admit_original_spawn_v3(self):
        self.require_original_capture_v3()
        need(self.complete and not self.kernel.spawn_entered,'completed earlier start before exactly one original spawn')
        now=self.kernel._clock(self.R)
        need(self.S<=now and self.schedule['earliest_launch_ns']<=now<=self.schedule['latest_launch_ns'],
             'carrier time consumed unchanged interval; Popen still inside original matched window')
        return self
