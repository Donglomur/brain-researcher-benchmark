"""Deterministic numeric-interchange preparation; raw IBL-to-interchange is missing.

This program is not a neural decoder, does not fit the behavioral-prior model,
and cannot establish authentic raw lineage merely from an operator declaration.
"""
import argparse,hashlib,io,json,math,pathlib,sys
import numpy as np
BUILD=pathlib.Path(__file__).resolve().parent
ROOT=BUILD.parents[1] if BUILD.name=='build' else BUILD
sys.path.insert(0,str(ROOT/'public/common'))
from artifact_io import Invalid,capture,strict_json,read_predictions
from bindings import bound,sha,fresh,write_json
from program_io import frozen_protocol

def split_ids(eid,ids):
    if len(ids)<10 or any(type(i)is not int or i<0 for i in ids) or len(set(ids))!=len(ids):raise Invalid('>=10 unique original integer trial IDs required')
    order=sorted(range(len(ids)),key=lambda i:hashlib.sha256((eid+'\0'+str(ids[i])).encode()).digest())
    a=math.floor(.7*len(ids));b=math.floor(.8*len(ids))
    return [np.asarray(order[:a]),np.asarray(order[a:b]),np.asarray(order[b:])]

def validate_case(c,protocol):
    fields={'eid','animal_id','target','trial_ids','n_units','sources','provenance','x','y','groups'}
    if type(c)is not dict or set(c)!=fields:raise Invalid('exact interchange case fields required')
    if c['eid'] not in protocol['cohort_eids'] or c['target'] not in protocol['targets']:raise Invalid('unexpected case')
    if type(c['animal_id'])is not str or not c['animal_id'].strip() or c['animal_id'].lower() in ['unknown','unresolved']:raise Invalid('resolved animal identity required')
    if type(c['n_units'])is not int or not 1<=c['n_units']<=100000:raise Invalid('neuron count required')
    spec=protocol['targets'][c['target']];prov=c['provenance']
    if type(prov)is not dict or any(prov.get(k)!=spec[k] for k in ['alignment','window_seconds','bin_seconds']):raise Invalid('paper-specific window identity required')
    for key in ['raw_to_interchange_source','complete_trial_eligibility_source','animal_identity_source','spike_sorting_version','behavior_units']:
        if type(prov.get(key))is not str or not prov[key].strip():raise Invalid('complete preparation provenance required: '+key)
    if c['target']=='prior' and not prov.get('fitted_prior_model_source'):raise Invalid('fitted prior provenance required, never block probability substitution')
    if type(c['sources'])is not list or not c['sources']:raise Invalid('original object descriptors required')
    import re
    for x in c['sources']:
        if type(x)is not dict or set(x)!={'url','version','bytes','sha256'} or not str(x['url']).startswith('https://') or not x['version'] or type(x['bytes'])is not int or x['bytes']<1 or not re.fullmatch('[0-9a-f]{64}',str(x['sha256'])):raise Invalid('versioned original source descriptors required')
    split_ids(c['eid'],c['trial_ids'])
    return None

class Writer:
    def __init__(self,root,cap):self.root=root;self.cap=cap;self.total=0
    def put(self,name,b):
        if self.total+len(b)>self.cap:raise Invalid('total prepared-output cap exceeded')
        p=self.root/name;p.parent.mkdir(parents=True,exist_ok=True)
        with p.open('xb') as f:f.write(b)
        self.total+=len(b);return {'path':name,'bytes':len(b),'sha256':sha(b)}
    def array(self,name,a):
        f=io.BytesIO();np.save(f,np.asarray(a,dtype='<f8'),allow_pickle=False);return self.put(name,f.getvalue())
    def json(self,name,a):return self.put(name,(json.dumps(a,indent=2,allow_nan=False)+'\n').encode())

def prepare(source,output,protocol_path,max_bytes):
    pb=capture(protocol_path,100000);frozen_protocol(pb)
    return _project_numeric_interchange(source,output,pb,max_bytes)

