"""Managed bytes always pass the original read/write owners; no metadata-only source grant."""
import os,stat
from pathlib import Path
from .domain import need,pin,sha,encoded,parse,relative
from .runtime.common import capture

def read(root,descriptor,budget,maximum):
    pin(descriptor);p=Path(root)/descriptor['path']
    need(descriptor['bytes']<=maximum,'selected read bound before open')
    return capture(Path(root),dict(descriptor,mode='0o444',role='n057-original-selected-source'),budget,maximum)

def write(journal,name,raw,readonly=True):
    relative(name);p=journal.root/name
    if p.parent!=journal.root:p.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    row=journal.write(name,raw)
    need(row['status']=='complete' and row['closed'] and row['observed_bytes']==len(raw),'actual complete original write')
    if readonly:os.chmod(p,0o444)
    d={'path':name,'bytes':len(raw),'sha256':sha(raw)}
    need(read(journal.root,d,journal.budget,len(raw))==raw,'whole original readback')
    return d

def json_write(journal,name,value):return write(journal,name,encoded(value))

def array_bytes(array):
    import io,numpy as np
    need(type(array) is np.ndarray and array.dtype.kind in 'fiu' and np.isfinite(array).all(),'plain finite scientific array')
    out=io.BytesIO();np.save(out,array,allow_pickle=False);return out.getvalue()

def array_read(root,desc,budget,shape,maximum):
    import io,numpy as np
    raw=read(root,desc,budget,maximum);a=np.load(io.BytesIO(raw),allow_pickle=False)
    need(type(a) is np.ndarray and tuple(a.shape)==tuple(shape) and a.dtype.kind in 'fiu' and np.isfinite(a).all(),'whole original primitive array shape/dtype/values')
    return a

def source_closure(root,rows,budget):
    need(type(rows) is list and rows and len(rows)<=256,'finite complete source closure')
    expected={r['path'] for r in rows};need(len(expected)==len(rows),'unique source members')
    actual=[]
    for base,dirs,files in os.walk(root,followlinks=False):
        need(not any((Path(base)/n).is_symlink() for n in dirs+files),'no source aliases')
        actual.extend((Path(base)/n).relative_to(root).as_posix() for n in files)
        need(len(actual)<=256,'closed source census')
    need(set(actual)==expected,'exact source closure including runtime, no undeclared helper')
    return {r['path']:read(root,r,budget,1048576) for r in rows}
