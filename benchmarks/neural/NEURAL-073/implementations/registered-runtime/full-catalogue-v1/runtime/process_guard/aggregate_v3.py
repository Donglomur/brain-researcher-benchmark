"""Additive real candidate/broker/monitor aggregate. No native work on import."""
from dataclasses import dataclass,asdict
import hashlib
import json
import os
from pathlib import Path
import selectors
import socket
import subprocess
import threading
import time
import weakref
from ..core.custody import VerifiedAuthority,digest,canonical,require_digest
from ..core.plan import ContextState
from ..core import oom_witness
from ..core.outcomes import (classify_process,classify_aggregate,monitor_event_valid,
    monitor_exhaustion_valid,ledger_exhaustion_valid,valid_violation)
from ..core.resources import CandidateCaps,BudgetExceeded,ResourceLedger
from ..provider_transport.protocol import AdapterAdmission
from .barrier_v2 import GuardContextV2
from .contracts import GuardError,GuardAdmission
from .linux import _read,_write,_kv,_file_pin,_no_symlink_path,parse_cpuset
from . import monitor_v3

_SEAL=object();_LEASES=weakref.WeakKeyDictionary();_CLOSURES=weakref.WeakKeyDictionary();_EXHAUSTIONS=weakref.WeakKeyDictionary()


def require_single_native_supervisor():
    """Exact current supervisor only; at most two task entries, never a PID scan."""
    if threading.current_thread() is not threading.main_thread() or threading.active_count()!=1:
        raise GuardError('dedicated single-threaded trusted supervisor required')
    names=[]
    with os.scandir('/proc/self/task') as entries:
        for entry in entries:
            names.append(entry.name)
            if len(names)>1:raise GuardError('native threads remain; preexec launch refused')
    validate_native_task_names(names,os.getpid())


def validate_native_task_names(names,pid):
    """Pure validator; this alone cannot authorize or qualify a native launch."""
    if names!=[str(pid)]:raise GuardError('exact single native main-thread identity required')


def guard_required_bindings(admission,monitor_runtime,caps=None):
    admission.validate();monitor_runtime.validate();caps=caps or CandidateCaps()
    if admission.scratch_capacity_bytes!=caps.writable_bytes:
        raise GuardError('full selected512GiB scratch opportunity required; no smaller profile')
    return {'context_digest':digest(admission.context_id),'caps_digest':caps.binding_digest,
        'guard_admission_digest':admission.binding_digest,'environment_evidence_digest':admission.environment_evidence_digest,
        'control_source_digest':admission.control_source_digest,'aggregate_monitor_contract_digest':monitor_runtime.binding_digest,
        'oom_witness_contract_digest':monitor_runtime.oom_contract_digest}


@dataclass(frozen=True)
class MonitorRuntime:
    python_path:str
    python_bytes:int
    python_sha256:str
    source_path:str
    source_bytes:int
    source_sha256:str
    native_contract_digest:str
    oom_witness_evidence_digest:str

    def validate(self):
        for path in (self.python_path,self.source_path):
            if not isinstance(path,str) or not path.startswith('/') or str(Path(path))!=path:
                raise GuardError('explicit pinned monitor executable/source paths required')
        for n in (self.python_bytes,self.source_bytes):
            if type(n) is not int or n<=0:raise GuardError('positive monitor pin length required')
        for d in (self.python_sha256,self.source_sha256,self.native_contract_digest,self.oom_witness_evidence_digest):require_digest(d)

    @property
    def binding_digest(self):return digest(asdict(self))

    @property
    def oom_contract_digest(self):return oom_witness.contract_digest(self.oom_witness_evidence_digest)


