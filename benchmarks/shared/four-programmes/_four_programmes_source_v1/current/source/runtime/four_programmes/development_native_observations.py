"""Fixed original-H process/ack/subtree/receipt producers.

No launch, qualification or native authority is created on import. The selected
bootstrap caller remains gated until its full context authority is adopted and
implemented. This module implements actual producer work behind that boundary;
it does not accept a supplied identity, group census, success record or callback.
"""
import json
import os
import time
from .common import need, same, bounded_size, encode, failure
from .backend_capture import CanonicalPublisher, CapturedRecord
from .development_handles import DevelopmentAttemptHandle
from .observer import HostObserver, RunningProcess, KernelGroup, OriginalProcessObservation, _ORIGINAL
from .precommit_records import validate_type
from .backend_linux_host_observation import (HostNativeIOCustody,
    observe_original_host_group_membership, resolve_original_host_threads)
from .backend_linux_observations import read_kernel_fd, process_identity_from_observation


class DevelopmentNativeObservation:
    """One actual kernel's source-owned producer, registered before effects."""
    def __init__(self,kernel,publisher):
        from .development_worker_io import DevelopmentWorkerKernel
        need(type(kernel) is DevelopmentWorkerKernel and type(kernel.attempt) is DevelopmentAttemptHandle,
             'actual fixed original kernel, not a record/provider')
        a=kernel.attempt;a.require_live_original()
        need(a.worker_kernel is kernel and kernel.prepare_entered and kernel.running is a.process and
             type(a.host) is HostObserver and type(kernel.running) is RunningProcess and
             kernel.running.owner is a.host and a.host.active.get(kernel.running.spec['nonce']) is kernel.running,
             'same original prepared RunningProcess registered before native work')
        need(kernel.native_observations is None and a.native_observations is None and
             type(publisher) is CanonicalPublisher and publisher.owner is a.owner and publisher.condition is None,
             'one actual H producer and original host publication owner')
        self.kernel=kernel;self.attempt=a;self.owner=a.owner;self.publisher=publisher;self.io=None
        self.raw_first=None;self.secondaries=[];self.prefix_entered=False;self.prefix_complete=False
        self.launch_entered=False;self.identity_complete=False;self.identity=None;self.identity_prefixes=[]
        self.identity_slots=[];self.identity_close_entered=False;self.identity_closed=False
        self.launch_census=None;self.launch_threads=None;self.whole_census=None
        self.whole_entered=False;self.finish_entered=False;self.receipt=None;self.receipt_record=None
        self.observation=None;self.last_time=None;self.launch_body=None
        kernel.native_observations=self;a.native_observations=self
        self.io=HostNativeIOCustody.for_original_observation(self)

    def retain(self,error,site,unknown=None):
        if self.raw_first is None:self.raw_first=error
        elif error is not self.raw_first:self.secondaries.append(error)
        self.kernel.retain(error,'native_observation_'+site,unknown)

    def _now(self,deadline):
        self.publisher.meter.check();now=time.monotonic_ns();a=self.attempt
        need(type(now) is int and self.owner.parent.original_origin<=now<=deadline<=a.evidence_deadline_ns and
             (self.last_time is None or now>=self.last_time),'same original H clock and unchanged cutoff')
        self.last_time=now;return now

    def _reserve(self,n=16384):
        self.publisher.meter.charge('work_units',n*64)
        self.publisher.meter.charge('retained_bytes',n*16)

    def _capture_body(self,cap,kind):
        need(type(cap) is CapturedRecord and cap.owner is self.owner and cap.kind==kind and
             cap._attempt.complete is cap,'actual completed same-owner captured parent')
        self._reserve(len(cap.raw)+4096)
        body=cap.body;validate_type(kind,body);return body

    def _prefix(self):
        if self.launch_body is None:
            self.launch_body=self._capture_body(self.attempt.arm.launch,'DevelopmentLaunchRequest')
        return self.launch_body['output_prefix']

    def capture_attempt_v1(self):
        need(not self.prefix_entered,'one original attempt publication including failure')
        self.prefix_entered=True
        try:
            a=self.attempt;k=self.kernel;r=k.running
            a.require_live_original();self._reserve();prefix=self._prefix();l=self.launch_body
            need(not k.spawn_entered and not a.spawn_entered and not r.record['spawn_attempted'] and
                 l['launch_nonce'] in a.host.consumed and a.prefix_capture is None,
                 'actual consumed nonce and pre-spawn original base, no future process identity')
            self._now(a.run_deadline_ns)
            body={'schema':'ci_developmentattempt_v2','condition':a.condition,
                'cost_prefix':self.owner.cost_prefix(),'evidence_deadline_ns':a.evidence_deadline_ns,
                'first_error':None,'group_observation':None,'identity':None,
                'known_records':[a.arm.request.pin,a.arm.launch.pin,a.arm.exposure.pin,
                                 a.arm.state_capture.pin,a.arm.workspace_capture.pin],
                'launch_request':a.arm.launch.pin,'nonce_consumed':True,'original_start_ns':None,
                'owner_binding':self.owner.parent.binding_pin,'pair_plan':a.pair.pair_plan.pin,
                'run_deadline_ns':a.run_deadline_ns,'spawn_state':'not_attempted','start_observation_ns':None}
            cap=self.publisher.capture(prefix+'_ATTEMPT.json','DevelopmentAttempt',body)
            a.prefix_capture=cap;self.prefix_complete=True
            return cap
        except BaseException as error:self.retain(error,'attempt');raise

    def _slot(self):
        slot=self.io.slot('proc');self.identity_slots.append(slot);return slot

    def _read(self,directory,name,cap,label):
        slot=self._slot();slot.openat(directory.fd,name,os.O_RDONLY|os.O_NONBLOCK)
        raw=read_kernel_fd(slot,cap,self.attempt.run_deadline_ns)
        self.identity_prefixes.append((label,raw));return raw

    def _close_identity(self):
        if self.identity_close_entered:return self.identity_closed
        self.identity_close_entered=True;first=None
        for slot in reversed(self.identity_slots):
            if not slot.close():
                error=slot.raw_first or RuntimeError('unknown original H identity descriptor close')
                if first is None:first=error
                self.retain(error,'identity_close','descriptor_close')
                for secondary in slot.raw_secondaries:self.retain(secondary,'identity_close_secondary')
        self.identity_closed=all(x.closed for x in self.identity_slots)
        if first is not None:raise first
        return self.identity_closed

    def _observe_worker_identity(self):
        """Actual anchored boot/PID/start/parent observations; never an ack echo."""
        a=self.attempt;r=a.process;original=None
        try:
            need(type(r) is RunningProcess and r is self.kernel.running and r.owner is a.host and
                 r.child is not None and r.record['spawn_acknowledged'] and r.identity is None,
                 'same actual returned original child, before first identity')
            self._reserve();pid=r.child.pid
            need(type(pid) is int and pid>0,'actual returned positive child PID')
            root=self._slot();root.fixed_proc_root()
            sysdir=self._slot();sysdir.openat(root.fd,'sys',os.O_RDONLY|os.O_DIRECTORY)
            kerneldir=self._slot();kerneldir.openat(sysdir.fd,'kernel',os.O_RDONLY|os.O_DIRECTORY)
            randomdir=self._slot();randomdir.openat(kerneldir.fd,'random',os.O_RDONLY|os.O_DIRECTORY)
            # boot_id is a fixed existing kernel identity, never an entropy request.
            boot=self._read(randomdir,'boot_id',128,'boot_id').decode('ascii').strip()
            directory=self._slot();directory.openat(root.fd,str(pid),os.O_RDONLY|os.O_DIRECTORY)
            before=self._read(directory,'stat',8192,'worker_stat_before')
            identity,fields=process_identity_from_observation(before,pid,boot,a.host.mapping,
                r.spec['nonce'],r.spec['source'],r.spec['parent_launch'])
            parent=self.owner.parent.identity
            need(fields['parent_pid']==parent['pid'],'actual child parent matches original H identity')
            parentdir=self._slot();parentdir.openat(root.fd,str(parent['pid']),os.O_RDONLY|os.O_DIRECTORY)
            parent_before=self._read(parentdir,'stat',8192,'host_stat_before')
            observed_parent,_=process_identity_from_observation(parent_before,parent['pid'],boot,a.host.mapping,
                parent['launch_nonce'],parent['source'],parent['parent_launch'])
            need(same(observed_parent,parent),'actual H PID/start/boot, not a reused parent PID')
            after=self._read(directory,'stat',8192,'worker_stat_after')
            identity_after,fields_after=process_identity_from_observation(after,pid,boot,a.host.mapping,
                r.spec['nonce'],r.spec['source'],r.spec['parent_launch'])
            parent_after=self._read(parentdir,'stat',8192,'host_stat_after')
            observed_parent_after,_=process_identity_from_observation(parent_after,parent['pid'],boot,a.host.mapping,
                parent['launch_nonce'],parent['source'],parent['parent_launch'])
            need(same(identity,identity_after) and same(observed_parent_after,parent) and
                 fields_after['parent_pid']==parent['pid'] and fields_after['state'] not in ('Z','X'),
                 'unchanged live original child and H parent through actual observation')
            # Retain original identity before any later close/clock/publication can fail.
            r.identity=identity;self.identity=identity
        except BaseException as error:original=error;self.retain(error,'identity','process_identity');raise
        finally:
            try:self._close_identity()
            except BaseException:
                if original is None:raise
        self._now(a.run_deadline_ns);self.identity_complete=True
        return self.identity

    def capture_launch_v3(self):
        need(not self.launch_entered,'one original launch evidence producer including failures')
        self.launch_entered=True
        try:
            a=self.attempt;k=self.kernel;a.require_live_original()
            need(self.prefix_complete and k.spawn_entered and a.spawn_entered and k.running is a.process and
                 k.raw_first is None and a.raw_first is None,'actual original successful spawn/setup prefix')
            self._capture_body(a.prefix_capture,'DevelopmentAttempt')
            self._observe_worker_identity()
            from .backend_launch_group_v3 import HLaunchGroupOwnerV3
            group_owner=HLaunchGroupOwnerV3(self)
            group_owner.run_v3()
            prefix=self._prefix()
            request=self._capture_body(a.arm.request,'DevelopmentRequest')
            pair_plan=self._capture_body(a.pair.pair_plan,'DevelopmentPairPlan')
            need(request['pair_plan']==a.pair.pair_plan.pin,'same actual pair plan selected before launch')
            ack={'schema':'ci_development_worker_launch_ack_v1','condition':a.condition,
                'cost_prefix':self.owner.cost_prefix(),'evidence_deadline_ns':a.evidence_deadline_ns,
                'group_observation':a.group_capture.pin,'launch_request':a.arm.launch.pin,
                'nonce':self.launch_body['launch_nonce'],'original_attempt':a.prefix_capture.pin,
                'original_start_ns':a.started_ns,'owner_binding':self.owner.parent.binding_pin,
                'pair_id':pair_plan['pair_id'],'request':a.arm.request.pin,'run_deadline_ns':a.run_deadline_ns,
                'source_admission':a.pair.contract.profile['source_admission'],'worker_identity':self.identity}
            a.launch_ack=self.publisher.capture(prefix+'_WORKER_ACK.json','WorkerLaunchAck',ack)
            self._now(a.run_deadline_ns)
            return a.launch_ack
        except BaseException as error:self.retain(error,'launch');raise

    def capture_whole_arm_v1(self):
        """Observe final empty PID AND TID hierarchy before removing its anchors."""
        from .backend_linux_cgroup import GroupCensus
        need(not self.whole_entered,'one original final whole-arm capture')
        self.whole_entered=True
        try:
            a=self.attempt;k=self.kernel;g=k.group
            need(k.finish_entered and a.finish_attempted and k.wait_consumed and not k.reap_unknown and
                 self.identity_complete and type(g) is KernelGroup and g is a.process.group and
                 g.fd is not None and not g.removed,'actual original reaped worker with retained live group anchor')
            self._reserve();g.own()
            need(type(g.identity) is tuple and len(g.identity)==2,'actual retained original group inode pair')
            census=GroupCensus(self.io,g.fd,{'device':g.identity[0],'inode':g.identity[1]},
                self.identity['pid'],None,a.evidence_deadline_ns,stopped_whole_arm=True)
            self.whole_census=census;self.io.censuses.append(census);census.run();g.own()
            need(census.stable and census.closed and not census.residual_pids and not census.residual_thread_ids,
                 'complete empty stopped whole arm; no excluded live worker')
            body={'schema':'ci_subtree_observation_v1','attempt':a.prefix_capture.pin,'condition':a.condition,
                'cost_prefix':self.owner.cost_prefix(),'enumeration_complete':True,'excluded_live_worker':None,
                'members':[],'observed_ns':census.observed_ns,'producer':'host','root':self.identity,
                'scope':'whole_arm','unresolved_count':0}
            a.whole_arm_capture=self.publisher.capture(self._prefix()+'_WHOLE_ARM.json','SubtreeObservation',body)
            return a.whole_arm_capture
        except BaseException as error:self.retain(error,'whole_arm','whole_arm');raise

    def finish_original_process_v1(self):
        """Publish the original completed kernel; do not wait/drain/close again."""
        from .development_evidence import DevelopmentEvidenceCapture, CapturedStreamBytes
        need(not self.finish_entered,'one original process receipt attempt, no publication retry')
        self.finish_entered=True;a=self.attempt;k=self.kernel;r=k.running
        need(type(r) is RunningProcess and r is a.process and r.owner is a.host and
             a.host.active.get(r.spec['nonce']) is r and not r.finish_attempted,
             'same original registered process, not already completed by another observer')
        r.finish_attempted=True
        # Preserve the kernel's actual earlier first error in the original
        # RunningProcess before any later evidence/clock/budget projection can
        # fail. Those later errors must never become its apparent first error.
        if k.raw_first is not None and r.primary is None:
            r.primary=k.raw_first
            r.record['original_failure']=failure(k.raw_first)
        stdout=stderr=None
        try:
            need(k.finish_entered and a.finish_attempted,'actual original kernel cleanup already attempted')
            e=a.evidence_capture
            need(type(e) is DevelopmentEvidenceCapture and e.attempt is a and e.streams is k.streams and
                 e.owner is self.owner and e.publisher.outputs is self.publisher.outputs,
                 'actual original captured streams and same output owner')
            self._reserve(bounded_size(r.record)+bounded_size(k.physical_prefix)+16384)
            record=r.record
            record.update(natural_exit=k.natural_exit,exit_code=k.exit_code,
                streams_eof=dict(k.streams.eof),group_empty=bool(k.final_physical and k.final_physical['worker']['empty']),
                group_removed=k.group_removed,forced=k.forced,timed_out=record.get('timed_out',False),
                original_failure=failure(k.raw_first) if k.raw_first is not None else None,
                cleanup_errors=[failure(x) for x in k.raw_secondaries],
                unknown_dimensions=sorted(set(k.unknown)|set(self.owner.parent.unknown)),
                physical_final_known=k.final_physical is not None,physical_final=k.final_physical,
                physical_prefix=k.physical_prefix,publication_complete=False,identity=r.identity)
            record['stream_materialization']={};record['original_output_prefixes']=[]
            for side in ('stdout','stderr'):
                item=e.stream_attempts.get(side);cap=None if item is None else item.complete
                valid=(type(cap) is CapturedStreamBytes and cap.evidence is e and cap.source_streams is k.streams and
                       cap.side==side and type(cap.raw) is bytes and len(cap.raw)==k.streams.counts[side])
                record['stream_materialization'][side]=valid
                record[side]=cap.pin if valid else None;record[side+'_bytes']=k.streams.counts[side]
                if valid:
                    record['original_output_prefixes'].append(cap.pin)
                    if side=='stdout':stdout=cap.raw
                    else:stderr=cap.raw
            need(stdout is not None and stderr is not None,'both actual original raw stream captures retained')
            if a.whole_arm_capture is None:record['unknown_dimensions'].append('whole_arm_observation')
            record['closed_ns']=self._now(a.evidence_deadline_ns);record['costs']=self.owner.cost_prefix()
            bound=bounded_size(record);self._reserve(bound)
            # Exact earlier receipt cannot attest its own successful publication.
            self.receipt_record=json.loads(encode(record));self.receipt=None
            self.receipt=self.publisher.outputs.publish(self._prefix()+'_PROCESS.json',self.receipt_record)
            reread=self.publisher.outputs.read(self.receipt,self.publisher.maximum_bytes,metadata=True)
            need(reread==encode(self.receipt_record),'complete original process receipt readback before H success')
            self._now(a.evidence_deadline_ns);record['publication_complete']=True
        except BaseException as error:
            self.retain(error,'original_receipt','original_terminal_publication')
            if r.primary is not None and r.primary is not error:
                r.record['cleanup_errors'].append(failure(error))
            r.own_failure(error,'original_terminal_publication');r.record['publication_complete']=False
        # Factory call occurs only here after the exact actual source-owned
        # kernel/evidence/receipt path. No externally supplied record is accepted.
        self.observation=OriginalProcessObservation(_ORIGINAL,r.record,self.receipt,self.receipt_record,
                                                     stdout,stderr,r.identity)
        a.process_observation=self.observation
        if k.wait_consumed and not k.reap_unknown and k.group_removed and k.group_closed:
            a.host.active.pop(r.spec['nonce'],None)
        return self.observation
