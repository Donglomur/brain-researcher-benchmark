"""Future raw-spike binning, one recording at a time; never invoked in BUILD."""
import hashlib,json,zipfile
from pathlib import Path
import numpy as np
from artifact_io import capture_regular,decode_json
CODES={0:'outside',1:'L1',23:'L23',4:'L4',5:'L5',6:'L6'}
KEYS={'unit_id','unit_electrode','spike_times','spike_end','trial_start','trial_stop','electrode_id','electrode_y','electrode_layer'}
def normalized(record,arrays):
 a=arrays;starts=np.asarray(a['trial_start'])
 if starts.ndim!=1 or not np.all(np.isfinite(starts))or np.any(starts-.05<0)or np.any(starts[1:]-.05<starts[:-1]+.05):
  raise ValueError('nonnegative nonoverlapping complete analysis windows required')
 n=len(a['unit_id']);t=len(starts);edges=np.arange(-50,51,dtype=np.float64)/1000
 if t*n*100*4>100_000_000:raise ValueError('per-record count memory cap')
 counts=np.empty((t,n,100),dtype=np.uint32);lo=0
 for u,hi in enumerate(a['spike_end']):
  spikes=a['spike_times'][lo:int(hi)];lo=int(hi)
  for trial,start in enumerate(a['trial_start']):
   positions=np.searchsorted(spikes,start+edges,side='left');counts[trial,u]=np.diff(positions)
 depths=sorted(set(a['electrode_y'].tolist()));rank={x:i for i,x in enumerate(depths)}
 contacts=[{'electrode_id':int(i),'depth_rank':rank[float(y)],'layer':CODES[int(l)]}for i,y,l in zip(a['electrode_id'],a['electrode_y'],a['electrode_layer'])]
 return {'recording_id':record['asset_id'],'participant_id':record['participant_id'],'area':record['area'],'counts':counts,'unit_electrode_id':[int(a['electrode_id'][i])for i in a['unit_electrode']],'electrodes':contacts}
def records(packet,manifest):
 for row in manifest['recordings']:
  rel=Path(row['file'])
  if rel.is_absolute()or len(rel.parts)!=1 or rel.suffix!='.npz':raise ValueError('pinned sibling array archive')
  body=capture_regular(packet/rel,8_000_000)
  if len(body)!=row['pin']['bytes']or hashlib.sha256(body).hexdigest()!=row['pin']['sha256']:raise ValueError('selected array identity')
  import io
  with zipfile.ZipFile(io.BytesIO(body))as z:
   if {x.filename for x in z.infolist()}!={k+'.npy'for k in KEYS}or len(z.infolist())!=len(KEYS)or sum(x.file_size for x in z.infolist())>8_000_000:raise ValueError('primitive NPZ bounds')
  with np.load(io.BytesIO(body),allow_pickle=False)as z:arrays={k:z[k]for k in KEYS}
  yield normalized(row,arrays)
def load_manifest(path,expected_sha):
 body=capture_regular(path,4_000_000)
 if hashlib.sha256(body).hexdigest()!=expected_sha:raise ValueError('operator packet manifest pin')
 m=decode_json(body)
 if m['status']!='complete'or len(m['recordings'])!=47:raise ValueError('complete47 source packet')
 return m
