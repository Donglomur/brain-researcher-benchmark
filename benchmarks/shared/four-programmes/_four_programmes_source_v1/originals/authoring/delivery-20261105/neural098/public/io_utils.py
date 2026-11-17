"""Bounded captured-byte admission; no scientific payloads at import."""
import hashlib
import io
import json
import os
import stat


def capture(path,limit,expected=None):
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    with os.fdopen(fd,'rb') as f:
        before=os.fstat(f.fileno())
        if not stat.S_ISREG(before.st_mode) or not 0<before.st_size<=limit:raise ValueError('bounded ordinary file')
        body=f.read(limit+1);after=os.fstat(f.fileno())
        sig=lambda s:(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
        if len(body)!=before.st_size or sig(before)!=sig(after):raise ValueError('unstable file')
    digest=hashlib.sha256(body).hexdigest()
    if expected is not None and digest!=expected:raise ValueError('captured source pin mismatch')
    return body,digest


def unique(pairs):
    result={}
    for k,v in pairs:
        if k in result:raise ValueError('duplicate key')
        result[k]=v
    return result


def read_json(path,limit=4000000,expected=None):
    raw,digest=capture(path,limit,expected)
    return json.loads(raw.decode('utf-8'),object_pairs_hook=unique,
                      parse_constant=lambda _:(_ for _ in ()).throw(ValueError('nonfinite JSON'))),digest


def read_features(path,sha,n):
    import numpy as np
    raw,_=capture(path,24000128,sha)
    f=io.BytesIO(raw);version=np.lib.format.read_magic(f)
    if version!=(1,0):raise ValueError('bounded NPYv1 feature container')
    shape,fortran,dtype=np.lib.format.read_array_header_1_0(f,max_header_size=10000)
    if shape!=(n,5,6) or fortran or dtype!=np.dtype('<f8') or len(raw)-f.tell()!=n*5*6*8:
        raise ValueError('NPY header/body bounds before array allocation')
    f.seek(0);a=np.load(f,allow_pickle=False)
    if f.tell()!=len(raw) or a.dtype!=np.dtype('<f8') or a.shape!=(n,5,6):
        raise ValueError('exact float64 (trials,5,6) array; availability validated from duration')
    return a


def write_json(path,value):
    raw=json.dumps(value,allow_nan=False,separators=(',',':')).encode()+b'\n'
    if len(raw)>4000000:raise ValueError('output byte cap')
    with open(path,'xb') as f:f.write(raw)
