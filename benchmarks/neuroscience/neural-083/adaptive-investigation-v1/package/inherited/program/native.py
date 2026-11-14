"""Task-specific native lifecycle primitives; exact reviewed Docker class retained."""
import base64,hashlib,json,os,re,selectors,signal,stat,subprocess,sys,time,uuid
from pathlib import Path
IMAGE="sha256:385454f413cc6f607bc7e6bfc0246c365fe3a5d6ee8f8a9fdef47196b6141156"
LABEL="org.neurobench.neural083-program-owner"
PROFILE={k:dict(cap=100000,volume=8388608,memory=134217728,reply=400000,responses=16000000,name="predictions.json") for k in ("infer",)}
PROFILE["fit"]=dict(cap=536870912,volume=553648128,memory=4294967296,reply=715840000,responses=1000000000,name="model.bin")
MAX_READY_PROBES=16
READY_SECONDS=30
READY_TMPFS="rw,noexec,nosuid,nodev,size=4096,mode=0700,uid=65534,gid=65534"
VOLUME_OPTIONS="size=8388608,uid=65534,gid=65534,mode=0770,noexec,nosuid,nodev"
def need(ok,msg):
    if not ok:raise ValueError(msg)

def pin(raw):return {'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}

def encoded(value):return (json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()

def parse(raw):
    def pairs(rows):
        out={}
        for k,v in rows:need(k not in out,'Duplicate JSON key');out[k]=v
        return out
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda _:need(False,'Nonfinite JSON'))

def path(p):
    p=Path(p).absolute();need('..' not in p.parts and not any(x.is_symlink() for x in (p,*p.parents)),'Unlinked canonical path')
    need(not any(c in str(p) for c in ',\n\r\0'),'Unambiguous mount path');return p

# This exact helper is embedded in the three existing owner bodies, not imported.
PROC_READ_CAP = 65_536
PROC_ENTRY_CAP = 4096
PROC_STAT_CAP = 4096


def _pinned_platform(metadata_read):
    required = ('waitid', 'P_PID', 'WEXITED', 'WNOHANG', 'WNOWAIT',
                'CLD_EXITED', 'CLD_KILLED', 'CLD_DUMPED', 'waitstatus_to_exitcode')
    if (sys.platform != 'linux' or not all(hasattr(os, name) for name in required)
            or signal.getsignal(signal.SIGCHLD) != signal.SIG_DFL
            or not callable(metadata_read)):
        raise ValueError('Linux waitid/WNOWAIT, default SIGCHLD and selected metadata budget required')
    # Explicit whole grant is charged before Popen; failed/partial scans are not refunded.
    metadata_read(PROC_READ_CAP)


class _PinnedGroup:
    """Exclusive child-reaper owner. A proc snapshot is never absence proof."""
    def __init__(self, process):
        self.process = process
        self.pid = process.pid
        self.reaped = False
        self.signals_retired = False
        self.wait_ownership_lost = False
        self.terminal = None
        self.signal_events = []
        self.post_reap_probe = False
        self.scan_started = False
        self.proc_entries = self.proc_read_reserved = self.proc_read_bytes = 0
        self.proc_prefixes = []
        self.members = []
        self.errors = []

    def observe(self, deadline, block=False):
        if self.reaped or self.wait_ownership_lost:
            raise RuntimeError('original child wait ownership unavailable')
        while True:
            if time.monotonic() >= deadline:
                raise TimeoutError('original unreaped child observation cutoff')
            try:
                found = os.waitid(os.P_PID, self.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT)
            except ChildProcessError:
                self.wait_ownership_lost = True
                raise
            if found is not None:
                if (found.si_pid != self.pid or found.si_code not in
                        (os.CLD_EXITED, os.CLD_KILLED, os.CLD_DUMPED)):
                    self.wait_ownership_lost = True
                    raise RuntimeError('unexpected original waitid identity or status')
                value = found.si_status if found.si_code == os.CLD_EXITED else -found.si_status
                if self.terminal is not None and self.terminal != value:
                    self.wait_ownership_lost = True
                    raise RuntimeError('original terminal status changed while unreaped')
                self.terminal = value
                return value
            if not block:
                return None
            time.sleep(min(.01, max(0, deadline - time.monotonic())))

    def send(self, sig, deadline):
        if self.signals_retired or self.reaped or self.wait_ownership_lost:
            raise RuntimeError('group signaling permanently retired')
        # WNOWAIT checks wait ownership immediately before every destructive signal.
        self.observe(deadline)
        if os.getpgid(self.pid) != self.pid or os.getsid(self.pid) != self.pid:
            raise RuntimeError('original leader no longer owns its new session/group')
        if time.monotonic() >= deadline:
            raise TimeoutError('original group signal cutoff')
        os.killpg(self.pid, sig)
        self.signal_events.append(int(sig))

    def _stat_body(self, root_fd, name, deadline):
        directory = handle = None
        raw = bytearray()
        self.proc_prefixes.append(raw)
        first = None
        try:
            directory = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                                dir_fd=root_fd)
            handle = os.open('stat', os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                             dir_fd=directory)
            if not stat.S_ISREG(os.fstat(handle).st_mode):
                raise ValueError('ordinary proc stat metadata required')
            while len(raw) <= PROC_STAT_CAP:
                if time.monotonic() >= deadline:
                    raise TimeoutError('original proc snapshot cutoff')
                wanted = min(256, PROC_STAT_CAP + 1 - len(raw))
                if self.proc_read_reserved + wanted > PROC_READ_CAP:
                    raise ValueError('complete proc snapshot exceeds precharged metadata grant')
                self.proc_read_reserved += wanted
                part = os.read(handle, wanted)
                self.proc_read_bytes += len(part)
                if not part:
                    break
                raw.extend(part)
            if len(raw) > PROC_STAT_CAP:
                raise ValueError('proc stat metadata cap')
        except BaseException as error:
            first = error
        finally:
            for fd in (handle, directory):
                if fd is not None:
                    try:
                        os.close(fd)
                    except BaseException as error:
                        self.errors.append(error)
                        if first is None:
                            first = error
        if first is not None:
            raise first
        return bytes(raw)

    def other_members(self, deadline):
        if self.scan_started or self.reaped or self.wait_ownership_lost or self.terminal is None:
            raise RuntimeError('one unreaped-terminal proc snapshot only')
        self.scan_started = True
        root = iterator = None
        first = None
        saw_leader = False
        try:
            root = os.open('/proc', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            iterator = os.scandir(root)
            for item in iterator:
                self.proc_entries += 1
                if self.proc_entries > PROC_ENTRY_CAP or time.monotonic() >= deadline:
                    raise ValueError('bounded complete proc name inventory')
                name = item.name
                if not name.isascii() or not name.isdigit():
                    continue
                try:
                    raw = self._stat_body(root, name, deadline)
                except (FileNotFoundError, ProcessLookupError):
                    # Vanishing proc metadata is ignorable only after known closure.
                    # Keep the original first error; raw close errors remain on this owner.
                    if self.errors:
                        raise
                    # A vanished process does not prove global absence; final probe does.
                    continue
                close = raw.rfind(b')')
                opened = raw.find(b'(')
                fields = raw[close + 1:].split() if close >= 0 else []
                if opened < 1 or close <= opened or len(fields) < 20:
                    raise ValueError('complete proc stat identity')
                pid = int(raw[:opened].strip())
                pgid, session, start = int(fields[2]), int(fields[3]), int(fields[19])
                if pid != int(name):
                    raise ValueError('proc directory/stat PID mismatch')
                if pid == self.pid:
                    if pgid != self.pid or session != self.pid or fields[0] not in (b'Z', b'X'):
                        raise ValueError('original held terminal leader identity')
                    saw_leader = True
                elif pgid == self.pid:
                    self.members.append({'pid': pid, 'start_ticks': start,
                                         'state': fields[0].decode('ascii')})
            if not saw_leader:
                raise ValueError('held leader missing from complete proc view')
            self.observe(deadline)
        except BaseException as error:
            first = error
        finally:
            for resource in (iterator,):
                if resource is not None:
                    try:
                        resource.close()
                    except BaseException as error:
                        self.errors.append(error)
                        if first is None:
                            first = error
            if root is not None:
                try:
                    os.close(root)
                except BaseException as error:
                    self.errors.append(error)
                    if first is None:
                        first = error
        if first is not None:
            raise first
        return tuple(self.members)

    def reap(self, deadline):
        # No signal can ever follow this transition, even if wait fails/times out.
        self.signals_retired = True
        if self.reaped or self.wait_ownership_lost:
            raise RuntimeError('sole original child reap unavailable')
        if time.monotonic() >= deadline:
            raise TimeoutError('original sole reap cutoff')
        # Observe terminal state without reaping, then use one nonblocking real
        # waitpid. Popen.wait can conceal ECHILD as zero; do not use that shortcut.
        self.observe(deadline, block=True)
        try:
            pid, status = os.waitpid(self.pid, os.WNOHANG)
        except ChildProcessError:
            self.wait_ownership_lost = True
            raise
        if pid != self.pid:
            self.wait_ownership_lost = True
            raise RuntimeError('sole waitpid did not return the original terminal child')
        self.reaped = True
        value = os.waitstatus_to_exitcode(status)
        self.process.returncode = value
        if value != self.terminal:
            raise RuntimeError('reaped status differs from original WNOWAIT observation')
        return value

    def absent_after_reap(self):
        if not self.reaped or not self.signals_retired or self.post_reap_probe:
            raise RuntimeError('one read-only final group probe after sole reap')
        self.post_reap_probe = True
        try:
            os.killpg(self.pid, 0)
        except ProcessLookupError:
            return True
        return False  # Includes a reused PGID; never authorize another signal.

    def evidence(self):
        return {'platform': 'linux_waitid_wnowait_proc',
                'exclusive_child_reaper_required': True,
                'leader_exit_observed_unreaped': self.terminal is not None,
                'signals_retired_before_reap': self.signals_retired,
                'wait_ownership_lost': self.wait_ownership_lost,
                'final_read_only_probe_after_reap': self.post_reap_probe,
                'proc_snapshot_is_absence_proof': False,
                'proc_metadata_reserved_bytes': PROC_READ_CAP,
                'proc_read_dispatch_reserved_bytes': self.proc_read_reserved,
                'proc_metadata_actual_bytes': self.proc_read_bytes,
                'proc_directory_entries': self.proc_entries,
                'other_group_members_observed': list(self.members),
                'proc_descriptor_closure_known': not self.errors,
                'proc_cleanup_error_types': [type(error).__name__ for error in self.errors],
                'metadata_cost_scope': 'precharged_managed_proc_reads_not_OS_internal_IO'}


class CommandError(RuntimeError):pass

class Docker:
    """Streaming-capped CLI with a held Linux leader until signaling retires."""
    def __init__(self,binary,socket,*,metadata_read):
        self.prefix=[binary,'--host','unix://'+str(path(socket))];self.records=[];self.reaped=True
        self.env={k:v for k,v in os.environ.items() if k not in ('DOCKER_HOST','DOCKER_CONTEXT')}
        self.metadata_read=metadata_read;self.ownership_records=[]
        self.last_original=None;self.original_failures=[]
    def __call__(self,args,end,phase,cap=131072):
        start=time.monotonic();need(end-start>1,'Command deadline')
        p=s=group=None;bufs={'out':bytearray(),'err':bytearray()};error=None;rc=None
        original=None;cleanup_errors=[];eof={'out':False,'err':False}
        previous_reaped=self.reaped;child_reaped=False;cleanup_ok=True
        group_absent=False;survivor_observed=False;group_error=None
        self.reaped=False
        try:
            # Existing whole/query budget owns this grant; never a new allowance.
            _pinned_platform(self.metadata_read)
            p=subprocess.Popen(self.prefix+args,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=self.env,bufsize=0,start_new_session=True)
            group=_PinnedGroup(p)
            s=selectors.DefaultSelector()
            for key,f in [('out',p.stdout),('err',p.stderr)]:os.set_blocking(f.fileno(),False);s.register(f,selectors.EVENT_READ,key)
            while s.get_map():
                left=end-time.monotonic()-1;need(left>0,'Command timeout')
                for k,_ in s.select(min(.1,left)):
                    try:raw=os.read(k.fileobj.fileno(),min(65536,cap+1-sum(map(len,bufs.values()))))
                    except BlockingIOError:continue
                    if not raw:eof[k.data]=True;s.unregister(k.fileobj);continue
                    # Retain the exact consumed cap-plus-probe prefix on refusal.
                    bufs[k.data].extend(raw);need(sum(map(len,bufs.values()))<=cap,'Streaming CLI cap')
            rc=group.observe(end-1,block=True)
            need(rc==0,'Docker command failure')
            survivor_observed=bool(group.other_members(end-1))
            if survivor_observed:raise CommandError('Owned CLI group members observed with held leader')
            need(time.monotonic()<end-1,'CLI natural observation before original work cutoff')
        except BaseException as exc:
            original=exc;error=type(exc).__name__
        finally:
            # Preserve the inherited one-second reserve inside the original end.
            cleanup_end=min(end,time.monotonic()+1)
            if group is not None:
                if original is not None:
                    try:group.send(signal.SIGKILL,cleanup_end)
                    except ProcessLookupError:pass
                    except BaseException as exc:cleanup_errors.append(exc)
                try:rc=group.reap(cleanup_end);child_reaped=True
                except BaseException as exc:cleanup_errors.append(exc)
                if group.reaped:
                    try:group_absent=group.absent_after_reap()
                    except BaseException as exc:cleanup_errors.append(exc)
            elif p is not None:
                cleanup_errors.append(RuntimeError('original group owner unavailable'))
            if s is not None:
                try:s.close()
                except BaseException as exc:cleanup_errors.append(exc)
            if p is not None:
                for stream in (p.stdout,p.stderr):
                    if stream is not None:
                        try:stream.close()
                        except BaseException as exc:cleanup_errors.append(exc)
            if group is not None:
                cleanup_errors.extend(group.errors)  # Retain each original close error object.
            cleanup_in_time=time.monotonic()<cleanup_end
            cleanup_ok=child_reaped and group_absent and group is not None and not group.errors and not cleanup_errors and cleanup_in_time
            group_error=type(cleanup_errors[0]).__name__ if cleanup_errors else None
            self.reaped=previous_reaped and cleanup_ok
            self.records.append({'phase':phase,'returncode':rc,'error_type':error,'observed_retained_bytes':sum(map(len,bufs.values())),'seconds':time.monotonic()-start,'client_reaped':child_reaped,'cleanup_complete':cleanup_ok,'cleanup_before_original_cutoff':cleanup_in_time,'owned_group_absence_observed':group_absent,'leader_exited_with_group_alive':survivor_observed,'group_probe_or_cleanup_error':group_error})
            self.ownership_records.append(dict(phase=phase,ownership=None if group is None else group.evidence(),stdout_eof=eof['out'],stderr_eof=eof['err'],cleanup_error_types=[type(x).__name__ for x in cleanup_errors]))
            # Strong originals stay separate from JSON metadata and are not copied.
            self.last_original=dict(stdout=bufs['out'],stderr=bufs['err'],first=original,cleanup_errors=cleanup_errors,owner=group,record=self.records[-1])
        if original is not None:
            self.original_failures.append(self.last_original)
            original.actual_cli_original=self.last_original
            raise original
        if not cleanup_ok:
            failure=CommandError('CLI cleanup incomplete');failure.actual_cli_original=self.last_original
            self.last_original['first']=failure;self.original_failures.append(self.last_original)
            raise failure
        return bytes(bufs['out'])

class BoundedDocker(Docker):
    """Preventive per-case journal/response bound inside the existing16MB debit."""
    def __init__(self,binary,socket,kind,*,metadata_read):
        super().__init__(binary,socket,metadata_read=metadata_read);self.calls=0;self.response_reservations=0;self.profile=PROFILE[kind]
    def __call__(self,args,end,phase,cap=131072):
        need(type(cap)is int and 0<cap<=self.profile['reply'],'bounded exact CLI reply cap')
        need(self.calls<64 and self.response_reservations+cap+1<=self.profile['responses'],'whole case CLI allowance')
        self.calls+=1;self.response_reservations+=cap+1
        return super().__call__(args,end,phase,cap)

def call(d,args,end,phase,cap=131072,seconds=8):return d(args,min(end,time.monotonic()+seconds),phase,cap)

def wait_holder_ready(d,holder,end,kind=None):
    # One readiness allowance is clipped by the original phase work deadline.
    ready_end=min(end,time.monotonic()+READY_SECONDS)
    argv=['exec',holder['id'],'python','-I','-B','/trusted/holder.py','ready','--owner-token',holder['owner'],'--kind',kind]
    for probe in range(MAX_READY_PROBES):
        need(time.monotonic()<ready_end,'original holder readiness deadline')
        value=parse(call(d,argv,ready_end,'holder_ready',4096))
        need(type(value)is dict and set(value)=={'ready'} and type(value['ready'])is bool,'exact typed holder readiness')
        need(time.monotonic()<ready_end,'holder readiness returned before original deadline')
        if value['ready'] is True:return
        if probe+1<MAX_READY_PROBES:
            left=ready_end-time.monotonic();need(left>0,'original holder readiness interval')
            time.sleep(min(.05,left))
    raise ValueError('holder readiness probe limit')

def inventory(d,kind,selector,end,phase):
    fmt='{{.Name}}' if kind=='volume' else '{{.ID}}';args=[kind,'ls']+([] if kind=='volume' else ['--all','--no-trunc'])+['--filter',selector,'--format',fmt]
    rows=call(d,args,end,phase,8192).decode('ascii').splitlines()
    need(len(rows)==len(set(rows)) and len(rows)<=3,'Bounded exact inventory')
    need(all(re.fullmatch('[a-f0-9]{64}',x) if kind=='container' else re.fullmatch('neural083-[a-f0-9]{24}-volume',x) for x in rows),'Exact inventory identifiers');return rows

def inspect(d,kind,name,end,phase):
    rows=parse(call(d,[kind,'inspect',name],end,phase));need(type(rows)is list and len(rows)==1,'One inspected resource');return rows[0]

def owned(v,item,owner):
    need(v['Name']==(item['name'] if item['kind']=='volume' else '/'+item['name']),'Exact resource name')
    labels=v.get('Labels') if item['kind']=='volume' else v['Config'].get('Labels')
    need(labels is not None and labels.get(LABEL)==owner,'Exact owner label')
    if item.get('id') is not None:need(v['Id']==item['id'],'Exact returned container ID')

def resource_inventory(d,item,owner,end,prefix):
    a=inventory(d,item['kind'],'label='+LABEL+'='+owner,end,prefix+'_owner')
    # The owner is unique per resource (same panel/case suffix plus role).
    b=inventory(d,item['kind'],'name=^'+('/' if item['kind']=='container' else '')+item['name']+'$',end,prefix+'_name')
    need(a==b and len(a)<=1,'Exact owner/name join');return a

def retire(d,item,end):
    owner=item['owner'];rows=resource_inventory(d,item,owner,end,'cleanup_'+item['kind']);removed=False
    if not item.get('attempted',False):
        return {'kind':item['kind'],'name':item['name'],'create_not_attempted':True,'collision_preserved':bool(rows),'observed_namespace_empty':rows==[],'removed':False,'closed':rows==[]}
    if rows:
        value=inspect(d,item['kind'],rows[0],end,'cleanup_inspect');owned(value,item,owner)
        if item['kind']=='container' and value['State']['Running']:
            call(d,['container','kill','--signal','KILL',rows[0]],end,'cleanup_kill',4096)
            call(d,['container','wait',rows[0]],end,'cleanup_wait',4096)
        call(d,[item['kind'],'rm',rows[0]],end,'cleanup_remove',4096);removed=True
    after=resource_inventory(d,item,owner,end,'absence_'+item['kind'])
    unknown=item.get('attempted',False) and not item.get('acknowledged',False) and not removed
    return {'kind':item['kind'],'name':item['name'],'removed':removed,'absence_observed':after==[],'creation_outcome_unknown':unknown,'closed':after==[] and not unknown}

def mounts_argv(mounts):
    result=[]
    for target,(kind,source,rw) in mounts.items():
        value='type='+kind+',src='+str(source)+',dst='+target+(',volume-nocopy' if kind=='volume' else '')+('' if rw else ',readonly')
        result+=['--mount',value]
    return result

def create_args(item,role,mounts,memory,kind):
    cmd=['-I','-B','/trusted/holder.py','hold','--owner-token',item['owner'],'--kind',kind] if role=='holder' else ['-I','-B','/entry.py',str(memory),kind]
    args=['container','create','--pull','never','--name',item['name'],'--label',LABEL+'='+item['owner'],'--cpus','1','--memory',str(memory),'--memory-swap',str(memory),'--pids-limit','64','--network','none','--cgroupns','private','--ipc','private','--read-only','--user','65534:65534','--cap-drop','ALL','--security-opt','no-new-privileges','--restart','no','--log-driver','none','--shm-size','16777216','--ulimit','core=0:0','--ulimit','nofile=128:128','--ulimit','fsize=536870912:536870912']
    if role=='holder':args+=['--init=false','--tmpfs','/ready:'+READY_TMPFS]
    else:args+=['--tmpfs','/tmp:rw,nosuid,nodev,noexec,size=33554432']
    for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):args+=['--env',key+'=1']
    return args+mounts_argv(mounts)+['--entrypoint','python',IMAGE,*cmd]

