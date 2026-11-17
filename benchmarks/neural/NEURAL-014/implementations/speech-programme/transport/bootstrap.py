"""Pinned small authenticator; every runtime module is captured before use."""
import hashlib,json,os,stat,time,types
from pathlib import Path

def initial(path,cap,deadline):
    if time.monotonic()>=deadline:raise TimeoutError('original source capture deadline')
    path=Path(path).absolute()
    if any(p.is_symlink() for p in (path,*path.parents)):raise ValueError('source path')
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        a=os.fstat(fd)
        if not stat.S_ISREG(a.st_mode) or a.st_nlink!=1 or not 0<a.st_size<=cap:raise ValueError('source extent')
        raw=os.read(fd,a.st_size+1);z=os.fstat(fd);n=path.lstat()
        if len(raw)!=a.st_size or any(getattr(a,k)!=getattr(z,k) or getattr(z,k)!=getattr(n,k) for k in ('st_dev','st_ino','st_mode','st_nlink','st_size','st_mtime_ns','st_ctime_ns')):raise ValueError('source changed')
        if time.monotonic()>=deadline:raise TimeoutError('original source capture deadline')
        return raw
    finally:os.close(fd)

def load(root,pin,deadline):
    raw=initial(root/'SOURCE_MANIFEST.json',262144,deadline)
    if {'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}!=pin:raise ValueError('external source pin')
    manifest=json.loads(raw);expected=manifest['files']['transport/common.py'];body=initial(root/'transport/common.py',100000,deadline)
    if {'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()}!=expected:raise ValueError('common source pin')
    c=types.ModuleType('neural014_common');c.__file__=str(root/'transport/common.py');exec(compile(body,c.__file__,'exec'),c.__dict__)
    manifest,bodies,cost=c.load(root/'SOURCE_MANIFEST.json',pin,deadline)
    return c,manifest,bodies,cost+len(raw)+len(body)+2
