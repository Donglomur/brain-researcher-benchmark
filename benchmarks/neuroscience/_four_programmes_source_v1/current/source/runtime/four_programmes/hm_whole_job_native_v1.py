"""Real fixed whole-job HM H campaign/stage producers, inactive on import.

All scientific execution uses the original worker APIs. This owner creates the
actual carrier/channel/launch, retains failures, and collects original outputs.
It never grants itself environment, isolation, provisioning or science authority.
"""
import fcntl
import os
import select
import stat
import time
from pathlib import Path
from .common import need, closed, integer, encode, parse, pin, failure, Store
from .channel import HostEndpoint
from .observer import (HostObserver, RunningProcess, OriginalProcessObservation,
    bind_hm_exit_accounting_v1, HMOwnExitAccountingV1)
from .source_session import SourceSession
from .hm_whole_job_profile_v1 import HMWholeJobReservationOwnerV1, PROGRAMME
from .hm_whole_job_controller_v1 import require_original_controller_v1
from .hm_whole_job_native_observations_v1 import (FORMAT_CAP, retain, exact_wrapper,
    HMNativeConfigurationV1, HMFixedVolumeCustodyV1, HMContinuousProcessClocksV1,
    HMStageChannelMeterV1)

_CAMPAIGN=object();_STAGE=object();_LIVE={}
FD_KEYS=('NEUROBENCH_HM_BOOTSTRAP_FD','NEUROBENCH_HM_READ_FD','NEUROBENCH_HM_WRITE_FD')


def _fd_identity(fd):
    s=os.fstat(fd);return [s.st_dev,s.st_ino,s.st_mode]


def _group_pids(group,meter,retention=None):
    """A complete actual lifetime high-water counter, never a polling maximum."""
    group.own();fd=None;first=None;raw=None;secondary=[]
    try:
        meter.charge('read_bytes',257)
        fd=os.open('pids.peak',os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=group.fd)
        raw=os.read(fd,257);need(len(raw)<=256 and raw.strip().isdigit(),'complete actual PID/TID peak')
        need(not os.read(fd,1),'actual PID/TID peak EOF')
    except BaseException as error:first=error
    finally:
        if fd is not None:
            try:os.close(fd)
            except BaseException as error:
                if first is None:first=error
                else:secondary.append(error)
    if first is not None:
        # Preserve the original read failure before secondary diagnostic code.
        if retention is not None:
            try:retention.retain(first,"group_pids")
            except BaseException as error:secondary.append(error)
        for error in tuple(secondary):
            if retention is not None:
                try:retention.retain(error,"group_pids_cleanup")
                except BaseException as diagnostic:secondary.append(diagnostic)
            try:meter.cleanup_errors.append(failure(error))
            except BaseException as diagnostic:secondary.append(diagnostic)
        try:first._hm_native_cleanup_errors_v1=tuple(secondary)
        except BaseException:pass  # diagnostic attachment never replaces raw first
        raise first
    group.own();return int(raw)


