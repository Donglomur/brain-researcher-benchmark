"""Strict pinned NPY transport; no pickle, archive expansion or candidate execution."""
import io as memory
import math
import numpy as np
import delivery_io as io

def read(path,pin,shape):
 io.need(type(shape)is list and len(shape) in (2,3) and all(type(n)is int and 1<=n<=100000 for n in shape) and math.prod(shape)*4<=600000000,'Bounded exact dimensions before decode')
 body=io.read(path,600000000,pin);stream=memory.BytesIO(body)
 version=np.lib.format.read_magic(stream)
 io.need(version==(1,0),'NPY1.0 only')
 actual,fortran,dtype=np.lib.format.read_array_header_1_0(stream,max_header_size=4096)
 io.need(actual==tuple(shape) and not fortran and dtype==np.dtype('<f4') and not dtype.hasobject,'Exactlittlefloat32/C/shape')
 io.need(stream.tell()+math.prod(shape)*4==len(body),'Exact NPY extent')
 arr=np.load(memory.BytesIO(body),allow_pickle=False)
 io.need(np.isfinite(arr).all(),'Finite signal/features');return arr

def write(path,arr,cap):
 import os
 a=np.ascontiguousarray(arr,dtype='<f4');io.need(np.isfinite(a).all(),'Finite features')
 buf=memory.BytesIO();np.lib.format.write_array(buf,a,version=(1,0),allow_pickle=False);body=buf.getvalue();io.need(len(body)<=cap,'Output cap')
 p=io.regular(path);fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
 with os.fdopen(fd,'wb') as f:f.write(body);f.flush();os.fsync(f.fileno())
 return io.pin(body)
