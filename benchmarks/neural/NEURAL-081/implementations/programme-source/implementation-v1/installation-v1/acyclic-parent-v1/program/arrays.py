"""Primitive NPY transport. NumPy is imported only in a qualified numeric role."""
import ast,hashlib,os,stat,struct
from pathlib import Path
import common as c

def numpy():
    import numpy as np
    return np

def exact_array(a,dtype,shape):
    np=numpy();c.need(type(a)is np.ndarray and a.dtype==np.dtype(dtype)and a.shape==tuple(shape)and a.dtype.kind in 'fiu','exact primitive array shape/dtype')
    c.need(bool(np.isfinite(a).all()),'finite complete numeric array');return a

DTYPES={'float32':('f',4),'float64':('f',8),'int32':('i',4),'int64':('i',8),'uint32':('u',4),'uint64':('u',8)}

def expected_extent(dtype,shape):
    c.need(type(dtype)is str and dtype in DTYPES and type(shape)is list,'fixed primitive dtype/shape metadata')
    count=1
    for n in shape:count*=c.integer(n,1)
    return count*DTYPES[dtype][1]

def npy_header(raw,dtype,shape):
    """Validate bounded header and exact payload before any numerical loading."""
    expected=expected_extent(dtype,shape)
    c.need(type(raw)is bytes and len(raw)>=10 and raw[:6]==b'\x93NUMPY','ordinary NPY magic')
    version=raw[6:8]
    c.need(version in (b'\x01\x00',b'\x02\x00'),'only bounded ordinary NPYv1/v2')
    prefix=10 if version==b'\x01\x00'else 12
    c.need(len(raw)>=prefix,'complete NPY length field')
    length=struct.unpack('<H'if prefix==10 else'<I',raw[8:prefix])[0]
    c.need(0<length<=65536 and prefix+length+expected==len(raw),'exact bounded header plus complete expected payload; no trailer')
    header=raw[prefix:prefix+length];c.need(header.endswith(b'\n'),'ordinary terminated NPY header')
    text=header.decode('latin1');tree=ast.parse(text.strip(),mode='eval')
    nodes=list(ast.walk(tree));c.need(len(nodes)<=1024 and type(tree.body)is ast.Dict,'bounded literal ordinary NPY object')
    keys=tree.body.keys;c.need(len(keys)==3 and all(type(k)is ast.Constant and type(k.value)is str for k in keys)and len({k.value for k in keys})==3,'three distinct literal header keys')
    value=ast.literal_eval(tree);c.exact(value,('descr','fortran_order','shape'))
    c.need(type(value['fortran_order'])is bool and value['fortran_order']is False,'C-order primitive body only')
    c.need(type(value['shape'])is tuple and all(type(n)is int and n>0 for n in value['shape'])and list(value['shape'])==shape,'exact complete typed shape before allocation')
    kind,size=DTYPES[dtype];allowed={order+kind+str(size)for order in('<','>')}
    c.need(type(value['descr'])is str and value['descr']in allowed,'exact primitive scalar dtype; no objects/structures/subarrays')
    return prefix+length,value['descr']

def read(desc,dtype,shape,budget,roots,*,max_array_bytes):
    expected=expected_extent(dtype,shape);c.integer(max_array_bytes,1);c.descriptor(desc)
    c.need(expected<=max_array_bytes and expected+10<desc['bytes']<=expected+65548,'preventive complete payload and bounded serialized extent')
    raw=c.capture(desc,budget,roots);offset,declared=npy_header(raw,dtype,shape)
    np=numpy()
    # Header is never delegated to np.load; its shape cannot cause allocation.
    a=np.frombuffer(raw,dtype=declared,count=expected//DTYPES[dtype][1],offset=offset).reshape(tuple(shape)).astype(dtype,copy=True)
    return exact_array(a,dtype,shape)

def write(path,a,budget):
    np=numpy();c.need(type(a)is np.ndarray and a.dtype.kind in 'fiu'and bool(np.isfinite(a).all()),'finite primitive non-executable array')
    import io
    buffer=io.BytesIO();np.save(buffer,a,allow_pickle=False);raw=buffer.getvalue()
    return c.publish(path,raw,budget)

def create_memmap(path,dtype,shape,budget,*,max_array_bytes):
    np=numpy();n=np.dtype(dtype).itemsize
    for extent in shape:n*=c.integer(extent,1)
    c.need(n<=c.integer(max_array_bytes,1),'prospective complete array extent')
    p=c.absolute(str(path));c.need(not p.exists()and not any(x.is_symlink()for x in p.parents),'fresh ordinary array')
    # NPY v2 header is bounded; retain the full conservative write reservation.
    budget.charge('write_bytes',n+65536)
    return np.lib.format.open_memmap(p,mode='w+',dtype=dtype,shape=tuple(shape),version=(2,0))

def seal_memmap(path,a,budget,roots):
    a.flush();p=c.absolute(str(path));fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW)
    try:os.fsync(fd)
    finally:os.close(fd)
    c.sync_directory(p.parent);s=p.stat();budget.charge('read_bytes',s.st_size+1)
    h=hashlib.sha256();n=0;fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        before=os.fstat(fd);c.need(stat.S_ISREG(before.st_mode)and before.st_nlink==1,'ordinary new NPY')
        while True:
            budget.check_clock();b=os.read(fd,1048576)
            if not b:break
            n+=len(b);h.update(b)
        after=os.fstat(fd);named=p.stat();fields=('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns','st_nlink','st_mode')
        c.need(n==s.st_size and all(getattr(before,k)==getattr(after,k)==getattr(named,k)for k in fields),'stable full NPY seal')
    finally:os.close(fd)
    budget.check_clock();return {'path':str(p),'bytes':n,'sha256':h.hexdigest()}
