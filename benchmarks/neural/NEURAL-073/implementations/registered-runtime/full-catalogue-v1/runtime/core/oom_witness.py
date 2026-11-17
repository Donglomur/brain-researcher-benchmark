"""Source-owned monitor-only OOM protection. Import performs no native work.

Pure receipt validation is not native qualification. The only positive capability
is issued after a real authenticated Popen child has a held-proc-directory write
and readback. The supervisor never receives -1000; payload launch drops privilege.
"""
import ctypes
import errno
import json
import os
import subprocess
import sys
import weakref
from .custody import VerifiedAuthority,canonical,digest,require_digest


class WitnessError(RuntimeError): pass
class MonitorExited(WitnessError): pass
class _LeafEmpty(WitnessError): pass


POLICY={'schema':'n073_monitor_oom_policy_v1','supervisor_adj':0,'monitor_adj':-1000,'payload_adj':0,
        'payload_no_new_privs':1,'payload_capability_masks':0,'monitor_forks_payloads':False,
        'memory_max_bytes':68719476736,'monitor_inside_aggregate':True,
        'sequence':'WAIT_OOM-held-proc-write-readback-durable-witness-GO-READY'}
_SEAL=object();_PROTECTIONS=weakref.WeakKeyDictionary()


def contract_digest(evidence_digest):
    require_digest(evidence_digest)
    return digest({'policy':POLICY,'evidence_digest':evidence_digest})


def parse_stat(text):
    """Pure exact PID and start-time decoder for an explicitly selected proc row."""
    if not isinstance(text,str) or ') ' not in text:raise WitnessError('invalid proc stat')
    split=text.rfind(') ');head=text[:text.index(' (')];fields=text[split+2:].split()
    if not head.isdecimal() or len(fields)<20 or not fields[19].isdecimal():raise WitnessError('invalid proc PID/start fields')
    return int(head),int(fields[19])


def parse_status(text):
    out={}
    for line in text.splitlines():
        if ':' not in line:continue
        k,v=line.split(':',1)
        if k in out:raise WitnessError('duplicate proc status field')
        out[k]=v.strip()
    return out


def validate_payload_status(status,adj):
    if type(adj) is not int or adj!=0:raise WitnessError('payload OOM eligibility differs from selected0')
    if status.get('NoNewPrivs')!='1':raise WitnessError('payload no_new_privs missing')
    for key in ('CapInh','CapPrm','CapEff','CapAmb'):
        value=status.get(key)
        if not isinstance(value,str) or not value or any(c not in '0123456789abcdefABCDEF' for c in value) or int(value,16)!=0:
            raise WitnessError('payload privilege could lower OOM eligibility: '+key)
    return True


def validate_protection_receipt(receipt,*,context_id,config_digest,runtime_digest,contract_digest,monitor_identity,monitor_pid=None):
    if not isinstance(receipt,dict):raise WitnessError('typed protection metadata mapping required')
    if not isinstance(monitor_identity,(tuple,list)) or len(monitor_identity)!=2 or any(type(v) is not int or v<0 for v in monitor_identity):
        raise WitnessError('expected monitor leaf identity must be two exact nonnegative integers')
    if monitor_pid is not None and (type(monitor_pid) is not int or monitor_pid<=0):raise WitnessError('expected monitor PID must be a positive exact integer')
    for value in (config_digest,runtime_digest,contract_digest):require_digest(value)
    if receipt.get('digest')!=digest({k:v for k,v in receipt.items() if k!='digest'}):raise WitnessError('protection digest mismatch')
    expected={'schema':'n073_monitor_oom_protection_v1','context_id':context_id,'config_digest':config_digest,
              'runtime_digest':runtime_digest,'contract_digest':contract_digest,'monitor_leaf_identity':list(monitor_identity),
              'score_before':0,'score_after':-1000,'supervisor_adj':0,'readback_before_go':True}
    if any(type(receipt.get(k)) is not type(v) or receipt[k]!=v for k,v in expected.items()):raise WitnessError('protection policy/context/custody mismatch')
    for key in ('monitor_pid','monitor_start_ticks','supervisor_pid','supervisor_start_ticks','writer_pid'):
        if type(receipt.get(key)) is not int or receipt[key]<=0:raise WitnessError('positive native PID/start identity required')
    identity=receipt.get('proc_directory_identity')
    if not isinstance(identity,list) or len(identity)!=2 or any(type(v) is not int or v<0 for v in identity):raise WitnessError('held proc-directory identity required')
    if receipt['writer_pid']!=receipt['supervisor_pid'] or receipt['monitor_pid']==receipt['supervisor_pid']:raise WitnessError('writer/child isolation mismatch')
    if monitor_pid is not None and receipt['monitor_pid']!=monitor_pid:raise WitnessError('actual Popen PID mismatch')
    require_digest(receipt.get('evidence_digest'))
    if globals()['contract_digest'](receipt['evidence_digest'])!=contract_digest:raise WitnessError('protection evidence contract mismatch')
    return json.loads(canonical(receipt))


