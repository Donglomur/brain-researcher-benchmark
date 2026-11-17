"""Future authentic numerical I/O; imported numpy is supplied only by admitted native session."""
import hashlib
import os
import stat
from pathlib import Path
from .guard import need,ordinary,descriptor,bare,encoded

def verify_file(root,d,budget):
    descriptor(d);p=ordinary(root,d['path']);budget.charge('read_bytes',d['bytes']+1)
    fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK);h=hashlib.sha256();n=0
    try:
        before=os.fstat(fd);need(stat.S_ISREG(before.st_mode) and before.st_nlink==1 and before.st_size==d['bytes'],'exact data extent and ordinary mode')
        with os.fdopen(fd,'rb',closefd=False) as f:
            while True:
                budget.check();body=f.read(min(1024*1024,d['bytes']+1-n))
                if not body:break
                n+=len(body);h.update(body);need(n<=d['bytes'],'data beyond descriptor')
        fields=('st_dev','st_ino','st_size','st_nlink','st_mtime_ns','st_ctime_ns');after=os.fstat(fd);named=p.lstat()
        need(all(getattr(before,k)==getattr(after,k)==getattr(named,k) for k in fields),'data identity stable')
        need(n==d['bytes'] and h.hexdigest()==d['sha256'],'actual data bytes match admitted descriptor');budget.check();return p
    finally:os.close(fd)

def load_array(np,root,d,shape,budget,*,allow_undefined=False):
    p=verify_file(root,d,budget);budget.charge('read_bytes',d['bytes'])
    a=np.load(p,allow_pickle=False)
    need(type(a)is np.ndarray and list(a.shape)==list(shape),'exact source array shape')
    need(a.dtype.kind in ('f','i','u') and not a.dtype.hasobject,'plain numeric data only')
    need(bool((~np.isinf(a)).all()) and (allow_undefined or bool(np.isfinite(a).all())),'finite raw input or explicit derived undefined values; no hidden omission')
    verify_file(root,d,budget);return a

def save_array(np,publisher,name,array):
    need(name.endswith('.npy'),'native array suffix');p=ordinary(publisher.root,name)
    need(p.parent==publisher.root,'flat array output')
    need(array.dtype.kind in ('f','i','u','b') and not array.dtype.hasobject,'plain numeric output')
    # NaN is retained for declared undefined statistics; never serialized as JSON NaN.
    publisher.budget.charge('write_bytes',int(array.nbytes)+4096)
    record={'path':name,'complete':False,'maximum_header_reservation':4096};publisher.outputs.append(record)
    try:
        with p.open('xb') as f:np.save(f,array,allow_pickle=False);f.flush();os.fsync(f.fileno())
        publisher.budget.check();n=p.stat().st_size;need(n<=int(array.nbytes)+4096,'reserved NPY extent')
        h=hashlib.sha256()
        publisher.budget.charge('read_bytes',n+1)
        with p.open('rb') as f:
            for chunk in iter(lambda:f.read(65536),b''):publisher.budget.check();h.update(chunk)
        record.update(bytes=n,sha256=h.hexdigest(),complete=True,shape=list(array.shape),dtype=array.dtype.str)
        return {k:record[k] for k in ('path','bytes','sha256')}
    except BaseException as e:e.known_output_prefix=publisher.state();raise

def finite_json(value):
    import math
    if hasattr(value,'item'):value=value.item()
    if isinstance(value,float) and not math.isfinite(value):return None
    if isinstance(value,dict):return {str(k):finite_json(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [finite_json(v) for v in value]
    return value
