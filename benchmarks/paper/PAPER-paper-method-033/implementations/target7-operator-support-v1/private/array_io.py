"""Strict primitive C-order float32 artifacts; decode only after extent validation."""
import math
import delivery_io as d

def read(path,pin,shape,unit=False):
 import numpy as np
 d.need(type(shape)is list and 1<=len(shape)<=5 and all(type(v)is int and 0<v<=1000000 for v in shape),'Geometry')
 d.need(math.prod(shape)*4<=2_000_000_000,'Per-array bound')
 # NPY1 has a two-byte header length; reject candidate size before any open/hash.
 d.check_pin(pin,min(2_000_000_000,math.prod(shape)*4+65545))
 with d.verified_stream(path,pin)as f:
  d.need(np.lib.format.read_magic(f)==(1,0),'NPY1 only');actual,order,dtype=np.lib.format.read_array_header_1_0(f)
  d.need(list(actual)==shape and not order and dtype.str=='<f4' and f.tell()+math.prod(shape)*4==pin['bytes'],'Exact primitive extent')
  f.seek(0);x=np.load(f,allow_pickle=False)
  d.need(np.isfinite(x).all()and(not unit or((x>=0).all()and(x<=1).all())),'Finite values/range');return x

def write(path,x,cap):
 import numpy as np,io,os
 x=np.ascontiguousarray(x,dtype='<f4');d.need(np.isfinite(x).all(),'Finite conversion')
 h=io.BytesIO();np.lib.format.write_array_header_1_0(h,{'descr':'<f4','fortran_order':False,'shape':x.shape})
 d.need(len(h.getvalue())+x.nbytes<=cap,'Exact retained extent cap')
 p=d.regular(path)
 with p.open('xb')as f:np.lib.format.write_array(f,x,version=(1,0),allow_pickle=False)
 p.chmod(0o444);return d.read(p,cap,retain=False)
