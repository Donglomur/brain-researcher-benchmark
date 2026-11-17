"""Stream projected experiments into a full index, then one bounded case/arm array view."""
from pathlib import Path
from collections import Counter,defaultdict
import hashlib,hmac
import delivery_io as io
import cohort_binding
import protocol as p

def token(key,*parts):return hmac.new(key,'|'.join(map(str,parts)).encode(),hashlib.sha256).hexdigest()
def method(root):return {n:io.read(root/n,200000,retain=False) for n in('extract.py','nwb_source.py','protocol.py','delivery_io.py','cohort_binding.py')}
def validate_projection(q,r,root):
 io.exact(q,['format','experiment','mouse','source','record_sha256','rows','census','method']);io.need(q['format']=='neural062_projection_v1' and q['experiment']==r['ophys_experiment_id'] and q['mouse']==r['mouse_id'] and q['record_sha256']==io.pin(io.canonical(r))['sha256'] and q['source']['blake2b_512']==r['asset']['file_hash'] and q['method']==method(root),'Exact projection source/method/record')
 io.need(type(q['rows'])is list and len(q['rows'])<=20000,'Full bounded experiment events');seen=set()
 for x in q['rows']:
  io.exact(x,['presentation_id','group','image_name','context','running_bin','covariates','PRE','POST']);identity=(x['group'],x['presentation_id']);io.need(type(x['presentation_id'])is int and type(x['group'])is str and identity not in seen,'Unique native event');seen.add(identity)
  io.need(x['context'] in p.CONTEXTS and x['running_bin'] in('missing','below1','1to5','5to10','10plus') and type(x['image_name'])is str and 1<=len(x['image_name'])<=512,'Exact event metadata')
  p.features(x['covariates'],8);p.features(x['PRE'],14);p.features(x['POST'],14)
  io.need(all(v is None for v in x['PRE']) or all(v is not None for v in x['PRE']),'Common PRE support');io.need(all(v is None for v in x['POST']) or all(v is not None for v in x['POST']),'Common POST support')

def generation(root,pins,key,cohort_path=None):
 cohort_path=Path(root)/'COHORT.json'if cohort_path is None else Path(cohort_path)
 io.read(cohort_path,16000000,cohort_binding.PIN,retain=False)
 io.need(io.read(root/'protocol.py',200000)==io.read(root.parent/'public/protocol.py',200000),'Protocol aliases')
 source={n:io.read(root/n,16000000,retain=False) for n in('prepare.py','protocol.py','extract.py','nwb_source.py','delivery_io.py','cohort_binding.py')};source['COHORT.json']=cohort_binding.PIN;source['PROTOCOL.json']=io.read(root.parent/'public/PROTOCOL.json',200000,retain=False)
 return io.pin(io.canonical({'source':source,'projection_pins':pins,'key_sha256':hashlib.sha256(key).hexdigest()}))['sha256']