def admission(value,item,role,mounts,memory,kind):
    owned(value,item,item['owner']);h=value['HostConfig'];c=value['Config']
    need(value['Image']==c['Image']==IMAGE and c['User']=='65534:65534' and c['Entrypoint']==['python'],'Exact image/user/entry')
    expected=['-I','-B','/trusted/holder.py','hold','--owner-token',item['owner'],'--kind',kind] if role=='holder' else ['-I','-B','/entry.py',str(memory),kind]
    need(c['Cmd']==expected and h['Memory']==h['MemorySwap']==memory and h['NanoCpus']==1000000000 and h['PidsLimit']==64,'Exact command/resources')
    need(h['NetworkMode']=='none' and h['ReadonlyRootfs'] is True and h['CgroupnsMode']=='private' and h['LogConfig']['Type']=='none','Isolation and no logs')
    need(h.get('Privileged') is False and not h.get('CapAdd') and not h.get('Devices') and not h.get('DeviceRequests') and h.get('PidMode') in ('','private') and h.get('IpcMode')=='private','No device or host namespace access')
    need(h['CapDrop']==['ALL'] and 'no-new-privileges' in h['SecurityOpt'] and h['RestartPolicy']['Name']=='no' and h['AutoRemove'] is False and h['ShmSize']==16777216,'No capabilities/restarts or extra shared memory')
    actual={x['Destination']:(x['Type'],x['Name'] if x['Type']=='volume' else x['Source'],x['RW']) for x in value['Mounts']}
    need(len(value['Mounts'])==len(mounts) and actual=={k:(kind,str(source),rw) for k,(kind,source,rw) in mounts.items()},'Exact mounts; no host writable candidate bind')
    need(all(not rw for kind,_,rw in mounts.values() if kind=='bind'),'All host bindings read-only')
    need(h.get('Tmpfs')=={'/ready':READY_TMPFS} if role=='holder' else h['Tmpfs']=={'/tmp':'rw,nosuid,nodev,noexec,size=33554432'},'Exact private readiness or bounded scratch')
    if role=='holder':need(h.get('Init') is False,'Holder PID1 profile disables injected init')
    limits={x['Name']:(x['Soft'],x['Hard']) for x in h['Ulimits']};need(limits=={'core':(0,0),'nofile':(128,128),'fsize':(536870912,536870912)},'Bounded file extent')

