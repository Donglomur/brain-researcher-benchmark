"""Future qualified Linux enforcement. Nothing executes on import.

All filesystem/process methods require authentic signed authority first. This
source does not qualify bwrap, kernel, exports or the dedicated storage provider.
"""
from dataclasses import asdict
import ctypes
import errno
import hashlib
import json
import os
from pathlib import Path
import resource
import selectors
import stat
import subprocess
import sys
import threading
import time

from ..core.custody import VerifiedAuthority,digest,require_digest
from ..core import oom_witness
from ..core.resources import CandidateCaps,ResourceLedger,BudgetExceeded
from .contracts import GuardError,GuardAdmission,assemble_argv,cgroup_limits,validate_mounts


def _read(path, limit=1048576):
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC)
    try:
        chunks=[]; remaining=limit+1
        while remaining:
            b=os.read(fd,min(65536,remaining))
            if not b: break
            chunks.append(b);remaining-=len(b)
        data=b''.join(chunks)
        if len(data)>limit: raise GuardError('bounded control read overflow')
        return data.decode('utf-8')
    finally: os.close(fd)


def _write(path,value):
    fd=os.open(path,os.O_WRONLY|os.O_NOFOLLOW|os.O_CLOEXEC)
    try:
        payload=(value+'\n').encode('ascii')
        if os.write(fd,payload)!=len(payload): raise GuardError('short cgroup write')
    finally: os.close(fd)


def _kv(text):
    result={}
    for line in text.splitlines():
        parts=line.split()
        if len(parts)!=2 or parts[0] in result: raise GuardError('invalid kernel counter schema')
        try: value=int(parts[1])
        except ValueError: raise GuardError('invalid kernel counter value') from None
        if value<0: raise GuardError('negative kernel counter')
        result[parts[0]]=value
    return result


def _unescape_mount(value):
    for key,val in (('\\040',' '),('\\011','\t'),('\\012','\n'),('\\134','\\')):
        value=value.replace(key,val)
    return value


def parse_mountinfo(text):
    """Pure kernel-text decoder, not a filesystem readiness certificate."""
    entries=[]
    for line in text.splitlines():
        fields=line.split(); split=fields.index('-')
        if split<6 or len(fields)<split+4: raise GuardError('invalid mountinfo record')
        entries.append({'id':int(fields[0]),'device':fields[2],'root':_unescape_mount(fields[3]),
            'path':_unescape_mount(fields[4]),'options':fields[5].split(','),
            'fstype':fields[split+1],'source':_unescape_mount(fields[split+2]),
            'super_options':fields[split+3].split(',')})
    return entries


def parse_cpuset(value):
    cpus=[]
    for item in value.strip().split(','):
        parts=item.split('-')
        if len(parts)==1:cpus.append(int(parts[0]))
        elif len(parts)==2:
            lo,hi=map(int,parts)
            if lo>hi or hi-lo>65536:raise GuardError('invalid bounded cpuset range')
            cpus.extend(range(lo,hi+1))
        else:raise GuardError('invalid cpuset')
    if any(x<0 for x in cpus) or len(cpus)!=len(set(cpus)):raise GuardError('duplicate/negative CPU')
    return tuple(sorted(cpus))


def _no_symlink_path(path):
    p=Path(path)
    if str(p.resolve(strict=True))!=str(p): raise GuardError('symlink or noncanonical host binding')
    return p


def _file_pin(path,size,sha,mode=None):
    p=_no_symlink_path(path);st=p.stat()
    if not stat.S_ISREG(st.st_mode) or st.st_size!=size or st.st_mode & (stat.S_ISUID|stat.S_ISGID|0o022):
        raise GuardError('pinned regular file identity/mode failed')
    if mode is not None and stat.S_IMODE(st.st_mode)!=mode: raise GuardError('source mode mismatch')
    fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC)
    try:
        before=os.fstat(fd);h=hashlib.sha256();n=0
        while True:
            b=os.read(fd,min(1048576,size+1-n))
            if not b: break
            n+=len(b);h.update(b)
            if n>size: raise GuardError('pinned file grew')
        after=os.fstat(fd)
        if (n!=size or h.hexdigest()!=sha or (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)!=
            (after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns)):
            raise GuardError('pinned file content changed')
    finally:os.close(fd)