def caseid(key,mouse,image_set,context):return token(key,'case',mouse,image_set,context)
def rowid(key,r,x):return token(key,'event',r['ophys_experiment_id'],x['group'],x['presentation_id'])
def build_index(projections,pins,key,root,cohort_path=None):
 cohort=cohort_binding.load(root,cohort_path);rows=cohort['rows'];io.need(set(pins)=={r['ophys_experiment_id'] for r in rows},'All1936 projections');io.need(len(key)==32,'Private32-byte key')
 records={};vocabulary={s:None for s in p.SETS};queries=defaultdict(list);references=defaultdict(list);case_meta={}
 # First pass establishes all class dictionaries and matched support without neural outcomes.
 for r in rows:
  exp=r['ophys_experiment_id'];q=io.json_file(Path(projections)/(exp+'.json'),16000000,pins[exp]);validate_projection(q,r,root)
  names=sorted({x['image_name'] for x in q['rows']});io.need(len(names)==8,'Exactly8 shown-image identities in every complete experiment')
  if vocabulary[r['image_set']] is None:vocabulary[r['image_set']]=names
  io.need(names==vocabulary[r['image_set']],'Same known vocabulary acrossallmice in image set')
  counts=defaultdict(Counter)
  for x in q['rows']:counts[(x['context'],x['running_bin'])][x['image_name']]+=1
  supported={k for k,v in counts.items() if set(v)==set(names)}
  rec={'cohort':r,'projection_pin':pins[exp],'strata':{c+'|'+b:dict(v) for (c,b),v in counts.items()},'supported':sorted(c+'|'+b for c,b in supported),'census':q['census']};records[exp]=rec
  if r['split']!='train':
   for context in p.CONTEXTS:
    cid=caseid(key,r['mouse_id'],r['image_set'],context);case_meta[cid]={'mouse':r['mouse_id'],'image_set':r['image_set'],'context':context,'split':r['split']};queries.setdefault(cid,[]);references.setdefault(cid,[])
   for x in q['rows']:
    if (x['context'],x['running_bin']) not in supported:continue
    cid=caseid(key,r['mouse_id'],r['image_set'],x['context']);rid=rowid(key,r,x);queries[cid].append(rid);references[cid].append({'id':rid,'label':names.index(x['image_name']),'experiment':exp,'bin':x['running_bin']})
 gen=generation(root,pins,key,cohort_path);cases=[];gold=[]
 for cid,meta in sorted(case_meta.items()):
  ids=sorted(queries[cid]);io.need(len(ids)==len(set(ids)) and len(ids)<=500000,'Bounded unique complete query');expected=sorted(r['ophys_experiment_id'] for r in rows if r['mouse_id']==meta['mouse'] and r['image_set']==meta['image_set'])
  cases.append({'case':cid,'query_ids':ids});gold.append({'case':cid,**meta,'expected_experiments':expected,'rows':sorted(references[cid],key=lambda x:x['id'])})
 return {'format':'neural062_index_v1','generation':gen,'records':records,'case_meta':case_meta,'vocabulary':vocabulary,'key_sha256':hashlib.sha256(key).hexdigest()},{'format':'neural062_plan_v1','generation':gen,'cases':cases},{'format':'neural062_reference_v1','generation':gen,'cases':gold}

def feature(x,r,arm):
 cov=x['covariates'];values=cov+[int(v is None) for v in cov[:4]]+[int(x['PRE'][0] is None),int(x['POST'][0] is None)]+p.static(r)
 for w in {'CONTEXT':(),'PRE':('PRE',),'POST':('POST',),'PRE_POST':('PRE','POST')}[arm]:values+=x[w]
 p.features(values,len(p.names(arm)));return values

