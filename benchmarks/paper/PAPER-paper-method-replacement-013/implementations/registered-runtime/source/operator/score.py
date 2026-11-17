"""Strict all-file admission before any private target or fixed-reference access."""
import sys,argparse,tempfile,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'public'))
from contract import *
from array_io import array,finite,snapshot
import metrics
import numpy as np
from stage import target_values

def admit(v,q,root,owned):
    submission(v,q);require(sum(r['array']['bytes'] for r in v['predictions'])<=16_000_000_000,'full candidate bound')
    for row,c in zip(v['predictions'],q['cases']):
        d=row['array'];snapshot(root,d,owned)
        with array(owned,d) as a:
            finite(a)
            if c['definition']['kind']=='counts':require(bool((a>=0).all()),'nonnegative events')
            if c['definition']['kind']=='classification':require(bool(((a>=0)&(a<=1)).all()) and bool((np.abs(a.sum(1)-1)<=1e-8).all()),'complete probability support')

def metric(kind,y,p,centers=None):
    if kind=='counts':
        require(y.shape==p.shape,'complete count geometry')
        out=metrics.event_counts([int(x) for x in y.reshape(-1)],[int(x) for x in p.reshape(-1)])
        true_sets=[set(int(i) for i in np.flatnonzero((v>0).any(axis=0))) for v in y]
        pred_sets=[set(int(i) for i in np.flatnonzero((v>0).any(axis=0))) for v in p]
        out['unqualified_source_interval_diagnostics']=metrics.source_interval_id_scores(true_sets,pred_sets)
        return out
    if kind=='classification':return metrics.classification([int(x) for x in y[:,0]],p.tolist(),centers)
    require(y.shape==p.shape,'complete behavior geometry')
    names=('speed','phi','theta') if kind=='joint' else ('speed',)
    return {name:metrics.regression(y[:,j].tolist(),p[:,j].tolist()) for j,name in enumerate(names)}

def endpoint_values(kind,v):
    if kind=='counts':return {k:v[k] for k in ('count_intersection_f1','presence_f1','precision','recall')}
    if kind=='classification':return {k:v[k] for k in ('accuracy','balanced_accuracy','weighted_f1','decoded_center_pearson')}
    return {name+'/'+k:m[k] for name,m in v.items() for k in ('pearson_r','r2','rmse')}

def biological_macro(kind,y,p,support,centers):
    """Equal recordings within animal, then equal animals; null support retained."""
    groups={}
    for i,row in enumerate(support):groups.setdefault((row['animal'],row['recording']),[]).append(i)
    by_animal={};records=[]
    for (animal,recording),ix in groups.items():
        values=endpoint_values(kind,metric(kind,y[ix],p[ix],centers));records.append({'animal':animal,'recording':recording,'windows':len(ix),'values':values});by_animal.setdefault(animal,[]).append(values)
    def macro(vs):return {k:metrics.mean([v[k] for v in vs]) if all(v[k] is not None for v in vs) else None for k in vs[0]}
    animals=[{'animal':k,'values':macro(v)} for k,v in by_animal.items()]
    return {'recordings':records,'animals':animals,'equal_animal_mean':macro([x['values'] for x in animals]),'identity_qualification_external':True}

def _grade_admitted(v,q,owned,target_loader,observations,reference_loader=None,production=True):
    query(q,production);submission(v,q)
    target=target_binding(q,target_loader())
    records={r['id']:r for r in target['bridge']['recordings']};rows=[]
    for row,c in zip(v['predictions'],q['cases']):
        test=[r for r in rows_for(q,c) if r['split']=='test'];y=target_values(c,test,records,observations)
        with array(owned,row['array']) as p:
            values=metric(c['definition']['kind'],y,p,c['class_centers'])
            macro=biological_macro(c['definition']['kind'],y,p,test,c['class_centers'])
        rows.append({'case_id':row['case_id'],'definition':c['definition'],'metrics':values,'biological_macro':macro})
    result={'schema':'neuroformer_assessment_v1','task_id':TASK,'query_sha256':digest(q),'arm':v['arm'],'rows':rows,
      'binary_reward':None,'whole_paper_reproduced':False,'source_metric_parity_qualified':False,
      'independent_biological_generalization':'requires authenticated identities and isolated held-session production'}
    if reference_loader is not None:result['fixed_reference']=compare(result,reference_loader())
    return result

def grade(v,q,candidate_root,target_loader,observations,reference_loader=None,production=True):
    query(q,production)
    with tempfile.TemporaryDirectory(prefix='neuroformer-private-admission-') as owned:
        admit(v,q,candidate_root,owned)
        return _grade_admitted(v,q,owned,target_loader,observations,reference_loader,production)

def leaves(x,prefix=''):
    out={}
    if type(x) is dict:
        for k,v in x.items():out.update(leaves(v,prefix+'/'+k))
    elif type(x) in (float,int) or x is None:out[prefix]=x
    return out

def compare(result,ref):
    exact(ref,('schema','task_id','query_sha256','reference_program_sha256','reference_run_sha256','rows'))
    require(ref['schema']=='neuroformer_fixed_metrics_v1' and ref['task_id']==TASK and ref['query_sha256']==result['query_sha256'],'independent reference support')
    for k in ('reference_program_sha256','reference_run_sha256'):sha256(ref[k])
    require(type(ref['rows']) is list and len(ref['rows'])==len(result['rows']),'full fixed reference roster')
    rows=[]
    for a,b in zip(result['rows'],ref['rows']):
        exact(b,('case_id','metrics','equal_animal_mean'));require(a['case_id']==b['case_id'],'fixed reference case order')
        av=leaves({'pooled':a['metrics'],'equal_animal':a['biological_macro']['equal_animal_mean']});bv=leaves({'pooled':b['metrics'],'equal_animal':b['equal_animal_mean']});require(set(av)==set(bv),'exact fixed metric fields');delta={}
        for key,x in av.items():
            y=bv[key]
            if y is not None:number(y)
            d=None if x is None or y is None else x-y
            leaf=key.rsplit('/',1)[-1];direction=-1 if leaf=='rmse' else 1 if leaf in ('pearson_r','r2','accuracy','balanced_accuracy','weighted_f1','decoded_center_pearson','count_intersection_f1','presence_f1','precision','recall') else None
            delta[key]={'absolute_deviation':abs(d) if d is not None else None,'signed_candidate_minus_reference':d,
                        'favorable_signed_change':d*direction if d is not None and direction is not None else None}
        rows.append({'case_id':a['case_id'],'metrics':delta})
    return {'rows':rows,'reference_run_sha256':ref['reference_run_sha256'],'runtime_qualification_inferred':False,'tolerance_or_pass_threshold':None}

def main():
    a=argparse.ArgumentParser(description=__doc__)
    for k in ('query','query-sha256','submission','target','observations','output'):a.add_argument('--'+k,required=True)
    a.add_argument('--reference');a.add_argument('--reference-sha256');x=a.parse_args();fresh(x.output)
    require(bool(x.reference)==bool(x.reference_sha256),'paired reference operands')
    b=capture(x.query);require(hashlib.sha256(b).hexdigest()==x.query_sha256,'trusted query');q=query(decode(b));v=load(x.submission)
    def ref():
        b=capture(x.reference);require(hashlib.sha256(b).hexdigest()==x.reference_sha256,'independently selected fixed reference');return decode(b)
    result=grade(v,q,Path(x.submission).parent,lambda:load(x.target),x.observations,ref if x.reference else None)
    save(x.output,result)
if __name__=='__main__':main()
