"""CBraMod full-primary-panel prediction artifact grader; never runs a model."""
import argparse
import json
import math
from pathlib import Path
import sys
import tempfile
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'public'))
from contract import need,exact,sha,cases,submission,digest
from arrays import snapshot,inspect_npy
from io_utils import read
from metrics import classify,regress,seed_summary,finite_scalar


def fields(task):
    return {'binary':['balanced_accuracy','average_precision','trapezoidal_pr_auc','auroc'],
        'multiclass':['balanced_accuracy','cohen_kappa','weighted_f1'],
        'regression':['pearson','r2','rmse']}[task]


def metric_values(target,predictions,d,qrow,purpose):
    groups=[r['group'] for r in qrow['rows']] if purpose=='improvement' else None
    values=regress(target,predictions[:,0],groups) if d['task']=='regression' else classify(target,predictions,d['classes'],groups)
    return {name:values[name] for name in fields(d['task'])}


def aggregate(rows,panel,abi):
    result=[]
    for d in panel['primary_downstream_datasets']:
        selected=[r for r in rows if r['dataset']==d['id']]
        for method in dict.fromkeys(r['method'] for r in selected):
            runs=[r for r in selected if r['method']==method]
            need([r['seed_slot'] for r in runs]==list(range(5)),'five complete ordered seed slots')
            report={key:seed_summary([r['metrics'][key] for r in runs]) for key in fields(d['task'])}
            for value in report.values():
                value['paper_sd']=None if abi['seed_sd_ddof'] is None else value['sd_population' if abi['seed_sd_ddof']==0 else 'sd_sample']
            if d['task']=='binary':report['auc_pr']=None if abi['pr_definition']=='unresolved' else report[abi['pr_definition']].copy()
            result.append({'dataset':d['id'],'method':method,'seed_slots':5,'metrics':report})
    return result


def references(value,panel,purpose):
    spec=cases(panel,purpose,reference=True);dmap={d['id']:d for d in panel['primary_downstream_datasets']}
    need(type(value) is dict and set(value)=={c['id'] for c in spec},'all fixed comparator/condition/seed references')
    for c in spec:
        exact(value[c['id']],fields(dmap[c['dataset']]['task']))
        for v in value[c['id']].values():need(v is None or finite_scalar(v),'finite or explicit undefined reference')
    return [{**c,'metrics':value[c['id']]} for c in spec]


