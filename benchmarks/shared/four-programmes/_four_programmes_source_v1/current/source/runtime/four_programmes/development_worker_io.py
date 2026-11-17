"""Concrete original-H worker process/group/pipe ownership.

This is the native implementation kernel of the separate development route.
The fixed H entry must first acquire its independently admitted worker bootstrap
transport. No such transport or qualification is created by this module. Raw
kernel completion is not a ProcessObservation, receipt, or pair capability.
"""
import os
import selectors
import stat
import subprocess
import time
from .common import need, integer
from .development_handles import DevelopmentAttemptHandle
from .development_streams import DevelopmentStreams, NAMES
from .observer import HostObserver, KernelGroup, RunningProcess, _ORIGINAL
from .precommit_records import CONDITIONS

class DevelopmentWorkerKernel:
    """One actual H-owned worker; registration precedes new effects."""
    def __init__(self, attempt):
        need(type(attempt) is DevelopmentAttemptHandle, 'fixed original development attempt')
        attempt.require_live_original()
        need(attempt.worker_kernel is None and type(attempt.host) is HostObserver,
             'one fixed kernel under the original host observer')
        self.attempt=attempt;self.owner=attempt.owner;self.host=attempt.host
        self.raw_first=None;self.raw_secondaries=[]
        self.prepare_entered=False;self.spawn_entered=False;self.finish_entered=False
        self.kill_entered=False;self.wait_entered=False;self.wait_consumed=False
        self.raw_wait_result=None;self.reap_unknown=False;self.poll_calls=0
        self.group=None;self.running=None;self.selector=None;self.streams=None
        self.selector_close_entered=False;self.selector_closed=False
        self.unknown=set();self.physical_prefix=[];self.final_physical=None
        self.group_removed=False;self.group_closed=False;self.forced=False
        self.natural_exit=False;self.exit_code=None;self.raw_complete=False
        self.preexec_first=None;self.preexec_secondaries=[]
        self.preexec_group_close_entered=False;self.preexec_group_closed=False
        self.native_observations=None
        self.unspawned_cleanup_entered=False;self.cleanup_dispositions={}
        attempt.worker_kernel=self

    def retain(self,error,site,unknown=None):
        if self.raw_first is None:self.raw_first=error
        elif error is not self.raw_first:self.raw_secondaries.append(error)
        if unknown is not None:self.unknown.add(unknown)
        self.attempt.retain(error,site,unknown if unknown in
            ('read_bytes','write_bytes','work_units','retained_bytes','cpu_ns','wall_ns','process_starts') else None)

    def _clock(self,deadline):
        self.owner.check()
        now=time.monotonic_ns();integer(now)
        need(now<deadline,'original H worker interval, no renewal')
        return now

    def prepare_v1(self):
        need(not self.prepare_entered,'one original group/pipe owner preparation')
        self.prepare_entered=True
        a=self.attempt;c=a.pair.contract;l=a.arm.launch.body
        try:
            a.require_live_original()
            if c.profile['schema']=='four_native_development_profile_v3':
                from .native_control_plan_v4 import NativeControlPlanV4
                need(type(a.native_control_plan)is NativeControlPlanV4 and a.native_control_plan.attempt is a,
                     'actual full native schedule before group preparation')
                a.native_control_plan.require_original()
                need(a.native_control_plan.ledger is a.native_channel.reservation_ledger and
                     a.native_control_plan.ledger.control_host.complete and a.native_control_plan.ledger.control_arm.complete,
                     'actual original complete seven-dimensional reservations before native effects')
            need(self.host.meter is self.owner.host and
                 l['argv']==c.profile['entry_argv']==c.policy['entry_argv'] and
                 l['environment']==c.profile['environment'] and
                 l['request']==a.arm.request.pin and l['exposure']==a.arm.exposure.pin and
                 l['profile']==c.profile_pin and l['owner_binding']==self.owner.parent.binding_pin and
                 l['state_identity']==a.arm.state_capture.pin and
                 l['workspace_identity']==a.arm.workspace_capture.pin and
                 l['source_closure']==c.policy['source_closure'],
                 'exact original profile/arm/request/state/exposure/source selection')
            need(l['launch_nonce'] not in self.host.consumed,'same original nonce not previously attempted')
            self.host.consumed.add(l['launch_nonce'])
            self._clock(a.run_deadline_ns)
            limits={k:v for k,v in c.worker['limits'].items() if k!='schema'}
            spec={'mode':'ci_development_v2','argv':list(l['argv']),'cwd':l['cwd'],
                  'env':dict(c.environment),'source':c.profile['launcher_source'],
                  'campaign':self.owner.parent.clock['campaign_id'],'nonce':l['launch_nonce'],
                  'parent_launch':c.profile['parent_launch'],'group_parent':c.profile['group_parent'],
                  'group_name':l['group_name'],'limits':limits,
                  'run_deadline_ns':a.run_deadline_ns,'evidence_deadline_ns':a.evidence_deadline_ns,
                  'output_prefix':l['output_prefix']}
            # This raw running object does not assert a process identity. The
            # independently selected native identity producer supplies it later.
            self.running=RunningProcess(_ORIGINAL,self.host,spec);a.process=self.running
            self.host.active[l['launch_nonce']]=self.running
            self.streams=DevelopmentStreams(self.owner,c.profile['maximum_stream_bytes'])
            a.streams=self.streams
            self.group=KernelGroup(c.profile['group_parent'],l['group_name'],self.owner.host)
            self.running.group=self.group
            self.group.prepare(limits)
            return self
        except BaseException as error:
            self.retain(error,'DevelopmentWorkerKernel.prepare',unknown='group_preparation')
            raise

    def _join_original_entry(self):
        # Called only in the fixed pre-exec path. Original descriptor ownership
        # and raw first-error preservation do not depend on formatter callbacks.
        groupfd=self.group.entry_fd;fd=None;first=None
        try:
            fd=os.open('cgroup.procs',os.O_WRONLY|os.O_NOFOLLOW,dir_fd=groupfd)
            raw=str(os.getpid()).encode('ascii');offset=0
            while offset<len(raw):
                n=os.write(fd,raw[offset:]);need(type(n) is int and 0<n<=len(raw)-offset,
                                               'complete original child group join')
                offset+=n
            os.set_inheritable(groupfd,False)
        except BaseException as error:
            first=error;self.preexec_first=error
        if fd is not None:
            closing,fd=fd,None
            try:os.close(closing)
            except BaseException as error:
                if first is None:first=error;self.preexec_first=error
                else:self.preexec_secondaries.append(error)
        if not self.preexec_group_close_entered:
            self.preexec_group_close_entered=True
            try:os.close(groupfd);self.preexec_group_closed=True
            except BaseException as error:
                if first is None:first=error;self.preexec_first=error
                else:self.preexec_secondaries.append(error)
        # In a real fork these are child-local raw owners. No parent receipt
        # claims to have observed them: the separately selected bootstrap
        # failure transport must carry their bounded evidence, or it is unknown.
        if first is not None:raise first

    def spawn_original_v3(self, carrier):
        """Fixed original carrier/start caller; no supplied descriptor tuple."""
        need(self.prepare_entered and self.raw_first is None and not self.spawn_entered,
             'one prepared original native spawn')
        try:
            from .development_native_observations import DevelopmentNativeObservation
            need(type(self.native_observations) is DevelopmentNativeObservation and
                 self.attempt.native_observations is self.native_observations and
                 self.native_observations.prefix_complete and self.attempt.prefix_capture is not None,
                 'actual earlier source-owned original attempt capture before Popen')
            self.attempt.require_live_original()
            need(self.running is self.attempt.process and self.running.owner is self.host and
                 self.host.active.get(self.running.spec['nonce']) is self.running and
                 self.group is self.running.group,
                 'same actual registered process/group before native spawn')
            from .backend_bootstrap_carrier_v3 import HBootstrapCarrierOwnerV3
            need(type(carrier)is HBootstrapCarrierOwnerV3 and carrier.attempt is self.attempt,
                 'actual same-attempt original carrier, never supplied FDs')
            carrier.require_spawn_original_v3()
            pass_fds=(198,199)
            need(self.group.entry_fd not in pass_fds,'distinct original group FD remains H-owned')
            a=self.attempt
            a.start_observation.admit_original_spawn_v3()
            self.owner.arms[a.condition].spawn_attempt()
            self.spawn_entered=True;a.spawn_entered=True
            a.spawn_state='attempted_unacknowledged'
            self.running.record['spawn_attempted']=True
            child=subprocess.Popen(self.running.spec['argv'],cwd=self.running.spec['cwd'],
                env=self.running.spec['env'],stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,close_fds=True,pass_fds=pass_fds+(self.group.entry_fd,),
                start_new_session=True,preexec_fn=self._join_original_entry)
            self.running.child=child # Retain before any further native operation.
            self.running.record['spawn_acknowledged']=True;a.spawn_state='acknowledged'
            # Both returned pipes belong to the owner before either is configured.
            for name in NAMES:
                stream=getattr(child,name)
                self.streams.original_streams[name]=stream
                self.streams.streams[name]=stream
            self.selector=selectors.DefaultSelector();a.selector=self.selector
            self.running.selector=self.selector
            for name in NAMES:
                stream=self.streams.streams[name]
                need(stream is not None,'actual original returned pipe')
                self.owner.host.charge('work_units',256)
                os.set_blocking(stream.fileno(),False)
                self.selector.register(stream,selectors.EVENT_READ,name)
            self.native_observations.capture_launch_v3()
            return self.running
        except BaseException as error:
            self.retain(error,'DevelopmentWorkerKernel.spawn','spawn_or_pipe_setup')
            raise
        finally:
            if self.spawn_entered:
                try:carrier.close_parent_exec_aliases_once()
                except BaseException as error:
                    self.retain(error,'DevelopmentWorkerKernel.parent_alias_close','descriptor_close')

    def observe_physical_v1(self):
        need(self.group is not None,'actual original worker group')
        self.owner.host.charge('retained_bytes',4096)
        self.owner.host.charge('work_units',4096)
        own=self.group.sample()
        # Retain actual observation before conversion/admission may fail.
        self.physical_prefix.append({'worker':own,'whole':None,'storage_bytes':None})
        row=self.physical_prefix[-1]
        self.owner.observe_child_cpu(self.attempt.condition,own['cpu_ns'])
        row['whole']=self.host.whole_group.sample()
        row['storage_bytes']=self.host.storage.observe()
        limits=self.running.spec['limits'];whole=row['whole']
        need(own['cpu_ns']<=limits['cpu_ns'] and own['memory_peak']<=limits['memory_bytes'] and
             whole['cpu_ns']<=limits['whole_cpu_ns'] and whole['memory_peak']<=limits['whole_memory_bytes'] and
             row['storage_bytes']<=limits['whole_storage_bytes'],'original arm and aggregate physical bounds')
        return row

    def _poll_v1(self):
        need(not self.reap_unknown,'ambiguous original reap cannot be retried')
        if self.wait_consumed:return self.exit_code
        self.owner.host.charge('work_units',256)
        self.poll_calls+=1
        try:raw=self.running.child.poll()
        except BaseException as error:
            self.reap_unknown=True;self.retain(error,'DevelopmentWorkerKernel.poll','reap');raise
        if raw is None:return None
        # Store raw return and consume the reap BEFORE validating it.
        self.raw_wait_result=raw;self.wait_consumed=True
        self.attempt.wait_result=raw;self.attempt.wait_consumed=True
        need(type(raw) is int,'actual integer original process status')
        self.exit_code=raw;self.natural_exit=True
        return raw

    def pump_v1(self):
        need(self.spawn_entered and self.running is not None,'actual entered original spawn')
        if self.raw_first is not None:return False
        try:
            now=self._clock(self.attempt.run_deadline_ns)
            self.observe_physical_v1()
            for key,_ in self.selector.select(min(.05,max(0,(self.attempt.run_deadline_ns-now)/1e9))):
                state=self.streams.read_ready(key.data)
                if state=='eof':self.selector.unregister(key.fileobj)
            result=self._poll_v1()
            if result is not None and not self.selector.get_map():
                need(result==0,'actual natural integer zero')
                need(self.group.sample()['empty'],'whole original arm has no descendants')
                return False
            return True
        except BaseException as error:
            self.retain(error,'DevelopmentWorkerKernel.pump','observation');return False

    def pump_ready_v1(self):
        """One nonblocking raw-stream/physical step for the paired H driver.

        This uses the same original R, observations, read ownership and poll
        checks as pump_v1. It cannot wait on one arm while the other arm has a
        pending H request or an undrained original stream.
        """
        need(self.spawn_entered and self.running is not None,'actual entered original spawn')
        if self.raw_first is not None:return False
        try:
            self._clock(self.attempt.run_deadline_ns)
            self.observe_physical_v1()
            for key,_ in self.selector.select(0):
                state=self.streams.read_ready(key.data)
                if state=='eof':self.selector.unregister(key.fileobj)
            result=self._poll_v1()
            if result is not None and not self.selector.get_map():
                need(result==0,'actual natural integer zero')
                need(self.group.sample()['empty'],'whole original arm has no descendants')
                return False
            return True
        except BaseException as error:
            self.retain(error,'DevelopmentWorkerKernel.pump_ready','observation');return False

    def capture_available_evidence_v1(self,publisher):
        """Capture actual known outputs; this never constructs a completion."""
        need(self.finish_entered and self.attempt.finish_attempted,
             'original kernel closure precedes terminal evidence capture')
        from .development_evidence import DevelopmentEvidenceCapture
        try:return DevelopmentEvidenceCapture(self.attempt,publisher).capture_available_v1()
        except BaseException as error:
            self.retain(error,'DevelopmentWorkerKernel.capture_available_evidence')
            raise

    def _cleanup(self, name, effect):
        try:
            self.owner.terminal_host.charge('work_units',4096)
            self._clock(self.attempt.evidence_deadline_ns)
            effect()
        except BaseException as error:self.retain(error,'DevelopmentWorkerKernel.'+name,name)

    def _relinquish(self,name,effect):
        # Finite once-only release of an already-owned handle is independent
        # of a failed later clock/accounting check. Never renew a deadline or
        # grant productive IO. Preserve unknown cleanup cost and attempt the
        # original close even if its accounting observation fails.
        try:
            self.owner.terminal_host.charge('work_units',4096)
            self._clock(self.attempt.evidence_deadline_ns)
        except BaseException as error:self.retain(error,'DevelopmentWorkerKernel.'+name+'_admission',name+'_cost')
        try:effect()
        except BaseException as error:self.retain(error,'DevelopmentWorkerKernel.'+name,name)

    def _wait_once(self):
        if self.wait_consumed or self.reap_unknown:return
        need(not self.wait_entered,'one original blocking wait attempt')
        self.wait_entered=True
        remaining=(self.attempt.evidence_deadline_ns-time.monotonic_ns())/1e9
        need(remaining>0,'unchanged H evidence interval for original wait')
        try:raw=self.running.child.wait(timeout=remaining)
        except BaseException as error:
            self.reap_unknown=True;self.retain(error,'DevelopmentWorkerKernel.wait','reap');raise
        self.raw_wait_result=raw;self.wait_consumed=True
        self.attempt.wait_result=raw;self.attempt.wait_consumed=True
        need(type(raw) is int,'actual original integer wait status')
        self.exit_code=raw
        # A forced/failure cleanup exit never becomes a natural exit.
        if self.raw_first is None and not self.forced:self.natural_exit=True

    def _remove_unspawned_group_v2(self):
        """Remove only the actual registered never-spawned group, without a receipt.

        No physical sample or empty-process observation is fabricated. Original
        FD/path identities and kernel rmdir enforce the finite release. Missing
        identity (including a failed earlier open/fstat) stays unknown and the
        independent descriptor closes still run. No foreign/nested tree walk.
        """
        a=self.attempt;r=self.running;g=self.group
        need(not self.spawn_entered and not a.spawn_entered and
             type(r) is RunningProcess and r is a.process and r.owner is self.host and
             self.host.active.get(r.spec['nonce']) is r and r.child is None and
             not r.record['spawn_attempted'] and type(g) is KernelGroup and r.group is g,
             'actual same registered pre-spawn process/group ownership')
        need(g.created,'actual acquired group before pre-spawn removal')
        g.own()
        if g.entry_created and not g.entry_removed:
            need(g.entry_fd is not None and g.entry_identity is not None,
                 'retained entry identity before partial-group removal')
            observed=os.fstat(g.entry_fd);current=os.stat('entry',dir_fd=g.fd,follow_symlinks=False)
            need((observed.st_dev,observed.st_ino)==(current.st_dev,current.st_ino)==g.entry_identity and
                 stat.S_ISDIR(current.st_mode),'same acquired entry leaf before partial-group removal')
            os.rmdir('entry',dir_fd=g.fd);g.entry_removed=True
        g.path.rmdir();g.removed=True;self.group_removed=True

    def _finish_unspawned_v2(self):
        """Finite cleanup for a prefix that never entered Popen; never success."""
        self.unspawned_cleanup_entered=True
        self.cleanup_dispositions['spawn']='not_entered'
        self.cleanup_dispositions['wait']='not_entered_no_child'
        if self.streams is None:self.cleanup_dispositions['streams']='not_acquired'
        else:
            for name in NAMES:
                if not self.streams.close_attempted[name]:
                    self._relinquish(name+'_close',lambda n=name:self.streams.close(n))
                self.cleanup_dispositions[name+'_close']=('closed' if self.streams.closed[name] else 'failed_or_unknown')
            self.cleanup_dispositions['stream_materialization']='unreached_pre_spawn'
        if self.selector is None:self.cleanup_dispositions['selector']='not_acquired'
        elif not self.selector_close_entered:
            def close_selector():
                self.selector_close_entered=True
                original=self.selector;self.selector=None
                original.close();self.selector_closed=True
            self._relinquish('selector_close',close_selector)
            self.cleanup_dispositions['selector']='closed' if self.selector_closed else 'failed_or_unknown'
        if self.group is None:self.cleanup_dispositions['group']='not_acquired'
        else:
            self.cleanup_dispositions['group_remove']='not_created' if not self.group.created else 'entered'
            if self.group.created:
                self._relinquish('unspawned_group_remove',self._remove_unspawned_group_v2)
                self.cleanup_dispositions['group_remove']='removed' if self.group_removed else 'failed_or_unknown'
            def close_group():
                need(type(self.group) is KernelGroup and self.running is not None and
                     self.running.group is self.group,'same retained original partial group')
                self.group.close();self.group_closed=True
            self._relinquish('group_close',close_group)
            self.cleanup_dispositions['group_close']='closed' if self.group_closed else 'failed_or_unknown'
        self.cleanup_dispositions['native_observation']='unavailable_pre_spawn'
        self.raw_complete=False
        return self

    def finish_raw_v1(self):
        """Close raw original owners independently; never publishes a receipt."""
        if self.finish_entered:return self
        self.finish_entered=True
        self.attempt.finish_attempted=True
        first=self.attempt.raw_first
        if first is None:first=self.owner.parent.first_raw
        if first is not None and self.raw_first is None:self.raw_first=first
        try:self.owner.enter_terminal()
        except BaseException as error:self.retain(error,'DevelopmentWorkerKernel.enter_terminal','terminal_entry')
        if not self.spawn_entered and (self.running is None or self.running.child is None):
            return self._finish_unspawned_v2()
        if self.raw_first is not None and self.group is not None and self.group.created:
            def kill():
                self.kill_entered=True;self.forced=True;self.group.kill()
            self._cleanup('group_kill',kill)
        if self.running is not None and self.running.child is not None:
            self._cleanup('wait',self._wait_once)
        if self.streams is not None:
            for name in NAMES:
                if not self.streams.close_attempted[name]:
                    self._relinquish(name+'_close',lambda n=name:self.streams.close(n))
                if not self.streams.materialization_attempted[name]:
                    self._cleanup(name+'_materialize',lambda n=name:self.streams.materialize(n))
        if self.selector is not None and not self.selector_close_entered:
            def close_selector():
                self.selector_close_entered=True
                original=self.selector;self.selector=None
                original.close();self.selector_closed=True
            self._relinquish('selector_close',close_selector)
        if self.group is not None:
            def observe_whole_arm():
                from .development_native_observations import DevelopmentNativeObservation
                need(type(self.native_observations) is DevelopmentNativeObservation and
                     self.attempt.native_observations is self.native_observations,
                     'actual H producer remains retained through final empty-group observation')
                self.native_observations.capture_whole_arm_v1()
            self._cleanup('whole_arm_observation',observe_whole_arm)
            def sample():
                self.final_physical=self.observe_physical_v1()
                need(self.final_physical['worker']['empty'],'actual complete original arm is empty')
            self._cleanup('final_physical',sample)
            if self.final_physical is not None and self.final_physical['worker']['empty']:
                def remove():self.group.remove();self.group_removed=True
                self._cleanup('group_remove',remove)
            def close_group():
                self.group.close();self.group_closed=True
            self._relinquish('group_close',close_group)
        self.raw_complete=(self.raw_first is None and self.wait_consumed and not self.reap_unknown and
            self.natural_exit and self.exit_code==0 and not self.forced and self.group_removed and
            self.group_closed and self.selector_closed and self.streams is not None and self.streams.complete and
            self.final_physical is not None and not self.unknown)
        # Actual original-process receipt, typed native identities, complete
        # stream/cost/workspace products and pair captures are later producers.
        return self

