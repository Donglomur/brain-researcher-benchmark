"""Capsule-only primitive arrays with explicit pre-effect byte/shape admission."""
from pathlib import Path
import io
from .core import need
from .native.io import read,write_new,identity,relative
def array(root,descriptor,max_bytes):
    import numpy as np
    need(type(descriptor)is dict and descriptor["bytes"]<=max_bytes,"Declared array budget before read")
    body=read(Path(root)/relative(descriptor["path"]),descriptor["bytes"],descriptor)
    stream=io.BytesIO(body)
    version=np.lib.format.read_magic(stream)
    need(version in ((1,0),(2,0)),"Bounded primitive NPY format")
    shape,fortran,dtype=np.lib.format._read_array_header(stream,version,max_header_size=4096)
    count=1
    for n in shape:
        need(type(n)is int and n>0,"Positive array dimension");count*=n
        need(count<=max_bytes,"Finite array extent before allocation")
    need(dtype.kind in "fiu" and not dtype.hasobject and list(shape)==descriptor["shape"],"Exact primitive shape before allocation")
    need(count*dtype.itemsize<=max_bytes and count*dtype.itemsize==len(body)-stream.tell(),"Exact payload extent before allocation")
    stream.seek(0);x=np.load(stream,allow_pickle=False,max_header_size=4096)
    need(isinstance(x,np.ndarray)and x.dtype.kind in "fiu"and list(x.shape)==descriptor["shape"],"Primitive exact array shape")
    need(x.nbytes<=max_bytes and np.isfinite(x).all(),"Finite bounded primitive array")
    return x
def save(root,name,x,cap):
    import numpy as np
    need(isinstance(x,np.ndarray)and x.dtype.kind in "fiu" and np.isfinite(x).all(),"Primitive finite output")
    need(x.nbytes+4096<=cap,"Output extent admitted before serialization")
    stream=io.BytesIO();np.save(stream,x,allow_pickle=False);body=stream.getvalue()
    pin=write_new(Path(root)/relative(name),body,cap)
    return {"path":name,**pin,"shape":list(x.shape),"dtype":str(x.dtype)}