def _project_numeric_interchange(source,output,pb,max_bytes):
    # Generic pure projection used only after frozen protocol admission above;
    # generated tests call it directly under a distinct invented fixture name.
    fresh(output);protocol=strict_json(pb)
    mb=capture(source/'INTERCHANGE.json',10_000_000);manifest=strict_json(mb)
    if type(manifest)is not dict or set(manifest)!={'schema','cases'} or manifest['schema']!='trial_session_numeric_interchange_v1':raise Invalid('numeric interchange manifest required')
    expected={(e,t) for e in protocol['cohort_eids'] for t in protocol['targets']}
    cases=manifest['cases']
    if type(cases)is not list or len(cases)!=len(expected) or {(c.get('eid'),c.get('target')) for c in cases}!=expected:raise Invalid('all40sessions x all4targets required; no silent omission')
    ordered=sorted(cases,key=lambda c:(protocol['cohort_eids'].index(c['eid']),list(protocol['targets']).index(c['target'])))
    for c in ordered:validate_case(c,protocol)
    membership={}
    for eid in protocol['cohort_eids']:
        union=sorted({i for c in ordered if c['eid']==eid for i in c['trial_ids']})
        membership[eid]=[{union[i] for i in ix} for ix in split_ids(eid,union)]
    splits=[]
    for c in ordered:
        parts=[np.asarray([i for i,t in enumerate(c['trial_ids']) if t in pool],dtype=int) for pool in membership[c['eid']]]
        if any(len(ix)==0 for ix in parts):raise Invalid('each target needs nonempty train/validation/query under shared original-trial split')
        splits.append(parts)
    for e in protocol['cohort_eids']:
        if len({c['animal_id'] for c in cases if c['eid']==e})!=1:raise Invalid('same session must have one animal identity')
    output.mkdir();w=Writer(output,max_bytes);public=[];yy=[];templates=[];gg=[];offset=0;goffset=0;source_records=[]
    for i,(c,parts) in enumerate(zip(ordered,splits)):
        spec=protocol['targets'][c['target']];k=len(c['trial_ids']);t=spec['neural_bins'];n=c['n_units'];d=spec['output_bins']
        # Decode captured authenticated bytes, never reopen a path after hashing.
        x=read_predictions(bound(source,c['x']),(k,t,n));y=read_predictions(bound(source,c['y']),(k,d));g=read_predictions(bound(source,c['groups']),(k,3))
        if np.any(x<0) or np.any(x>2**53) or np.any(x!=np.floor(x)):raise Invalid('exact nonnegative spike counts required; no uint8 cast')
        if c['target']=='choice' and not np.isin(y,[0.,1.]).all():raise Invalid('binary choice mapping required')
        if c['target']=='prior' and np.any((y<0)|(y>1)):raise Invalid('fitted prior must be a probability in[0,1]')
        row={'case_id':f'case-{i:03d}','eid':c['eid'],'animal_id':c['animal_id'],'target':c['target'],'n_units':n,'neural_bins':t,'output_bins':d,'query_trials':len(parts[2]),'offset':[offset,offset+len(parts[2])*d],'group_offset':[goffset,goffset+len(parts[2])],'files':{},'trial_ids':{}}
        for label,ix in zip(['train','validation','query'],parts):
            row['trial_ids'][label]=[c['trial_ids'][j] for j in ix]
            row['files'][label+'_x']=w.array(f'public/data/case-{i:03d}-{label}-x.npy',x[ix])
            if label!='query':row['files'][label+'_y']=w.array(f'public/data/case-{i:03d}-{label}-y.npy',y[ix])
        # A training-only time template is a transparent no-neural-information control.
        mean=np.sum(y[parts[0]]/len(parts[0]),axis=0)
        if not np.isfinite(mean).all():raise Invalid('training template arithmetic unavailable')
        yy.append(y[parts[2]].ravel());templates.append(np.broadcast_to(mean,(len(parts[2]),d)).ravel());gg.append(g[parts[2]])
        offset=row['offset'][1];goffset=row['group_offset'][1];public.append(row)
        source_records.append({'case_id':row['case_id'],'sources':c['sources'],'provenance':c['provenance'],'input_pins':{key:c[key] for key in ['x','y','groups']}})
    panel={'schema':'trial_session_panel_v1','condition':protocol['condition'],'protocol_sha256':sha(pb),'methods':protocol['methods'],'prediction_rows':offset,'group_rows':goffset,'cases':public,'raw_lineage_verified':False}
    pd=w.json('public/PANEL.json',panel)
    refs={key:w.array('private/'+key+'.npy',a) for key,a in [('truth',np.concatenate(yy)),('template',np.concatenate(templates)),('groups',np.concatenate(gg))]}
    for d in refs.values():d['path']=pathlib.PurePosixPath(d['path']).name
    w.json('private/reference.json',{'schema':'trial_session_reference_v1','panel_sha256':pd['sha256'],**refs})
    w.json('private/PREPARATION.json',{'status':'prepared_from_operator_numeric_interchange','raw_IBL_to_interchange_verified':False,'protocol_sha256':sha(pb),'interchange_sha256':sha(mb),'all_cases':len(public),'source_records':source_records,'preparer_sha256':sha(pathlib.Path(__file__).read_bytes()),'scientific_fits_or_scores':False})
    return {'prepared_files_bytes':w.total,'case_count':len(public),'raw_source_bridge':'missing'}

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--source',type=pathlib.Path,required=True);ap.add_argument('--output',type=pathlib.Path,required=True);ap.add_argument('--max-bytes',type=int,required=True);ap.add_argument('--protocol',type=pathlib.Path,default=ROOT/'public/common/PROTOCOL.json');a=ap.parse_args()
    if not 1<=a.max_bytes<=100_000_000_000:raise SystemExit('explicit bounded output allowance required')
    print(json.dumps(prepare(a.source,a.output,a.protocol,a.max_bytes)))
