"""Complete108-record manifest and isolatedcase preparation; no model execution."""
import argparse,hashlib,json,random,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'public'))
import protocol as p
import delivery_io as io
import array_io
import provision

def validate_record(r):
 p.exact(r,['schema','person','session','source_pin','schema_binding_pin','epochs','offline_labels','online_labels','offline_onsets','online_onsets','array_shape'])
 p.need(r['schema']=='neural083_record_v1' and r['person'] in p.PEOPLE and r['session'] in p.SESSIONS and r['array_shape']==[200,251,20],'Native recordidentity')
 for kind in ('source_pin','schema_binding_pin','epochs'):io.check_pin(r[kind],700000000)
 for phase in ('offline','online'):
  y=r[phase+'_labels'];p.need(type(y)is list and len(y)==100 and all(type(v)is int and v in (0,1) for v in y) and y.count(0)==y.count(1)==50,'Full100balancednativephase')
  p.indices(r[phase+'_onsets'])
 return r

def make_panel(records,secret):
 p.need(type(secret)is bytes and len(secret)==32,'Private32byteIDkey')
 p.need([(r['person'],r['session']) for r in records]==[(person,s) for person in p.PEOPLE for s in p.SESSIONS],'All54×2records numericorder')
 for r in records:validate_record(r)
 p.need(len({r['source_pin']['sha256'] for r in records})==108,'Distinct sourceobjects, no duplicatepersoncopy')
 generation=hashlib.sha256(secret+io.canonical(records)).hexdigest();cases=[];truth=[]
 for r in records:
  ids=[p.token(secret,'trial',f"{r['person']}:{r['session']}:{i}") for i in range(100)];order=sorted(range(100),key=lambda i:ids[i]);case=p.token(secret,'case',f"{r['person']}:{r['session']}");person=p.token(secret,'person',r['person'])
  cases.append({'case':case,'person':person,'session':r['session'],'query':[ids[i] for i in order]})
  truth.append({'case':case,'labels':[r['online_labels'][i] for i in order]})
 return {'schema':'neural083_panel_v1','generation':generation,'settings':list(p.SETTINGS),'arms':list(p.ARMS),'cases':cases},{'schema':'neural083_targets_v1','generation':generation,'cases':truth}

def read_records(root,source_manifest):
 expected=provision.load(source_manifest);records=[validate_record(io.json_file(root/f'person{pp:02d}_session{ss}'/'record.json',65536)) for pp in p.PEOPLE for ss in p.SESSIONS]
 for row,bound in zip(records,expected):p.need((row['person'],row['session'])==(bound['person'],bound['session']) and row['source_pin']=={k:bound[k] for k in ('bytes','sha256')},'Preparedrecord exactsourceidentity join')
 return records

def stage(root,source_manifest,secret,person,session,setting,arm,out,max_bytes):
 import numpy as np
 p.need(arm in p.ARMS,'Knownarm');out=io.regular(out);p.need(not out.exists(),'Freshisolatedoutput')
 records=read_records(root,source_manifest);panel,_=make_panel(records,secret);by={(r['person'],r['session']):r for r in records}
 picks=p.training_selection(person,session,setting,records);train=[];labels=[];groups=[];roles=[];query=None
 target=by[person,session];case=panel['cases'][(person-1)*2+session-1]
 for pp,ss,n,role in picks:
  r=by[pp,ss];y=r['offline_labels'][:n].copy()
  if arm=='PERMUTED_EEG':random.Random(83083+1000*pp+10*ss+n).shuffle(y)
  arr=None if arm=='CONTEXT' else array_io.read(root/f'person{pp:02d}_session{ss}'/'epochs.npy',r['epochs'],[200,251,20])
  rows=[p.context(ss,i,r['offline_onsets']) for i in range(n)] if arm=='CONTEXT' else arr[:n]
  for i in range(n):
   train.append((p.token(secret,'training',f'{pp}:{ss}:{i}'),rows[i],y[i],p.token(secret,'person',pp),role,(i%5 if role=='calibration' else (pp-1)%5)))
 train.sort(key=lambda x:x[0]);x=np.asarray([r[1] for r in train],dtype='<f4')
 rawq=[p.context(session,i,target['online_onsets']) for i in range(100)] if arm=='CONTEXT' else array_io.read(root/f'person{person:02d}_session{session}'/'epochs.npy',target['epochs'],[200,251,20])[100:]
 order=sorted(range(100),key=lambda i:p.token(secret,'trial',f'{person}:{session}:{i}'));q=np.asarray([rawq[i] for i in order],dtype='<f4')
 p.need(x.nbytes+q.nbytes+2000000<=max_bytes,'Boundedonecasepacket; neverreducepanel')
 io.fresh(out);xp=array_io.write(out/'training.npy',x,max_bytes);qp=array_io.write(out/'query.npy',q,max_bytes)
 v={'schema':'neural083_case_v1','generation':panel['generation'],'case':case['case'],'setting':setting,'arm':arm,'training_shape':list(x.shape),'query_shape':list(q.shape),'training_pin':xp,'query_pin':qp,'training':[{'trial':r[0],'y':r[2],'person':r[3],'role':r[4],'inner_fold':r[5]} for r in train],'query':case['query']}
 io.put(out/'case.json',v,2000000);return v

def main():
 a=argparse.ArgumentParser();a.add_argument('--records-root',type=Path,required=True);a.add_argument('--source-manifest',type=Path,required=True);a.add_argument('--key',type=Path,required=True);a.add_argument('--output',type=Path,required=True);a.add_argument('--person',type=int);a.add_argument('--session',type=int);a.add_argument('--setting',choices=p.SETTINGS);a.add_argument('--arm',choices=p.ARMS);a.add_argument('--max-output-bytes',type=int,default=300000000);q=a.parse_args();secret=io.read(q.key,32)
 if q.person is None:
  panel,truth=make_panel(read_records(q.records_root,q.source_manifest),secret);io.fresh(q.output);io.put(q.output/'panel.json',panel,1000000);io.put(q.output/'targets.json',truth,1000000)
 else:stage(q.records_root,q.source_manifest,secret,q.person,q.session,q.setting,q.arm,q.output,q.max_output_bytes)
if __name__=='__main__':main()
