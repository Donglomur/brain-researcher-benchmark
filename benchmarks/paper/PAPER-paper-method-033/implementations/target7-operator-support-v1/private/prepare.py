"""Authenticated original-shard extraction/indexing. No fitting or metric calculation.
Run only after complete data/storage authorization; no authentic data used in build.
"""
from pathlib import Path
import hashlib,hmac,io,json,tarfile
import delivery_io as d,protocol as p,provision
ROOT=Path(__file__).resolve().parent
VOXELS={1:15724,2:14278,5:13039,7:12682}

def generation():
 from binding import FROZEN
 for n,pin in FROZEN.items():d.read(ROOT/n,pin['bytes'],pin)
 d.need((ROOT/'protocol.py').read_bytes()==(ROOT.parent/'public/protocol.py').read_bytes(),'Protocol alias')
 names=['INPUT_MANIFEST.json','COHORT.json','CODE_PROVENANCE.json','binding.py','prepare.py','protocol.py','provision.py','delivery_io.py','array_io.py','native_bridge.py','native_predict.py']
 return hashlib.sha256(b''.join(n.encode()+b'\0'+(ROOT/n).read_bytes()+b'\0'for n in names)).hexdigest()

def extract(source,out,cap):
 """Only native-required fields; verify every full designated shard on same open handle."""
 m=d.json_file(ROOT/'INPUT_MANIFEST.json',1000000);rows=provision.designated_records(m)
 d.need(type(cap)is int and cap>=sum(r['bytes']for r in rows),'Explicit full-release output reservation')
 out=d.regular(out);out.mkdir(parents=True,exist_ok=False);members=[];used=0;seen=set()
 for r in rows:
  if not r['path'].endswith('.tar'):continue
  parts=r['path'].split('/');split=parts[1];subject=next(f'subj{s:02d}'for s in p.SUBJECTS if f'subj{s:02d}'in r['path'])
  with d.verified_stream(d.resolve(source,r['path']),{k:r[k]for k in('bytes','sha256')})as f:
   with tarfile.open(fileobj=f,mode='r:')as archive:
    for item in archive:
     d.need(item.isfile()and Path(item.name).name==item.name and item.size<=10000000,'Ordinary bounded flat TAR member')
     key,ext=item.name.split('.',1);d.need(key.startswith('sample')and key[6:].isdigit(),'Native sample identity')
     if ext not in ('jpg','nsdgeneral.npy','coco73k.npy'):continue
     rel=f'webdataset_avg_split/{split}/{subject}/{item.name}';d.need(rel not in seen,'No duplicate shard member');seen.add(rel)
     used+=item.size;d.need(used<=cap,'Cumulative retained cap');body=archive.extractfile(item).read(item.size+1);d.need(len(body)==item.size,'Full member')
     target=d.resolve(out,rel);target.parent.mkdir(parents=True,exist_ok=True)
     with target.open('xb')as q:q.write(body)
     members.append({'path':rel,**d.pin(body)})
 receipt={'generation':generation(),'members':members,'retained_bytes':used,'all_required_shards_verified':True,'native_runtime_verified':False}
 d.put(out/'EXTRACTED.json',receipt,30000000);return d.pin(d.canonical(receipt))

def header(body):
 import numpy as np
 f=io.BytesIO(body);d.need(np.lib.format.read_magic(f)==(1,0),'NPY1 source header')
 shape,order,dtype=np.lib.format.read_array_header_1_0(f);d.need(not dtype.hasobject and not order and dtype.kind in 'ifu','Primitive C-order numeric source')
 d.need(f.tell()+int(__import__('math').prod(shape))*dtype.itemsize==len(body),'Exact source payload extent');return shape,dtype

