"""Pinned standalone native context monitor. Import has no effects.

Executed only by the authentic aggregate guard, via inherited private descriptors.
No provider, credentials, neural values, directory discovery or foreign PID search.
"""
import hashlib
import json
import os
import select
import sys
import time


def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()


def read(path,limit=65536):
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC)
    try:
        data=os.read(fd,limit+1)
        if len(data)>limit:raise RuntimeError('bounded native counter read overflow')
        return data.decode('ascii')
    finally:os.close(fd)


def counters(text):
    result={}
    for line in text.splitlines():
        key,value=line.split()
        if key in result or not value.isdecimal():raise RuntimeError('invalid native counter')
        result[key]=int(value)
    return result


def proc_ticks(text):
    """Linux proc-stat contract requiring native qualification of its tick resolution."""
    fields=text[text.rfind(')')+2:].split()
    if len(fields)<20:raise RuntimeError('incomplete explicit guardian proc-stat')
    return int(fields[11])+int(fields[12]),int(fields[19])


def observe(cfg):
    st=os.stat(cfg['aggregate'],follow_symlinks=False)
    if [st.st_dev,st.st_ino]!=cfg['aggregate_identity']:raise RuntimeError('aggregate identity changed')
    cpu=counters(read(cfg['aggregate']+'/cpu.stat'))['usage_usec']*1000
    ticks,start=proc_ticks(read('/proc/'+str(cfg['guardian_pid'])+'/stat'))
    if start!=cfg['guardian_start_ticks'] or ticks<cfg['guardian_base_cpu_ticks']:
        raise RuntimeError('guardian identity/counters changed')
    # Two independently quantized utime/stime fields: add two tick widths as a
    # disclosed conservative upper bound, not an exact nanosecond measurement.
    guardian=((ticks-cfg['guardian_base_cpu_ticks']+2)*1000000000+cfg['clock_ticks']-1)//cfg['clock_ticks']
    fs=os.statvfs(cfg['scratch'])
    mem=counters(read(cfg['aggregate']+'/memory.events'))
    return {'monotonic_ns':time.monotonic_ns(),'aggregate_cpu_ns':cpu,
        'guardian_cpu_upper_bound_ns':guardian,'guardian_tick_ns_ceiling':(1000000000+cfg['clock_ticks']-1)//cfg['clock_ticks'],
        'total_context_cpu_ns':cfg['initial_cpu_ns']+cfg['initial_guardian_cpu_ns']+cpu+guardian,
        'memory_current_bytes':int(read(cfg['aggregate']+'/memory.current').strip()),
        'memory_peak_bytes':int(read(cfg['aggregate']+'/memory.peak').strip()),
        'allocated_scratch_bytes':(fs.f_blocks-fs.f_bfree)*fs.f_frsize,
        'memory_events':mem,'populated':counters(read(cfg['aggregate']+'/cgroup.events'))['populated']}


def violation(obs,caps,started):
    pairs=(('wall_ns',obs['monotonic_ns']-started,caps['wall_ns']),
        ('cpu_ns',obs['total_context_cpu_ns'],caps['cpu_ns']),
        ('private_rss_conservative_memory_peak',obs['memory_peak_bytes'],caps['private_rss_bytes']),
        ('writable_bytes',obs['allocated_scratch_bytes'],caps['writable_bytes']))
    for name,value,limit in pairs:
        if value>limit:return {'dimension':name,'used':value,'cap':limit}
    if obs['memory_events'].get('oom',0) or obs['memory_events'].get('oom_kill',0):
        return {'dimension':'aggregate_memory_oom','events':obs['memory_events']}
    return None


def kill_owned(cfg):
    st=os.stat(cfg['aggregate'],follow_symlinks=False)
    if [st.st_dev,st.st_ino]!=cfg['aggregate_identity']:raise RuntimeError('refuse unrelated aggregate kill')
    fd=os.open(cfg['aggregate']+'/cgroup.kill',os.O_WRONLY|os.O_NOFOLLOW|os.O_CLOEXEC)
    try:
        if os.write(fd,b'1\n')!=2:raise RuntimeError('short owned termination write')
    finally:os.close(fd)


