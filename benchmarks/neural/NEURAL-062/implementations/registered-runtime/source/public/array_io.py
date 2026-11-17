"""Read exact pinned NPY1 float32 matrices from the same verified descriptor."""
import math
import numpy as np
import delivery_io as io

def read(path,pin,shape):
 io.need(type(shape)is list and len(shape)==2 and all(type(n)is int and n>=0 for n in shape) and math.prod(shape)*4<=4_000_000_000,'Bounded matrix')
 with io.verified_stream(path,pin) as f:
  version=np.lib.format.read_magic(f);io.need(version==(1,0),'NPY1only');actual,order,dtype=np.lib.format.read_array_header_1_0(f,max_header_size=4096)
  io.need(actual==tuple(shape) and not order and dtype==np.dtype('<f4') and f.tell()+math.prod(shape)*4==pin['bytes'],'Exact NPY geometry/extent')
  f.seek(0);a=np.load(f,allow_pickle=False)
 io.need(not np.isinf(a).any(),'No infinite features');return a