def output_reply(raw,kind):
    PRED_CAP=PROFILE[kind]["cap"]
    obj=parse(raw);need(type(obj)is dict and set(obj)=={'schema','kind','bytes','sha256','base64'} and obj['schema']=='neural083-capture-v1' and obj['kind']==kind,'Trusted capture schema')
    need(type(obj['bytes'])is int and 0<obj['bytes']<=PRED_CAP and type(obj['base64'])is str and len(obj['base64'])<=4*((PRED_CAP+2)//3),'Bounded captured output')
    body=base64.b64decode(obj['base64'],validate=True);need(pin(body)=={k:obj[k] for k in ('bytes','sha256')},'Opaque output pin');return body

def phase(s,here,current,program,model,attempt,kind,ordinal,source,budget,deadline):
    """Exact selected fit or whole-fold inference, owned closure before capture."""
    need(kind in PROFILE and (model is not None)==(kind=='infer'),'sealed model only in inference')
    prof=PROFILE[kind];seconds=s[kind+'_seconds'] if kind in ('fit','infer') else s['reference_seconds'];started=time.monotonic();end=min(deadline,started+seconds+130);work=end-35
    prefix='neural083-'+uuid.uuid4().hex[:24];d=BoundedDocker(s['docker_binary'],s['docker_socket'],kind,metadata_read=budget.read)
    items=[];closures=[];body=None;natural=None;error=None;program_pin=None;original_error=None;secondary_errors=[];closed_before_capture=False
    def publish(path,value,cap=8192):return c.save(path,c.encoded(value),cap,budget.tick,budget.write)
    def item(role,which):
        row=dict(kind=which,name=prefix+'-'+role,owner=prefix+'/'+role,attempted=False,acknowledged=False)
        publish(attempt/('INTENT-'+role+'.json'),dict(resource=row,creation_obligation_until_closed=True));items.append(row);return row
    def before(row):need(resource_inventory(d,row,row['owner'],work,'before_'+row['kind'])==[],'fresh exact resource')
    def container(row,role,mounts,memory):
        before(row);row['attempted']=True
        identity=call(d,create_args(row,role,mounts,memory,kind),work,'create_'+role,4096,12).decode().strip()
        need(re.fullmatch('[a-f0-9]{64}',identity),'exact acknowledged container');row.update(id=identity,acknowledged=True)
        admission(inspect(d,'container',identity,work,'admit_'+role),row,role,mounts,memory,kind)
    try:
        program_pin=c.pin(c.capture(program,1048576,None,budget.tick,budget.read))
        need(stat.S_ISSOCK(path(s['docker_socket']).stat().st_mode),'existing Unix Docker socket')
        image=parse(call(d,['image','inspect',IMAGE,'--format','{{json .}}'],work,'image'))
        need(image['Id']==IMAGE and not image['Config'].get('Volumes') and (not image['Config'].get('Healthcheck') or image['Config']['Healthcheck'].get('Test')==['NONE']),'fixed cached image without implicit processes/volumes')
        volume=item('volume','volume');before(volume);volume['attempted']=True
        options='size='+str(prof['volume'])+',uid=65534,gid=65534,mode=0770,noexec,nosuid,nodev'
        returned=call(d,['volume','create','--driver','local','--label',LABEL+'='+volume['owner'],'--opt','type=tmpfs','--opt','device=tmpfs','--opt','o='+options,volume['name']],work,'volume_create',4096).decode().strip()
        need(returned==volume['name'],'exact volume acknowledgment');volume['acknowledged']=True
        v=inspect(d,'volume',volume['name'],work,'volume_admit');owned(v,volume,volume['owner'])
        need(v['Driver']=='local' and v['Options']==dict(type='tmpfs',device='tmpfs',o=options),'exact selected bounded tmpfs')
        holder=item('holder','container');hm={'/trusted/holder.py':('bind',here/'holder.py',False),'/capture':('volume',volume['name'],False)}
        container(holder,'holder',hm,prof['memory']);call(d,['container','start',holder['id']],work,'holder_start',4096);wait_holder_ready(d,holder,work,kind)
        candidate=item('candidate','container')
        mounts={'/submission/program.py':('bind',program,False),'/entry.py':('bind',here/'candidate_entry.py',False),'/input':('bind',current,False),'/output':('volume',volume['name'],True)}
        if model is not None:mounts['/model/model.bin']=('bind',model,False)
        container(candidate,'candidate',mounts,s['memory_bytes'])
        need(work-time.monotonic()>seconds+1,'full selected producer interval remains')
        begin=time.monotonic();call(d,['container','start',candidate['id']],work,'candidate_start',4096)
        raw=d(['container','wait',candidate['id']],min(work,begin+seconds),'candidate_wait',4096);need(raw.strip()==b'0','natural candidate zero')
        v=inspect(d,'container',candidate['id'],work,'candidate_exit');owned(v,candidate,candidate['owner'])
        natural={k:v['State'][k] for k in ('Status','Running','Dead','Pid','ExitCode','OOMKilled')};c.validate_natural_exit(natural)
        closed=retire(d,candidate,work);closures.append(closed);need(closed['closed'],'candidate removed before output capture')
        items.remove(candidate);closed_before_capture=True
        raw=call(d,['exec',holder['id'],'python','-I','-B','/trusted/holder.py','capture','--owner-token',holder['owner'],'--kind',kind],work,'opaque_capture',prof['reply'],30)
        body=output_reply(raw,kind)
    except BaseException as exc:error=type(exc).__name__;original_error=exc
    finally:
        for row in reversed(items):
            try:closures.append(retire(d,row,end))
            except BaseException as exc:
                secondary_errors.append(exc);closures.append(dict(kind=row['kind'],name=row['name'],closed=False,error_type=type(exc).__name__))
    try:
        c.validate_cli_commands(d.records,prof['reply'])
        c.validate_process_ownership(d.ownership_records,d.records)
    except BaseException as exc:
        if error is None:error=type(exc).__name__;original_error=exc
        else:secondary_errors.append(exc)
    good=error is None and body is not None and closed_before_capture and len(closures)==3 and all(x['closed'] is True for x in closures) and d.reaped and natural is not None and time.monotonic()<end
    result=dict(image=IMAGE,producer_memory_bytes=s['memory_bytes'],producer_seconds=seconds,program=program_pin,phase_started_monotonic=started,phase_deadline=end,worker_deadline=deadline,schema='neural083-sequential-native-phase-v2',kind=kind,ordinal=ordinal,source=source,status='failed',closures=closures,all_native_resources_closed=bool(good),cli_reaped=d.reaped,natural_exit=natural,producer_closed_before_capture=closed_before_capture,error_type=error,command_metadata=d.records,process_ownership_metadata=d.ownership_records,private_scoring_called=False)
    if good:result['output']=c.save(attempt/prof['name'],body,prof['cap'],budget.tick,budget.write);result['status']='captured'
    result['elapsed_seconds']=time.monotonic()-started
    try:publish(attempt/'NATIVE.json',result,262144)
    except BaseException as exc:
        if original_error is None:original_error=exc
        else:secondary_errors.append(exc)
    if original_error is None and not (good and time.monotonic()<end):
        original_error=ValueError('complete phase deadline/closure')
    if original_error is not None:
        original_error.actual_native_transport=d
        original_error.actual_native_record=result
        original_error.native_secondary_errors=secondary_errors
        raise original_error
    return result
