"""Small source-authentication entry shared by observer and worker."""
import hashlib,json,os,stat,types
from pathlib import Path
def initial(path,cap):
    path=Path(path).absolute()
    if any(p.is_symlink() for p in (path,*path.parents)):raise ValueError('source path')
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        a=os.fstat(fd)
        if not stat.S_ISREG(a.st_mode) or a.st_nlink!=1 or not 0<a.st_size<=cap:raise ValueError('source extent')
        raw=os.read(fd,a.st_size+1);z=os.fstat(fd);n=path.lstat()
        if len(raw)!=a.st_size or any(getattr(a,k)!=getattr(z,k) or getattr(z,k)!=getattr(n,k) for k in ('st_dev','st_ino','st_mode','st_nlink','st_size','st_mtime_ns','st_ctime_ns')):raise ValueError('source changed')
        return raw
    finally:os.close(fd)
def load(here,pin,deadline):
    raw=initial(here/'SOURCE_MANIFEST.json',65536)
    if {'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}!=pin:raise ValueError('external source pin')
    manifest=json.loads(raw);expected=manifest['files']['common.py'];body=initial(here/'common.py',100000)
    if {'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()}!=expected:raise ValueError('common source pin')
    c=types.ModuleType('neural083_common');c.__file__=str(here/'common.py');exec(compile(body,c.__file__,'exec'),c.__dict__)
    manifest,bodies,cost=c.load(here/'SOURCE_MANIFEST.json',pin,deadline)
    if bodies['bootstrap.py']!=initial(here/'bootstrap.py',100000):raise ValueError('selected bootstrap')
    return c,manifest,bodies,cost+len(raw)+len(body)+len(bodies['bootstrap.py'])+3