def index(root,receipt,secret):
 import numpy as np
 d.need(type(secret)is bytes and len(secret)==32,'32-byte private key');g=generation();d.need(receipt['generation']==g and receipt['all_required_shards_verified']is True,'Current source extraction')
 grouped={};rows={}
 for r in receipt['members']:
  parts=r['path'].split('/');d.need(len(parts)==4 and parts[0]=='webdataset_avg_split','Native path');split,sub=parts[1:3];key,ext=parts[3].split('.',1)
  d.need(split in('train','val','test')and sub in [f'subj{x:02d}'for x in p.SUBJECTS],'Full selected cohort');group=grouped.setdefault((sub,split,key),{});d.need(ext not in group,'Unique member field');group[ext]=r
 for s in p.SUBJECTS:
  rows[s]={}
  for split,count in [('train',p.TRAIN_RELEASE),('val',p.VALIDATION_RELEASE),('test',p.N_TEST)]:
   keys=sorted(k for sub,sp,k in grouped if sub==f'subj{s:02d}'and sp==split);d.need(len(keys)==count,'Exact complete native image support');records=[]
   for key in keys:
    rr=grouped[(f'subj{s:02d}',split,key)];d.need(set(rr)=={'jpg','nsdgeneral.npy','coco73k.npy'},'Complete native fields')
    def body(ext):r=rr[ext];return d.read(d.resolve(root,r['path']),10000000,{k:r[k]for k in('bytes','sha256')})
    b=body('coco73k.npy');shape,dtype=header(b);d.need(shape in((),(1,))and dtype.kind in 'iu','Scalar source image index');image=int(np.load(io.BytesIO(b),allow_pickle=False).reshape(-1)[0]);d.need(0<=image<73000,'Original NSD image identity')
    shape,dtype=header(body('nsdgeneral.npy'));d.need(shape==(3,VOXELS[s])and dtype.kind=='f','Three native repeated NSDGeneral responses; no inferred repair')
    records.append({'key':key,'image_id':image,'files':rr})
   d.need(len({r['image_id']for r in records})==count,'Unique images within split');rows[s][split]=records
  sets=[{r['image_id']for r in rows[s][x]}for x in('train','val','test')];d.need(not(sets[0]&sets[1]or sets[0]&sets[2]or sets[1]&sets[2]),'Within-person split overlap')
 shared={r['image_id']for r in rows[1]['test']};d.need(all({r['image_id']for r in rows[s]['test']}==shared for s in p.SUBJECTS),'All four people share exact982query images')
 d.need(all(not(shared&{r['image_id']for r in rows[s][split]})for s in p.SUBJECTS for split in('train','val')),'No shared query image in any source training/validation')
 cases=[]
 for c in p.cases():
  r=rows[c['subject']];cid=c['case_id'];q=[hmac.new(secret,(g+':'+cid+':'+str(x['image_id'])).encode(),hashlib.sha256).hexdigest()for x in r['test']]
  cases.append({**c,'query_ids':q,'train_keys':[x['key']for x in r['train'][:c['budget']]],'validation_keys':[x['key']for x in r['val']]})
 return {'generation':g,'cases':cases,'private_source_rows':rows,'selection':'first lexicographically sorted K training keys;300validation separate','runtime_verified':False}

def main():
 import argparse
 a=argparse.ArgumentParser();sub=a.add_subparsers(dest='mode',required=True);x=sub.add_parser('extract');x.add_argument('--source',required=True);x.add_argument('--output',required=True);x.add_argument('--max-output-bytes',type=int,required=True)
 x=sub.add_parser('view');x.add_argument('--source',required=True);x.add_argument('--plan',required=True);x.add_argument('--plan-pin',required=True);x.add_argument('--case',required=True);x.add_argument('--output',required=True);x.add_argument('--max-output-bytes',type=int,required=True)
 x=sub.add_parser('reference');x.add_argument('--source',required=True);x.add_argument('--plan',required=True);x.add_argument('--plan-pin',required=True);x.add_argument('--output',required=True);x.add_argument('--max-output-bytes',type=int,required=True)
 x=sub.add_parser('index');x.add_argument('--source',required=True);x.add_argument('--receipt-pin',required=True);x.add_argument('--key',required=True);x.add_argument('--output',required=True);z=a.parse_args()
 if z.mode=='extract':print(json.dumps(extract(z.source,z.output,z.max_output_bytes)))
 elif z.mode=='view':make_view(z.source,d.json_file(z.plan,60000000,d.json_file(z.plan_pin)),z.case,z.output,z.max_output_bytes)
 elif z.mode=='reference':print(json.dumps(reference(z.source,d.json_file(z.plan,60000000,d.json_file(z.plan_pin)),z.output,z.max_output_bytes)))
 else:d.put(z.output,index(z.source,d.json_file(Path(z.source)/'EXTRACTED.json',30000000,d.json_file(z.receipt_pin)),d.read(z.key,32)),60000000)