def grade(candidate,q,panel,artifact_root,load_private):
    spec=submission(candidate,q,panel);dmap={d['id']:d for d in panel['primary_downstream_datasets']};qmap={d['id']:d for d in q['datasets']}
    captured={}
    with tempfile.TemporaryDirectory(prefix='cbramod-artifacts-') as tmp:
        try:
            for i,(item,c) in enumerate(zip(candidate['files'],spec)):
                destination=Path(tmp)/str(i);a=snapshot(artifact_root,item,destination)
                try:
                    if dmap[c['dataset']]['task']!='regression':
                        # Full probability admission before any protected target read.
                        for start in range(0,len(a),4096):
                            part=a[start:start+4096];need((part>=0).all() and (part<=1).all() and (np.abs(part.astype(np.float64).sum(axis=1)-1)<=1e-6).all(),'complete normalized class probabilities')
                finally:a._mmap.close()
                captured[c['id']]=destination
            gold=load_private();exact(gold,('query_sha256','targets','reference_metrics','reference_source_sha256'))
            need(gold['query_sha256']==digest(q),'private query binding');sha(gold['reference_source_sha256'])
            need(type(gold['targets']) is dict and set(gold['targets'])==set(dmap),'all12 private target datasets')
            ref=references(gold['reference_metrics'],panel,q['purpose'])
            for name,y in gold['targets'].items():
                need(type(y) in (np.ndarray,np.memmap) and y.shape==(len(qmap[name]['rows']),) and y.dtype.kind in 'fiu','complete private target vector')
                need(np.isfinite(y).all() and (np.abs(y)<=1e100).all(),'bounded finite targets')
                if dmap[name]['task']!='regression':need(np.equal(y,np.floor(y)).all() and (y>=0).all() and (y<dmap[name]['classes']).all(),'exact class-order labels')
            rows=[]
            for c,item in zip(spec,candidate['files']):
                # Reopen only an owned validated capture; at most one map is live.
                a=inspect_npy(captured[c['id']],item['shape'],item['dtype'])
                try:rows.append({**c,'metrics':metric_values(gold['targets'][c['dataset']],a,dmap[c['dataset']],qmap[c['dataset']],q['purpose'])})
                finally:a._mmap.close()
            summary=aggregate(rows,panel,q['metric_abi']);fixed=aggregate(ref,panel,q['metric_abi']);comparisons=[]
            for row in summary:
                for base in fixed:
                    if row['dataset']!=base['dataset'] or q['purpose']=='reproduction' and row['method']!=base['method']:continue
                    result={}
                    for metric,a in row['metrics'].items():
                        b=base['metrics'][metric]
                        if a is None or b is None or a['mean'] is None or b['mean'] is None:delta=None
                        else:
                            delta=a['mean']-b['mean']
                            if q['purpose']=='reproduction':delta=abs(delta)
                            elif metric=='rmse':delta=-delta
                            if not math.isfinite(delta):delta=None
                        result[metric]=delta
                    comparisons.append({'dataset':row['dataset'],'method':row['method'],'fixed_reference_method':base['method'],
                        'absolute_seed_mean_deviation' if q['purpose']=='reproduction' else 'signed_seed_mean_gain':result})
            return {'schema':'cbramod_artifact_result_v1','purpose':q['purpose'],'condition':q['condition'],
                'information_arm_label':candidate['information_arm'],'access_attested':False,'methods':summary,'comparisons':comparisons,
                'cross_dataset_score':None,'binary_reward':None,'scientific_qualification':False,'full_paper_reproduced':False,
                'metric_abi':q['metric_abi'],'limits':['Artifact metrics do not authenticate models, seeds, pretraining exclusion, selected checkpoint, subject identity or actual training exposure.','All other appendix families and authentic source/native/data qualification remain required.']}
        finally:
            captured.clear()


def main(argv=None):
    p=argparse.ArgumentParser();p.add_argument('--candidate',required=True);p.add_argument('--operator',required=True);a=p.parse_args(argv)
    try:
        op,_=read(a.operator,1_000_000)
        if any(op.get(k) is None for k in ('query','targets','reference_metrics')):
            print(json.dumps({'status':'data_unavailable','score':None,'target_loader_calls':0}));return 2
        root=Path(a.operator).resolve().parent
        def bound(row):
            need(type(row['path']) is str and not Path(row['path']).is_absolute() and '..' not in Path(row['path']).parts,'relative operator path');sha(row['sha256']);return root/row['path']
        q,_=read(bound(op['query']),256_000_000,op['query']['sha256']);c,_=read(a.candidate,4_000_000);panel,_=read(ROOT/'public/PANEL.json',2_000_000)
        def private():
            refs,_=read(bound(op['reference_metrics']),16_000_000,op['reference_metrics']['sha256']);targets={}
            need(type(op['targets']) is dict and sum(r['bytes'] for r in op['targets'].values())<=100_000_000,'bounded complete target storage')
            with tempfile.TemporaryDirectory(prefix='cbramod-gold-') as tmp:
                for i,(name,row) in enumerate(op['targets'].items()):
                    bound(row);arr=snapshot(root,row,Path(tmp)/str(i))
                    try:need(arr.ndim==2 and arr.shape[1]==1,'target N-by-one rectangle');targets[name]=np.array(arr[:,0],copy=True)
                    finally:arr._mmap.close()
            return {'query_sha256':digest(q),'targets':targets,'reference_metrics':refs,'reference_source_sha256':op['reference_source_sha256']}
        result=grade(c,q,panel,Path(a.candidate).resolve().parent,private)
        print(json.dumps(result,allow_nan=False));return 0
    except (ValueError,TypeError,KeyError,OSError,OverflowError,RecursionError) as e:
        print(json.dumps({'status':'invalid_or_operator_error','score':None,'error':str(e)}));return 2


if __name__=='__main__':raise SystemExit(main())
