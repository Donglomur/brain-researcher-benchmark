"""Primitive same-captured-byte NPY transport; object/structured arrays forbidden."""
import hashlib, io, math
from pathlib import Path
import numpy as np
from .io_contract import capture, fresh

CAP = 256_000_000

def read_array(path, desc, *, shape=None, cap=CAP, allow_nan=False):
    if not isinstance(desc,dict) or set(desc)!={'path','bytes','sha256','shape','dtype'}:
        raise ValueError('Exact primitive array descriptor required')
    if not isinstance(desc['shape'],list) or any(type(x) is not int or x<=0 for x in desc['shape']) or not isinstance(desc['sha256'],str) or len(desc['sha256'])!=64 or any(c not in '0123456789abcdef' for c in desc['sha256']):raise ValueError('Exact descriptor shape/hash types')
    if not isinstance(desc['path'],str) or '\\' in desc['path'] or Path(desc['path']).name!=desc['path'] or not desc['path'].endswith('.npy'):
        raise ValueError('Single relative NPY basename required')
    if type(desc['bytes']) is not int or not 0<desc['bytes']<=cap: raise ValueError('Array byte cap')
    body=capture(Path(path)/desc['path'], cap)
    if len(body)!=desc['bytes'] or hashlib.sha256(body).hexdigest()!=desc['sha256']:
        raise ValueError('Array identity mismatch')
    f=io.BytesIO(body); version=np.lib.format.read_magic(f)
    if version==(1,0): dims,fort,dtype=np.lib.format.read_array_header_1_0(f,max_header_size=4096)
    elif version==(2,0): dims,fort,dtype=np.lib.format.read_array_header_2_0(f,max_header_size=4096)
    else: raise ValueError('NPY version')
    if fort or dtype.str not in ('<f4','<f8','<i8','|b1') or any(type(x) is not int or x<=0 for x in dims) or not 1<=len(dims)<=3:
        raise ValueError('Primitive C-order nonempty array required')
    if list(dims)!=desc['shape'] or dtype.str!=desc['dtype'] or (shape is not None and tuple(dims)!=tuple(shape)):
        raise ValueError('Array shape/dtype mismatch')
    if math.prod(dims)*dtype.itemsize!=len(body)-f.tell(): raise ValueError('Array exact payload size')
    x=np.frombuffer(body,dtype=dtype,offset=f.tell()).reshape(dims)
    if dtype.kind=='f' and (np.isinf(x).any() or (not allow_nan and np.isnan(x).any())): raise ValueError('Invalid array availability')
    return x

def write_array(path, x, *, cap=CAP, allow_nan=False):
    path=fresh(path); x=np.asarray(x)
    if x.dtype.kind=='f': x=np.asarray(x,dtype='<f4' if x.dtype.itemsize==4 else '<f8',order='C')
    elif x.dtype.kind in 'iu': x=np.asarray(x,dtype='<i8',order='C')
    elif x.dtype.kind=='b': x=np.asarray(x,dtype='?',order='C')
    else: raise ValueError('Primitive numeric array required')
    if x.ndim not in (1,2,3) or not x.size or x.nbytes>cap-4096 or (x.dtype.kind=='f' and (np.isinf(x).any() or (not allow_nan and np.isnan(x).any()))):
        raise ValueError('Bounded nonempty finite array required')
    with path.open('xb') as f: np.save(f,x,allow_pickle=False)
    body=capture(path,cap)
    return {'path':path.name,'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest(),'shape':list(x.shape),'dtype':x.dtype.str}
