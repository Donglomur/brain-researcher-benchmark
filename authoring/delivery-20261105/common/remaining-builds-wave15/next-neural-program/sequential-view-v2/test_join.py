"""One full production metadata join. No arrays, files, native or scientific fit."""
from pathlib import Path
import json,types,math
HERE=Path(__file__).absolute().parent
CAP=7864320 # prospective exclusive7.5MiB retained/canonical interval
RESERVED=CAP
actual=0

def module(name,**bindings):
 p=HERE/'program'/name;m=types.ModuleType(name);m.__file__=str(p);m.__dict__.update(bindings);exec(compile(p.read_bytes(),str(p),'exec'),m.__dict__);return m
c=module('common.py');contracts=module('contracts.py',c=c);store=module('store.py',c=c,contracts=contracts,stream=None)
def measure(v):
 global actual
 size=0
 for fragment in json.JSONEncoder(sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).iterencode(v):
  size+=len(fragment.encode('ascii'));actual+=len(fragment.encode('ascii'))
  if actual>CAP:raise RuntimeError('precharged canonical serialization ceiling')
 return size

def main():
 assert math.gcd(7919,21600)==1
 assets=[];labels=[];count=0
 for p in range(1,55):
  for session in (1,2):
   for phase in ('train','test'):
    pairs=[]
    for trial in range(100):
     pairs.append((format((count*7919)%21600,'064x'),trial%4+1));count+=1
    pairs.sort();name='p%02d-s%d-%s.npy'%(p,session,phase)
    assets.append(dict(person=p,session=session,phase=phase,signals=dict(path=name,bytes=1600128,sha256='a'*64),ids=[q for q,_ in pairs]))
    labels.extend(dict(id=q,person=p,session=session,phase=phase,label=label) for q,label in pairs)
 pool=dict(schema='neural084_pool_v1',generation='fixture',assets=assets,gold=dict(path='gold.json',bytes=1,sha256='b'*64));gold=dict(schema='neural084_gold_v1',generation='fixture',rows=labels)
 records,files=store.metadata_join(pool,gold)
 retained=measure(pool)+measure(gold)+measure(records)+measure(files)
 assert retained<=CAP and len(records)==21600 and len(files)==216
 canonical=dict(records=records,assets=assets,descriptors=tuple(range(216)))
 for p in range(1,55):
  tr,order,ds=store.fold_rows(canonical,p,'fit');qr,qorder,qds=store.fold_rows(canonical,p,'query')
  assert len(tr)==21200 and len(qr)==400 and len(ds)==212 and len(qds)==4
  assert all(r['person']!=p for r in tr) and all(r['person']==p for r in qr)
  assert all(ds[s]==r['source'] and i==r['row'] for r,(s,i) in zip(tr,order))
  assert all(qds[s]==r['source'] and i==r['row'] for r,(s,i) in zip(qr,qorder))
  assert {r['id'] for r in tr}.isdisjoint(r['id'] for r in qr)
 del tr,qr,order,qorder,ds,qds,records,canonical
 # Reuse the one input fixture. Fail early except the final support check;
 # no previous complete record result is retained during a refusal.
 groups=1
 def refuse():
  nonlocal groups
  try:store.metadata_join(pool,gold)
  except ValueError:groups+=1
  else:raise AssertionError('changed complete provenance accepted')
 value=labels[0]['person'];labels[0]['person']=54;refuse();labels[0]['person']=value
 value=labels[1]['id'];labels[1]['id']=labels[0]['id'];refuse();labels[1]['id']=value
 value=assets[-1];assets.pop();refuse();assets.append(value)
 value=labels[0]['label'];labels[0]['label']=value%4+1;refuse();labels[0]['label']=value
 value=labels[0]['label'];labels[0]['label']=True;refuse();labels[0]['label']=value
 assert groups==6
 print(json.dumps(dict(groups=groups,passed=True,canonical_actual_bytes=actual,canonical_reserved_bytes=RESERVED,retained_canonical_bound_bytes=CAP,physical_fixture_writes=0,full54_training_query_rowplans=54,all_native_or_array_reads=0),sort_keys=True))
if __name__=='__main__':main()
