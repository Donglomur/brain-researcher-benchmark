"""Invented tiny-neuron fixtures; no original observations."""
import sys,copy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'public'),str(ROOT/'operator')]
import numpy as np
from contract import *
from array_io import describe

def make(root):
    cohorts={k:{'neurons':2,'source_recording':k+'0','animal':k+'mouse','source_manifest_sha256':'a'*64} for k in COHORTS}
    cases=[];records=[];supports={};T=1200
    for cohort in COHORTS:
        for i in range(3):
            rid=cohort+str(i);dire=root/rid;dire.mkdir()
            arrays={'neural':np.ones((T,2),dtype='<i4'),'speed':np.linspace(0,1,T//10).reshape(-1,1).astype('<f8'),
              'speed_class':(np.arange(T//10)%25).reshape(-1,1).astype('<i4'),'video':np.zeros((T//10,2,2),dtype='|u1')}
            if cohort=='lateral':arrays['gaze']=np.zeros((T//10,2),dtype='<f8')
            ds={}
            for name,a in arrays.items():
                path=dire/(name+'.npy');np.save(path,a,allow_pickle=False);ds[name]=describe(path,rid+'/'+name+'.npy',a.shape,a.dtype.str)
            records.append({'id':rid,'animal':cohort+'mouse','cohort':cohort,'neurons':2,'ticks':T,'neural_tick_us':5000,'behavior_tick_us':50000,
              'event_definition_sha256':'b'*64,'class_map_sha256':'c'*64,'source_ids':['original'],'arrays':ds})
    for p in PANEL:
        cohort=p['cohort'];rows=[]
        for split,n,start in (('train',100,40),('validation',2,1080),('test',2,1140)):
            rec=cohort+'0'
            if p['family']=='held_session_speed':rec=cohort+str(('train','validation','test').index(split));start=40
            for j in range(n):
                t=start+10*j;rows.append({'id':f'{cohort}-{split}-{j}','recording':rec,'animal':cohort+'mouse','start_tick':t,'stop_tick':t+10,'context_start_tick':t-40,'split':split})
        if p['family']=='fewshot_speed':rows=[r for r in rows if r['split']!='train' or int(r['id'].split('-')[-1])<p['budget_percent']]
        sid=cohort+'-'+('fewshot'+str(p['budget_percent']) if p['family']=='fewshot_speed' else 'held' if p['family']=='held_session_speed' else 'blocked' if p['family'].startswith('blocked_') else 'source')
        policy='held_session' if p['family']=='held_session_speed' else 'blocked_time' if p['family'].startswith('blocked_') else 'source_split'
        supports[sid]={'cohort':cohort,'policy':policy,'rows':rows}
        c={'definition':copy.deepcopy(p),'policy':'held_session' if p['family']=='held_session_speed' else 'blocked_time' if p['family'].startswith('blocked_') else 'source_split',
         'support_id':sid,'output_shape':[2,10,2] if p['kind']=='counts' else [2,KINDS[p['kind']]],'class_centers':list(range(25)) if p['kind']=='classification' else None,
         'bindings':{'preprocessing_sha256':'d'*64,'source_metric_qualification_sha256':'e'*64,'reference_training_sha256':'f'*64}}
        cases.append(c)
    q={'schema':'neuroformer_query_v1','task_id':TASK,'source_revision':REVISION,'cohorts':cohorts,'supports':supports,'cases':cases,
       'qualification':{'source_manifest_sha256':'a'*64,'split_plan_sha256':'b'*64,'normalization_sha256':'c'*64,'metric_profile':'prospective_finite_artifact_v1','native_runtime_qualified':False}}
    b={'schema':'neuroformer_qualified_bridge_v1','closed_operator_exclusive':True,'source_roster_sha256':'a'*64,'transformation_program_sha256':'b'*64,
       'original_inputs':[{'source_id':'original','bytes':42,'sha256':'e'*64}],'recordings':records}
    q['qualification']['bridge_sha256']=digest(b)
    return q,b

def candidate(root,q):
    (root/'predictions').mkdir();rows=[]
    for i,c in enumerate(q['cases']):
        kind=c['definition']['kind'];a=np.ones(c['output_shape'],dtype='<i4' if kind=='counts' else '<f8')
        if kind=='classification':a/=25
        name=f'predictions/{i:04d}.npy';np.save(root/name,a,allow_pickle=False)
        rows.append({'case_id':c['definition']['id'],'array':describe(root/name,name,a.shape,a.dtype.str)})
    return {'schema':'neuroformer_submission_v1','task_id':TASK,'query_sha256':digest(q),'arm':'paper_and_data','predictions':rows}
