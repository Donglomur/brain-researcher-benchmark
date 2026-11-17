"""Task-specific primitive NPZ packet admission; identical bytes are hashed/decoded."""
import hashlib,io,json,math,stat,zipfile
from pathlib import Path
import numpy as np
from io_contract import capture,decode
FILE_CAP=134217728
TOTAL_CANDIDATE_CAP=1073741824

def pinned(path,descriptor,cap=FILE_CAP):
 if set(descriptor)!={'path','bytes','sha256'}:raise ValueError('exact file descriptor fields')
 if type(descriptor['bytes']) is not int or not 0<=descriptor['bytes']<=cap:raise ValueError('file cap')
 raw=capture(path,cap)
 if len(raw)!=descriptor['bytes'] or hashlib.sha256(raw).hexdigest()!=descriptor['sha256']:raise ValueError('captured packet identity mismatch')
 return raw

def _npz(raw,names):
 with zipfile.ZipFile(io.BytesIO(raw)) as z:
  infos=z.infolist()
  if len(infos)!=len(names) or {x.filename for x in infos}!={x+'.npy' for x in names} or any(x.file_size>FILE_CAP or x.flag_bits&1 or x.is_dir() for x in infos) or sum(x.file_size for x in infos)>FILE_CAP:raise ValueError('exact bounded primitive NPZ members required')
  for inf in infos:
   with z.open(inf) as stream:
    ver=np.lib.format.read_magic(stream)
    if ver==(1,0):shape,fort,dt=np.lib.format.read_array_header_1_0(stream)
    elif ver==(2,0):shape,fort,dt=np.lib.format.read_array_header_2_0(stream)
    else:raise ValueError('NPY format version')
    if dt.hasobject or dt.kind not in 'fiu' or len(shape)>2 or any(type(x) is not int or x<0 for x in shape) or math.prod(shape)*dt.itemsize>FILE_CAP:raise ValueError('primitive numeric fixed-dimensional array required')
 with np.load(io.BytesIO(raw),allow_pickle=False) as z:return {k:np.array(z[k],copy=True) for k in names}

def npz(raw,names):
 try:return _npz(raw,names)
 except (zipfile.BadZipFile,EOFError,UnicodeError,RecursionError,OverflowError) as e:raise ValueError('Malformed bounded primitive NPZ') from e

def safe_relative(path):
 p=Path(path)
 if p.is_absolute() or not p.parts or any(x in ('.','..') for x in p.parts):raise ValueError('relative packet path required')
 return p

def get_json(root,desc):return decode(pinned(root/safe_relative(desc['path']),desc,30000000))
def get_npz(root,desc,names):return npz(pinned(root/safe_relative(desc['path']),desc),names)

def index(path,sha,task):
 raw=capture(path,30000000)
 if hashlib.sha256(raw).hexdigest()!=sha:raise ValueError('operator-selected index pin mismatch')
 d=decode(raw)
 if set(d)!={'schema','task_id','roster_sha256','sessions','limitations'} or d['schema']!='neuropixels_task_packet_v1' or d['task_id']!=task:raise ValueError('exact task packet index')
 from io_contract import ROSTER_SHA256
 if d['roster_sha256']!=ROSTER_SHA256:raise ValueError('roster binding')
 return d

def validate_public(meta,sid,donor):
 required={'schema','task_id','session_id','mouse_id','unit_ids','areas','unit_metadata','rows','baseline_rates','support','exposure_seconds','state_policy'}
 if set(meta)!=required or meta['schema']!='neuropixels_session_v1' or meta['session_id']!=sid or meta['mouse_id']!=donor:raise ValueError('session metadata identity')
 ids=meta['unit_ids']
 if not ids or len(ids)!=len(set(ids)) or any(not isinstance(x,str) or not x for x in ids):raise ValueError('unique unit IDs')
 if len(meta['areas'])!=len(ids) or len(meta['unit_metadata'])!=len(ids):raise ValueError('unit axes')
 rows=meta['rows'];rid=[r['id'] for r in rows]
 if not rows or len(rid)!=len(set(rid)):raise ValueError('unique trials')
 if set(r['split'] for r in rows)!={'FIT','VALIDATION','QUERY'}:raise ValueError('complete partitions')
 base=np.asarray(meta['baseline_rates'],dtype=float)
 if base.shape!=(len(ids),) or not np.isfinite(base).all() or np.any(base<=0):raise ValueError('positive bound FIT baselines')
 return meta

def counts(arr,shape):
 if arr.shape!=shape or arr.dtype.kind not in 'iu' or np.any(arr<0):raise ValueError('exact nonnegative integer count matrix')
 return arr

def describe(path,root):
 raw=path.read_bytes();return {'path':str(path.relative_to(root)),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}

def write_json(path,value):
 raw=(json.dumps(value,indent=2,allow_nan=False)+'\n').encode()
 with path.open('xb') as f:f.write(raw)
 return len(raw)