def resolve_terminal_event(prior,terminal,*,returncode,protection_digest):
    """Pure race-resolution check; not evidence that a process actually exited."""
    for row in (prior,terminal):
        if not isinstance(row,dict) or row.get('digest')!=digest({k:v for k,v in row.items() if k!='digest'}):raise WitnessError('terminal transition event digest')
    if type(returncode) is not int or returncode!=0:raise WitnessError('unexpected monitor death cannot resolve to a qualified terminal')
    if terminal.get('kind') not in ('stopped','exhausted_drained'):raise WitnessError('natural exit lacks terminal evidence')
    for key in ('context_id','config_digest','oom_protection_digest'):
        if terminal.get(key)!=prior.get(key):raise WitnessError('terminal custody transition mismatch')
    if terminal.get('oom_protection_digest')!=protection_digest:raise WitnessError('terminal protection mismatch')
    if type(prior.get('index')) is not int or type(terminal.get('index')) is not int or terminal['index']<prior['index']:
        raise WitnessError('terminal event moved backwards')
    if prior.get('kind')=='violation' and (terminal['kind']!='exhausted_drained' or terminal.get('body',{}).get('violation_digest')!=prior['digest']):
        raise WitnessError('original exhaustion missing from terminal transition')
    return json.loads(canonical(terminal))


def _read_at(directory,name,limit=65536):
    fd=os.open(name,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=directory)
    try:
        data=os.read(fd,limit+1)
        if len(data)>limit:raise WitnessError('bounded selected proc read overflow')
        return data.decode('ascii')
    finally:os.close(fd)


def _write_adj(directory,value):
    fd=os.open('oom_score_adj',os.O_WRONLY|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=directory)
    try:
        data=(str(value)+'\n').encode('ascii')
        if os.write(fd,data)!=len(data):raise WitnessError('short OOM adjustment write')
    finally:os.close(fd)


def _proc_directory(pid):
    if type(pid) is not int or pid<=0:raise WitnessError('explicit positive PID required')
    return os.open('/proc/'+str(pid),os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)


