"""Bounded non-pickle numeric containers; imported science only inside workers."""
import io,zipfile,math
from .contracts import need,closed,canonical,parse,digest,descriptor

def load_arrays(raw,expected=None,cap=32*2**20):
 import numpy as np
 need(type(raw)is bytes and len(raw)<=cap,'compressed array cap')
 with zipfile.ZipFile(io.BytesIO(raw))as z:
  rows=z.infolist();need(len(rows)<=10000 and len({x.filename for x in rows})==len(rows),'unique finite archive')
  need(sum(x.file_size for x in rows)<=cap,'decoded array cap')
  names=[]
  for x in rows:
   need(x.filename.endswith('.npy')and '/'not in x.filename and '\\'not in x.filename and not(x.flag_bits&1),'plain NPY member');names.append(x.filename[:-4])
   with z.open(x)as f:
    version=np.lib.format.read_magic(f)
    need(version in((1,0),(2,0)),'NPY version')
    shape,fortran,dtype=(np.lib.format.read_array_header_1_0(f)if version==(1,0)else np.lib.format.read_array_header_2_0(f))
    need(not dtype.hasobject and dtype.fields is None and dtype.kind in'biufUS','primitive array dtype')
    n=math.prod(shape);need(n*dtype.itemsize<=cap and all(type(i)is int and i>=0 for i in shape),'bounded shape')
  if expected is not None:need(set(names)==set(expected),'exact array field union')
 with np.load(io.BytesIO(raw),allow_pickle=False)as src:out={k:src[k]for k in src.files}
 return out

def dump_arrays(arrays,cap=512*2**20):
 import numpy as np
 need(type(arrays)is dict and len(arrays)<=10000,'array mapping');decoded=0
 for k,v in arrays.items():
  need(type(k)is str and k and all(c.isalnum()or c=='_'for c in k),'plain array name');a=np.asarray(v);need(not a.dtype.hasobject and a.dtype.fields is None and a.dtype.kind in'biufUS','nonobject arrays');decoded+=a.nbytes
 need(decoded<=cap,'decoded output cap');buf=io.BytesIO();np.savez_compressed(buf,**arrays);raw=buf.getvalue();need(len(raw)<=cap,'compressed output cap');return raw

def state_encode(state,bindings,limits):
 import numpy as np
 count=0;arrays={}
 def visit(v):
  nonlocal count
  count+=1;need(count<=limits['max_state_nodes'],'state node cap')
  if isinstance(v,np.ndarray):
   name='a%06d'%len(arrays);need(not v.dtype.hasobject and v.dtype.fields is None and v.dtype.kind in'biufUS','state numeric primitive');arrays[name]=v;return{'type':'array','name':name}
  if type(v)in(str,int,bool)or v is None:return{'type':'scalar','value':v}
  if type(v)is float:need(math.isfinite(v),'finite state scalar');return{'type':'scalar','value':v}
  if type(v)in(list,tuple):return{'type':'tuple'if type(v)is tuple else'list','items':[visit(x)for x in v]}
  if type(v)is dict:need(all(type(k)is str for k in v),'string state keys');return{'type':'dict','items':{k:visit(x)for k,x in sorted(v.items())}}
  raise ValueError('no arbitrary fitted object/pickle in state')
 tree=visit(state);arr=dump_arrays(arrays,limits['max_state_bytes']);meta=canonical({'schema':'NLB017_numeric_state_v1','bindings':bindings,'tree':tree,'arrays':{'bytes':len(arr),'sha256':digest(arr)},'nodes':count})
 need(len(meta)+len(arr)<=limits['max_state_bytes'],'whole state byte cap');return meta,arr

def state_decode(meta,raw,bindings,limits):
 d=parse(meta);closed(d,{'schema','bindings','tree','arrays','nodes'});need(d['schema']=='NLB017_numeric_state_v1'and d['bindings']==bindings,'state source/training/query identity')
 need(d['arrays']=={'bytes':len(raw),'sha256':digest(raw)}and len(meta)+len(raw)<=limits['max_state_bytes'],'state content binding')
 a=load_arrays(raw,cap=limits['max_state_bytes']);used=set();count=0
 def visit(v):
  nonlocal count
  count+=1;need(count<=limits['max_state_nodes'],'state node cap');need(type(v)is dict,'state node');t=v.get('type')
  if t=='array':closed(v,{'type','name'});need(v['name']in a and v['name']not in used,'one-to-one state array');used.add(v['name']);return a[v['name']]
  if t=='scalar':closed(v,{'type','value'});need(type(v['value'])in(str,int,bool,float,type(None)),'primitive state scalar');return v['value']
  if t in('tuple','list'):closed(v,{'type','items'});xs=[visit(x)for x in v['items']];return tuple(xs)if t=='tuple'else xs
  need(t=='dict','state node type');closed(v,{'type','items'});return{k:visit(x)for k,x in v['items'].items()}
 out=visit(d['tree']);need(used==set(a)and count==d['nodes'],'complete state census');return out

PREDICTION_KEYS={'expected_counts','trial_ids','heldout_unit_ids','bin_left_edges_ms','prediction_units','panel_fingerprint'}
def prediction(raw,support,case_index=None):
 import numpy as np
 p=load_arrays(raw,PREDICTION_KEYS);n=574 if case_index is None else 1
 need(p['expected_counts'].shape==(n,140,45)and p['expected_counts'].dtype.kind in'if'and np.isfinite(p['expected_counts']).all()and (p['expected_counts']>0).all(),'finite strictly-positive expected counts')
 ids=support['eval_trial_ids']if case_index is None else[support['eval_trial_ids'][case_index]]
 for key,want in(('trial_ids',ids),('heldout_unit_ids',support['heldout_unit_ids']),('bin_left_edges_ms',support['bin_left_edges_ms'])):need(np.array_equal(p[key],want),'prediction support '+key)
 need(p['prediction_units'].shape==()and p['prediction_units'].item()=='expected_spikes_per_bin','prediction units');need(p['panel_fingerprint'].shape==()and p['panel_fingerprint'].item()==support['panel_fingerprint'],'public panel identity');return p
