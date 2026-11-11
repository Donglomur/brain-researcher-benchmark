"""Concrete bounded Linux metadata/file observations; no effect on import.

These observation functions do not create root/native authority. Their exact
source-owned caller must select the opened artifact/proc/group owner first.
"""
import hashlib
import os
import stat
from .common import need, same, integer
from .precommit_records import validate_type
from .backend_linux_io import DescriptorSlot, NativeIOCustody


def _regular(slot):
    need(type(slot) is DescriptorSlot and slot in slot.custody.slots and slot.fd is not None and
         not slot.close_entered,'retained source-owned original descriptor')
    s=os.fstat(slot.fd)
    need(stat.S_ISREG(s.st_mode),'actual original regular file')
    return s


def read_kernel_fd(slot,cap,deadline):
    """Only a previously opened fixed Linux metadata FD, never a path alias."""
    need(slot.role in ('proc','group') and type(cap) is int and 0<cap<=1048576,'bounded selected kernel metadata role')
    slot.set_nonblocking();out=[];count=0
    try:
        _regular(slot)
        while count<=cap:
            n=min(4096,cap+1-count);need(n>0,'bounded kernel observation')
            part=slot.custody.recv(slot,n,deadline)
            if part is None:
                slot.custody.wait_ready(slot,deadline);continue
            out.append(part);count+=len(part)
            if not part:break
        need(count<=cap,'whole kernel observation within original selected cap')
        slot.custody.meter.charge('retained_bytes',count)
        return b''.join(out)
    except BaseException as error:slot.retain(error);raise


def hash_artifact_fd(slot,expected,deadline):
    """Whole selected immutable bytes, with before/after identity and no EOF overread."""
    validate_type('Pin',expected)
    need(slot.role in ('executable','model','template','tokenizer','renderer'),'closed actual artifact role')
    c=slot.custody;before=None;count=0;digest=hashlib.sha256()
    try:
        c.work();before=_regular(slot)
        need(before.st_size==expected['bytes'] and before.st_nlink==1 and
             stat.S_IMODE(before.st_mode)&0o222==0,'exact selected extent and immutable artifact mode')
        slot.set_nonblocking()
        while count<expected['bytes']:
            n=min(65536,expected['bytes']-count)
            data=c.recv(slot,n,deadline)
            if data is None:c.wait_ready(slot,deadline);continue
            need(data!=b'','no truncated original artifact')
            count+=len(data);c.work(len(data));digest.update(data);c.now(deadline)
        after=os.fstat(slot.fd)
        fields=('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns','st_mode','st_nlink')
        need(all(getattr(before,k)==getattr(after,k) for k in fields),'same actual immutable opened artifact throughout')
        observed=digest.hexdigest()
        need(count==expected['bytes'] and observed==expected['sha256'],'whole original artifact matches selected digest')
        return {'bytes':count,'sha256':observed,'stat':after,'observed_ns':c.now(deadline)}
    except BaseException as error:slot.retain(error);raise


def parse_proc_stat(raw,expected_pid):
    need(type(raw) is bytes and len(raw)<=8192,'bounded original proc stat bytes')
    start=raw.find(b'(');end=raw.rfind(b')')
    need(start>0 and end>start and int(raw[:start].strip())==expected_pid,'actual proc PID owner')
    fields=raw[end+2:].split();need(len(fields)>=20,'complete process start/parent/group fields')
    parent=int(fields[1]);group=int(fields[2]);session=int(fields[3]);ticks=int(fields[19])
    for n in (expected_pid,parent,group,session,ticks):integer(n)
    return {'pid':expected_pid,'parent_pid':parent,'process_group':group,'session':session,
            'start_ticks':ticks,'state':fields[0].decode('ascii')}


def process_identity_from_observation(raw,pid,boot,mapping,nonce,source,parent_launch):
    """No PID-only proof: caller retains opened namespace/pidfd and mapping owner."""
    validate_type('Pin',source);validate_type('Pin',parent_launch)
    need(type(boot) is str and boot==mapping['boot_id'] and
         os.sysconf('SC_CLK_TCK')==mapping['clock_ticks'],'same original boot and qualified clock tick domain')
    p=parse_proc_stat(raw,pid)
    offset=mapping['tick_to_monotonic_offset_ns'];need(type(offset) is int,'original integer clock translation')
    start=p['start_ticks']*1000000000//mapping['clock_ticks']+offset;integer(start,1)
    identity={'boot_id':boot,'pid':pid,'start_monotonic_ns':start,'launch_nonce':nonce,
              'source':source,'parent_launch':parent_launch}
    validate_type('OriginalProcessIdentity',identity)
    return identity,p


def assert_same_open_directory(fd,named_stat,expected):
    """Compare an existing source-owned mount/workspace anchor; never issue it."""
    a=os.fstat(fd)
    need(stat.S_ISDIR(a.st_mode) and stat.S_ISDIR(named_stat.st_mode) and
         (a.st_dev,a.st_ino)==(named_stat.st_dev,named_stat.st_ino)==(expected['device'],expected['inode']),
         'same retained directory owner and source-selected named identity')
    return a


def observe_namespace_links(proc_dir_fd,custody,deadline):
    """Fixed namespace census, for an actual previously anchored process directory."""
    from .backend_linux_host_observation import HostNativeIOCustody
    need(type(custody) in (NativeIOCustody,HostNativeIOCustody),'fixed original worker or independent H observation owner')
    if type(custody)is HostNativeIOCustody:custody.original_worker_identity()
    result={}
    for name in ('mnt','pid','net','user','ipc','uts','cgroup'):
        custody.now(deadline);custody.meter.charge('read_bytes',256);custody.meter.charge('retained_bytes',256)
        # These fixed proc namespace symlinks are kernel identity interfaces,
        # not artifact/path aliases or permission to traverse arbitrary links.
        value=os.readlink('ns/'+name,dir_fd=proc_dir_fd)
        need(type(value) is str and len(value)<=255 and value.startswith(name+':[') and value.endswith(']'),
             'fixed actual kernel namespace identity')
        result[name]=value
    return result


def server_subtree_census(group_dir_fd,worker_pid,server_pid,custody,deadline):
    """Actual cgroup.procs census with fixed /proc ancestry, no empty-list inference.

    Qualified native isolation must prevent membership escape. This function
    proves only the observed census under that separately admitted guarantee.
    It does not itself establish isolation or create a successful wire record.
    """
    slot=custody.slot('group');slot.openat(group_dir_fd,'cgroup.procs',os.O_RDONLY|os.O_NONBLOCK)
    try:raw=read_kernel_fd(slot,65536,deadline)
    finally:closed=slot.close()
    need(closed,'actual census descriptor closure')
    words=raw.split();need(len(words)<=4096 and all(x.isdigit() for x in words),'finite complete original cgroup PID list')
    pids=[int(x) for x in words];need(len(pids)==len(set(pids)),'unique kernel process membership')
    need(worker_pid in pids,'fixed worker still alive while recording server closure')
    # No unrelated child may be silently reclassified as outside the server.
    # Caller has stopped agent/tool launches before this whole group census.
    residual=[p for p in pids if p!=worker_pid]
    return {'worker_present':True,'server_present':server_pid in residual,
            'residual_pids':residual,'leaf_enumeration_complete':True,
            'subtree_containment_proven':False,'observed_ns':custody.now(deadline)}