def _tree_pin(root,members,mounts):
    root=_no_symlink_path(root)
    covering=[m for m in mounts if str(root)==m['path'] or str(root).startswith(m['path'].rstrip('/')+'/')]
    if not covering: raise GuardError('source tree has no qualified mount')
    parent=max(covering,key=lambda m:len(m['path']))
    if 'ro' not in parent['options']: raise GuardError('immutable source backing mount required')
    if any(m['path'].startswith(str(root)+'/') for m in mounts):
        raise GuardError('nested source mounts require a new explicit tree contract')
    expected={m.path:m for m in members};seen=set()
    # Traverse only the expressly authorized tree, admitting no extra file or type.
    for base,dirs,files in os.walk(root,followlinks=False):
        for name in dirs:
            p=Path(base)/name
            if p.is_symlink() or not stat.S_ISDIR(p.lstat().st_mode): raise GuardError('source directory type')
        for name in files:
            p=Path(base)/name;relative=p.relative_to(root).as_posix()
            if relative not in expected: raise GuardError('unlisted member in public/runtime tree')
            pin=expected[relative];_file_pin(p,pin.bytes,pin.sha256,pin.mode);seen.add(relative)
    if seen!=set(expected): raise GuardError('missing immutable source member')


class GuardContext:
    """One owned cgroup and one whole-context ledger, across both phases.

    No reset/retry of authority or budgets. Native activation requires independently
    qualified signed environment evidence, and refuses on current BUILD ONLY Mac.
    """
    def __init__(self,admission,*,authority,ledger):
        if not isinstance(admission,GuardAdmission): raise GuardError('typed guard admission required')
        admission.validate()
        if not isinstance(authority,VerifiedAuthority): raise GuardError('verified authentic authority required before effects')
        if not isinstance(ledger,ResourceLedger) or ledger.context_id!=admission.context_id:
            raise GuardError('same-context existing resource ledger required')
        self.a=admission;self.ledger=ledger;self.authority=authority
        self.bindings={'context_digest':digest(admission.context_id),'caps_digest':CandidateCaps().binding_digest,
            'guard_admission_digest':admission.binding_digest,'environment_evidence_digest':admission.environment_evidence_digest,
            'control_source_digest':admission.control_source_digest}
        authority.require(role='candidate_author',domain='authentic',bindings=self.bindings)
        if sys.platform!='linux': raise GuardError('Linux bwrap/cgroup-v2 qualification required; unsupported platform')
        self.state='authenticated';self.cg=None;self.root=None;self.identity=None;self.run_number=0
        self.receipts=[];self.freeze_receipt=None;self.closed=False
        self.initial_cpu_ns=ledger.cpu_ns;self.host_cpu_start=time.process_time_ns()

    def _authorize(self,authority,role,extra=None):
        if not isinstance(authority,VerifiedAuthority): raise GuardError('verified authority required')
        authority.require(role=role,domain='authentic',bindings={**self.bindings,**(extra or {})})
        if sys.platform!='linux' or self.closed: raise GuardError('unsupported/closed guard')

    def _owned(self):
        if self.cg is None or self.identity is None: raise GuardError('owned cgroup not prepared')
        st=self.cg.lstat()
        if (st.st_dev,st.st_ino)!=self.identity or self.cg.is_symlink():
            raise GuardError('owned cgroup identity changed; no unrelated kill permitted')

    def prepare(self):
        self._authorize(self.authority,'candidate_author')
        if self.state!='authenticated': raise GuardError('prepare is single-use')
        self.ledger._open()
        if not set(os.sched_getaffinity(0)) <= set(self.a.cpus):
            raise GuardError('dedicated supervisor must already share the admitted16-CPU affinity')
        mounts=parse_mountinfo(_read('/proc/self/mountinfo'))
        scratch=[m for m in mounts if m['path']==self.a.scratch_mount]
        if len(scratch)!=1: raise GuardError('exact independently admitted scratch mount required')
        sm=scratch[0]
        if (sm['id']!=self.a.scratch_mount_id or sm['device']!=self.a.scratch_device or sm['root']!='/'
            or sm['fstype'] not in ('ext4','xfs','tmpfs') or 'rw' not in sm['options']
            or sum(m['device']==sm['device'] for m in mounts)!=1):
            raise GuardError('scratch dedicated mount/exclusivity binding mismatch')
        _no_symlink_path(self.a.scratch_mount)
        fs=os.statvfs(self.a.scratch_mount)
        if fs.f_blocks*fs.f_frsize!=self.a.scratch_capacity_bytes:
            raise GuardError('hard filesystem capacity differs from admitted bound')
        # This checks total dedicated capacity, not ordinary available free space.
        if any(Path(self.a.scratch_mount).iterdir()):
            raise GuardError('scratch must be dedicated empty provisioned filesystem')
        cg_mount=[m for m in mounts if m['id']==self.a.cgroup_parent_mount_id and m['fstype']=='cgroup2'
            and (self.a.cgroup_parent==m['path'] or self.a.cgroup_parent.startswith(m['path'].rstrip('/')+'/'))]
        if len(cg_mount)!=1: raise GuardError('admitted cgroup-v2 mount missing')
        parent=_no_symlink_path(self.a.cgroup_parent)
        if not {'cpu','cpuset','memory'}<=set(_read(parent/'cgroup.subtree_control').split()):
            raise GuardError('delegated parent controllers must already be enabled')
        _file_pin(self.a.bwrap_path,self.a.bwrap_bytes,self.a.bwrap_sha256)
        _tree_pin(self.a.runtime_root,self.a.runtime_members,mounts)
        for mount in self.a.initial_phase_mounts:_tree_pin(mount.source,mount.members,mounts)
        name='n073-'+digest(self.a.context_id)[:32]
        self.cg=parent/name
        self.cg.mkdir(mode=0o700) # Exclusive; an existing group is never adopted.
        st=self.cg.lstat();self.identity=(st.st_dev,st.st_ino)
        self.root=Path(self.a.scratch_mount)/name
        try:
            for key,value in cgroup_limits(self.a).items():_write(self.cg/key,value)
            if parse_cpuset(_read(self.cg/'cpuset.cpus.effective'))!=self.a.cpus:
                raise GuardError('actual16-CPU assignment differs from admitted binding')
            for key in ('cpu.max','memory.max','memory.swap.max','memory.oom.group'):
                if _read(self.cg/key).strip()!=cgroup_limits(self.a)[key]:
                    raise GuardError('kernel cgroup ceiling readback differs')
            if 'populated' not in _kv(_read(self.cg/'cgroup.events')) or not (self.cg/'cgroup.kill').exists():
                raise GuardError('required owned-group termination interface absent')
            if int(_read(self.cg/'cpu.stat').split('usage_usec ',1)[1].split()[0])!=0:
                raise GuardError('new owned cgroup unexpectedly has prior CPU usage')
            self.root.mkdir(mode=0o700)
            for d in ('work','tmp','capture'):(self.root/d).mkdir(mode=0o700)
            self.state='prequery'
            return {'state':self.state,'guard_admission_digest':self.a.binding_digest,
                'cgroup_identity':list(self.identity),'scratch_capacity':self.a.scratch_capacity_bytes,
                'enforcement':'memory.max conservatively bounds total cgroup resident/cache, not an exact private-RSS meter'}
        except BaseException:
            self.state='prepare_failed'
            raise

    def _meter(self):
        self._owned()
        cpu=_kv(_read(self.cg/'cpu.stat'));events=_kv(_read(self.cg/'memory.events'))
        rss=int(_read(self.cg/'memory.current').strip())
        fs=os.statvfs(self.a.scratch_mount)
        used=(fs.f_blocks-fs.f_bfree)*fs.f_frsize
        host_cpu=time.process_time_ns()-self.host_cpu_start
        record={'monotonic_ns':time.monotonic_ns(),'cpu_ns':self.initial_cpu_ns+cpu['usage_usec']*1000+host_cpu,
            'owned_cgroup_cpu_ns':cpu['usage_usec']*1000,'trusted_supervisor_process_cpu_ns':host_cpu,
            'cgroup_memory_current_bytes':rss,'dedicated_filesystem_allocated_bytes':used,
            'memory_events':events,'populated':_kv(_read(self.cg/'cgroup.events'))['populated']}
        self.ledger.observe(monotonic_ns=record['monotonic_ns'],total_cpu_ns=record['cpu_ns'],
            private_rss_bytes=rss,writable_bytes=used,simultaneous_cores=16,gpu_devices=0,evidence_digest=digest(record))
        return record

    def _kill_owned(self):
        self._owned();_write(self.cg/'cgroup.kill','1')
        deadline=time.monotonic()+10
        while _kv(_read(self.cg/'cgroup.events'))['populated']:
            if time.monotonic()>deadline:raise GuardError('owned tree did not drain; freeze/closure forbidden')
            time.sleep(.01)

    def run(self,*,authority,phase,mounts,argv,request_id):
        role='candidate_author' if phase=='prequery' else 'candidate_query'
        extra={'phase_mounts_digest':digest([asdict(m) for m in mounts]),'argv_digest':digest(list(argv))}
        if phase=='query':
            if not self.freeze_receipt:raise GuardError('query requires prequery process freeze barrier')
            extra['freeze_barrier_digest']=self.freeze_receipt['receipt_digest']
        self._authorize(authority,role,extra)
        if self.state!=phase:raise GuardError('invalid phase transition')
        if threading.current_thread() is not threading.main_thread() or threading.active_count()!=1:
            raise GuardError('single-threaded trusted launcher required for safe preexec attachment')
        validate_mounts(mounts,phase=phase,arm=self.a.arm)
        oom_witness.eligible_supervisor()
        self._meter();self.ledger._open()
        actual_mounts=parse_mountinfo(_read('/proc/self/mountinfo'))
        _file_pin(self.a.bwrap_path,self.a.bwrap_bytes,self.a.bwrap_sha256)
        for mount in mounts:_tree_pin(mount.source,mount.members,actual_mounts)
        for d in ('work','tmp','capture'):_no_symlink_path(self.root/d)
        command=assemble_argv(self.a,mounts,phase=phase,candidate_argv=argv,work_directory=str(self.root/'work'))
        self.ledger.begin_tool(request_id,tool='source_owned_bwrap_process',input_digest=digest(command))
        self.run_number+=1
        capture=self.root/'capture'; paths=[capture/f'{self.run_number:06d}.{name}' for name in ('stdout','stderr')]
        files=[];proc=None;sel=selectors.DefaultSelector();termination='natural';counts={'stdout':0,'stderr':0}
        last=None;failure=None;capture_complete=True
        try:
            files=[open(p,'xb',buffering=0) for p in paths]
            owned_procs=str(self.cg/'cgroup.procs')
            def attach_before_exec():
                # Trusted attachment runs before exec(bwrap), hence before ANY
                # candidate instruction; descendants inherit this cgroup.
                fd=os.open(owned_procs,os.O_WRONLY|os.O_NOFOLLOW|os.O_CLOEXEC)
                try:
                    value=str(os.getpid()).encode('ascii')
                    if os.write(fd,value)!=len(value):raise GuardError('short candidate cgroup attachment')
                finally:os.close(fd)
                oom_witness.payload_before_exec()
                resource.setrlimit(resource.RLIMIT_CORE,(0,0))
                resource.setrlimit(resource.RLIMIT_FSIZE,(CandidateCaps().writable_bytes,CandidateCaps().writable_bytes))
                if ctypes.CDLL(None,use_errno=True).prctl(38,1,0,0,0)!=0: # PR_SET_NO_NEW_PRIVS
                    raise GuardError('candidate no_new_privs readied launch failed')
            proc=subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                shell=False,close_fds=True,start_new_session=True,preexec_fn=attach_before_exec,
                cwd='/',env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8'})
            for stream,name,target in zip((proc.stdout,proc.stderr),('stdout','stderr'),files):
                os.set_blocking(stream.fileno(),False);sel.register(stream,selectors.EVENT_READ,(name,target))
            killed=False
            while sel.get_map() or proc.poll() is None:
                try:
                    last=self._meter()
                    if last['memory_events'].get('oom',0) or last['memory_events'].get('oom_kill',0):
                        termination='candidate_memory_exhaustion';self.state='exhausted';self._kill_owned();killed=True
                except BudgetExceeded as exc:
                    termination='candidate_budget_exhaustion';self.state='exhausted';failure=str(exc);self._kill_owned();killed=True
                if proc.poll() is not None and not killed:
                    # Detached descendants may not retain pipes or escape phase closure.
                    self._kill_owned();killed=True
                for key,_ in sel.select(.05):
                    name,target=key.data
                    block=os.read(key.fileobj.fileno(),65536)
                    if not block:sel.unregister(key.fileobj);key.fileobj.close();continue
                    try:target.write(block)
                    except OSError as exc:
                        termination=('candidate_scratch_exhaustion' if exc.errno in (errno.ENOSPC,errno.EDQUOT)
                                     else 'infrastructure_capture_failure')
                        self.state='exhausted';failure=repr(exc);self._kill_owned();raise
                    counts[name]+=len(block)
            # Even when the last pipe closes simultaneously with leader exit,
            # no detached descendant may survive into unmonitored model waiting.
            self._kill_owned()
            returncode=proc.wait()
        except BaseException as exc:
            capture_complete=False
            failure=repr(exc)
            if termination=='natural':termination='infrastructure_or_launch_failure'
            if proc is not None:self._kill_owned();proc.wait(timeout=10)
            raise
        finally:
            sel.close()
            for f in files:
                try:os.fsync(f.fileno())
                except OSError as exc:capture_complete=False;failure=repr(exc);termination='infrastructure_capture_durability_failure'
                finally:f.close()
            if proc is not None:
                try:last=self._meter()
                except BudgetExceeded as exc:termination='candidate_budget_exhaustion';self.state='exhausted';failure=str(exc)
            receipt={'schema':'n073_process_original_outcome_v1','context_id':self.a.context_id,'phase':phase,
                'request_id':request_id,'argv':command,'returncode':None if proc is None else proc.poll(),
                'termination':termination,'failure':failure,'captures':[str(p) for p in paths],
                'capture_bytes':counts,'last_observation':last,'guard_admission_digest':self.a.binding_digest,
                'capture_complete':capture_complete,
                'sampling_interval_seconds':.05,'qualification':'future native evidence required; counters retain any termination overshoot'}
            receipt['receipt_digest']=digest(receipt);self.receipts.append(receipt)
            if self.root is not None:
                out=self.root/'capture'/f'{self.run_number:06d}.receipt.json'
                try:
                    with open(out,'x',encoding='utf-8') as f:json.dump(receipt,f,sort_keys=True,allow_nan=False);f.flush();os.fsync(f.fileno())
                except OSError as exc:
                    receipt['receipt_persistence_error']=repr(exc)
                    receipt['receipt_digest']=digest({k:v for k,v in receipt.items() if k!='receipt_digest'})
                    # The parent must preserve this in-memory original incident in
                    # trusted evaluator storage; never claim durable capture here.
        return receipt

    def freeze_barrier(self,*,authority):
        self._authorize(authority,'candidate_author')
        if self.state!='prequery':raise GuardError('freeze barrier allowed once after prequery')
        self._kill_owned();meter=self._meter()
        if meter['populated']!=0:raise GuardError('unclosed prequery processes')
        receipt={'schema':'n073_prequery_process_freeze_v1','context_id':self.a.context_id,
            'populated':0,'meter':meter,'phase_outcomes_digest':digest(self.receipts),
            'next_requirement':'parent must freeze/pin immutable F program before query authority'}
        receipt['receipt_digest']=digest(receipt);self.freeze_receipt=receipt;self.state='query'
        return receipt

    def close(self,*,authority):
        self._authorize(authority,'close')
        if self.state not in ('prequery','query','exhausted'):raise GuardError('guard cannot close incomplete preparation')
        self._kill_owned()
        try:meter=self._meter()
        except BudgetExceeded:
            meter={'violation':self.ledger.violation,'monotonic_ns':time.monotonic_ns()}
        receipt={'schema':'n073_process_guard_close_v1','context_id':self.a.context_id,'populated':0,
            'meter':meter,'original_outcomes_digest':digest(self.receipts),'scratch_retained':str(self.root),
            'provider_closure':'parent must settle provider accounting before ResourceLedger.close'}
        receipt['receipt_digest']=digest(receipt);self._owned();self.cg.rmdir();self.closed=True;self.state='closed'
        return receipt