def _leaf_identity(path,identity,pid):
    fd=os.open(path,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
    try:
        st=os.fstat(fd)
        if [st.st_dev,st.st_ino]!=list(identity):raise WitnessError('owned monitor leaf changed')
        values=_read_at(fd,'cgroup.procs').split()
        if not values:raise _LeafEmpty('monitor leaf became empty')
        if values!=[str(pid)]:raise WitnessError('monitor leaf must contain exactly its owned leader')
    finally:os.close(fd)


def eligible_supervisor(*,expected_start=None):
    """Actual own-process check; does not change its score or scan foreign tasks."""
    if sys.platform!='linux':raise WitnessError('Linux native witness qualification absent')
    pid=os.getpid();fd=_proc_directory(pid)
    try:
        actual,start=parse_stat(_read_at(fd,'stat'));adj=int(_read_at(fd,'oom_score_adj').strip())
        if actual!=pid or adj!=0 or (expected_start is not None and start!=expected_start):raise WitnessError('supervisor must remain exact eligible process')
        return {'pid':pid,'start_ticks':start,'adj':adj,'status':parse_status(_read_at(fd,'status'))}
    finally:os.close(fd)


def payload_before_exec():
    """Trusted child hook, called only after authenticated cgroup attachment.

    This never sets -1000. It drops inherited Linux capabilities before exec,
    clears ambient capability inheritance and forbids later exec privilege gain.
    Qualification must verify this libc/kernel ABI and bwrap's separate namespace
    boundary. The broker is source-pinned; this is not a network sandbox for it.
    """
    if sys.platform!='linux':raise WitnessError('Linux payload custody required')
    own=eligible_supervisor();fd=_proc_directory(own['pid'])
    try:
        _write_adj(fd,0)
        if int(_read_at(fd,'oom_score_adj').strip())!=0:raise WitnessError('payload OOM score readback failed')
        libc=ctypes.CDLL(None,use_errno=True)
        libc.prctl.argtypes=[ctypes.c_int,ctypes.c_ulong,ctypes.c_ulong,ctypes.c_ulong,ctypes.c_ulong]
        libc.prctl.restype=ctypes.c_int
        if libc.prctl(47,4,0,0,0)!=0:raise WitnessError('clear ambient capabilities failed')
        class Header(ctypes.Structure):_fields_=[('version',ctypes.c_uint32),('pid',ctypes.c_int)]
        class Data(ctypes.Structure):_fields_=[('effective',ctypes.c_uint32),('permitted',ctypes.c_uint32),('inheritable',ctypes.c_uint32)]
        header=Header(0x20080522,0);data=(Data*2)()
        libc.capset.argtypes=[ctypes.POINTER(Header),ctypes.POINTER(Data)];libc.capset.restype=ctypes.c_int
        if libc.capset(ctypes.byref(header),data)!=0:raise WitnessError('drop payload capabilities failed')
        if libc.prctl(38,1,0,0,0)!=0:raise WitnessError('payload no_new_privs failed')
        validate_payload_status(parse_status(_read_at(fd,'status')),int(_read_at(fd,'oom_score_adj').strip()))
        if parse_stat(_read_at(fd,'stat'))!=(own['pid'],own['start_ticks']):raise WitnessError('payload identity changed')
    finally:os.close(fd)


class MonitorProtection:
    __slots__=('__weakref__',)
    def __init__(self,seal):
        if seal is not _SEAL:raise WitnessError('actual held-directory protection required')
    def to_dict(self):
        row=_PROTECTIONS.get(self)
        if row is None:raise WitnessError('unregistered monitor protection')
        return json.loads(canonical(row['receipt']))
    def verify_live(self):
        row=_PROTECTIONS.get(self)
        if row is None or row['closed']:raise WitnessError('missing/closed protection custody')
        p=row['proc'];receipt=row['receipt'];fd=row['fd']
        if p.poll() is not None:raise MonitorExited('protected monitor is no longer alive')
        try:
            actual=parse_stat(_read_at(fd,'stat'))
            actual_adj=int(_read_at(fd,'oom_score_adj').strip())
        except OSError as exc:
            if exc.errno in (errno.ENOENT,errno.ESRCH):
                try:p.wait(timeout=.1)
                except subprocess.TimeoutExpired:raise exc
                raise MonitorExited('owned proc entries ended with monitor') from exc
            raise
        if actual!=(p.pid,receipt['monitor_start_ticks']):raise WitnessError('protected monitor start identity changed')
        st=os.fstat(fd)
        if [st.st_dev,st.st_ino]!=receipt['proc_directory_identity'] or actual_adj!=-1000:raise WitnessError('monitor immunity/custody changed')
        try:_leaf_identity(row['leaf'],receipt['monitor_leaf_identity'],p.pid)
        except _LeafEmpty as exc:
            try:p.wait(timeout=.1)
            except subprocess.TimeoutExpired:raise exc
            raise MonitorExited('owned monitor exited during leaf readback') from exc
        eligible_supervisor(expected_start=receipt['supervisor_start_ticks'])
        return receipt['digest']
    def close(self):
        row=_PROTECTIONS.get(self)
        if row is None or row['closed']:raise WitnessError('protection descriptor close order')
        os.close(row['fd']);row['closed']=True


def protect_owned_monitor(proc,*,context_id,leaf,leaf_identity,config_digest,runtime_digest,evidence_digest,
                          supervisor_start,authority,bindings):
    """Parent is the sole writer; a live owned child is blocked at WAIT_OOM."""
    contract=contract_digest(evidence_digest)
    required={**bindings,'context_digest':digest(context_id),'aggregate_monitor_contract_digest':runtime_digest,
              'oom_witness_contract_digest':contract}
    if not isinstance(authority,VerifiedAuthority):raise WitnessError('authentic typed authority required before proc access')
    authority.require(role='candidate_author',domain='authentic',bindings=required)
    if sys.platform!='linux' or not isinstance(proc,subprocess.Popen):raise WitnessError('actual Linux owned Popen required')
    supervisor=eligible_supervisor(expected_start=supervisor_start)
    # Explicit privilege failure before the write; the kernel remains authoritative.
    status=supervisor['status']
    if not int(status.get('CapEff','0'),16)&(1<<24):raise WitnessError('CAP_SYS_RESOURCE needed for monitor-only protection')
    if proc.poll() is not None:raise WitnessError('monitor died before protection')
    _leaf_identity(leaf,leaf_identity,proc.pid)
    fd=_proc_directory(proc.pid)
    try:
        st=os.fstat(fd);pid,start=parse_stat(_read_at(fd,'stat'));before=int(_read_at(fd,'oom_score_adj').strip())
        if pid!=proc.pid or before!=0:raise WitnessError('monitor did not inherit exact eligible supervisor score')
        _write_adj(fd,-1000)
        after=int(_read_at(fd,'oom_score_adj').strip());after_stat=os.fstat(fd)
        if (after!=-1000 or parse_stat(_read_at(fd,'stat'))!=(pid,start)
            or (st.st_dev,st.st_ino)!=(after_stat.st_dev,after_stat.st_ino) or proc.poll() is not None):raise WitnessError('monitor write/readback identity failure')
        _leaf_identity(leaf,leaf_identity,pid);eligible_supervisor(expected_start=supervisor_start)
        receipt={'schema':'n073_monitor_oom_protection_v1','context_id':context_id,'config_digest':config_digest,
            'runtime_digest':runtime_digest,'contract_digest':contract,'evidence_digest':evidence_digest,
            'monitor_pid':pid,'monitor_start_ticks':start,'proc_directory_identity':[st.st_dev,st.st_ino],
            'monitor_leaf_identity':list(leaf_identity),'score_before':before,'score_after':after,
            'supervisor_pid':supervisor['pid'],'supervisor_start_ticks':supervisor['start_ticks'],
            'supervisor_adj':supervisor['adj'],'writer_pid':os.getpid(),'readback_before_go':True}
        receipt['digest']=digest(receipt)
        validate_protection_receipt(receipt,context_id=context_id,config_digest=config_digest,runtime_digest=runtime_digest,
            contract_digest=contract,monitor_identity=leaf_identity,monitor_pid=proc.pid)
        token=MonitorProtection(_SEAL);_PROTECTIONS[token]={'fd':fd,'proc':proc,'leaf':leaf,'receipt':receipt,'closed':False}
        return token
    except BaseException:
        os.close(fd)
        raise
