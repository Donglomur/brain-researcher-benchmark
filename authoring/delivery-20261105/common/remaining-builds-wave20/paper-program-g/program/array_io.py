"""Trusted typed array transport; no payload access on import."""
from pathlib import Path
from common import *

def open_array(desc,budget,shape,dtype):
    import numpy as np
    read(desc['path'],desc,budget,desc['bytes'],retain=False)
    a=np.load(ordinary(desc['path']),allow_pickle=False,mmap_mode='r');need(a.shape==tuple(shape) and a.dtype==np.dtype(dtype),'exact typed full array');return a

def save_array(path,a,budget):
    import numpy as np
    need(type(a)is np.ndarray and a.dtype.kind in 'fiub' and not a.dtype.hasobject,'ordinary numeric array')
    path=ordinary(path);mkdir_owned(path.parent,budget);budget.reserve(path.parent,a.nbytes+131072);budget.writing(a.nbytes+131072)
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o400)
    try:
        with os.fdopen(fd,'wb',closefd=False)as f:np.lib.format.write_array(f,a,allow_pickle=False);f.flush();os.fsync(fd)
        os.fchmod(fd,0o444)
    finally:os.close(fd)
    sync(path.parent);return {'path':str(path),**captured(path,budget,a.nbytes+131072)}

def raw_panel(desc,rows,columns,budget):
    import numpy as np
    need(desc['bytes']==8*rows*columns,'exact complete raw probability panel');read(desc['path'],desc,budget,desc['bytes'],retain=False);a=np.memmap(ordinary(desc['path']),dtype='<f8',mode='r',shape=(rows,columns))
    for start in range(0,rows,128):
        block=a[start:start+128];budget.reading(block.nbytes);need(np.isfinite(block).all() and (block>=0).all() and (block<=1).all(),'every submitted probability finite in[0,1]')
    return a
