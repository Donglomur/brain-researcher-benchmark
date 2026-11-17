"""Durable fixed-size external receipt slot, reused from reviewed observer."""
import os,stat,time
from pathlib import Path

def slot(path,raw,deadline,*,create,stamp=None):
    if time.monotonic()>=deadline or len(raw)>8192:raise ValueError('receipt deadline/extent')
    raw+=b' '*(8192-len(raw));flags=os.O_WRONLY|os.O_NOFOLLOW|os.O_NONBLOCK
    if create:flags|=os.O_CREAT|os.O_EXCL
    fd=os.open(path,flags,0o600)
    try:
        a=os.fstat(fd)
        if not stat.S_ISREG(a.st_mode) or a.st_nlink!=1:raise ValueError('ordinary receipt')
        if stamp is not None and (a.st_dev,a.st_ino,a.st_size,a.st_mode)!=(stamp.st_dev,stamp.st_ino,8192,stamp.st_mode):raise ValueError('same reserved receipt inode')
        off=0
        while off<len(raw):
            if time.monotonic()>=deadline:raise TimeoutError('receipt write deadline')
            n=os.pwrite(fd,raw[off:],off)
            if n<=0:raise ValueError('receipt progress')
            off+=n
        if time.monotonic()>=deadline:raise TimeoutError('receipt fsync deadline')
        os.fsync(fd);z=os.fstat(fd);named=Path(path).lstat()
        if z.st_size!=8192 or any(getattr(z,k)!=getattr(named,k) for k in ('st_dev','st_ino','st_mode','st_nlink','st_size','st_mtime_ns','st_ctime_ns')):raise ValueError('receipt stable durable inode')
    finally:os.close(fd)
    d=os.open(Path(path).parent,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:os.fsync(d)
    finally:os.close(d)
    if time.monotonic()>=deadline:raise TimeoutError('receipt durability deadline')
    return z