class HMWorkerCarrierV1:
    def __init__(self,stage):
        self.stage=stage;self.campaign=stage.campaign;self.raw_first=None;self.secondaries=[]
        self.fds={};self.attempts=[];self.raw=None;self.body=None;self.descriptor=None
        self.close_attempted=set();self.closed=set();self.endpoint=None;self.endpoint_entered=False
        self.pass_fds=None;self.binding=None;self.complete=False;self.prepare_entered=False;stage.carrier=self

    def _close(self,name):
        if name in self.close_attempted:return name in self.closed
        self.close_attempted.add(name);fd=self.fds.pop(name,None)
        try:
            if fd is not None:os.close(fd)
            self.closed.add(name);return True
        except BaseException as error:retain(self,error,'carrier_close:'+name);return False

    def prepare_once(self):
        if self.prepare_entered and self.raw_first is not None:raise self.raw_first
        need(not self.prepare_entered,"one carrier attempt before any import or debit")
        self.prepare_entered=True
        need(not self.attempts,'one original carrier construction, including partial failure')
        s=self.stage;c=self.campaign;cfg=s.worker_configuration
        try:
            from .hm_whole_worker_contract_v1 import compile_worker_bootstrap_body_v1
            # The exact W bootstrap and terminal credit is debited to the one
            # original H Share before any carrier or worker effect. It is kept
            # on failure/unused exit; the W meter consumes that same credit.
            for name in ('bootstrap_limits','terminal_limits'):
                limits=cfg[name];closed(limits,('read_bytes','write_bytes','work_units','retained_bytes'))
                s.prepaid[name]={}
                for kind,value in limits.items():
                    integer(value,1);c.meter.charge(kind,value);s.prepaid[name][kind]=value
            need(cfg['bootstrap_limits']['read_bytes']>=FORMAT_CAP+1,
                 'full earlier carrier read bound prepaid before creation')
            for name in ('to_worker','from_worker'):
                self.attempts.append('pipe:'+name)
                r,w=os.pipe2(os.O_CLOEXEC|os.O_NONBLOCK)
                self.fds[name+'_read']=r;self.fds[name+'_write']=w
            pipes={'read':_fd_identity(self.fds['to_worker_read']),
                   'write':_fd_identity(self.fds['from_worker_write'])}
            launch=s.lease['descriptor']
            self.binding={'campaign':c.plan.body['campaign_id'],'source':c.plan.body['observer_source'],
                'launch':launch,'read_identity':pipes['read'],'write_identity':pipes['write'],
                'maximum_frame_bytes':cfg['metadata_cap']}
            self.body=compile_worker_bootstrap_body_v1(c.plan,
                resource_plan={'descriptor':c.plan.resource_plan_pin,'body':c.plan.resource_plan},
                lease=s.lease,subject=s.subject,request=s.request,launch_binding=self.binding,
                native_configuration={'descriptor':c.configuration.descriptor,'body':c.configuration.body},
                pipe_identities=pipes)
            self.raw=encode(self.body);need(0<len(self.raw)<=FORMAT_CAP,'complete fixed carrier format')
            self.descriptor=pin(self.raw)
            c.meter.charge('write_bytes',len(self.raw));c.meter.charge('retained_bytes',len(self.raw))
            self.attempts.append('memfd_create')
            self.fds['carrier_rw']=os.memfd_create('neurobench-hm-whole',os.MFD_CLOEXEC|os.MFD_ALLOW_SEALING)
            at=0
            while at<len(self.raw):
                c.meter.check();self.attempts.append(('carrier_write',at))
                n=os.write(self.fds['carrier_rw'],self.raw[at:]);need(n>0,'actual carrier write progress');at+=n
            self.attempts.append('seal');fcntl.fcntl(self.fds['carrier_rw'],fcntl.F_ADD_SEALS,15)
            need(fcntl.fcntl(self.fds['carrier_rw'],fcntl.F_GET_SEALS)==15,'actual complete immutable carrier seals')
            self.attempts.append('readonly_reopen')
            self.fds['carrier_ro']=os.open('/proc/self/fd/'+str(self.fds['carrier_rw']),os.O_RDONLY|os.O_CLOEXEC)
            need(_fd_identity(self.fds['carrier_ro'])==_fd_identity(self.fds['carrier_rw']) and
                 os.fstat(self.fds['carrier_ro']).st_size==len(self.raw),'same sealed actual carrier reopened readonly')
            need(self._close('carrier_rw'),'actual original writable carrier owner closed')
            self.pass_fds=(self.fds['carrier_ro'],self.fds['to_worker_read'],self.fds['from_worker_write'])
            self.complete=True;return self
        except BaseException as error:retain(self,error,'carrier_prepare');raise self.raw_first

    def open_endpoint_once(self):
        need(self.complete and not self.endpoint_entered,'one H endpoint after actual worker inheritance')
        self.endpoint_entered=True;s=self.stage
        # Retain the real endpoint object before its constructor can touch FDs.
        endpoint=object.__new__(HostEndpoint);self.endpoint=endpoint
        binding=dict(self.binding,read_identity=_fd_identity(self.fds['from_worker_read']),
                     write_identity=_fd_identity(self.fds['to_worker_write']))
        try:
            HostEndpoint.__init__(endpoint,self.fds['from_worker_read'],self.fds['to_worker_write'],
                binding=binding,selected_qualification=s.worker_configuration['selected_channel_qualification'],
                meter=HMStageChannelMeterV1(s))
            self.endpoint_complete=True
            # Endpoint now owns these two exact original descriptors.
            self.fds.pop('from_worker_read');self.fds.pop('to_worker_write')
            for name in ('carrier_ro','to_worker_read','from_worker_write'):
                need(self._close(name),'H closes each inherited W duplicate once')
            return endpoint
        except BaseException as error:retain(self,error,'endpoint_constructor');raise self.raw_first

    def close_once(self):
        if self.endpoint is not None and getattr(self,'endpoint_complete',False) and not getattr(self,'endpoint_close_entered',False):
            self.endpoint_close_entered=True
            try:self.endpoint.close();self.endpoint_closed=True
            except BaseException as error:retain(self,error,'endpoint_close')
        # Partial constructors never independently own numeric descriptors; the
        # original carrier slots still close each acquired FD exactly once.
        for name in tuple(self.fds):self._close(name)
        return not self.fds and self.raw_first is None and (
            self.endpoint is None or not getattr(self,'endpoint_complete',False) or getattr(self,'endpoint_closed',False))


