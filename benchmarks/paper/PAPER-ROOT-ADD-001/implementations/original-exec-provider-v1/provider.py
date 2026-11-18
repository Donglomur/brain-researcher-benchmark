"""Explicit Linux exec-reset baseline; no default practical campaign claim.

Native execution requires an externally authenticated admission/qualification.
This source has generated controls only. A closure record is attributed provider
observation, not independent OS attestation. Never pass an untrusted backend.
"""
from __future__ import annotations

from dataclasses import dataclass
import base64
import ctypes
import fcntl
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import resource
import selectors
import signal
import stat
import sys
import time
import types
import uuid

ENTRY_SHA256 = '530452d9b82b87fd395c9faf2496a7de2411c2ca3eb1b0053b21b8fd233de615'
BUNDLE_SHA256 = 'a54bdb02d3d9d0be74bafaab3503175a6eaf867ee5299b97c5983bc2ea30a8a7'
MODE = 'exec_reset_bwrap_v1'
HERE = Path(__file__).resolve().parent


def need(ok, message):
    if not ok:
        raise ValueError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(value):
    return (json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()


def digest(value):
    return type(value) is str and len(value) == 64 and all(c in '0123456789abcdef' for c in value)


def integer(value, lo=1, hi=2**63-1):
    return type(value) is int and lo <= value <= hi


def parse(raw):
    def pairs(items):
        value = {}
        for key, item in items:
            need(key not in value, 'Duplicate JSON key')
            value[key] = item
        return value
    return json.loads(raw,object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite JSON')))


def _source(path, expected, limit=131072):
    with open(path,'rb') as stream:
        raw = stream.read(limit+1)
    need(len(raw) <= limit and sha(raw) == expected,'Pinned source dependency')
    module = types.ModuleType('_language_exec_'+expected[:12])
    module.__file__, module.__package__ = str(path), ''
    sys.modules[module.__name__] = module
    exec(compile(raw,str(path),'exec',dont_inherit=True),module.__dict__)
    return module


PUBLIC = _source(HERE/'participant_entry.py',ENTRY_SHA256)
B = _source(HERE.parent/'original-compact-bundles-v1/bundle.py',BUNDLE_SHA256)


def identity():
    """Operator source identity, not the participant runtime/tree identity."""
    with open(__file__,'rb') as stream:
        raw = stream.read(131073)
    need(len(raw) <= 131072,'Bounded provider source')
    return sha(encoded({'provider.py':sha(raw),'participant_entry.py':ENTRY_SHA256,
                        'compact_bundle_dependency':BUNDLE_SHA256}))


CAPS = {'tree_read_bytes','feature_read_bytes','kernel_read_bytes','kernel_write_bytes',
        'staging_bytes','sandbox_copy_bytes','visible_input_bytes',
        'stdout_bytes','stderr_bytes','journal_bytes','max_jobs','max_requests',
        'working_bytes','bundle_bytes','per_request_seconds','cleanup_seconds',
        'run_seconds','child_memory_bytes','pids','tmpfs_bytes','cpu_quota_us','cpu_period_us',
        'child_cpu_seconds','request_stdout_bytes','request_stderr_bytes'}
CONFIG_KEYS = {'schema','mode','condition','candidate_sha256','provider_source_sha256',
               'store_sha256','schedule_sha256','runtime','candidate','assistance','bwrap',
               'cgroup_parent','python_path','caps'}


def config_snapshot(config):
    need(type(config) is dict and len(config) == len(CONFIG_KEYS) and set(config) == CONFIG_KEYS,
         'Exact provider configuration')
    for key in CONFIG_KEYS-{'runtime','candidate','assistance','bwrap','caps'}:
        need(type(config[key]) is str and 0 < len(config[key]) <= 4096,'Bounded primitive config strings before serialization')
    for key in ('runtime','candidate','assistance'):
        value=config[key]
        need(type(value) is dict and len(value) == 3 and set(value) == {'root','manifest','manifest_sha256'}
             and all(type(v) is str and 0 < len(v) <= 4096 for v in value.values()),
             'Bounded primitive tree descriptors before serialization')
    value=config['bwrap']
    need(type(value) is dict and len(value) == 4 and set(value) == {'path','bytes','sha256','version'}
         and integer(value['bytes']) and all(type(value[k]) is str and 0 < len(value[k]) <= 4096
             for k in ('path','sha256','version')),'Bounded primitive executable descriptor')
    need(type(config['caps']) is dict and len(config['caps']) == len(CAPS)
         and set(config['caps']) == CAPS and all(integer(v) for v in config['caps'].values()),
         'Bounded primitive caps before serialization')
    # JSON is bounded before any filesystem or process operation.
    raw = encoded(config)
    need(len(raw) <= 32768,'Bounded primitive configuration')
    c = parse(raw)
    need(c['schema'] == 'language-exec-provider/v1' and c['mode'] == MODE,
         'Explicit supported baseline mode; no fallback or default')
    need(c['condition'] in ('paper_data','paper_data_author_code'),'Frozen information condition')
    for key in ('candidate_sha256','provider_source_sha256','store_sha256','schedule_sha256'):
        need(digest(c[key]),'Exact frozen identity '+key)
    need(type(c['caps']) is dict and set(c['caps']) == CAPS
         and all(integer(v) for v in c['caps'].values()),'Finite explicit complete resource caps')
    p = c['caps']
    need(p['working_bytes'] <= 1024**3 and 64 <= p['bundle_bytes'] <= 128*1024**2
         and p['cleanup_seconds'] <= 60 and p['per_request_seconds']+p['cleanup_seconds'] <= p['run_seconds']
         and p['max_requests'] <= 6776076 and p['max_jobs'] <= 58926
         and p['cpu_quota_us'] <= p['cpu_period_us'] and p['cpu_period_us'] <= 1000000
         and p['pids'] <= 256 and p['request_stderr_bytes'] <= 1024**2,
         'Bounded single-CPU baseline and cleanup reserve')
    for key in ('runtime','candidate','assistance'):
        desc = c[key]
        need(type(desc) is dict and set(desc) == {'root','manifest','manifest_sha256'}
             and digest(desc['manifest_sha256']),'Exact frozen tree descriptor')
        for field in ('root','manifest'):
            need(type(desc[field]) is str and 0 < len(desc[field]) <= 4096
                 and Path(desc[field]).is_absolute(),'Absolute bounded host descriptor')
    need(c['candidate_sha256'] == c['candidate']['manifest_sha256'],'Global candidate is its complete frozen tree')
    need(type(c['bwrap']) is dict and set(c['bwrap']) == {'path','bytes','sha256','version'}
         and c['bwrap']['version'] == '0.11.0' and digest(c['bwrap']['sha256'])
         and integer(c['bwrap']['bytes'],1,64*1024**2),'Exact qualified bubblewrap executable')
    need(type(c['bwrap']['path']) is str and Path(c['bwrap']['path']).is_absolute()
         and type(c['cgroup_parent']) is str and Path(c['cgroup_parent']).is_absolute(), 'Absolute native paths')
    need(type(c['python_path']) is str and c['python_path'].startswith('/usr/')
         and '..' not in PurePosixPath(c['python_path']).parts,'Declared generic runtime interpreter')
    return c


def admission_snapshot(c, admission):
    keys = {'schema','mode','config_sha256','protocol_sha256','qualification_sha256',
            'qualification_scope','admitted_until_unix','root_admission_id'}
    need(type(admission) is dict and len(admission) == len(keys) and set(admission) == keys,
         'External admission required')
    need(integer(admission['admitted_until_unix']) and all(type(admission[k]) is str
         and 0 < len(admission[k]) <= 128 for k in keys-{'admitted_until_unix'}),
         'Bounded primitive admission before serialization')
    a = parse(encoded(admission))
    need(a['schema'] == 'language-native-execution-admission/v1' and a['mode'] == MODE
         and a['config_sha256'] == sha(encoded(c)),'Admission binds exact runtime/condition/caps/source/store')
    need(digest(a['protocol_sha256']) and digest(a['qualification_sha256'])
         and a['qualification_scope'] == 'linux-bwrap011-cgroupv2-execreset-native'
         and integer(a['admitted_until_unix']) and a['admitted_until_unix'] > time.time()
         and type(a['root_admission_id']) is str and 0 < len(a['root_admission_id']) <= 128,
         'Live root admission and separately retained native qualification required')
    return a


def safe_path(path):
    path = Path(path)
    need(path.is_absolute(),'Absolute path required')
    for node in reversed((path,)+tuple(path.parents)):
        if node.exists() or node.is_symlink():
            need(not node.is_symlink(),'No symlink ancestor')
    return path


def stable_tuple(s):
    return (s.st_dev,s.st_ino,s.st_mode,s.st_nlink,s.st_size,s.st_mtime_ns,s.st_ctime_ns)


class Meter:
    def __init__(self,caps):
        self.caps = dict(caps)
        self.values = {name:0 for name in ('tree_read_bytes','feature_read_bytes','kernel_read_bytes','kernel_write_bytes',
                      'staging_bytes','sandbox_copy_bytes',
                      'visible_input_bytes','stdout_bytes','stderr_bytes','journal_bytes','max_jobs','max_requests')}
        self.observed = {'tree_read_bytes':0,'feature_read_bytes':0,'kernel_read_bytes':0,'kernel_write_bytes':0,
                         'stdout_bytes':0,'stderr_bytes':0}
    def charge(self,key,amount):
        need(integer(amount,0) and self.values[key]+amount <= self.caps[key], 'Cumulative '+key+' budget')
        self.values[key] += amount


def read_owned(path, size, expected, meter, key, *, executable=False, readonly=True):
    """No-follow regular/single-link stable read; EOF probe charged before open."""
    need(integer(size,0) and digest(expected),'Exact bounded file descriptor')
    meter.charge(key,size+1)
    path = safe_path(path)
    fd = os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC)
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
             and before.st_size == size and not before.st_mode & (stat.S_ISUID|stat.S_ISGID)
             and (not readonly or not before.st_mode & 0o222),
             'Immutable regular single-link source')
        need(not executable or before.st_mode & 0o111,'Executable source mode')
        chunks, remaining = [], size+1
        while remaining:
            part = os.read(fd,min(remaining,1024**2))
            if not part: break
            meter.observed[key] += len(part)
            chunks.append(part); remaining -= len(part)
        raw = b''.join(chunks)
        need(len(raw) == size and sha(raw) == expected and stable_tuple(os.fstat(fd)) == stable_tuple(before)
             and stable_tuple(path.stat(follow_symlinks=False)) == stable_tuple(before),'Exact stable authenticated source')
        return raw, before
    finally:
        os.close(fd)


