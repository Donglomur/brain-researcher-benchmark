"""Finite protected task file effects; no overwrite, cleanup, or data discovery."""
import ctypes
import hashlib
import os
import stat
import time
from pathlib import Path
from find032.core import Custody, encode_json
from find032_runtime.failure_evidence import _exception
from .schema import need, path

ORIGINALS = []


def identity(s):
    return (s.st_dev, s.st_ino, s.st_mode, s.st_nlink, s.st_size, s.st_mtime_ns, s.st_ctime_ns)


def root(name, custody):
    p = path(str(name)); fd = None
    try:
        fd = os.open(p, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
        need(stat.S_ISDIR(os.fstat(fd).st_mode), 'ordinary opened root')
        return fd
    except BaseException as error:
        custody.catch('open task root', error)
        if fd is not None: custody.close('failed root descriptor', lambda: os.close(fd))
        custody.raise_first()


def directory_identity(fd):
    selected=os.fstat(fd)
    need(stat.S_ISDIR(selected.st_mode) and selected.st_uid==0 and stat.S_IMODE(selected.st_mode)==0o700,
         'private original directory identity')
    return {'device':selected.st_dev,'inode':selected.st_ino,'uid':selected.st_uid,
            'gid':selected.st_gid,'mode':stat.S_IMODE(selected.st_mode)}


def join_directory(fd,expected):
    need(type(expected)is dict and directory_identity(fd)==expected,'same originally owned directory')


def join_named_directory(parent_fd,name,expected):
    selected=os.stat(name,dir_fd=parent_fd,follow_symlinks=False)
    need(stat.S_ISDIR(selected.st_mode) and
         {'device':selected.st_dev,'inode':selected.st_ino,'uid':selected.st_uid,'gid':selected.st_gid,
          'mode':stat.S_IMODE(selected.st_mode)}==expected,'same named original directory')


def read_at(fd, name, budget, custody, *, maximum, expected=None, mode=None, retain=True):
    need(type(name) is str and '/' not in name and name not in ('', '.', '..') and '\\' not in name and '\x00' not in name,
         'one finite file basename')
    need(type(maximum) is int and maximum > 0, 'selected bounded capture')
    local = Custody(custody); handle = None; parts = []; result = None
    try:
        token = budget.reserve('read', maximum)
        handle = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC, dir_fd=fd)
        before = os.fstat(handle)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and 0 < before.st_size <= maximum,
             'private ordinary bounded body')
        if mode is not None: need(stat.S_IMODE(before.st_mode) == mode, 'selected body mode')
        if expected is not None: need(before.st_size == expected['bytes'], 'selected exact body extent')
        digest = hashlib.sha256(); count = 0
        while count < before.st_size:
            budget.checkpoint(); b = os.read(handle, min(65536, before.st_size-count))
            need(bool(b), 'complete bounded capture'); digest.update(b); count += len(b)
            if retain: parts.append(b)
        after = os.fstat(handle); named = os.stat(name, dir_fd=fd, follow_symlinks=False)
        need(identity(before) == identity(after) == identity(named), 'stable original named body')
        observed = {'name':name,'bytes':count,'sha256':digest.hexdigest()}
        if expected is not None: need(observed['sha256'] == expected['sha256'], 'selected full-file digest')
        budget.observed(token, count); result = ((b''.join(parts) if retain else None), observed)
    except BaseException as error:
        if local.first is None: local.catch('protected body capture', error)
        ORIGINALS.append((error, parts))
    finally:
        if handle is not None: local.close('protected body close', lambda: os.close(handle))
    local.raise_first(); return result


def read_absolute(name, expected, budget, custody):
    p=path(name); fd=root(p.parent,custody); result=None
    try: result=read_at(fd,p.name,budget,custody,maximum=expected['bytes'],expected=expected,mode=expected['mode'])
    except BaseException as error:
        if custody.first is None: custody.catch('selected ordinary absolute read',error)
    finally: custody.close('absolute parent close',lambda:os.close(fd))
    custody.raise_first();return result


def write_at(fd,name,body,budget,custody):
    need(type(name)is str and name not in ('','.','..') and '/' not in name and '\\' not in name and '\x00' not in name,
         'one publication basename')
    need(type(body)is bytes,'exact publication bytes')
    local=Custody(custody); handle=None; count=0; result=None
    try:
        token=budget.reserve('write',len(body)); creation=budget.reserve('files',1)
        handle=os.open(name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,0o600,dir_fd=fd)
        budget.observed(creation,1)
        while count<len(body):
            budget.checkpoint();n=os.write(handle,memoryview(body)[count:count+65536])
            need(0<n<=min(65536,len(body)-count),'finite publication progress');count+=n
        os.fsync(handle);os.fchmod(handle,0o400);os.fsync(fd)
        s=os.fstat(handle);n=os.stat(name,dir_fd=fd,follow_symlinks=False)
        need(identity(s)==identity(n) and s.st_size==len(body) and s.st_nlink==1,'same complete publication')
        budget.observed(token,count)
        result={'name':name,'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()}
    except BaseException as error:
        if local.first is None:local.catch('create-only publication',error)
        ORIGINALS.append((error,name,body,count))
    finally:
        if handle is not None:local.close('publication close',lambda:os.close(handle))
    local.raise_first();return result


def errors(custody):
    # No exception repr, locals, private body, or credential is serialized.
    rows=[]
    for event in custody.events[:64]:
        rows.append({'index':event.index,'boundary':event.boundary[:160],'error':_exception(event.raw)})
    return {'occurrences':len(custody.events),'first64':rows,'truncated':len(custody.events)>64,
            'raw_objects_retained_only_in_current_process':True}


def rename_no_replace(source_parent,source_name,target_parent,target_name,budget,custody,*,
                      verified_output_fd,original_directories):
    """Linux renameat2(RENAME_NOREPLACE), selected only after real owner closure."""
    need(all(type(x)is str and x not in ('','.','..') and '/' not in x for x in (source_name,target_name)),
         'fixed no-replace directory transition')
    budget.checkpoint()
    join_directory(source_parent,original_directories['run'])
    join_directory(target_parent,original_directories['parent'])
    join_directory(verified_output_fd,original_directories['outputs'])
    join_named_directory(source_parent,source_name,original_directories['outputs'])
    token=budget.reserve('files',1)
    library=ctypes.CDLL(None,use_errno=True)
    function=library.renameat2
    function.argtypes=[ctypes.c_int,ctypes.c_char_p,ctypes.c_int,ctypes.c_char_p,ctypes.c_uint]
    function.restype=ctypes.c_int
    # A failed/unknown transition is not automatically retried or deleted.
    rc=function(source_parent,source_name.encode(),target_parent,target_name.encode(),1)
    if rc!=0:raise OSError(ctypes.get_errno(),'protected no-replace rename failed')
    budget.observed(token,1)
    join_directory(verified_output_fd,original_directories['outputs'])
    join_named_directory(target_parent,target_name,original_directories['outputs'])
    try:os.stat(source_name,dir_fd=source_parent,follow_symlinks=False)
    except FileNotFoundError:pass
    else:need(False,'source name absent after original no-replace transition')
    os.fsync(source_parent);os.fsync(target_parent);budget.checkpoint()
