"""Exact trusted portable stager under the selected task's dependency versions."""
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import stat
import sys


def main():
    for name,version in [('numpy','2.2.6'),('h5py','3.13.0')]:
        if importlib.metadata.version(name)!=version:raise ValueError('Exact trusted staging dependencies')
    p=Path(sys.argv[1]).absolute();expected=json.loads(sys.argv[2])
    if any(x.is_symlink()for x in (p,*p.parents)):raise ValueError('Unlinked operator source')
    fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    with os.fdopen(fd,'rb')as f:
        a=os.fstat(f.fileno())
        if not(stat.S_ISREG(a.st_mode) and a.st_nlink==1 and 0<a.st_size<=100000):raise ValueError('Bounded source')
        raw=f.read(a.st_size+1);z=os.fstat(f.fileno());n=p.lstat()
    if len(raw)!=a.st_size or any(getattr(a,k)!=getattr(z,k)or getattr(a,k)!=getattr(n,k)for k in ('st_dev','st_ino','st_size','st_nlink','st_mtime_ns','st_ctime_ns')):raise ValueError('Stable source')
    if {'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}!={k:expected[k]for k in ('bytes','sha256')}:raise ValueError('Exact accepted operator')
    sys.argv=[str(p),*sys.argv[3:]]
    exec(compile(raw,str(p),'exec'),{'__name__':'__main__','__file__':str(p)})


if __name__=='__main__':main()