def make_view(root,plan,cid,out,cap):
 """One case only. Query image/key/COCO identifiers never enter candidate view."""
 import shutil
 d.need(plan['generation']==generation(),'Current source generation');case=next((r for r in plan['cases']if r['case_id']==cid),None);d.need(case is not None,'Known case')
 out=d.regular(out);out.mkdir(parents=True,exist_ok=False);used=0;files=[]
 def copy(r,name):
  nonlocal used
  used+=r['bytes'];d.need(used<=cap,'Cumulative view cap');dst=d.resolve(out,name);dst.parent.mkdir(parents=True,exist_ok=True)
  with d.verified_stream(d.resolve(root,r['path']),{k:r[k]for k in('bytes','sha256')})as f:
   with dst.open('xb')as q:shutil.copyfileobj(f,q,1048576)
  files.append({'path':name,**{k:r[k]for k in('bytes','sha256')}})
 people=sorted(set(case['source_subjects']+[case['subject']]))
 for s in people:
  if case['mode']=='reset' and s!=case['subject']:
   pre=plan['private_source_rows'].get(str(s),plan['private_source_rows'].get(s))
   for split in('train','val'):
    for r in pre[split]:
     for ext,f in r['files'].items():copy(f,f'pretraining/webdataset_avg_split/{split}/subj{s:02d}/{r["key"]}.{ext}')
  row=plan['private_source_rows'][str(s)]if str(s)in plan['private_source_rows']else plan['private_source_rows'][s]
  for split in('train','val'):
   selected=row[split][:case['budget']]if split=='train'else row[split]
   for r in selected:
    for ext,f in r['files'].items():copy(f,f'webdataset_avg_split/{split}/subj{s:02d}/{r["key"]}.{ext}')
 row=plan['private_source_rows'].get(str(case['subject']),plan['private_source_rows'].get(case['subject']))
 for q,r in zip(case['query_ids'],row['test']):copy(r['files']['nsdgeneral.npy'],f'query/{q}.npy')
 view={'generation':plan['generation'],'case':case,'files':files,'query_targets_present':False,'isolation_qualified':False}
 d.put(out/'VIEW.json',view,30000000);return view

def reference(root,plan,out,cap):
 import numpy as np,array_io
 from PIL import Image
 d.need(plan['generation']==generation(),'Current plan');out=d.regular(out);out.mkdir(parents=True,exist_ok=False);used=0;images={}
 for s in p.SUBJECTS:
  row=plan['private_source_rows'].get(str(s),plan['private_source_rows'].get(s));images[s]=[]
  for i,r in enumerate(row['test']):
   rec=r['files']['jpg'];body=d.read(d.resolve(root,rec['path']),10000000,{k:rec[k]for k in('bytes','sha256')})
   im=Image.open(io.BytesIO(body));d.need(im.size==(425,425),'Native NSD JPEG geometry; do not rescale silently');x=np.asarray(im.convert('RGB'),dtype='<f4').transpose(2,0,1)[None]/255
   name=f'targets/s{s:02d}/{i:04d}.npy';q=d.resolve(out,name);q.parent.mkdir(parents=True,exist_ok=True);remaining=cap-used;pin=array_io.write(q,x,remaining);used+=pin['bytes'];images[s].append({'path':name,**pin})
 ref={'generation':plan['generation'],'cases':{c['case_id']:{'query_ids':c['query_ids'],'images':images[c['subject']]}for c in plan['cases']}}
 d.put(out/'REFERENCE.json',ref,10000000);return d.pin(d.canonical(ref))

if __name__=='__main__':main()
