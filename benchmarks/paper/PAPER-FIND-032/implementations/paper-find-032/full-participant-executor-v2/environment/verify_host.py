"""Future constructed-host ABI check; no neural data, fitting, or native claim."""
import argparse
import hashlib
import importlib
import json
import os
from pathlib import Path
import platform
import stat
import sys


def need(value,message):
    if not value:
        raise RuntimeError(message)


ORIGINAL_ERRORS=[]


def capture(path,maximum):
    need(path.is_absolute() and not any(p.is_symlink() for p in (path,*path.parents)),
         'absolute unlinked verification source')
    before=path.lstat()
    need(stat.S_ISREG(before.st_mode) and before.st_nlink==1 and before.st_size<=maximum,
         'bounded ordinary verification source')
    identity=lambda x:(x.st_dev,x.st_ino,x.st_mode,x.st_nlink,x.st_size,x.st_mtime_ns,x.st_ctime_ns)
    fd=None;parts=[];first=None;secondary=None
    try:
        fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC)
        need(identity(before)==identity(os.fstat(fd)),'opened verification source identity')
        left=before.st_size
        while left:
            raw=os.read(fd,min(left,65536));need(bool(raw),'short verification source')
            parts.append(raw);left-=len(raw)
        need(not os.read(fd,1),'verification source grew')
        need(identity(before)==identity(os.fstat(fd))==identity(path.lstat()),'stable verification source')
    except BaseException as error:first=error
    finally:
        if fd is not None:
            try:os.close(fd)
            except BaseException as error:secondary=error
    if first is not None:
        if secondary is not None:first.add_note('Secondary verification close: '+repr(secondary))
        ORIGINAL_ERRORS.append((first,secondary,tuple(parts)));raise first
    if secondary is not None:
        ORIGINAL_ERRORS.append((secondary,None,tuple(parts)));raise secondary
    return b''.join(parts)


def executable_pin(path):
    need(not any(p.is_symlink() for p in (path,*path.parents)),'unlinked executable pin')
    before=path.lstat()
    need(stat.S_ISREG(before.st_mode) and before.st_nlink==1 and before.st_uid==0 and
         stat.S_IMODE(before.st_mode)==0o755 and 0<before.st_size<=134217728,'finite executable pin')
    identity=lambda x:(x.st_dev,x.st_ino,x.st_mode,x.st_nlink,x.st_size,x.st_mtime_ns,x.st_ctime_ns)
    fd=None;first=None;secondary=None;prefix=b'';digest=hashlib.sha256();count=0
    try:
        fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC)
        need(identity(before)==identity(os.fstat(fd)),'opened executable identity')
        while count<before.st_size:
            prefix=os.read(fd,min(65536,before.st_size-count));need(bool(prefix),'short executable')
            digest.update(prefix);count+=len(prefix)
        need(not os.read(fd,1),'executable extent grew')
        need(identity(before)==identity(os.fstat(fd))==identity(path.lstat()),'stable emitted executable pin')
    except BaseException as error:first=error
    finally:
        if fd is not None:
            try:os.close(fd)
            except BaseException as error:secondary=error
    if first is not None:
        if secondary is not None:first.add_note('Secondary executable close: '+repr(secondary))
        ORIGINAL_ERRORS.append((first,secondary,prefix,count));raise first
    if secondary is not None:
        ORIGINAL_ERRORS.append((secondary,None,prefix,count));raise secondary
    return {'bytes':count,'sha256':digest.hexdigest(),'mode':stat.S_IMODE(before.st_mode)}


def main():
    parser=argparse.ArgumentParser(allow_abbrev=False)
    parser.add_argument('--environment-lock',type=Path,required=True)
    args=parser.parse_args()
    prefix=Path('/opt/find032-host/python-3.11.11')
    python=prefix/'bin/python3.11'
    numerical=prefix/'lib/python3.11/site-packages'
    need(sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
         'actual reference -I -S -B import shape')
    need(platform.system()=='Linux' and platform.machine()=='x86_64' and os.geteuid()==0,
         'actual selected host architecture/root')
    need(platform.python_version()=='3.11.11' and Path(sys.executable)==python,
         'actual fixed-prefix CPython')
    need(not any(p.is_symlink() for p in (python,*python.parents)), 'ordinary runtime executable')
    s=python.lstat()
    need(stat.S_ISREG(s.st_mode) and s.st_nlink==1 and s.st_uid==0 and stat.S_IMODE(s.st_mode)==0o755,
         'ordinary root-owned runtime binary')
    need(numerical.is_dir() and not numerical.is_symlink(), 'actual explicit numerical root')
    need(os.environ.get('R_HOME')=='/usr/lib/R' and os.environ.get('LD_LIBRARY_PATH')=='/usr/lib/R/lib'
         and os.environ.get('TZ')=='UTC','actual reference native environment')
    raw=capture(args.environment_lock,77230)
    need(len(raw)==77230 and hashlib.sha256(raw).hexdigest()==
         '1f70006eb7965e7f70188295adf24a0711db927aabc8c736db638f426ab15e60','exact accepted lock')
    lock=json.loads(raw)
    need(lock['schema']=='find032_environment_inputs_v1' and lock['python']=='3.11.11','same accepted lock')
    sys.path.append(str(numerical))
    # The accepted verifier checks all35 distributions, exact versions/active
    # dependency edges, all six imports and R/BayesFactor exports. Repeat its
    # actual fixed source under -S, after adding only the explicit numerical root.
    verifier=args.environment_lock.parent/'verify_environment.py'
    body=capture(verifier,4848)
    need(len(body)==4848 and hashlib.sha256(body).hexdigest()==
         'c124311ed3634d01dccb0c4b56e7d633e6472a0ab0765ab722cf5234dfd2225b',
         'unchanged exact accepted environment verifier')
    namespace={'__name__':'find032_host_environment_verifier','__file__':str(verifier)}
    exec(compile(body,str(verifier),'exec'),namespace)
    old=sys.argv
    try:
        sys.argv=[str(verifier),'--lock',str(args.environment_lock)]
        namespace['main']()
    finally:
        sys.argv=old
    selected_pin=executable_pin(python)
    print(json.dumps({'schema':'find032_host_runtime_selection_v1','python':str(python),
        'python_pin':selected_pin,
        'numerical_search_roots':[str(numerical)],
        'runtime_environment':{'R_HOME':'/usr/lib/R','LD_LIBRARY_PATH':'/usr/lib/R/lib','TZ':'UTC'},
        'cpython_prefix_relocated':False,'native_qualification':False,'scientific_qualification':False},sort_keys=True))


if __name__=='__main__':
    main()