def make_view(index,projections,key,case,arm,output,root,cohort_path=None):
 import numpy as np
 io.need(index['generation']==generation(root,{e:v['projection_pin'] for e,v in index['records'].items()},key,cohort_path),'Current view source generation')
 io.need(hashlib.sha256(key).hexdigest()==index['key_sha256'] and case in index['case_meta'],'Exact index/key/case');meta=index['case_meta'][case];io.need(caseid(key,meta['mouse'],meta['image_set'],meta['context'])==case,'Case binding');dim=len(p.names(arm));records=index['records']
 chosen=[(e,v) for e,v in records.items() if v['cohort']['image_set']==meta['image_set'] and (v['cohort']['split']=='train' or v['cohort']['mouse_id']==meta['mouse'])]
 def count(rec):return sum(sum(v.values()) for k,v in rec['strata'].items() if k in rec['supported'] and k.split('|')[0]==meta['context'])
 ntrain=sum(count(v) for e,v in chosen if v['cohort']['split']=='train');nquery=sum(count(v) for e,v in chosen if v['cohort']['mouse_id']==meta['mouse']);io.need(0<ntrain<=3000000 and nquery<=500000,'Full bounded view counts')
 io.reserve('write_bytes',128+ntrain*(dim+2)*4+128+nquery*dim*4)
 out=io.fresh(output);pub=out/'public';pub.mkdir();train=np.lib.format.open_memmap(pub/'train.npy',mode='w+',dtype='<f4',shape=(ntrain,dim+2),version=(1,0));query_rows=[];ti=0;group_runs=[]
 train_experiments=[v for e,v in chosen if v['cohort']['split']=='train' and count(v)>0];by_mouse=Counter(v['cohort']['mouse_id'] for v in train_experiments);nmice=len(by_mouse)
 for exp,rec in chosen:
  r=rec['cohort'];q=io.json_file(Path(projections)/(exp+'.json'),16000000,rec['projection_pin']);validate_projection(q,r,root);bins=[k for k in rec['supported'] if k.split('|')[0]==meta['context']]
  for x in q['rows']:
   k=x['context']+'|'+x['running_bin']
   if x['context']!=meta['context'] or k not in bins:continue
   v=feature(x,r,arm);a=[np.nan if z is None else z for z in v]
   if r['split']=='train':
    w=ntrain/(nmice*by_mouse[r['mouse_id']]*len(bins)*8*rec['strata'][k][x['image_name']]);train[ti]=a+[index['vocabulary'][meta['image_set']].index(x['image_name']),w];ti+=1
    group=token(key,'training-mouse',r['mouse_id'])
    if group_runs and group_runs[-1]['group']==group:group_runs[-1]['count']+=1
    else:group_runs.append({'group':group,'count':1})
   else:query_rows.append((rowid(key,r,x),a))
 io.need(ti==ntrain and len(query_rows)==nquery,'Exact view support');train.flush();del train;query_rows.sort(key=lambda z:z[0]);query=np.lib.format.open_memmap(pub/'query.npy',mode='w+',dtype='<f4',shape=(nquery,dim),version=(1,0))
 for i,(_,v) in enumerate(query_rows):query[i]=v
 query.flush();del query
 arrays={}
 for name,shape in [('train.npy',[ntrain,dim+2]),('query.npy',[nquery,dim])]:arrays[name]={'shape':shape,**io.read(pub/name,4_000_000_000,empty=True,retain=False)};(pub/name).chmod(0o444)
 view={'format':'neural062_view_v1','generation':index['generation'],'case':case,'arm':arm,'feature_names':list(p.names(arm)),'classes':list(range(8)),'query_ids':[i for i,_ in query_rows],'arrays':arrays};io.put(pub/'VIEW.json',view,40000000)
 io.put(pub/'TRAIN_GROUPS.json',{'schema':'neural062.train-mouse-groups.v1','rows':ntrain,'runs':group_runs},16000000)
 return view
if __name__=='__main__':
 import argparse
 a=argparse.ArgumentParser();s=a.add_subparsers(dest='cmd',required=True);x=s.add_parser('index');x.add_argument('--projections',required=True);x.add_argument('--pins',required=True);x.add_argument('--key',required=True);x.add_argument('--output',required=True)
 x=s.add_parser('view');x.add_argument('--index',required=True);x.add_argument('--index-pin',required=True);x.add_argument('--projections',required=True);x.add_argument('--key',required=True);x.add_argument('--case',required=True);x.add_argument('--arm',choices=p.ARMS,required=True);x.add_argument('--output',required=True);q=a.parse_args();root=Path(__file__).resolve().parent;key=io.read(q.key,32)
 if q.cmd=='index':
  index,plan,gold=build_index(q.projections,io.json_file(q.pins,1000000),key,root);out=io.fresh(q.output);pin=io.put(out/'INDEX.json',index,32000000);io.put(out/'INDEX.pin.json',pin);io.put(out/'PLAN.json',plan,320000000);io.put(out/'REFERENCE.json',gold,640000000)
 else:make_view(io.json_file(q.index,32000000,io.json_file(q.index_pin)),q.projections,key,q.case,q.arm,q.output,root)