class BrokerLease:
    __slots__=('__weakref__',)
    def __init__(self,seal):
        if seal is not _SEAL:raise GuardError('broker lease requires real aggregate preparation')

    def require(self,admission,state,ledger):
        record=_LEASES.get(self)
        if record is None:raise GuardError('unregistered broker lease')
        g=record['guard']
        if (record['admission_digest']!=admission.binding_digest or state.context.context_id!=g.a.context_id
            or state.context.arm!=g.a.arm or ledger is not g.ledger or record['closed']):raise GuardError('broker context/admission/ledger mismatch')
        g._broker_owned();g._meter()
        return {'context_id':g.a.context_id,'aggregate_identity':g.aggregate_identity,
                'broker_identity':g.broker_identity,'capture_directory':record['admission'].capture_directory,
                'oom_protection_digest':g.monitor_protection.to_dict()['digest'],
                'payload_eligibility_contract_digest':g.monitor_runtime.oom_contract_digest}

    def _spawn(self):
        record=_LEASES.get(self)
        if record is None or record['spawned'] or record['closed']:raise GuardError('broker launch is registered/single-use')
        g=record['guard'];g._broker_owned();g._meter()
        require_single_native_supervisor()
        oom_witness.eligible_supervisor(expected_start=g.guardian_start_ticks)
        record['spawned']=True
        # Descriptor is opened under pinned ownership before fork; no untrusted
        # executable/tokenizer instruction can precede child cgroup attachment.
        fd=os.open(g.broker/'cgroup.procs',os.O_WRONLY|os.O_NOFOLLOW|os.O_CLOEXEC)
        def attach():
            value=str(os.getpid()).encode('ascii')
            if os.write(fd,value)!=len(value):raise GuardError('short broker cgroup attachment')
            os.close(fd)
            oom_witness.payload_before_exec()
        try:
            proc=subprocess.Popen(list(record['admission'].argv),stdin=subprocess.PIPE,stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,shell=False,close_fds=True,pass_fds=(fd,),start_new_session=True,
                preexec_fn=attach,cwd='/',env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8'})
            record['process']=proc
            return proc
        finally:os.close(fd)

    def observe(self):
        record=_LEASES.get(self)
        if record is None:raise GuardError('unregistered broker lease')
        return record['guard']._meter()

    def terminate_owned(self):
        record=_LEASES.get(self)
        if record is None:raise GuardError('unregistered broker lease')
        g=record['guard'];g._broker_owned();g._kill_group(g.broker,g.broker_identity)

    def exhaustion_evidence(self):
        record=_LEASES.get(self)
        if record is None or not record['spawned'] or record['closed']:raise GuardError('registered open broker required')
        return record['guard'].settle_exhaustion()

    def _closed_receipt(self,transport_receipt,*,exhaustion=None):
        record=_LEASES.get(self)
        if record is None or record['closed'] or not record['spawned']:raise GuardError('broker closure order')
        g=record['guard'];g._broker_owned()
        if _kv(_read(g.broker/'cgroup.events'))['populated']!=0:raise GuardError('actual broker descendants remain')
        if any(r['status']=='reserved' for r in g.ledger.provider_requests.values()):raise GuardError('unresolved provider usage blocks broker closure')
        if exhaustion is None:g._meter()
        else:
            evidence=_EXHAUSTIONS.get(exhaustion) if isinstance(exhaustion,ExhaustionEvidence) else None
            if evidence is None or evidence['guard'] is not g:raise GuardError('actual same-guard exhaustion custody required')
            if g.aggregate_failure or g.closure_errors:raise GuardError('later infrastructure failure blocks broker closure')
            g._require_drained_leaves()
        closure=BrokerClosure(_SEAL)
        body={'context_id':g.a.context_id,'aggregate_identity':list(g.aggregate_identity),
            'broker_identity':list(g.broker_identity),'provider_admission_digest':record['admission_digest'],
            'transport_receipt':json.loads(canonical(transport_receipt)),'populated':0,
            'exhaustion_evidence':None if exhaustion is None else exhaustion.to_dict(),
            'oom_protection_digest':g.monitor_protection.to_dict()['digest']}
        body['digest']=digest(body);_CLOSURES[closure]={'guard':g,'lease':self,'body':body}
        record['closed']=True;g.broker_closure=closure
        return closure


class ExhaustionEvidence:
    __slots__=('__weakref__',)
    def __init__(self,seal):
        if seal is not _SEAL:raise GuardError('actual monitor/ledger and owned drain required')
    def to_dict(self):
        row=_EXHAUSTIONS.get(self)
        if row is None:raise GuardError('unregistered exhaustion evidence')
        return json.loads(canonical(row['body']))


class BrokerClosure:
    __slots__=('__weakref__',)
    def __init__(self,seal):
        if seal is not _SEAL:raise GuardError('broker closure requires actual owned drain')
    def to_dict(self):
        record=_CLOSURES.get(self)
        if record is None:raise GuardError('unregistered broker closure')
        return json.loads(canonical(record['body']))


class AggregateGuardContextV3(GuardContextV2):
    def __init__(self,admission,*,monitor_runtime,authority,ledger):
        if not isinstance(admission,GuardAdmission) or not isinstance(ledger,ResourceLedger):
            raise GuardError('typed guard admission and actual common ResourceLedger required')
        if not isinstance(monitor_runtime,MonitorRuntime):raise GuardError('typed pinned monitor runtime required')
        monitor_runtime.validate()
        if admission.scratch_capacity_bytes!=ledger.caps.writable_bytes:
            raise GuardError('full selected scratch capacity required before activation')
        super().__init__(admission,authority=authority,ledger=ledger)
        self.monitor_runtime=monitor_runtime
        self.bindings['aggregate_monitor_contract_digest']=monitor_runtime.binding_digest
        self.bindings['oom_witness_contract_digest']=monitor_runtime.oom_contract_digest
        self._authorize(authority,'candidate_author')
        self.aggregate=None;self.aggregate_identity=None;self.broker=None;self.broker_identity=None
        self.monitor_group=None;self.monitor_identity=None;self.monitor_proc=None;self.monitor_socket=None
        self.monitor_cfg=None;self.monitor_last_index=-1;self.monitor_latest=None;self.monitor_protection=None
        self.broker_lease=None;self.broker_closure=None;self.aggregate_closed=False
        self.aggregate_failure=None;self.closure_errors=[];self.original_exhaustion_event=None;self.exhaustion_evidence=None
        self.resource_reclassifications=[]
        ticks,start=monitor_v3.proc_ticks(_read('/proc/'+str(os.getpid())+'/stat'))
        self.guardian_base_ticks=ticks;self.guardian_start_ticks=start
        self.initial_guardian_cpu_ns=max(0,time.process_time_ns()-self.host_cpu_start)

    def _aggregate_owned(self):
        if self.aggregate is None:raise GuardError('aggregate not prepared')
        st=self.aggregate.lstat()
        if self.aggregate.is_symlink() or (st.st_dev,st.st_ino)!=self.aggregate_identity:
            raise GuardError('aggregate ownership changed; no unrelated action allowed')

    def _broker_owned(self):
        self._aggregate_owned()
        st=self.broker.lstat()
        if self.broker.is_symlink() or (st.st_dev,st.st_ino)!=self.broker_identity:raise GuardError('broker ownership changed')

    @staticmethod
    def _kill_group(path,identity):
        st=path.lstat()
        if path.is_symlink() or (st.st_dev,st.st_ino)!=identity:raise GuardError('refuse changed owned group')
        _write(path/'cgroup.kill','1');deadline=time.monotonic()+10
        while _kv(_read(path/'cgroup.events'))['populated']:
            if time.monotonic()>deadline:raise GuardError('owned descendants failed to drain')
            time.sleep(.01)

    def prepare(self):
        self._authorize(self.authority,'candidate_author')
        original=super().prepare()
        self.aggregate,self.aggregate_identity=self.cg,self.identity
        try:
            if not (self.aggregate/'memory.peak').exists():raise GuardError('qualified aggregate memory.peak required')
            _write(self.aggregate/'cgroup.subtree_control','+cpu +cpuset +memory')
            groups={}
            for name in ('candidate','broker','monitor'):
                path=self.aggregate/name;path.mkdir(mode=0o700)
                _write(path/'cpuset.mems',','.join(map(str,self.a.memory_nodes)))
                _write(path/'cpuset.cpus',','.join(map(str,self.a.cpus)))
                if parse_cpuset(_read(path/'cpuset.cpus.effective'))!=self.a.cpus:raise GuardError('child CPU assignment differs')
                if _read(path/'memory.max').strip()!='max' or _read(path/'cpu.max').split()[0]!='max':
                    raise GuardError('child must inherit shared aggregate ceilings, not separate budgets')
                st=path.lstat();groups[name]=(path,(st.st_dev,st.st_ino))
            self.cg,self.identity=groups['candidate'];self.broker,self.broker_identity=groups['broker']
            self.monitor_group,self.monitor_identity=groups['monitor']
            self._start_monitor()
            original.update(aggregate_identity=list(self.aggregate_identity),candidate_identity=list(self.identity),
                broker_identity=list(self.broker_identity),monitor_identity=list(self.monitor_identity),
                actual_resource_parent='one shared aggregate; no per-child budget multiplication')
            self._meter();return original
        except BaseException as exc:
            self.state='prepare_failed';self._remember_error('monitor_prepare',exc)
            if self.aggregate is not None:
                try:self._kill_group(self.aggregate,self.aggregate_identity)
                except BaseException as cleanup:self._remember_error('prepare_owned_cleanup',cleanup)
            raise

    def _start_monitor(self):
        require_single_native_supervisor()
        oom_witness.eligible_supervisor(expected_start=self.guardian_start_ticks)
        m=self.monitor_runtime
        _file_pin(m.python_path,m.python_bytes,m.python_sha256)
        _file_pin(m.source_path,m.source_bytes,m.source_sha256)
        if Path(m.source_path).resolve()!=Path(monitor_v3.__file__).resolve():raise GuardError('monitor pin must identify selected source module')
        root=self.root/'capture'/'monitor-v3';root.mkdir(mode=0o700)
        caps=self.ledger.caps
        cfg={'schema':'n073_aggregate_monitor_config_v3','context_id':self.a.context_id,
            'candidate':str(self.cg),'candidate_identity':list(self.identity),
            'broker':str(self.broker),'broker_identity':list(self.broker_identity),'aggregate':str(self.aggregate),
            'aggregate_identity':list(self.aggregate_identity),'scratch':self.a.scratch_mount,'capture_root':str(root),
            'monitor_leaf':str(self.monitor_group),'monitor_leaf_identity':list(self.monitor_identity),
            'monitor_runtime_digest':m.binding_digest,'oom_contract_digest':m.oom_contract_digest,
            'oom_evidence_digest':m.oom_witness_evidence_digest,'oom_policy':oom_witness.POLICY,
            'guardian_pid':os.getpid(),'guardian_start_ticks':self.guardian_start_ticks,
            'guardian_base_cpu_ticks':self.guardian_base_ticks,'initial_guardian_cpu_ns':self.initial_guardian_cpu_ns,
            'clock_ticks':os.sysconf('SC_CLK_TCK'),'initial_cpu_ns':self.initial_cpu_ns,
            'started_ns':self.ledger.started_ns,'caps':{k:getattr(caps,k) for k in ('wall_ns','cpu_ns','private_rss_bytes','writable_bytes')}}
        raw=canonical(cfg)
        if len(raw)>65536:raise GuardError('bounded private monitor configuration exceeded')
        cfgpath=root/'config.json'
        fd=os.open(cfgpath,os.O_RDWR|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        if os.write(fd,raw)!=len(raw):os.close(fd);raise GuardError('short monitor config write')
        os.fsync(fd);os.lseek(fd,0,os.SEEK_SET)
        control,child=socket.socketpair();cgfd=os.open(self.monitor_group/'cgroup.procs',os.O_WRONLY|os.O_NOFOLLOW)
        stderr=open(root/'original-stderr.bin','xb',buffering=0)
        def attach_monitor():
            pid=str(os.getpid()).encode('ascii')
            if os.write(cgfd,pid)!=len(pid):raise GuardError('short monitor cgroup attachment')
            os.close(cgfd)
        try:
            self.monitor_proc=subprocess.Popen([m.python_path,'-I',m.source_path,str(fd),str(child.fileno()),hashlib.sha256(raw).hexdigest()],
                stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=stderr,close_fds=True,
                pass_fds=(fd,child.fileno(),cgfd),preexec_fn=attach_monitor,start_new_session=True,
                cwd='/',env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8'})
        finally:os.close(fd);os.close(cgfd);child.close();stderr.close()
        self.monitor_socket=control;self.monitor_cfg=cfg
        deadline=min(time.monotonic()+10,self.ledger.started_ns/1e9+caps.wall_ns/1e9)
        def await_message(expected):
            message=b''
            while message!=expected:
                if self.monitor_proc.poll() is not None:raise GuardError('original monitor died before protected readiness')
                left=deadline-time.monotonic()
                if left<=0:raise GuardError('monitor protection handshake timed out before workload GO')
                control.settimeout(min(.1,left))
                try:block=control.recv(len(expected)-len(message))
                except socket.timeout:continue
                if not block:raise GuardError('monitor control EOF before protected readiness')
                message+=block
                if not expected.startswith(message):raise GuardError('invalid monitor protection handshake')
        await_message(b'WAIT_OOM\n')
        self.monitor_protection=oom_witness.protect_owned_monitor(self.monitor_proc,
            context_id=self.a.context_id,leaf=str(self.monitor_group),leaf_identity=self.monitor_identity,
            config_digest=digest(cfg),runtime_digest=m.binding_digest,evidence_digest=m.oom_witness_evidence_digest,
            supervisor_start=self.guardian_start_ticks,authority=self.authority,bindings=self.bindings)
        protection=self.monitor_protection.to_dict();raw_protection=canonical(protection)+b'\n'
        if len(raw_protection)>65536:raise GuardError('bounded protection receipt overflow')
        monitor_v3.write_exclusive(str(root/'oom-protection.json'),raw_protection)
        monitor_v3.sync_directory(str(root))
        self.monitor_protection.verify_live()
        control.settimeout(max(.001,deadline-time.monotonic()))
        control.sendall(('GO '+protection['digest']+'\n').encode('ascii'))
        await_message(b'READY\n')
        self.monitor_protection.verify_live()
        control.settimeout(None)

    def _monitor_event(self,name='latest.json'):
        if self.monitor_cfg is None:raise GuardError('monitor configuration missing')
        event=json.loads(_read(Path(self.monitor_cfg['capture_root'])/name,65536))
        if (not monitor_event_valid(event) or event.get('context_id')!=self.a.context_id
            or event.get('config_digest')!=digest(self.monitor_cfg)):
            raise GuardError('actual monitor snapshot context/config/digest mismatch')
        if name=='latest.json' and event['index']<self.monitor_last_index:raise GuardError('monitor state went backwards')
        if self.monitor_protection is None:raise GuardError('monitor protection missing before workload')
        protection=self.monitor_protection.to_dict()
        oom_witness.validate_protection_receipt(protection,context_id=self.a.context_id,config_digest=digest(self.monitor_cfg),
            runtime_digest=self.monitor_runtime.binding_digest,contract_digest=self.monitor_runtime.oom_contract_digest,
            monitor_identity=self.monitor_identity,monitor_pid=self.monitor_proc.pid)
        if event.get('oom_protection_digest')!=protection['digest']:raise GuardError('monitor event protection join failed')
        # Terminal records may outlive /proc entries; natural exit and joined
        # terminal evidence are checked by settle/close, not a forged live read.
        if event['kind'] not in ('exhausted_drained','stopped'):
            exited=self.monitor_proc.poll() is not None
            if not exited:
                try:self.monitor_protection.verify_live()
                except oom_witness.MonitorExited:exited=True
            if exited:
                # The initial poll can observe exit after latest was read, just
                # as live readback can. Both require one fresh durable terminal
                # joined to actual natural return0, never a guessed live PID.
                terminal=json.loads(_read(Path(self.monitor_cfg['capture_root'])/'latest.json',65536))
                terminal=oom_witness.resolve_terminal_event(event,terminal,returncode=self.monitor_proc.poll(),protection_digest=protection['digest'])
                if name=='latest.json':event=terminal
        return event

    def _remember_error(self,where,exc):
        error={'where':where,'type':type(exc).__name__,'message':str(exc)}
        self.closure_errors.append(error)
        if self.aggregate_failure is None:self.aggregate_failure=error
        return error

    def _raise_native_exhaustion(self,event):
        if not monitor_exhaustion_valid(event):raise GuardError('invalid native exhaustion record')
        self.original_exhaustion_event=event
        bad=event['body']['violation']
        if bad['dimension']=='aggregate_memory_oom':
            used=bad['events'].get('oom',0)+bad['events'].get('oom_kill',0)
            self.ledger.violation={'dimension':'aggregate_memory_oom_events','used':used,'cap':0}
            raise BudgetExceeded('aggregate_memory_oom_events',used,0)
        self.ledger.violation=dict(bad)
        raise BudgetExceeded(bad['dimension'],bad['used'],bad['cap'])

    def _meter(self):
        self._aggregate_owned()
        try:
            event=self._monitor_event();body=event['body']
            if event['kind'] in ('violation','exhausted_drained'):
                original=event if event['kind']=='violation' else self._monitor_event('original-exhaustion.json')
                # Remember the original before ledger accounting can raise.
                if not monitor_exhaustion_valid(original):raise GuardError('invalid original monitor exhaustion')
                self.original_exhaustion_event=original
            if event['kind'] in ('original_failure','cleanup_failure'):raise GuardError('original monitor failure retained')
            obs=body.get('observation',body)
            if event['index']>self.monitor_last_index:
                self.monitor_last_index=event['index'];self.monitor_latest=obs
                self.ledger.observe(monotonic_ns=obs['monotonic_ns'],total_cpu_ns=obs['total_context_cpu_ns'],
                    private_rss_bytes=obs['memory_peak_bytes'],writable_bytes=obs['allocated_scratch_bytes'],
                    simultaneous_cores=16,gpu_devices=0,evidence_digest=event['digest'])
            if self.original_exhaustion_event is not None:self._raise_native_exhaustion(self.original_exhaustion_event)
            if self.monitor_proc is None or self.monitor_proc.poll() is not None:raise GuardError('aggregate monitor died; context cannot continue')
            if time.monotonic_ns()-obs['monotonic_ns']>1000000000:raise GuardError('qualified native monitor heartbeat exceeded1second')
            return {'monotonic_ns':obs['monotonic_ns'],'cpu_ns':obs['total_context_cpu_ns'],
                'memory_events':obs['memory_events'],'populated':_kv(_read(self.cg/'cgroup.events'))['populated'],
                'aggregate_observation':obs,'actual_meter_digest':event['digest']}
        except BudgetExceeded:
            self.state='exhausted'
            # The monitor remains alive to persist its actual drain record.
            # Guard-side cleanup failure must not replace the original violation.
            for path,identity in ((self.cg,self.identity),(self.broker,self.broker_identity)):
                try:self._kill_group(path,identity)
                except BaseException as cleanup:self._remember_error('exhaustion_owned_drain',cleanup)
            raise
        except BaseException as exc:
            self._remember_error('aggregate_meter',exc);self.state='exhausted'
            try:self._kill_group(self.aggregate,self.aggregate_identity)
            except BaseException as cleanup:self._remember_error('meter_failure_owned_kill',cleanup)
            raise

    def _require_drained_leaves(self):
        self._broker_owned()
        for path,identity in ((self.cg,self.identity),(self.broker,self.broker_identity)):
            st=path.lstat()
            if path.is_symlink() or (st.st_dev,st.st_ino)!=identity:raise GuardError('owned leaf custody changed')
            if _kv(_read(path/'cgroup.events'))['populated']!=0:raise GuardError('actual candidate/broker descendants remain')

    def exhaustion_pending(self):
        """Read actual current evidence; never infer exhaustion from error strings."""
        if self.aggregate_failure or self.closure_errors:raise GuardError('original aggregate infrastructure failure')
        if self.monitor_cfg is None:return False
        event=self._monitor_event()
        if event['kind'] in ('violation','exhausted_drained'):
            original=event if event['kind']=='violation' else self._monitor_event('original-exhaustion.json')
            if not monitor_exhaustion_valid(original):raise GuardError('native exhaustion evidence invalid')
            return True
        if event['kind'] not in ('ready','observation'):raise GuardError('monitor failure/closure is not candidate exhaustion')
        return any(ledger_exhaustion_valid(v,self.a.context_id) and v['values']==self.ledger.violation
                   for v in self.ledger.events)

    def settle_exhaustion(self):
        """Real source path only: durable original evidence, usage, and owned drain."""
        if self.aggregate_failure or self.closure_errors or self.resource_reclassifications:raise GuardError('infrastructure incident blocks exhaustion closure')
        if self.monitor_proc is None:raise GuardError('missing actual monitor')
        if any(v['status']=='reserved' for v in self.ledger.provider_requests.values()):raise GuardError('unresolved usage blocks settled exhaustion')
        event=self._monitor_event()
        native=event['kind'] in ('violation','exhausted_drained')
        if native:
            original=event if event['kind']=='violation' else self._monitor_event('original-exhaustion.json')
            if not monitor_exhaustion_valid(original):raise GuardError('missing genuine native violation')
            self.original_exhaustion_event=original
            # No signal to monitor: it must complete its own durable drain naturally.
            self.monitor_proc.wait(timeout=10)
            terminal=self._monitor_event()
            if (self.monitor_proc.returncode!=0 or terminal['kind']!='exhausted_drained'
                or terminal['body'].get('violation_digest')!=original['digest']
                or terminal['body'].get('candidate_populated')!=0 or terminal['body'].get('broker_populated')!=0):
                raise GuardError('native exhausted monitor did not complete qualified drain')
            source={'kind':'native_monitor','original_event':original,'terminal_event':terminal}
        else:
            if event['kind'] not in ('ready','observation'):raise GuardError('monitor failure cannot become ledger exhaustion')
            allowed={'model_calls','input_tokens','output_tokens','output_tokens_reserved','tool_calls'}
            violation=self.ledger.violation
            if not valid_violation(violation) or violation['dimension'] not in allowed:raise GuardError('no selected, settled ledger exhaustion')
            events=[v for v in self.ledger.events if ledger_exhaustion_valid(v,self.a.context_id) and v['values']==violation]
            if not events:raise GuardError('original ledger violation event missing')
            self._meter()  # Actual fresh healthy monitoring, not an arithmetic substitute.
            source={'kind':'trusted_ledger','original_event':events[-1],'monitor_event':event}
        for path,identity in ((self.cg,self.identity),(self.broker,self.broker_identity)):self._kill_group(path,identity)
        self._require_drained_leaves()
        token=ExhaustionEvidence(_SEAL)
        body={'schema':'n073_actual_settled_exhaustion_v2','context_id':self.a.context_id,
            'aggregate_identity':list(self.aggregate_identity),'source':source,'candidate_populated':0,'broker_populated':0,
            'settled_provider_requests_digest':digest(self.ledger.provider_requests)}
        body['digest']=digest(body);_EXHAUSTIONS[token]={'guard':self,'body':body}
        self.exhaustion_evidence=token;self.state='exhausted';return token

    def issue_broker_lease(self,provider_admission,provider_state,provider_authority):
        self._authorize(self.authority,'candidate_author')
        if not isinstance(provider_admission,AdapterAdmission) or not isinstance(provider_state,ContextState):raise GuardError('typed provider state/admission required')
        provider_admission.validate();provider_state.allow_model_call()
        if not isinstance(provider_authority,VerifiedAuthority):raise GuardError('actual provider authority required')
        provider_authority.require(role='candidate_query' if provider_state.state=='query_open' else 'candidate_author',domain='authentic',bindings={
            'context_digest':provider_state.context.binding_digest,'provider_admission_digest':provider_admission.binding_digest,
            'caps_digest':self.ledger.caps.binding_digest})
        if (self.broker_lease is not None or provider_admission.context_id!=self.a.context_id
            or provider_state.context.context_id!=self.a.context_id
            or provider_state.context.arm!=self.a.arm or self.state not in ('prequery','query')
            or provider_admission.capture_directory!=str(self.root/'capture'/'broker-v2')):
            raise GuardError('one broker, same exact context and private bounded scratch required')
        self._broker_owned();self._meter()
        if _kv(_read(self.broker/'cgroup.events'))['populated']:raise GuardError('new broker leaf is not empty')
        lease=BrokerLease(_SEAL)
        _LEASES[lease]={'guard':self,'admission':provider_admission,'admission_digest':provider_admission.binding_digest,
            'spawned':False,'closed':False,'process':None}
        self.broker_lease=lease;return lease

    def freeze_barrier(self,*,authority,broker_closure=None):
        if self.a.arm=='F':
            record=_CLOSURES.get(broker_closure) if isinstance(broker_closure,BrokerClosure) else None
            if record is None or record['guard'] is not self or broker_closure is not self.broker_closure:
                raise GuardError('F freeze requires registered actual broker closure')
            self._broker_owned()
            if _kv(_read(self.broker/'cgroup.events'))['populated']:raise GuardError('F broker remains alive')
        # Base V2 candidate-only barrier binds self.cg to candidate leaf. I broker
        # and the continuous monitor remain alive under the aggregate budget.
        return super().freeze_barrier(authority=authority)

    def run(self,*,authority,phase,mounts,argv,request_id):
        self._authorize(authority,'candidate_author' if phase=='prequery' else 'candidate_query')
        require_single_native_supervisor()
        start_receipts=len(self.receipts)
        try:
            result=super().run(authority=authority,phase=phase,mounts=mounts,argv=argv,request_id=request_id)
        except BaseException as exc:
            if len(self.receipts)>start_receipts:
                corrected=self._classify_capacity(self.receipts[-1])
                if corrected is not None:raise GuardError('infrastructure scratch capacity failure; original receipt retained') from exc
            raise
        correction=self._classify_capacity(result)
        if correction is not None:
            result={**result,'resource_reclassification':correction,'qualification_invalid':True,
                'original_receipt_digest':result['receipt_digest']}
            result['receipt_digest']=digest({k:v for k,v in result.items() if k!='receipt_digest'})
        return classify_process(result,context_id=self.a.context_id)

    def _classify_capacity(self,original):
        if original.get('termination')!='candidate_scratch_exhaustion':return None
        fs=os.statvfs(self.a.scratch_mount);used=(fs.f_blocks-fs.f_bfree)*fs.f_frsize
        if used>=self.ledger.caps.writable_bytes:return None
        correction={'original_receipt_digest':original['receipt_digest'],
            'original_termination':original['termination'],'observed_allocated_bytes':used,
            'selected_writable_ceiling':self.ledger.caps.writable_bytes,
            'classification':'infrastructure_capacity_failure',
            'reason':'ENOSPC/EDQUOT before independently observed selected ceiling is not candidate exhaustion'}
        self.resource_reclassifications.append(correction);self.aggregate_failure=correction
        return correction

    def close(self,*,authority):
        self._authorize(authority,'close')
        if self.aggregate_closed:raise GuardError('aggregate closure is single-use')
        self.aggregate_closed=True
        for path,identity in ((self.cg,self.identity),(self.broker,self.broker_identity)):
            try:self._kill_group(path,identity)
            except BaseException as exc:self._remember_error('close_work_drain',exc)
        terminal=None;monitor_stop='missing'
        if self.monitor_proc is not None:
            try:
                event=self._monitor_event()
                if event['kind'] in ('violation','exhausted_drained'):
                    self.monitor_proc.wait(timeout=10)
                    self.original_exhaustion_event=self._monitor_event('original-exhaustion.json')
                    monitor_stop='exhaustion_completed'
                elif self.monitor_proc.poll() is None:
                    self.monitor_socket.sendall(b'STOP\n');self.monitor_proc.wait(timeout=10);monitor_stop='requested'
                else:monitor_stop='unexpected_already_exited'
                terminal=self._monitor_event()
                if terminal['kind']=='exhausted_drained' and self.monitor_proc.returncode==0:
                    self.original_exhaustion_event=self._monitor_event('original-exhaustion.json')
                    monitor_stop='exhaustion_completed'
            except BaseException as exc:
                self._remember_error('monitor_close',exc);monitor_stop='forced_owned_termination'
                try:self._kill_group(self.monitor_group,self.monitor_identity);self.monitor_proc.wait(timeout=10)
                except BaseException as cleanup:self._remember_error('monitor_forced_cleanup',cleanup)
        try:self._kill_group(self.aggregate,self.aggregate_identity)
        except BaseException as exc:self._remember_error('aggregate_final_drain',exc)
        final=None;final_meter_error=None;populated=None
        try:
            final=monitor_v3.observe(self.monitor_cfg);populated=final['populated']
            final['total_context_cpu_ns']=max(final['total_context_cpu_ns'],self.ledger.cpu_ns)
            self.ledger.observe(monotonic_ns=final['monotonic_ns'],total_cpu_ns=final['total_context_cpu_ns'],
                private_rss_bytes=final['memory_peak_bytes'],writable_bytes=final['allocated_scratch_bytes'],
                simultaneous_cores=16,gpu_devices=0,evidence_digest=digest(final))
        except BudgetExceeded as exc:final_meter_error={'type':type(exc).__name__,'message':str(exc)}
        except BaseException as exc:
            final_meter_error=self._remember_error('final_meter',exc)
        invalid=[classify_process(r,context_id=self.a.context_id).to_dict() for r in self.receipts
                 if classify_process(r,context_id=self.a.context_id).classification=='infrastructure_invalid']
        for path,identity in ((self.cg,self.identity),(self.broker,self.broker_identity),(self.monitor_group,self.monitor_identity),(self.aggregate,self.aggregate_identity)):
            try:
                st=path.lstat()
                if (st.st_dev,st.st_ino)!=identity:raise GuardError('changed directory cannot be removed')
                path.rmdir()
            except BaseException as exc:self._remember_error('owned_group_removal',exc)
        if self.monitor_socket is not None:
            try:self.monitor_socket.close()
            except BaseException as exc:self._remember_error('monitor_control_close',exc)
        protection=None if self.monitor_protection is None else self.monitor_protection.to_dict()
        if self.monitor_protection is not None:
            try:self.monitor_protection.close()
            except BaseException as exc:self._remember_error('protection_descriptor_close',exc)
        receipt={'schema':'n073_actual_aggregate_close_v3','context_id':self.a.context_id,'final_observation':final,
            'monitor_returncode':None if self.monitor_proc is None else self.monitor_proc.returncode,
            'monitor_stop':monitor_stop,'monitor_terminal_event':terminal,'original_exhaustion_event':self.original_exhaustion_event,
            'oom_protection_receipt':protection,'oom_contract_digest':self.monitor_runtime.oom_contract_digest,
            'monitor_config_digest':None if self.monitor_cfg is None else digest(self.monitor_cfg),
            'monitor_runtime_digest':self.monitor_runtime.binding_digest,'monitor_identity':None if self.monitor_identity is None else list(self.monitor_identity),
            'monitor_pid':None if self.monitor_proc is None else self.monitor_proc.pid,
            'resource_violation':self.ledger.violation,'populated':populated,'closure_errors':self.closure_errors,
            'aggregate_failure':self.aggregate_failure,'final_meter_error':final_meter_error,
            'resource_reclassifications':self.resource_reclassifications,'process_invalid_outcomes':invalid,
            'unresolved_provider_usage':[k for k,v in self.ledger.provider_requests.items() if v['status']=='reserved'],
            'broker_expected':self.broker_lease is not None,
            'broker_closure':None if self.broker_closure is None else self.broker_closure.to_dict(),
            'candidate_original_outcomes_digest':digest(self.receipts),'scratch_retained':str(self.root),
            'counter_semantics':'aggregate native counters plus guardian proc-tick upper bound; memory total resident/cache peak'}
        receipt['receipt_digest']=digest(receipt)
        self.closed=True;self.state='closed'
        return classify_aggregate(receipt,context_id=self.a.context_id)
