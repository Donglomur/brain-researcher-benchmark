"""Bounded numeric-only operator state codec; candidate models remain opaque."""
import json,struct
import numpy as np
from reference_math import state_to_npz_members,state_from_npz_members,retained_state_bytes
MAGIC=b'F036STAT1\n'

def encode(state):
    members=state_to_npz_members(state);payload=[];spec=[]
    for k,a in sorted(members.items()):
        a=np.ascontiguousarray(a,dtype='<i8'if a.dtype.kind=='i'else '<f8');b=a.tobytes();spec.append([k,a.dtype.str,list(a.shape),len(b)]);payload.append(b)
    header=json.dumps(spec,separators=(',',':')).encode('ascii')
    if len(header)>65536:raise ValueError('bounded state header')
    return MAGIC+struct.pack('<Q',len(header))+header+b''.join(payload)

def decode(raw,n_features):
    if type(raw)is not bytes or not raw.startswith(MAGIC)or len(raw)>len(MAGIC)+8+65536+retained_state_bytes(n_features):raise ValueError('bounded exact numeric state')
    pos=len(MAGIC);size=struct.unpack_from('<Q',raw,pos)[0];pos+=8
    if size>65536 or pos+size>len(raw):raise ValueError('bounded state metadata')
    specs=json.loads(raw[pos:pos+size]);pos+=size;out={}
    if type(specs)is not list or len(specs)!=12:raise ValueError('all twelve numeric state members')
    for k,dtype,shape,n in specs:
        if type(k)is not str or k in out or dtype not in('<i8','<f8')or type(shape)is not list or len(shape)not in(1,2)or any(type(x)is not int or x<1 for x in shape):raise ValueError('state member metadata')
        count=1
        for x in shape:count*=x
        if type(n)is not int or n!=8*count or n>retained_state_bytes(n_features)or pos+n>len(raw):raise ValueError('bounded state member extent')
        out[k]=np.frombuffer(raw,dtype=dtype,count=count,offset=pos).reshape(shape).copy();pos+=n
    if pos!=len(raw)or sum(a.nbytes for a in out.values())!=retained_state_bytes(n_features):raise ValueError('complete exact numeric state extent')
    result=state_from_npz_members(out)
    if result['mean'].shape!=(n_features,):raise ValueError('full feature state')
    return result
