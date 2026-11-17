"""Read-only non-object NPY access through one authenticated regular-file FD."""
import contextlib,hashlib,mmap,os,stat
from pathlib import Path
import numpy as np
from io_contract import require,sha256,exact
MAX_ARRAY=2_000_000_000
DTYPES=('<f8','<f4','<i8','<i4','<u4','<u2','|u1')


def descriptor(d):
    exact(d,('path','bytes','sha256','shape','dtype'))
    path=Path(d['path'])
    require(type(d['path']) is str and not path.is_absolute() and '..' not in path.parts and str(path)==d['path'],'relative canonical array path')
    require(type(d['bytes']) is int and 0<d['bytes']<=MAX_ARRAY,'array bytes')
    sha256(d['sha256']);require(type(d['shape']) is list and 1<=len(d['shape'])<=5,'array rank')
    require(all(type(n) is int and 0<n<=10_000_000 for n in d['shape']),'positive dimensions')
    require(d['dtype'] in DTYPES,'plain numeric dtype')
    return d


@contextlib.contextmanager
def array(root,d):
    descriptor(d);p=Path(root)
    require(not p.is_symlink(),'root symlink')
    for part in Path(d['path']).parts:
        p=p/part;require(not p.is_symlink(),'no array symlink')
    fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK); mm=None
    try:
        before=os.fstat(fd);require(stat.S_ISREG(before.st_mode) and before.st_size==d['bytes'],'exact regular array')
        with os.fdopen(os.dup(fd),'rb') as f:
            version=np.lib.format.read_magic(f);require(version in ((1,0),(2,0)),'NPY version')
            shape,fortran,dtype=np.lib.format._read_array_header(f,version,max_header_size=16384)
            offset=f.tell()
        require(not fortran and list(shape)==d['shape'] and dtype.str==d['dtype'] and not dtype.hasobject,'NPY shape/dtype/order')
        size=int(np.prod(shape,dtype=object))*dtype.itemsize
        require(offset+size==before.st_size,'no trailing or truncated array')
        os.lseek(fd,0,os.SEEK_SET);h=hashlib.sha256()
        while True:
            b=os.read(fd,1048576)
            if not b:break
            h.update(b)
        require(h.hexdigest()==d['sha256'],'array hash')
        mm=mmap.mmap(fd,0,access=mmap.ACCESS_READ)
        a=np.ndarray(shape=shape,dtype=dtype,buffer=mm,offset=offset)
        a.flags.writeable=False
        yield a
        after=os.fstat(fd)
        require(all(getattr(before,k)==getattr(after,k) for k in ('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns')),'stable mapped array')
        del a
    finally:
        if mm is not None:mm.close()
        os.close(fd)


def finite(a):
    flat=a.reshape(-1)
    for i in range(0,len(flat),131072):require(bool(np.isfinite(flat[i:i+131072]).all()),'finite array')


def snapshot(root,d,owned_store):
    """Copy into a fresh operator-owned store before target access.

    The producer must already be closed. This byte-only capture authenticates
    source before/after and the copy digest. Caller must never grant the producer
    access to owned_store; chmod is not a substitute for process isolation.
    """
    descriptor(d);p=Path(root)
    require(not p.is_symlink(),'root symlink')
    for part in Path(d['path']).parts:
        p=p/part;require(not p.is_symlink(),'source symlink')
    out=Path(owned_store)/d['path'];require(not out.exists() and not out.is_symlink(),'fresh snapshot')
    out.parent.mkdir(parents=True,exist_ok=True)
    fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        before=os.fstat(fd);require(stat.S_ISREG(before.st_mode) and before.st_size==d['bytes'],'snapshot exact regular input')
        h=hashlib.sha256();total=0
        with out.open('xb') as f:
            while True:
                b=os.read(fd,min(1048576,d['bytes']+1-total))
                if not b:break
                total+=len(b);require(total<=d['bytes'],'snapshot grew');h.update(b);f.write(b)
        after=os.fstat(fd)
        require(total==d['bytes'] and h.hexdigest()==d['sha256'],'snapshot bytes/hash')
        require(all(getattr(before,k)==getattr(after,k) for k in ('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns')),'snapshot input stable')
        out.chmod(0o444)
    finally:os.close(fd)
    return d


def describe(path,relative,shape,dtype):
    """Bounded hash of an owned completed numeric output, no array decode."""
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        s=os.fstat(fd);require(stat.S_ISREG(s.st_mode) and 0<s.st_size<=MAX_ARRAY,'owned regular array')
        h=hashlib.sha256()
        while True:
            b=os.read(fd,1048576)
            if not b:break
            h.update(b)
        t=os.fstat(fd);require(all(getattr(s,k)==getattr(t,k) for k in ('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns')),'owned output stable')
        return descriptor({'path':relative,'bytes':s.st_size,'sha256':h.hexdigest(),'shape':list(shape),'dtype':dtype})
    finally:os.close(fd)