def write_exclusive(path, data):
    """Original metadata persists or raises; no overwritten original evidence."""
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    try:
        offset=0
        while offset<len(data):
            wrote=os.write(fd,data[offset:])
            if wrote<=0:raise RuntimeError('durable monitor write made no progress')
            offset+=wrote
        os.fsync(fd)
    finally:os.close(fd)


def sync_directory(path):
    fd=os.open(path,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:os.fsync(fd)
    finally:os.close(fd)


def drain_work_leaves(cfg):
    """Keep monitor alive to persist a natural terminal record after real drain."""
    for name in ('candidate','broker'):
        path=cfg[name];identity=cfg[name+'_identity']
        st=os.stat(path,follow_symlinks=False)
        if [st.st_dev,st.st_ino]!=identity:raise RuntimeError('owned leaf identity changed')
        fd=os.open(path+'/cgroup.kill',os.O_WRONLY|os.O_NOFOLLOW|os.O_CLOEXEC)
        try:
            if os.write(fd,b'1\n')!=2:raise RuntimeError('short owned leaf termination write')
        finally:os.close(fd)
    deadline=time.monotonic()+10
    while True:
        populations={}
        for name in ('candidate','broker'):
            st=os.stat(cfg[name],follow_symlinks=False)
            if [st.st_dev,st.st_ino]!=cfg[name+'_identity']:raise RuntimeError('leaf identity changed during drain')
            populations[name+'_populated']=counters(read(cfg[name]+'/cgroup.events'))['populated']
        if all(value==0 for value in populations.values()):return populations
        if time.monotonic()>deadline:raise RuntimeError('actual owned leaves failed to drain')
        time.sleep(.01)


OOM_POLICY={'schema':'n073_monitor_oom_policy_v1','supervisor_adj':0,'monitor_adj':-1000,'payload_adj':0,
    'payload_no_new_privs':1,'payload_capability_masks':0,'monitor_forks_payloads':False,
    'memory_max_bytes':68719476736,'monitor_inside_aggregate':True,
    'sequence':'WAIT_OOM-held-proc-write-readback-durable-witness-GO-READY'}


def validate_go_receipt(cfg,receipt,expected_config_digest,go_digest):
    """Independent pure validator for the standalone -I monitor source closure."""
    if cfg.get('oom_policy')!=OOM_POLICY:raise RuntimeError('monitor-only fixed OOM policy required')
    contract=hashlib.sha256(canonical({'policy':OOM_POLICY,'evidence_digest':cfg['oom_evidence_digest']})).hexdigest()
    if contract!=cfg.get('oom_contract_digest'):raise RuntimeError('OOM evidence contract mismatch')
    actual=hashlib.sha256(canonical({k:v for k,v in receipt.items() if k!='digest'})).hexdigest()
    if receipt.get('digest')!=actual or go_digest!=actual:raise RuntimeError('private GO/witness digest mismatch')
    expected={'schema':'n073_monitor_oom_protection_v1','context_id':cfg['context_id'],'config_digest':expected_config_digest,
        'runtime_digest':cfg['monitor_runtime_digest'],'contract_digest':contract,'evidence_digest':cfg['oom_evidence_digest'],
        'monitor_leaf_identity':cfg['monitor_leaf_identity'],'supervisor_pid':cfg['guardian_pid'],
        'supervisor_start_ticks':cfg['guardian_start_ticks'],'writer_pid':cfg['guardian_pid'],
        'score_before':0,'score_after':-1000,'supervisor_adj':0,'readback_before_go':True}
    if any(type(receipt.get(k)) is not type(v) or receipt[k]!=v for k,v in expected.items()):raise RuntimeError('standalone protection policy/custody mismatch')
    for key in ('monitor_pid','monitor_start_ticks'):
        if type(receipt.get(key)) is not int or receipt[key]<=0:raise RuntimeError('actual positive monitor identity required')
    identity=receipt.get('proc_directory_identity')
    if not isinstance(identity,list) or len(identity)!=2 or any(type(v) is not int or v<0 for v in identity):raise RuntimeError('held proc directory identity missing')
    if receipt['monitor_pid']==cfg['guardian_pid']:raise RuntimeError('monitor cannot be the eligible supervisor')
    return receipt


def verify_self_protection(cfg,receipt):
    """Actual selected PID only; no broad process inventory or foreign mutation."""
    pid=os.getpid()
    if pid!=receipt['monitor_pid'] or os.getppid()!=cfg['guardian_pid']:raise RuntimeError('owned monitor process/parent mismatch')
    fd=os.open('/proc/'+str(pid),os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
    try:
        st=os.fstat(fd)
        if [st.st_dev,st.st_ino]!=receipt['proc_directory_identity']:raise RuntimeError('held monitor proc directory changed')
        def read_member(name):
            member=os.open(name,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=fd)
            try:
                data=os.read(member,65537)
                if len(data)>65536:raise RuntimeError('bounded self proc read overflow')
                return data.decode('ascii')
            finally:os.close(member)
        _,start=proc_ticks(read_member('stat'))
        if start!=receipt['monitor_start_ticks'] or int(read_member('oom_score_adj').strip())!=-1000:
            raise RuntimeError('monitor actual immunity/start readback failed')
    finally:os.close(fd)
    st=os.stat(cfg['monitor_leaf'],follow_symlinks=False)
    if [st.st_dev,st.st_ino]!=cfg['monitor_leaf_identity'] or read(cfg['monitor_leaf']+'/cgroup.procs').split()!=[str(pid)]:
        raise RuntimeError('actual monitor leaf custody changed')
    _,parent_start=proc_ticks(read('/proc/'+str(cfg['guardian_pid'])+'/stat'))
    if parent_start!=cfg['guardian_start_ticks'] or int(read('/proc/'+str(cfg['guardian_pid'])+'/oom_score_adj').strip())!=0:
        raise RuntimeError('supervisor immunity/identity changed')
    # Source is no-fork/no-exec; fail if unexpected native threads appear.
    with os.scandir('/proc/'+str(pid)+'/task') as entries:
        names=[]
        for entry in entries:
            names.append(entry.name)
            if len(names)>1:raise RuntimeError('monitor must remain a single trusted native thread')
    if names!=[str(pid)]:raise RuntimeError('monitor native task identity mismatch')


def append_control_fragment(prefix,block,expected):
    """Pure bounded stream-framing rule, used by the actual STOP receiver."""
    if not isinstance(prefix,bytes) or not isinstance(block,bytes) or not isinstance(expected,bytes) or not expected:
        raise RuntimeError('explicit bytes control frame required')
    if not block:raise RuntimeError('control EOF before complete frame')
    combined=prefix+block
    if len(combined)>len(expected) or not expected.startswith(combined):raise RuntimeError('invalid/overflow control frame')
    return combined


def receive_stop(control_fd):
    expected=b'STOP\n';command=b'';deadline=time.monotonic()+10
    while command!=expected:
        left=deadline-time.monotonic()
        if left<=0:raise RuntimeError('STOP frame deadline exceeded')
        ready,_,_=select.select([control_fd],[],[],left)
        if not ready:raise RuntimeError('STOP frame deadline exceeded')
        command=append_control_fragment(command,os.read(control_fd,len(expected)-len(command)+1),expected)
    return command


def await_protection(cfg,control_fd,expected_digest):
    if os.write(control_fd,b'WAIT_OOM\n')!=9:raise RuntimeError('short monitor protection wait message')
    deadline=time.monotonic()+10;message=b''
    while not message.endswith(b'\n'):
        left=deadline-time.monotonic()
        if left<=0:raise RuntimeError('protection GO timeout')
        ready,_,_=select.select([control_fd],[],[],left)
        if not ready:raise RuntimeError('protection GO timeout')
        block=os.read(control_fd,69-len(message))
        if not block:raise RuntimeError('protection control EOF')
        message+=block
        if len(message)>68:raise RuntimeError('protection GO frame overflow')
    if len(message)!=68 or not message.startswith(b'GO '):raise RuntimeError('invalid protection GO frame')
    go=message[3:-1].decode('ascii')
    receipt=json.loads(read(cfg['capture_root']+'/oom-protection.json',65536))
    validate_go_receipt(cfg,receipt,expected_digest,go);verify_self_protection(cfg,receipt)
    return receipt


def observe_protected(cfg,receipt):
    verify_self_protection(cfg,receipt)
    return observe(cfg)


def run(config_fd,control_fd,expected_digest):
    raw=os.read(config_fd,65537);os.close(config_fd)
    if len(raw)>65536 or hashlib.sha256(raw).hexdigest()!=expected_digest:raise RuntimeError('monitor config binding')
    cfg=json.loads(raw)
    if cfg['schema']!='n073_aggregate_monitor_config_v3' or cfg['caps']!={
        'wall_ns':172800000000000,'cpu_ns':2764800000000000,'private_rss_bytes':68719476736,'writable_bytes':549755813888}:
        raise RuntimeError('monitor exact selected caps')
    protection=await_protection(cfg,control_fd,expected_digest)
    index=0;head='0'*64;latest=cfg['capture_root']+'/latest.json';temp=cfg['capture_root']+'/latest.part'
    log=os.open(cfg['capture_root']+'/original-events.jsonl',os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    original_violation=None
    def publish(kind,body):
        nonlocal index,head
        event={'index':index,'previous':head,'kind':kind,'body':body,
               'context_id':cfg['context_id'],'config_digest':expected_digest,'oom_protection_digest':protection['digest']}
        event['digest']=hashlib.sha256(canonical(event)).hexdigest();data=canonical(event)+b'\n'
        if len(data)>65536:raise RuntimeError('bounded native monitor event exceeded65536bytes')
        offset=0
        while offset<len(data):
            wrote=os.write(log,data[offset:])
            if wrote<=0:raise RuntimeError('original monitor log write made no progress')
            offset+=wrote
        os.fsync(log)
        write_exclusive(temp,data);os.replace(temp,latest);sync_directory(cfg['capture_root'])
        head=event['digest'];index+=1
        return event
    def finish_exhausted(obs,bad):
        nonlocal original_violation
        event=publish('violation',{'observation':obs,'violation':bad,'started_ns':cfg['started_ns']})
        original_violation=event
        write_exclusive(cfg['capture_root']+'/original-exhaustion.json',canonical(event)+b'\n')
        sync_directory(cfg['capture_root'])
        populations=drain_work_leaves(cfg)
        publish('exhausted_drained',{'observation':observe_protected(cfg,protection),'violation_digest':event['digest'],**populations})
        return 0
    try:
        first=observe_protected(cfg,protection);publish('ready',first)
        if os.write(control_fd,b'READY\n')!=6:raise RuntimeError('short monitor ready write')
        while True:
            obs=observe_protected(cfg,protection);bad=violation(obs,cfg['caps'],cfg['started_ns'])
            if bad:return finish_exhausted(obs,bad)
            publish('observation',{'observation':obs,'violation':None,'started_ns':cfg['started_ns']})
            ready,_,_=select.select([control_fd],[],[],.05)
            if ready:
                command=receive_stop(control_fd)
                if command!=b'STOP\n':raise RuntimeError('guardian control invalid command')
                final=observe_protected(cfg,protection);final_bad=violation(final,cfg['caps'],cfg['started_ns'])
                if final_bad:return finish_exhausted(final,final_bad)
                publish('stopped',{'observation':final,'reason':'authenticated_guard_close'})
                return 0
    except BaseException as exc:
        # The immutable original-exhaustion file and original log remain intact.
        # Cleanup failures are additional evidence and never replace the cause.
        try:publish('original_failure',{'type':type(exc).__name__,'error':str(exc),
            'original_violation_digest':None if original_violation is None else original_violation['digest']})
        except BaseException:pass  # Original stderr/nonzero exit invalidates qualification.
        try:kill_owned(cfg)
        except BaseException as cleanup:
            try:publish('cleanup_failure',{'type':type(cleanup).__name__,'error':str(cleanup),
                'original_error':{'type':type(exc).__name__,'error':str(exc)},
                'original_violation_digest':None if original_violation is None else original_violation['digest']})
            except BaseException:pass
        raise
    finally:os.close(log);os.close(control_fd)


if __name__=='__main__':
    if len(sys.argv)!=4:raise SystemExit('explicit inherited config/control descriptors and digest required')
    raise SystemExit(run(int(sys.argv[1]),int(sys.argv[2]),sys.argv[3]))