class HMNativeStageAttemptV1:
    def __init__(self,token,campaign,sequence,pending):
        need(token is _STAGE,'actual fixed source-native stage factory')
        self.campaign=campaign;self.sequence=sequence;self.pending=pending;self.allocation=None
        self.raw_first=None;self.secondaries=[];self.carrier=None;self.running=None;self.start_entered=False
        self.finished=False;self.finish_entered=False;self.closure_complete=False;self.eligible=False
        self.loop_finished=False;self.observation=None;self.prepaid={};self.publications=[]
        self.start=None;self.worker_terminal=None;self.original_result=None;self.pid_samples=[]
        self.terminal_request=None;self.terminal_ack=None;self.actual_spawn_returned_ns=None
        self.protocol_eof_observed=False;self.protocol_eof_read_attempts=0;self.post_terminal_bytes=0
        self.outer_worker_launch_attempts=0
        self.subject=None;self.request=None;self.lease=None;self.final_clock=None
        self.storage_begin=None;self.storage_samples=[]

    def retain(self,error,site):retain(self,error,site)

    def _publish(self,tag,body):
        name='hm_whole_'+str(self.sequence)+'_'+tag+'.json'
        attempt={'name':name,'body':body,'descriptor':None};self.publications.append(attempt)
        d=self.campaign.host.outputs.publish(name,body);attempt['descriptor']=d
        return {'descriptor':d,'body':body}

    def prepare_once(self):
        c=self.campaign
        try:
            self.allocation=c.reservations.reserve_stage_once(self.sequence)
            a=self.allocation
            self.storage_begin=c.volume.sample()['allocated_bytes']
            cfg=c.configuration.body['worker_bootstrap'][a.stage]
            self.worker_configuration=cfg
            pending=self.pending;need(c.controller.endpoint.pending is pending,
                 'actual original C request still pending before native effects')
            b=pending['body']['body'];closed(b,('schema','sequence','profile','subject','scientific_request','original_authority'))
            need(b['schema']=='hm_whole_stage_dispatch_request_v1' and b['sequence']==self.sequence and
                 b['profile']==c.plan.pin,'exact current source-owned stage dispatch')
            self.subject=b['subject'];self.request=b['scientific_request'];exact_wrapper(self.subject);exact_wrapper(self.request)
            need(self.subject['body']['profile']==c.plan.pin and self.subject['body']['sequence']==self.sequence and
                 self.subject['body']['stage']==a.stage,'same exact stage subject')
            grace=c.plan.body['polling']['termination_grace_ns']
            self.run_deadline_ns=a.deadline_ns-grace
            need(a.begin_ns<self.run_deadline_ns<a.deadline_ns,'selected terminal grace inside full lifetime hold')
            lease={'schema':'hm_whole_stage_lease_v1','profile':c.plan.pin,'resource_plan':c.plan.resource_plan_pin,
                'sequence':self.sequence,'stage':a.stage,'subject':self.subject['descriptor'],
                'original_authority':b['original_authority'],'controller':c.controller.controller_identity,
                'host':c.controller.host_identity,'worker_nonce':a.row['worker_nonce'],
                'workspace_nonce':a.row['workspace_nonce'],'stage_started_ns':a.begin_ns,
                'deadline_ns':self.run_deadline_ns,'evidence_deadline_ns':a.deadline_ns}
            self.lease=self._publish('lease',lease)
            HMWorkerCarrierV1(self).prepare_once()
            return self
        except BaseException as error:
            if self.allocation is None:self.allocation=c.reservations.allocations.get(self.sequence)
            self.retain(error,'prepare');raise self.raw_first

    def launch_once(self):
        need(not self.start_entered and self.carrier.complete,'one actual prepared fixed worker launch')
        self.start_entered=True;c=self.campaign;a=self.allocation;cfg=self.worker_configuration
        try:
            env=dict(cfg['environment_values']);need(not any(k in env for k in FD_KEYS),'no preexisting inherited-FD overrides')
            env.update(dict(zip(FD_KEYS,map(str,self.carrier.pass_fds))))
            limits=a.row['physical'];hard=c.plan.resource_plan['hard_envelope']
            spec={'mode':'hm_stage','argv':[cfg['python_executable'],'-I','-m','four_programmes.hm_whole_worker_entry_v1'],
                'cwd':self.request['body']['package'],'env':env,'source':c.plan.body['worker_source'],
                'campaign':c.plan.body['campaign_id'],'nonce':a.row['worker_nonce'],
                'parent_launch':self.carrier.binding['launch'],'group_parent':c.configuration.body['group_parent'],
                'group_name':a.row['workspace_nonce'],'limits':{k:limits[k] for k in('memory_bytes','pids','cpu_ns','stream_bytes')},
                'run_deadline_ns':self.run_deadline_ns,'evidence_deadline_ns':a.deadline_ns,
                'output_prefix':'hm_whole_'+str(self.sequence)}
            spec['limits'].update(whole_cpu_ns=hard['cpu_ns'],whole_memory_bytes=hard['memory_bytes'],
                                  whole_storage_bytes=hard['retained_storage_bytes'])
            self.spec=spec
            need(self.outer_worker_launch_attempts==0 and limits["process_starts"]>=1,
                 "one nonrefundable outer-worker launch attempt inside original stage hold")
            self.outer_worker_launch_attempts+=1
            self.running=c.host.start(spec,pass_fds=self.carrier.pass_fds)
            self.actual_spawn_returned_ns=time.monotonic_ns()
            need(type(self.running)is RunningProcess and self.running.owner is c.host and
                 c.host.active.get(a.row['worker_nonce'])is self.running,'actual retained source-created worker return')
            self.running._hm_native_stage_v1=self
            if self.running.primary is not None:raise self.running.primary
            self.carrier.open_endpoint_once();return self.running
        except BaseException as error:
            if self.running is None:
                r=c.host.active.get(a.row['worker_nonce'])
                if type(r)is RunningProcess and r.owner is c.host and r.spec is getattr(self,'spec',None):
                    self.running=r;r._hm_native_stage_v1=self
            self.retain(error,'launch');raise self.raw_first

    def _start_request(self,pending):
        c=self.campaign;b=pending['body']['body'];r=self.running
        closed(b,('schema','profile','lease','subject','bootstrap','worker','stage'))
        need(self.start is None and b['schema']=='hm_whole_worker_start_request_v1' and
             b['profile']==c.plan.pin and b['lease']==self.lease['descriptor'] and
             b['subject']==self.subject['descriptor'] and b['bootstrap']==self.carrier.descriptor and
             b['worker']==r.identity and b['stage']==self.allocation.stage,
             'actual W request joins exact carrier, identity, source and original lease')
        body={'schema':'hm_whole_stage_start_v1','profile':c.plan.pin,'lease':self.lease['descriptor'],
            'subject':self.subject['descriptor'],'bootstrap':self.carrier.descriptor,'sequence':self.sequence,
            'stage':self.allocation.stage,'worker':r.identity,'host':c.controller.host_identity,
            'controller':c.controller.controller_identity,'observed_ns':time.monotonic_ns(),
            'stage_started_ns':self.allocation.begin_ns,'deadline_ns':self.run_deadline_ns,
            'evidence_deadline_ns':self.allocation.deadline_ns}
        self.start=self._publish('start',body)
        self.start_return=self.carrier.endpoint.respond(pending,status='observed',
            result={'schema':'hm_whole_worker_start_response_v1','start':self.start['descriptor'],'start_body':body})

    def _terminal_request(self,pending):
        c=self.campaign;b=pending['body']['body'];closed(b,('schema','profile','lease','stage','worker','terminal'))
        need(self.start is not None and self.terminal_request is None and
             b['schema']=='hm_whole_worker_terminal_request_v1' and b['profile']==c.plan.pin and
             b['lease']==self.lease['descriptor'] and b['stage']==self.allocation.stage and
             b['worker']==self.running.identity,'one actual terminal from original started W')
        self.terminal_request=pending
        cfg=self.worker_configuration;store=Store(cfg['terminal_root'],c.meter)
        d=b['terminal'];raw=store.read(d,cfg['metadata_cap'],metadata=True);body=parse(raw,cfg['metadata_cap'])
        self.worker_terminal={'descriptor':d,'body':body,'raw':raw}
        need(body['schema']=='hm_whole_worker_terminal_v1' and body['profile']==c.plan.pin and
             body['lease']==self.lease['descriptor'] and body['subject']==self.subject['descriptor'] and
             body['request']==self.request['descriptor'] and body['stage']==self.allocation.stage and
             body['sequence']==self.sequence and body['worker']==self.running.identity and
             body['start']==self.start['descriptor'] and body['result_root']==self.request['body']['output'],
             'actual full original W terminal identity and explicit result root')
        if body['result'] is not None:
            result_store=Store(self.request['body']['output'],c.meter)
            result_raw=result_store.read(body['result'],cfg['metadata_cap'],metadata=True)
            self.original_result={'descriptor':body['result'],'body':parse(result_raw,cfg['metadata_cap']),
                                  'raw':result_raw,'root':self.request['body']['output']}
        self.terminal_ack=self.carrier.endpoint.respond(pending,status='observed',result={
            'schema':'hm_whole_worker_terminal_response_v1','terminal':d,'received_ns':time.monotonic_ns()})

    def _observe_stage_storage(self,whole):
        need(self.storage_begin is not None,"actual storage observation before stage effects")
        now=whole["volume"]["allocated_bytes"];delta=now-self.storage_begin
        row={"observed_ns":whole["volume"]["observed_ns"],"allocated_delta_bytes":delta}
        self.storage_samples.append(row)
        need(0<=delta<=self.allocation.row["physical"]["retained_storage_bytes"],
             "actual conservative entire-stage retained physical growth within original hold")

    def poll_once(self):
        """Observe actual whole/W limits even inside a partial control frame."""
        c=self.campaign;r=self.running
        need(type(r)is RunningProcess and r.owner is c.host and
             c.stages.get(self.sequence)is self and r._hm_native_stage_v1 is self,
             "actual retained original stage polling owner")
        whole=c.observe_once();self._observe_stage_storage(whole)
        c.host._physical(r)
        self.pid_samples.append(_group_pids(r.group,c.meter,self))
        need(self.pid_samples[-1]<=self.allocation.row["physical"]["pids"],
             "actual original W task peak within its unchanged hold")

    def observe_protocol_eof_once(self):
        """After terminal ACK only EOF is legal; process exit is separate."""
        need(self.terminal_ack is not None,"protocol closure only after actual H terminal ACK")
        if self.protocol_eof_observed:return True
        endpoint=self.carrier.endpoint;self.protocol_eof_read_attempts+=1
        endpoint.meter.charge("read_bytes",1)
        endpoint.meter.charge("retained_bytes",1)
        try:raw=os.read(endpoint.read_fd,1)
        except BlockingIOError:return False
        self.post_terminal_bytes+=len(raw)
        need(raw==b"","no additional protocol bytes after terminal ACK")
        self.protocol_eof_observed=True;return True

    def observe_until_exit(self):
        c=self.campaign;r=self.running;endpoint=self.carrier.endpoint
        try:
            while True:
                self.poll_once()
                if not self.protocol_eof_observed and select.select([endpoint.read_fd],[],[],0)[0]:
                    if self.terminal_ack is not None:self.observe_protocol_eof_once()
                    else:
                        pending=endpoint.accept();body=pending["body"]["body"]
                        if body.get("schema")=="hm_whole_worker_start_request_v1":self._start_request(pending)
                        else:self._terminal_request(pending)
                if not c.host.pump(r,poll_interval_ns=c.plan.body["polling"]["interval_ns"]):
                    if r.primary is None and self.terminal_ack is not None:
                        need(self.observe_protocol_eof_once(),
                             "actual protocol EOF after all original worker descendants exit")
                    break
            if r.primary is not None:raise r.primary
        except BaseException as error:
            self.retain(error,'observe')
            try:r.own_failure(self.raw_first,'hm_native_stage_observation')
            except BaseException as later:self.retain(later,'observe_retention')
        finally:self.loop_finished=True

    def finish_once(self):
        if self.finish_entered:return self
        self.finish_entered=True;c=self.campaign;r=self.running
        if r is not None:
            self.loop_finished=True
            if self.raw_first is not None and r.primary is None:
                try:r.own_failure(self.raw_first,'hm_native_stage_prior_failure')
                except BaseException as error:self.retain(error,'finish_retention')
            try:
                self.pid_samples.append(_group_pids(r.group,c.meter,self))
            except BaseException as error:self.retain(error,'final_pid_peak')
            try:self.observation=c.host.finish(r,pump=False)
            except BaseException as error:self.retain(error,'original_host_finish')
        if self.carrier is not None:
            try:self.carrier_closed=self.carrier.close_once()
            except BaseException as error:self.carrier_closed=False;self.retain(error,'carrier_cleanup')
        else:self.carrier_closed=True
        try:
            self.final_physical=c.observe_once();self.final_clock=time.monotonic_ns()
            if self.storage_begin is not None:self._observe_stage_storage(self.final_physical)
        except BaseException as error:self.retain(error,'final_physical')
        self.finished=True
        try:
            need(type(self.observation)is OriginalProcessObservation and self.observation.success,
                 'actual original natural exit/streams/tree/physical/publication closure')
            need(self.worker_terminal is not None and self.original_result is not None and self.terminal_ack is not None and
                 self.protocol_eof_observed,
                 'actual original science result, terminal capture, H acknowledgement and protocol EOF')
            terminal=self.worker_terminal['body']
            need(terminal['original_failure'] is None and terminal['cleanup_errors']==[] and
                 terminal['source_session_closed'] is True and terminal['H_original_exit_still_required'] is True,
                 'original W completed source work, separate H exit observation')
            need(self.carrier_closed and self.pid_samples and max(self.pid_samples)<=self.allocation.row['physical']['pids'] and
                 self.final_clock<=self.allocation.deadline_ns and self.raw_first is None,
                 'complete retained original lifetime closure inside all selected limits')
            self.closure_complete=True;self.eligible=True
        except BaseException as error:self.retain(error,'closure_eligibility')
        return self

    def record(self):
        """H-private evidence. Reference bodies/streams require later seal barrier."""
        def wrapper(item):
            return None if item is None else {k:v for k,v in item.items()if k!='raw'}
        return {'schema':'hm_whole_native_stage_observation_v1','visibility':'H_private',
            'profile':self.campaign.plan.pin,'sequence':self.sequence,'stage':None if self.allocation is None else self.allocation.stage,
            'lease':self.lease,'subject':self.subject,'request':self.request,'start':self.start,
            'terminal':wrapper(self.worker_terminal),'original_result':wrapper(self.original_result),
            'protocol_eof_observed':self.protocol_eof_observed,
            'protocol_eof_read_attempts':self.protocol_eof_read_attempts,
            'post_terminal_bytes':self.post_terminal_bytes,
            'outer_worker_launch_attempts':self.outer_worker_launch_attempts,
            'descendant_process_creations':None,
            'process_start_accounting_qualification_hold':True,
            'process_starts_wire_meaning':'outer_worker_launch_attempts',
            'outer':None if self.observation is None else {'descriptor':self.observation.receipt,
                'body':self.observation.receipt_record,'actual_return':self.observation.record},
            'actual_spawn_returned_ns':self.actual_spawn_returned_ns,'stage_finished_ns':self.final_clock,
            'PID_lifetime_samples':self.pid_samples,'prepaid_original_H_credit':self.prepaid,
            'stage_storage':{'begin_allocated_bytes':self.storage_begin,'samples':self.storage_samples,
                'scope':'allocated physical growth of entire exclusive volume during stage, including H/C',
                'between_poll_transient_peak_known':False,'W_exclusive_attribution':False,
                'logical_capture_limits_separate':True,'unused_capacity_transferred':False},
            'finished':self.finished,'closure_complete':self.closure_complete,'eligible':self.eligible,
            'original_failure':None if self.raw_first is None else failure(self.raw_first),
            'secondary_errors':[{'site':site,'error':failure(e)}for e,site in self.secondaries],
            'W_subgroup_measured_from_birth':False,'prejoin_work':'enclosing whole domain; individual W startup attribution incomplete',
            'scientific_qualification':False}


