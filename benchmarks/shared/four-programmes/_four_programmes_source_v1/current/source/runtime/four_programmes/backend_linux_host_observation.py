"""Actual H-side native observation custody: no aggregate FD crosses to W.

This is a fixed source subtype with actual original H owner/attempt/channel;
it is not an injected provider, transported owner or RootBootstrapAdmission.
"""
import time
from .common import need,same,pin
from .backend_json import parse
from .precommit_records import validate_type
from .backend_capture import CapturedRecord
from .backend_linux_io import NativeIOCustody
from .backend_linux_channel import HNativeChannelOwner
from .observer import RunningProcess,KernelGroup


class HostNativeIOCustody(NativeIOCustody):
    def __init__(self,channel):
        need(type(channel) is HNativeChannelOwner and channel.attempt.native_channel is channel and
             channel.native_observer is None,'same actual original H channel and one native observer owner')
        channel.attempt.require_live_original()
        self.channel=channel;self.handle=channel.attempt;self.meter=channel.meter
        self.slots=[];self.raw_first=None;self.raw_secondaries=[];self.last_time=None
        self.known_read=0;self.known_written=0;self.unknown_read=False;self.unknown_write=False
        self.censuses=[];self.thread_resolutions=[]
        self.original_observation=None
        channel.native_observer=self

    @classmethod
    def for_original_observation(cls,observation):
        from .development_native_observations import DevelopmentNativeObservation
        need(cls is HostNativeIOCustody and type(observation) is DevelopmentNativeObservation and
             observation.attempt.native_observations is observation and observation.io is None,
             'one fixed original H producer, never a wire or caller observer')
        observation.attempt.require_live_original()
        io=cls.__new__(cls)
        io.channel=None;io.handle=observation.attempt;io.meter=observation.publisher.meter
        io.original_observation=observation
        io.slots=[];io.raw_first=None;io.raw_secondaries=[];io.last_time=None
        io.known_read=0;io.known_written=0;io.unknown_read=False;io.unknown_write=False
        io.censuses=[];io.thread_resolutions=[]
        observation.io=io
        return io

    def retain(self,error,site):
        if self.raw_first is None:self.raw_first=error
        elif error is not self.raw_first:self.raw_secondaries.append(error)
        self.handle.retain(error,'host_native_'+site)

    def now(self,deadline):
        self.meter.check();now=time.monotonic_ns();a=self.handle
        need(type(a.started_ns) is int and type(deadline) is int and
             a.started_ns<=now<=deadline<=a.evidence_deadline_ns<=a.owner.parent.original_deadline and
             (self.last_time is None or now>=self.last_time),'actual original H observation clock, no W deadline extension')
        self.last_time=now;return now

    def slot(self,role):
        need(role in ('group','proc','pidfd'),'fixed H metadata observation role only')
        return super().slot(role)

    def mark_unknown(self):
        for dimension in ('read_bytes','work_units','cpu_ns','wall_ns','retained_bytes'):
            self.handle.owner.parent.unknown.add(dimension)

    def original_worker_identity(self):
        a=self.handle;a.require_live_original();r=a.process;cap=a.launch_ack
        if self.original_observation is not None:
            o=self.original_observation
            need(a.native_observations is o and o.io is self and o.identity_complete and
                 o.kernel is a.worker_kernel and o.kernel.running is r and type(r) is RunningProcess and
                 r.owner is a.host and r.child is not None and r.identity is o.identity and
                 r.identity['pid']==r.child.pid and r.record['spawn_acknowledged'],
                 'actual earlier source-owned H worker identity, no ack cycle')
            return r.identity
        need(type(r) is RunningProcess and r.owner is a.host and r is self.channel.worker_process and
             r.child is not None and r.record['spawn_acknowledged'] and r.identity is not None and
             r.identity['pid']==r.child.pid,'same actual returned original H worker')
        need(type(cap) is CapturedRecord and cap.owner is a.owner and cap.kind=='WorkerLaunchAck' and
             cap._attempt.complete is cap,'actual earlier H-issued complete worker capture')
        raw=cap.raw;need(type(raw) is bytes and len(raw)<=1048576,'bounded original H capture')
        self.meter.charge('retained_bytes',len(raw));self.work(len(raw)*64+4096)
        descriptor=cap.pin;need(pin(raw)=={k:descriptor[k] for k in ('bytes','sha256')},'exact original captured worker bytes')
        body=parse(raw,len(raw),maximum_depth=64,maximum_members=len(raw),maximum_string_bytes=len(raw))
        validate_type('WorkerLaunchAck',body)
        need(same(body['worker_identity'],r.identity),
             'same retained native worker identity, not supplied dictionary authority')
        return r.identity


def observe_original_host_group_membership(io,deadline):
    """Raw whole aggregate observation from the exact retained H KernelGroup."""
    from .backend_linux_cgroup import GroupCensus
    need(type(io) is HostNativeIOCustody,'fixed H source observer only')
    worker=io.original_worker_identity();r=io.handle.process;group=r.group
    need(type(group) is KernelGroup and group.fd is not None and group.identity is not None,
         'actual original owned aggregate group, never a worker-supplied FD/inode pair')
    need(type(group.identity) is tuple and len(group.identity)==2 and
         all(type(x) is int and x>=0 for x in group.identity),'actual original KernelGroup inode tuple')
    census=GroupCensus(io,group.fd,{'device':group.identity[0],'inode':group.identity[1]},worker['pid'],None,deadline)
    io.censuses.append(census) # Original H retains before the first native effect.
    census.run();return census


def resolve_original_host_threads(io,census,deadline):
    from .backend_linux_threads import GroupThreadIdentityAttempt
    need(type(io) is HostNativeIOCustody and any(census is x for x in io.censuses) and
         census.io is io,'same original H-owned completed census')
    io.original_worker_identity()
    attempt=GroupThreadIdentityAttempt(census);io.thread_resolutions.append(attempt)
    # This is the actual source-selected HostObserver mapping object; no
    # request-supplied replacement is admitted by the production caller.
    attempt.run(io.handle.host.mapping,deadline);return attempt