def authenticate_tree(desc, kind, meter, working):
    root, manifest = safe_path(desc['root']), safe_path(desc['manifest'])
    s = manifest.stat(follow_symlinks=False)
    need(s.st_size <= 4*1024**2 and 8*s.st_size+4*1024**2 <= working,'Tree manifest working cap before read')
    raw, _ = read_owned(manifest,s.st_size,desc['manifest_sha256'],meter,'tree_read_bytes')
    value = parse(raw)
    need(type(value) is dict and set(value) == {'schema','kind','condition','directories','files'}
         and value['schema'] == 'language-frozen-public-tree/v1' and value['kind'] == kind,
         'Typed complete public tree; operator audits information content')
    need(type(value['directories']) is list and type(value['files']) is list
         and len(value['directories'])+len(value['files']) <= 100000
         and 2048*(len(value['directories'])+len(value['files']))+8*len(raw)+4*1024**2 <= working,
         'Complete tree metadata budget')
    def relative(name):
        need(type(name) is str and 0 < len(name) <= 1024 and not name.startswith('/')
             and str(PurePosixPath(name)) == name and '..' not in PurePosixPath(name).parts,
             'Canonical relative manifest path')
        return name
    dirs = [relative(n) for n in value['directories']]
    need(dirs == sorted(set(dirs)),'Canonical unique directory list')
    files = {}
    for row in value['files']:
        need(type(row) is dict and set(row) == {'path','bytes','sha256','mode'},'Exact tree member descriptor')
        name = relative(row['path'])
        need(name not in files and name not in dirs and integer(row['bytes'],0)
             and digest(row['sha256']) and row['mode'] in (0o444,0o555),'Canonical immutable tree member')
        files[name] = row
    need(list(files) == sorted(files),'Canonical member order')
    base = root.stat(follow_symlinks=False)
    need(stat.S_ISDIR(base.st_mode) and stat.S_IMODE(base.st_mode) == 0o555,'Immutable tree root')
    found_dirs, found_files, pending = [], [], ['']
    declared_dirs=set(dirs)
    while pending:
        parent=pending.pop()
        with os.scandir(root/parent) as entries:
            for entry in entries:
                need(len(found_dirs)+len(found_files) < len(dirs)+len(files),'No unlisted tree payload')
                name=(parent+'/' if parent else '')+entry.name
                need(len(name) <= 1024 and (name in declared_dirs or name in files),
                     'Declared bounded path before filesystem traversal or metadata retention')
                st=entry.stat(follow_symlinks=False)
                if name in declared_dirs:
                    need(stat.S_ISDIR(st.st_mode) and stat.S_IMODE(st.st_mode) == 0o555 and st.st_dev == base.st_dev,
                         'No links, writable directories or nested filesystem roots')
                    found_dirs.append(name);pending.append(name)
                else:
                    need(stat.S_ISREG(st.st_mode),'Only ordinary declared files')
                    found_files.append(name)
    need(sorted(found_dirs) == dirs and sorted(found_files) == sorted(files),'Complete tree roster; no hidden files')
    for name,row in files.items():
        need(4*row['bytes']+8*len(raw)+2048*(len(dirs)+len(files))+4*1024**2 <= working,
             'Tree member authentication working budget')
        data, st = read_owned(root/name,row['bytes'],row['sha256'],meter,'tree_read_bytes')
        need(stat.S_IMODE(st.st_mode) == row['mode'] and st.st_dev == base.st_dev,'Exact member mode/filesystem')
        del data
    fd = os.open(root,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
    try:
        need(os.fstat(fd).st_ino == base.st_ino and os.fstat(fd).st_dev == base.st_dev,'Stable tree root')
    except BaseException:
        os.close(fd)
        raise
    return fd,value,stable_tuple(base)


def command(config, fds):
    """Pure exact argv; only five public mounts plus a generic runtime root."""
    need(set(fds) == {'bwrap','runtime','candidate','assistance','entry','feature','bundle','descriptor'}
         and all(integer(v,3,2**20) for v in fds.values()) and len(set(fds.values())) == len(fds),
         'Distinct explicit source FDs')
    argv = [f'/proc/self/fd/{fds["bwrap"]}','--unshare-all','--unshare-user','--unshare-cgroup',
            '--disable-userns','--new-session','--die-with-parent','--cap-drop','ALL','--clearenv']
    for name,value in (('PATH','/usr/bin'),('LANG','C.UTF-8'),('LC_ALL','C.UTF-8'),
                       ('PYTHONDONTWRITEBYTECODE','1'),('OMP_NUM_THREADS','1'),('OPENBLAS_NUM_THREADS','1'),
                       ('MKL_NUM_THREADS','1'),('NUMEXPR_NUM_THREADS','1')):
        argv += ['--setenv',name,value]
    for key,dest in (('runtime','/'),('candidate','/candidate'),('assistance','/artifacts'),
                     ('entry','/executor/entry.py'),('feature','/input/features.npy')):
        argv += ['--ro-bind-fd',str(fds[key]),dest]
    for key,dest in (('bundle','/input/responses.bin'),('descriptor','/input/request.json')):
        argv += ['--ro-bind-data',str(fds[key]),dest]
    argv += ['--size',str(config['caps']['tmpfs_bytes']),'--tmpfs','/tmp',
             '--proc','/proc','--remount-ro','/proc','--dev','/dev',
             '--remount-ro','/dev/pts','--remount-ro','/dev','--remount-ro','/',
             '--chdir','/tmp',config['python_path'],'-I','-B','/executor/entry.py',
             str(config['caps']['bundle_bytes']),str(config['caps']['working_bytes'])]
    return argv


def sealed(raw, meter):
    need(type(raw) is bytes,'Immutable staging bytes')
    meter.charge('staging_bytes',len(raw))
    fd = os.memfd_create('selected-public-input',os.MFD_CLOEXEC|os.MFD_ALLOW_SEALING)
    try:
        at = 0
        while at < len(raw):
            count = os.write(fd,memoryview(raw)[at:]); need(count > 0,'Staging write progress'); at += count
        os.lseek(fd,0,os.SEEK_SET)
        os.fchmod(fd,0o555)
        flags = fcntl.F_SEAL_WRITE|fcntl.F_SEAL_GROW|fcntl.F_SEAL_SHRINK|fcntl.F_SEAL_SEAL
        fcntl.fcntl(fd,fcntl.F_ADD_SEALS,flags)
        need(fcntl.fcntl(fd,fcntl.F_GET_SEALS) == flags,'Complete immutable memfd seals')
        return fd
    except BaseException:
        os.close(fd); raise


def _write_at(fd,name,value,meter):
    raw = value.encode(); meter.charge('kernel_write_bytes',len(raw))
    out = os.open(name,os.O_WRONLY|os.O_CLOEXEC|os.O_NOFOLLOW,dir_fd=fd)
    try:
        written = os.write(out,raw); meter.observed['kernel_write_bytes'] += written
        need(written == len(raw),'Complete cgroup write')
    finally: os.close(out)


def _read_at(fd,name,meter,cap=4096):
    meter.charge('kernel_read_bytes',cap+1)
    source = os.open(name,os.O_RDONLY|os.O_CLOEXEC|os.O_NOFOLLOW,dir_fd=fd)
    try:
        raw = os.read(source,cap+1); meter.observed['kernel_read_bytes'] += len(raw)
        need(len(raw) <= cap,'Bounded cgroup metadata')
        return raw.decode().strip()
    finally: os.close(source)


def counters(text):
    return dict((key,int(value)) for key,value in (line.split() for line in text.splitlines()))


def _prctl():
    libc = ctypes.CDLL(None,use_errno=True)
    call = libc.prctl
    call.argtypes = [ctypes.c_int,ctypes.c_ulong,ctypes.c_ulong,ctypes.c_ulong,ctypes.c_ulong]
    call.restype = ctypes.c_int
    return call


def arm_parent_death(prctl, expected_parent):
    """Trusted child only: close the fork-to-bwrap parent-death window."""
    need(prctl(1,int(signal.SIGKILL),0,0,0) == 0, 'PR_SET_PDEATHSIG required')
    need(os.getppid() == expected_parent,'Original coordinator still owns child')
    need(prctl(38,1,0,0,0) == 0,'PR_SET_NO_NEW_PRIVS required before exec')


class LinuxBackend:
    """Actual OS implementation. Not executed by the generated test suite."""
    @staticmethod
    def require_platform():
        need(sys.platform == 'linux' and hasattr(os,'pidfd_open') and hasattr(signal,'pidfd_send_signal')
             and hasattr(os,'memfd_create'),'Qualified Linux pidfd/memfd required; no fallback')
        need(signal.getsignal(signal.SIGCHLD) == signal.SIG_DFL,'Exclusive default child reaping ownership')
        need(len(os.listdir('/proc/self/task')) == 1,'Single-threaded trusted launcher before fork')

    def invoke(self, config, fds, deadline, meter):
        self.require_platform()
        caps = config['caps']; parent = safe_path(config['cgroup_parent'])
        parentfd = os.open(parent,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
        name = 'language-'+uuid.uuid4().hex
        groupfd = None; pidfd = None; pid = None; status = None; admitted = False
        pipes = []; selector = selectors.DefaultSelector(); child_started = time.monotonic()
        stdout, stderr = bytearray(), bytearray(); natural = False; error = None
        cleanup_deadline = deadline+caps['cleanup_seconds']
        read = lambda fd,name: _read_at(fd,name,meter)
        write = lambda fd,name,value: _write_at(fd,name,value,meter)
        try:
            # Reserve cleanup control I/O separately before creating any owned process.
            cleanup_reads = (caps['cleanup_seconds']*101+8)*4097
            cleanup_writes = 1
            need(meter.values['kernel_read_bytes']+cleanup_reads+65536 <= meter.caps['kernel_read_bytes']
                 and meter.values['kernel_write_bytes']+cleanup_writes+1024 <= meter.caps['kernel_write_bytes'],
                 'Kernel cleanup metadata headroom before owned resources')
            need(read(parentfd,'cgroup.type') == 'domain','Delegated cgroup v2 domain required')
            os.mkdir(name,mode=0o700,dir_fd=parentfd)
            groupfd = os.open(name,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=parentfd)
            controls = {'memory.max':str(caps['child_memory_bytes']),'memory.swap.max':'0',
                        'pids.max':str(caps['pids']),
                        'cpu.max':f'{caps["cpu_quota_us"]} {caps["cpu_period_us"]}'}
            for key,value in controls.items():
                write(groupfd,key,value); need(read(groupfd,key) == value,'Kernel resource control readback')
            need(counters(read(groupfd,'cgroup.events')).get('populated') == 0,'Exclusive empty invocation cgroup')
            before = counters(read(groupfd,'memory.events'))
            out_r,out_w = os.pipe2(os.O_CLOEXEC); err_r,err_w = os.pipe2(os.O_CLOEXEC)
            gate_r,gate_w = os.pipe2(os.O_CLOEXEC); pipes += [out_r,out_w,err_r,err_w,gate_r,gate_w]
            argv = command(config,fds)
            prctl, original_parent = _prctl(),os.getpid()
            pid = os.fork()
            if pid == 0:
                try:
                    # Only trusted instructions occur before exec reset. No candidate import.
                    arm_parent_death(prctl,original_parent)
                    os.dup2(out_w,1); os.dup2(err_w,2)
                    null = os.open('/dev/null',os.O_RDONLY); os.dup2(null,0)
                    keep = set(fds.values())|{0,1,2,gate_r}
                    for namefd in os.listdir('/proc/self/fd'):
                        fd = int(namefd)
                        if fd not in keep:
                            try: os.close(fd)
                            except OSError: pass
                    resource.setrlimit(resource.RLIMIT_CORE,(0,0))
                    resource.setrlimit(resource.RLIMIT_CPU,(caps['child_cpu_seconds'],caps['child_cpu_seconds']))
                    resource.setrlimit(resource.RLIMIT_FSIZE,(caps['tmpfs_bytes'],caps['tmpfs_bytes']))
                    if os.read(gate_r,1) != b'G': os._exit(125)
                    os.close(gate_r)
                    for fd in fds.values(): os.set_inheritable(fd,True)
                    # The ELF executable FD is consumed by exec before CLOEXEC applies.
                    os.set_inheritable(fds['bwrap'],False)
                    os.execve(argv[0],argv,{'PATH':'/usr/bin','LANG':'C.UTF-8'})
                except BaseException:
                    os._exit(126)
            for fd in (out_w,err_w,gate_r): os.close(fd); pipes.remove(fd)
            pidfd = os.pidfd_open(pid,0)
            write(groupfd,'cgroup.procs',str(pid))
            need(read(groupfd,'cgroup.procs').split() == [str(pid)],'Stopped-gate child joined before exec')
            admitted = True
            need(os.write(gate_w,b'G') == 1,'Explicit exec gate release')
            os.close(gate_w); pipes.remove(gate_w)
            for fd,target,cap,key in ((out_r,stdout,caps['request_stdout_bytes'],'stdout_bytes'),
                                      (err_r,stderr,caps['request_stderr_bytes'],'stderr_bytes')):
                os.set_blocking(fd,False); selector.register(fd,selectors.EVENT_READ,(target,cap,key))
            while selector.get_map() or status is None:
                need(time.monotonic() < deadline,'Per-request/global deadline')
                for selected,_ in selector.select(min(.05,max(0,deadline-time.monotonic()))):
                    target,cap,key = selected.data
                    remaining = meter.caps[key]-meter.values[key]
                    need(remaining > 0,'Cumulative transport headroom before read/EOF probe')
                    extent = min(65536,cap-len(target)+1,remaining)
                    chunk = os.read(selected.fd,extent)
                    meter.observed[key] += len(chunk)
                    meter.charge(key,len(chunk))
                    if not chunk:
                        selector.unregister(selected.fd); os.close(selected.fd); pipes.remove(selected.fd)
                    else:
                        need(len(target)+len(chunk) <= cap,'Bounded prediction/diagnostic transport')
                        target.extend(chunk)
                if status is None:
                    waited, rawstatus = os.waitpid(pid,os.WNOHANG)
                    if waited: status = rawstatus
            natural = os.WIFEXITED(status) and os.WEXITSTATUS(status) == 0
            need(natural,'Candidate/bubblewrap must exit naturally with zero status')
            after = counters(read(groupfd,'memory.events'))
            need(after.get('oom_kill',0) == before.get('oom_kill',0) == 0
                 and counters(read(groupfd,'cgroup.events')).get('populated') == 0,
                 'All owned descendants absent without OOM')
            observation = {'natural_exit_zero':True,'owned_processes_absent':True,
                           'cgroup_name':name,'cgroup_inode':os.fstat(groupfd).st_ino,
                           'cgroup_device':os.fstat(groupfd).st_dev,'memory_events':after,
                           'cpu_stat':counters(read(groupfd,'cpu.stat')),
                           'elapsed_seconds':time.monotonic()-child_started,
                           'stdout_bytes':len(stdout),'stderr_bytes':len(stderr),
                           'stderr_sha256':sha(stderr),'stderr_prefix_base64':base64.b64encode(stderr[:1024]).decode(),
                           'gate_joined_before_exec':True,'pidfd_owned':True}
        except BaseException as exc:
            error = exc
        finally:
            selector.close()
            # Release a still-blocked trusted child before cleanup; EOF makes it exit.
            for fd in list(pipes):
                try: os.close(fd)
                except OSError: pass
            if groupfd is not None:
                try:
                    if counters(read(groupfd,'cgroup.events')).get('populated') != 0:
                        write(groupfd,'cgroup.kill','1')
                    while counters(read(groupfd,'cgroup.events')).get('populated') != 0:
                        need(time.monotonic() < cleanup_deadline,'Owned cgroup closure deadline')
                        time.sleep(.01)
                except BaseException as exc:
                    error = error or exc
            if pid is not None and status is None:
                try:
                    # Stable pidfd only; never signal a reaped/reused numeric PID.
                    if pidfd is not None: signal.pidfd_send_signal(pidfd,signal.SIGKILL)
                except ProcessLookupError: pass
                try:
                    while status is None:
                        waited,rawstatus = os.waitpid(pid,os.WNOHANG)
                        if waited: status = rawstatus; break
                        need(time.monotonic() < cleanup_deadline,'Owned child reap deadline')
                        time.sleep(.01)
                except BaseException as exc: error = error or exc
            if pidfd is not None: os.close(pidfd)
            if groupfd is not None: os.close(groupfd)
            try:
                os.rmdir(name,dir_fd=parentfd)
            except FileNotFoundError: pass
            except BaseException as exc: error = error or exc
            os.close(parentfd)
        if error is not None: raise error
        need(admitted and natural,'No transport released without complete native closure')
        return bytes(stdout),observation


@dataclass(frozen=True)
class FeatureHandle:
    token: str


def fail_latched(method):
    def guarded(self,*args,**kwargs):
        try: return method(self,*args,**kwargs)
        except BaseException:
            self.failed = True
            raise
    return guarded


class NativeProvider:
    def __init__(self,config,admission,*,evidence_root):
        self.config = config_snapshot(config); self.admission = admission_snapshot(self.config,admission)
        need(self.config['provider_source_sha256'] == identity(),'Actual provider source identity')
        LinuxBackend.require_platform()  # Before evidence creation, private inputs or launch.
        self.backend = LinuxBackend(); self.caps = self.config['caps']; self.meter = Meter(self.caps)
        self.failed = False; self.closed = False; self.feature = None; self.owned = []
        self.candidate_sha256 = self.config['candidate_sha256']
        self.provider_source_sha256 = self.config['provider_source_sha256']; self.condition = self.config['condition']
        remaining = self.admission['admitted_until_unix']-time.time()
        self.deadline = time.monotonic()+min(self.caps['run_seconds'],remaining)-self.caps['cleanup_seconds']
        need(self.deadline > time.monotonic(),'Whole-run cleanup reserve')
        root = safe_path(evidence_root)
        root.mkdir(mode=0o700,parents=False,exist_ok=False)
        self.root = root; self.journal = None; self.stage = root/'staging'
        self.journal_hash = hashlib.sha256(); self.fds = {}
        try:
            fd = os.open(root/'LIFECYCLE.jsonl',os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_CLOEXEC,0o600)
            try: self.journal = os.fdopen(fd,'wb',buffering=0)
            except BaseException:
                os.close(fd)
                raise
            self.stage.mkdir(mode=0o700)
            for key in ('runtime','candidate','assistance'):
                fd,manifest,_ = authenticate_tree(self.config[key],key,self.meter,self.caps['working_bytes'])
                self.owned.append(fd); self.fds[key] = fd
                need(manifest['condition'] == ('generic' if key == 'runtime' else self.condition),'Exact information-arm tree binding')
                if key == 'runtime':
                    need({'input','candidate','artifacts','executor','tmp','proc','dev'} <= set(manifest['directories'])
                         and self.config['python_path'][1:] in {r['path'] for r in manifest['files']},
                         'Generic rootfs with explicit empty mount slots and interpreter')
                    slots = {'input/features.npy','input/responses.bin','input/request.json','executor/entry.py'}
                    slotfiles = {r['path']:r for r in manifest['files']
                                 if r['path'].split('/')[0] in {'input','candidate','artifacts','executor','tmp','proc','dev'}}
                    need(set(slotfiles) == slots and all(r['bytes'] == 0 for r in slotfiles.values()),
                         'Exact empty readonly-root mount-slot placeholders; no hidden data/methods')
                if key == 'candidate': need('candidate.py' in {r['path'] for r in manifest['files']},'Frozen candidate entry')
            bwrap = self.config['bwrap']
            need(4*bwrap['bytes']+4*1024**2 <= self.caps['working_bytes'],
                 'Complete binary read/staging workspace before executable I/O')
            raw,_ = read_owned(bwrap['path'],bwrap['bytes'],bwrap['sha256'],self.meter,'tree_read_bytes',executable=True)
            need(raw.startswith(b'\x7fELF'),'Native non-setuid pinned ELF bubblewrap')
            # Keep a sealed executable image so its path cannot be rebound after authentication.
            self.fds['bwrap'] = sealed(raw,self.meter); self.owned.append(self.fds['bwrap'])
            entry,_ = read_owned(HERE/'participant_entry.py',(HERE/'participant_entry.py').stat().st_size,
                                ENTRY_SHA256,self.meter,'tree_read_bytes',readonly=False)
            self.fds['entry'] = self._stage_file('entry.py',entry); self.owned.append(self.fds['entry'])
            self._journal({'event':'open','mode':MODE,'config_sha256':sha(encoded(self.config)),
                           'admission':self.admission,'scientific_qualification':False})
        except BaseException:
            self.failed = True; self.close(); raise

    def _check(self):
        need(not self.failed and not self.closed and time.monotonic() < self.deadline,'Live unfailed admitted provider')

    def _stage_file(self,name,raw):
        """Ordinary private file for bwrap bind-fd; never an anonymous memfd mount.

        All write handles are closed before the readonly FD is returned. Host
        immutability is a qualified trusted-operator requirement, not an inode
        seal against a hostile same-UID host process.
        """
        self.meter.charge('staging_bytes',len(raw))
        path = self.stage/name
        fd = os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,0o600)
        try:
            at = 0
            while at < len(raw):
                size = os.write(fd,memoryview(raw)[at:]); need(size > 0,'Staging progress'); at += size
            os.fsync(fd); os.fchmod(fd,0o444)
        finally: os.close(fd)
        return os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC)

    def _journal(self,value):
        raw = encoded(value); need(len(raw) <= 8192,'Bounded lifecycle record')
        self.meter.charge('journal_bytes',len(raw))
        need(self.journal.write(raw) == len(raw),'Complete lifecycle record write')
        self.journal_hash.update(raw)

    @fail_latched
    def prepare_feature(self,path,spec,*,rows):
        self._check(); need(self.feature is None,'Exactly one source job feature alive')
        need(type(spec) is dict and len(spec) <= 16 and {'sha256','bytes','fortran_order'} <= set(spec)
             and digest(spec['sha256']) and integer(spec['bytes'],1)
             and type(spec['fortran_order']) is bool and integer(rows,2,144111),'Primitive exact feature spec')
        need(rows*240+1 <= spec['bytes'] <= rows*240+8192
             and 8*spec['bytes']+65536 <= self.caps['working_bytes'],'Feature pre-I/O workspace')
        self.meter.charge('max_jobs',1)
        try:
            raw,_ = read_owned(path,spec['bytes'],spec['sha256'],self.meter,'feature_read_bytes')
            PUBLIC.feature(raw,rows,spec['fortran_order'])
            fd = self._stage_file('feature.npy',raw)
            handle = FeatureHandle(uuid.uuid4().hex)
            self.feature = (handle,fd,{'sha256':spec['sha256'],'bytes':len(raw),
                                     'fortran_order':spec['fortran_order'],'rows':rows})
            return handle
        except BaseException:
            self.failed = True; raise

    @fail_latched
    def run_request(self,handle,bundle,descriptor):
        self._check(); need(self.feature is not None and handle is self.feature[0],'Owned active source feature handle')
        _,featurefd,feature = self.feature
        need(type(bundle) is bytes and len(bundle) <= self.caps['bundle_bytes'],'Bounded immutable permitted bundle')
        if type(descriptor) is dict:
            need(set(descriptor) == {'public_json','public_id'},'Exact descriptor carrier')
            raw,request_id = descriptor['public_json'],descriptor['public_id']
        else:
            raw,request_id = descriptor.public_json,descriptor.public_id
        need(type(raw) is bytes and len(raw) <= 8192 and digest(request_id) and sha(raw) == request_id,
             'Immutable content-bound public descriptor')
        need(8*(len(bundle)+feature['bytes'])+128*feature['rows']+65536
             +2*self.caps['request_stdout_bytes']+2*self.caps['request_stderr_bytes'] <= self.caps['working_bytes'],
             'Full transport/decode/staging workspace before decode or launch')
        value = parse(raw)
        need(type(value) is dict and type(value.get('context')) is dict,'Public context')
        context = dict(value['context']); context.pop('held_qid',None)
        need(set(context) == {'session','field','family','layer','lag_index','lag_bins'},'Exact source context keys')
        expected = B.make_descriptor(bundle,B.V.JobContext(**context),feature_sha256=feature['sha256'],
                    feature_bytes=feature['bytes'],feature_fortran_order=feature['fortran_order'],
                    byte_limit=self.caps['bundle_bytes'],working_limit=self.caps['working_bytes'])
        need(expected.public_json == raw and expected.public_id == request_id,'Actual selected feature/bundle/context identity')
        need(value['features']['shape'] == [feature['rows'],30],'Feature/bundle row geometry')
        need(self.meter.values['journal_bytes']+16384 <= self.caps['journal_bytes'],'Two complete lifecycle records reserved before launch')
        self.meter.charge('max_requests',1)
        self.meter.charge('visible_input_bytes',feature['bytes']+len(bundle)+len(raw))
        temporary = []
        try:
            bundlefd = sealed(bundle,self.meter); temporary.append(bundlefd)
            descriptorfd = sealed(raw,self.meter); temporary.append(descriptorfd)
            # bwrap --ro-bind-data makes a second copy inside its namespace.
            self.meter.charge('sandbox_copy_bytes',len(bundle)+len(raw))
            fds = dict(self.fds,feature=featurefd,bundle=bundlefd,descriptor=descriptorfd)
            self._journal({'event':'start','request':self.meter.values['max_requests'],'request_sha256':request_id,
                           'feature_bytes':feature['bytes'],'bundle_bytes':len(bundle),'descriptor_bytes':len(raw)})
            deadline = min(self.deadline,time.monotonic()+self.caps['per_request_seconds'])
            prediction,observation = self.backend.invoke(self.config,fds,deadline,self.meter)
            need(type(prediction) is bytes and observation.get('natural_exit_zero') is True
                 and observation.get('owned_processes_absent') is True,'Complete provider closure before release')
            for fd in temporary: os.close(fd)
            temporary.clear()
            closure = {'schema':'language-private-invocation-closure/v1','request_sha256':request_id,
                       'candidate_sha256':self.candidate_sha256,'provider_source_sha256':self.provider_source_sha256,
                       'natural_exit_zero':True,'owned_processes_absent':True,'private_view_retired':True,
                       'transport_sha256':sha(prediction)}
            self._journal({'event':'closed','request':self.meter.values['max_requests'],
                           'closure':closure,'observation':observation})
            return prediction,closure
        except BaseException as exc:
            self.failed = True
            try: self._journal({'event':'failed','request':self.meter.values['max_requests'],
                               'request_sha256':request_id,'error_type':type(exc).__name__,
                               'transport_released':False,'closure_qualified':False})
            except BaseException: pass
            raise
        finally:
            for fd in temporary:
                try: os.close(fd)
                except OSError: pass

    def release_feature(self,handle):
        need(self.feature is not None and handle is self.feature[0],'Exact owned feature retirement')
        try:
            os.close(self.feature[1]); (self.stage/'feature.npy').unlink()
        finally: self.feature = None

    def finish(self):
        self._check(); need(self.feature is None,'All job feature handles retired before finish')
        receipt = {'schema':'language-exec-provider-receipt/v1','mode':MODE,
                   'candidate_sha256':self.candidate_sha256,'provider_source_sha256':self.provider_source_sha256,
                   'condition':self.condition,'config_sha256':sha(encoded(self.config)),
                   'admission':self.admission,'counters':dict(self.meter.values),
                   'observed_source_and_kernel_bytes':dict(self.meter.observed),
                   'scientific_qualification':False,'full_campaign_completeness':'coordinator_must_verify',
                   'qualification_basis':'externally_retained_native_qualification_not_this_source_suite',
                   'logical_visibility_is_not_total_child_memory_or_filesystem_reads':True}
        self._journal({'event':'finish','counters_before_finish_record':dict(self.meter.values)})
        receipt['counters'] = dict(self.meter.values)
        receipt['lifecycle'] = {'path':'LIFECYCLE.jsonl','bytes':self.meter.values['journal_bytes'],
                                'sha256':self.journal_hash.hexdigest()}
        self.close()
        return receipt

    def close(self):
        if self.closed:
            return
        error = None
        if self.feature is not None:
            try: self.release_feature(self.feature[0])
            except BaseException as exc: error = error or exc
        for fd in self.owned:
            try: os.close(fd)
            except BaseException as exc: error = error or exc
        self.owned = []
        try:
            (self.stage/'entry.py').unlink(missing_ok=True)
            (self.stage/'feature.npy').unlink(missing_ok=True)
            self.stage.rmdir()
        except FileNotFoundError: pass
        except BaseException as exc: error = error or exc
        try:
            if self.journal is not None and not self.journal.closed:
                try: self.journal.flush(); os.fsync(self.journal.fileno())
                finally: self.journal.close()
        except BaseException as exc: error = error or exc
        self.closed = True
        if error is not None: self.failed = True; raise error