class HMNativeCampaignOwnerV1:
    def __init__(self,token,*,reservations,host,session,configuration_roots):
        need(token is _CAMPAIGN and type(reservations)is HMWholeJobReservationOwnerV1 and
             type(host)is HostObserver and type(session)is SourceSession and session.programme==PROGRAMME,
             'actual original compiled resources, observer and HM source session')
        need(reservations.campaign is None,'one original native campaign including failed construction')
        self.reservations=reservations;self.plan=reservations.plan;self.host=host;self.session=session
        self.meter=reservations.host_share;self.raw_first=None;self.secondaries=[];self.stages={};self.observations=[]
        self.configuration=None;self.volume=None;self.clocks=None;self.close_entered=False;self.closed=False
        self.controller=None
        self.owned_close_entered=False;self.final_tail=None
        self.controller_finish_entered=False;self.controller_observation=None
        self.controller_exit_owner=None;self.controller_final_physical=None
        self.final=None;reservations.campaign=self;_LIVE[id(self)]=self
        try:
            reservations.require_original();need(host.meter is self.meter and host.outputs.meter is self.meter,
                 'one actual original H meter for native observations and output publication')
            self.controller=require_original_controller_v1(reservations)
            need(self.controller.observer is host,'same original C/H native observer')
            HMNativeConfigurationV1(self,configuration_roots)
            HMFixedVolumeCustodyV1(self).open_once()
            self.controller_exit_owner=bind_hm_exit_accounting_v1(host,self.controller.controller_process,
                role='C',expected_identity=self.controller.controller_identity,clock_mapping=host.mapping,
                poll_interval_ns=self.plan.body['polling']['interval_ns'])
            HMContinuousProcessClocksV1(self).start_once()
            self.observe_once()
        except BaseException as error:
            self.retain(error,'campaign_prepare')
            try:self._finish_failed_prepare_controller_once()
            except BaseException as later:self.retain(later,'campaign_prepare_controller_cleanup')
            self.close_owned_once();raise self.raw_first

    def _finish_failed_prepare_controller_once(self):
        """Dispose only C already retained by this original constructor.

        A partially constructed exit owner registers itself before opening its
        pidfd. Its exact retained handle still needs disposal, even when the
        factory never returned. Missing final CPU remains a failure.
        """
        if self.controller is None:return
        need(not self.controller_finish_entered,'one failed preparation controller disposal')
        self.controller_finish_entered=True;r=self.controller.controller_process
        need(type(r)is RunningProcess and self.controller.observer is self.host and
             r.owner is self.host and self.host.active.get(r.spec['nonce'])is r,
             'only original constructor-retained C may be disposed')
        r.own_failure(self.raw_first,'campaign_prepare')
        bound=getattr(r,'_hm_exit_accounting_v1',None)
        if bound is not None:
            need(type(bound)is HMOwnExitAccountingV1 and bound.running is r and
                 bound.observer is self.host and self.host._hm_exit_owners_v1.get(id(r))is bound,
                 'same partial or complete original C exit owner')
            self.controller_exit_owner=bound
        self.controller_observation=self.host.finish(r,pump=bound is None)

    def retain(self,error,site):
        if self.raw_first is None:self.raw_first=error
        elif error is not self.raw_first:self.secondaries.append((error,site))
        try:self.reservations.retain(error,site)
        except BaseException as later:
            if later is not self.raw_first:self.secondaries.append((later,site+':retention'))

    def require_original(self):
        need(_LIVE.get(id(self))is self and self.reservations.campaign is self and not self.close_entered,
             'same retained live source-native campaign')
        self.reservations.require_original();self.configuration.require_original()
        need(require_original_controller_v1(self.reservations)is self.controller,'same original controller custody')
        if self.raw_first is not None:raise self.raw_first
        return self

    def observe_once(self):
        row={'clock':None,'whole':None,'volume':None,'whole_pids':None};self.observations.append(row)
        first=None
        for name,call in (('clock',self.clocks.sample),('whole',self.host.whole_group.sample),
                          ('volume',self.volume.sample),('whole_pids',lambda:_group_pids(self.host.whole_group,self.meter,self))):
            try:row[name]=call()
            except BaseException as error:
                if first is None:first=error
                self.retain(error,'whole_sample:'+name)
        if first is not None:raise self.raw_first
        delta=self.clocks.deltas(row['clock']);row['process_deltas']=delta
        hard=self.plan.resource_plan['hard_envelope'];overhead=self.plan.body['overhead']
        try:
            need(delta['H_own_cpu_ns']+delta['C_own_cpu_ns']<=overhead['cpu_ns'] and
                 delta['wall_ns']<=self.plan.evidence_deadline_ns-self.plan.origin_ns,
                 'actual continuous H/C operational CPU bound, no worker aggregate relabel')
            need(row['whole']['cpu_ns']<=hard['cpu_ns'] and row['whole']['memory_peak']<=hard['memory_bytes'] and
                 row['whole_pids']<=hard['pids'] and row['volume']['retained_delta_bytes']<=hard['retained_storage_bytes'],
                 'actual independently observed whole-job physical bounds')
        except BaseException as error:self.retain(error,'whole_limit');raise self.raw_first
        return row

    def poll_whole_once(self):
        """Actual C/H channel hook; never a caller-supplied observation."""
        if not self.close_entered:self.require_original()
        else:
            need(_LIVE.get(id(self))is self and self.reservations.campaign is self and
                 not self.owned_close_entered and not self.closed and
                 self.volume is not None and not self.volume.close_entered and
                 self.clocks is not None and not self.clocks.close_entered,
                 "same original live observation owner throughout final H response")
            self.plan.require_original();self.configuration.require_original()
            need(require_original_controller_v1(self.reservations)is self.controller,
                 "same actual retained C/H custody during final response")
        return self.observe_once()

    def run_stage_once(self,pending):
        self.require_original();need(self.controller.endpoint.pending is pending,'actual pending original C request')
        sequence=pending['body']['body']['sequence'];integer(sequence,1)
        need(sequence not in self.stages,'one native stage attempt including failure')
        stage=HMNativeStageAttemptV1(_STAGE,self,sequence,pending);self.stages[sequence]=stage
        try:stage.prepare_once();stage.launch_once();stage.observe_until_exit()
        except BaseException as error:stage.retain(error,'run')
        finally:stage.finish_once()
        if stage.allocation is not None:
            try:self.reservations.finish_stage_once(stage.allocation,stage)
            except BaseException as error:stage.retain(error,'allocation_finish')
        return stage

    def close_owned_once(self):
        """H invokes after its actual final response or failed publication."""
        if self.owned_close_entered:return self.closed
        self.owned_close_entered=True
        if (self.volume is not None and self.clocks is not None and
                self.volume.fd is not None and self.clocks.begin is not None):
            try:self.final_tail=self.observe_once()
            except BaseException as error:self.retain(error,"campaign_final_tail")
        for owner in (self.volume,self.clocks):
            if owner is None:continue
            try:owner.close_once()
            except BaseException as error:self.retain(error,'campaign_owned_close')
        self.closed=bool(self.volume and self.volume.closed and self.clocks and self.clocks.closed)
        return self.closed

    def finish_controller_once(self):
        """Actually observe/reap original C after H's final response, once.

        C's clock can disappear immediately after the response. The original
        observer captures its terminal own-CPU interval before reaping, and
        later continuous H samples consume that exact retained producer.
        """
        need(not self.controller_finish_entered,'one original C finish attempt, including failures')
        self.controller_finish_entered=True;r=self.controller.controller_process
        need(type(self.controller_exit_owner)is HMOwnExitAccountingV1 and
             self.controller_exit_owner.running is r and r.owner is self.host and
             self.host.active.get(r.spec['nonce'])is r,
             'actual same original observed C and retained exit accounting owner')
        try:
            while True:
                try:self.observe_once()
                except BaseException as error:
                    self.retain(error,'controller_finish_physical')
                    try:r.own_failure(error,'controller_finish_physical')
                    except BaseException as later:self.retain(later,'controller_finish_retention')
                if not self.host.pump(r,poll_interval_ns=self.plan.body['polling']['interval_ns']):break
            if r.primary is not None:self.retain(r.primary,'controller_process')
        except BaseException as error:self.retain(error,'controller_pump')
        finally:
            try:self.controller_observation=self.host.finish(r,pump=False)
            except BaseException as error:self.retain(error,'controller_finish')
        try:
            self.controller_final_physical=self.observe_once()
            need(type(self.controller_observation)is OriginalProcessObservation and self.controller_observation.success and
                 self.controller_exit_owner.reaped and self.controller_exit_owner.closed,
                 'actual original C natural exit/EOF/tree/physical/publication and exit-owner closure')
            self.controller_exit_owner.require_final(self.clocks.last_C_live_cpu_ns)
        except BaseException as error:self.retain(error,'controller_final_reconciliation')
        if self.raw_first is not None:raise self.raw_first
        return self.controller_observation

    def close_once(self,actual_controller_final_request):
        need(not self.close_entered,'one campaign prefix closure attempt including failure')
        self.close_entered=True;self.final_request=actual_controller_final_request
        try:
            need(self.controller.endpoint.pending is actual_controller_final_request and
                 actual_controller_final_request['body']['operation']=='final_report',
                 'actual final C request, never a caller success receipt')
            self.final=self.observe_once()
            need(len(self.stages)==3 and all(s.eligible and s.closure_complete for s in self.stages.values()) and
                 self.raw_first is None,'all full original reference/A/B native lifetimes completed')
        except BaseException as error:self.retain(error,'campaign_final_prefix')
        # These exact handles remain active during prefix persistence and
        # the original H response. Parent H finally closes them afterwards.
        return {'schema':'hm_whole_native_campaign_prefix_v1','profile':self.plan.pin,'final_observation':self.final,
            'stages':[s.record()for s in self.stages.values()],'owned_observation_handles_closed':self.closed,
            'continuous_final_H_response_observation_required':True,
            'original_failure':None if self.raw_first is None else failure(self.raw_first),
            'whole_group_is_independent_enclosing_counter':True,'overlapping_counters_summed_twice':False,
            'scope':'through actual final C request, before final H response and outer H/C process exit',
            'later_original_whole_reconciliation_required':True,'terminal_reservation_retained':True,
            'scientific_qualification':False}


def open_original_hm_native_campaign_v1(*,reservations,host,session,configuration_roots):
    return HMNativeCampaignOwnerV1(_CAMPAIGN,reservations=reservations,host=host,
                                 session=session,configuration_roots=configuration_roots)
