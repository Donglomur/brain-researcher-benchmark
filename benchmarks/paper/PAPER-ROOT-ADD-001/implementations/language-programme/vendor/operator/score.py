"""Continuous native reconstruction or trusted raw-prediction grading.
All declared candidate files are admitted before any private numerical callback.
"""
import argparse,sys
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'public'))
from delivery_io import need,read,decode,pin,put,resolve,check_pin,exact
from array_io import arrays,fresh_output
from protocol import SESSIONS,ARMS,FOLD_IDS,CAP,PROTOCOL_SHA,native_shapes
from core import correlation,hierarchical


def submission(raw,mode,design_sha,expected_ids):
    d=decode(raw);exact(d,['schema','mode','protocol_sha256','design_sha256','files'])
    need(d['schema']=='language_submission_v1' and d['mode']==mode and d['protocol_sha256']==PROTOCOL_SHA and d['design_sha256']==design_sha,'Submission identity')
    check_pin({'bytes':1,'sha256':d['design_sha256']},1)
    need(type(d['files']) is list and [r['id'] for r in d['files']]==list(expected_ids),'Exact complete ordered file roster')
    need(len({r['path'] for r in d['files']})==len(d['files']),'Unique output paths')
    for r in d['files']:
        exact(r,['id','path','bytes','sha256']+(['case_sha256'] if mode=='prediction' else []));check_pin({k:r[k] for k in ('bytes','sha256')},CAP)
    need(sum(r['bytes'] for r in d['files'])<=512*1024**2,'Total candidate file bound')
    return d


def capture_arrays(root,r,keys):
    raw=read(resolve(root,r['path']),CAP,{k:r[k] for k in ('bytes','sha256')})
    return arrays(raw,keys,CAP)


def native_admit(root,d):
    out={}
    for r in d['files']:
        shapes=native_shapes(r['id']);keys=[prefix+k for k in shapes for prefix in ('value_','defined_')]
        v=capture_arrays(root,r,keys)
        for k,shape in shapes.items():
            value=v['value_'+k];mask=v['defined_'+k]
            need(value.shape==mask.shape==shape and value.dtype.kind=='f' and value.dtype.itemsize in (4,8) and mask.dtype==np.dtype('uint8') and
                 np.isfinite(value).all() and np.isin(mask,[0,1]).all() and np.all(np.abs(value)<=1) and np.all(value[mask==0]==0),'Native correlation/mask contract')
        out[r['id']]=v
    return out


def native_evaluate(candidate,private_get):
    detail={};primary={};worst=0.;availability=[]
    for s,c in candidate.items():
        r=private_get(s);detail[s]={}
        for k in native_shapes(s):
            cm=c['defined_'+k];rm=r['defined_'+k];cv=c['value_'+k].astype(np.float64);rv=r['value_'+k].astype(np.float64)
            need(cm.shape==rm.shape==cv.shape==rv.shape,'Trusted reference geometry')
            need(np.array_equal(cm,rm),'Candidate availability must equal trusted full reference')
            m=rm.astype(bool);err=np.abs(cv-rv)
            detail[s][k]={'mae':float(err[m].mean()) if m.any() else None,'max_absolute_error':float(err[m].max()) if m.any() else None,'defined':int(m.sum()),'total':int(m.size)}
            if m.any():worst=max(worst,float(err[m].max()))
            if not m.all():availability.append({'session':s,'field':k,'undefined':int((~m).sum())})
        u=detail[s]['unit'];primary[s]=u['mae'] if u['defined']==u['total'] else None
    return {'mode':'native','primary_equal_person_unit_context_MAE':hierarchical(primary),'per_session_fields':detail,'max_absolute_error':worst,'trusted_undefined_support':availability,'scientific_pass':None,'method_execution_authenticated':False}


def binding_admit(b,design_sha):
    need(b.get('schema')=='language_episodes_v1' and b.get('design_sha256')==design_sha and list(b.get('episodes',{}))==FOLD_IDS,'Complete trusted episode collection')
    source_sets={}
    for eid,r in b['episodes'].items():
        c=r['case'];s=eid.rsplit('_f',1)[0];fold=int(eid[-1])
        need(c['schema']=='language_episode_v1' and c['id']==eid and c['session']==s and c['fold']==fold and c['protocol_sha256']==PROTOCOL_SHA and c['design_sha256']==design_sha and c['units']==SESSIONS[s]['units'] and type(c['rows']) is int and 2<=c['rows']<=SESSIONS[s]['time_bins'],'Trusted case geometry/identity')
        rows=r['source_rows'];need(len(rows)==c['rows'] and all(type(x) is int and 11<=x<SESSIONS[s]['time_bins'] for x in rows) and rows==sorted(set(rows)),'Ordered unique held rows')
        old=source_sets.setdefault(s,set());need(not old.intersection(rows),'Pooled query rows occur once');old.update(rows)
        need(len(c['query_ids'])==c['rows'] and len(set(c['query_ids']))==c['rows'],'Unique opaque case identities')
    return b


def prediction_admit(root,d,b):
    out={}
    for r in d['files']:
        c=b['episodes'][r['id']]['case']
        need(r['case_sha256']==pin(__import__('delivery_io').canonical(c))['sha256'],'Candidate exact public case join')
        a=capture_arrays(root,r,['prediction'])
        for x in a.values():need(x.shape==(c['rows'],c['units']) and x.dtype.kind=='f' and x.dtype.itemsize in (4,8) and np.isfinite(x).all(),'Every arm finite full prediction geometry')
        out[r['id']]={k:v.astype(np.float64) for k,v in a.items()}
    return out


def prediction_evaluate(predictions,b,private_get):
    sessions={};support={}
    for s in SESSIONS:
        ys=[];ps={k:[] for k in ARMS}
        for f in range(5):
            eid=f'{s}_f{f}';target,baselines=private_get(eid);y=np.asarray(target,dtype=np.float64);c=b['episodes'][eid]['case']
            need(y.shape==(c['rows'],c['units']) and np.isfinite(y).all(),'Trusted finite neural targets');ys.append(y)
            ps['candidate'].append(predictions[eid]['prediction'])
            need(set(baselines)==set(ARMS)-{'candidate'},'Exact trusted baseline roster')
            for k in ARMS[1:]:
                v=np.asarray(baselines[k],dtype=np.float64);need(v.shape==y.shape and np.isfinite(v).all(),'Trusted baseline geometry');ps[k].append(v)
        y=np.concatenate(ys);sessions[s]={};support[s]={}
        for k in ARMS:
            r,m=correlation(y,np.concatenate(ps[k]));sessions[s][k]=float(r.mean()) if m.all() else None
            support[s][k]={'defined_units':int(m.sum()),'total_units':len(m),'per_unit_correlation':r.tolist(),'defined':m.tolist()}
    aggregates={k:hierarchical({s:v[k] for s,v in sessions.items()}) for k in ARMS}
    gains={k:hierarchical({s:(v['candidate']-v[k] if v['candidate'] is not None and v[k] is not None else None) for s,v in sessions.items()}) for k in ARMS if k!='candidate'}
    return {'mode':'prediction','primary_equal_person_pearson':aggregates,'paired_candidate_gain':gains,'per_session':sessions,'support':support,'scientific_pass':None,'baseline_predictions_root_bound':True,'method_execution_authenticated':False,'note':'Trusted baseline manifest must be supplied only by the operator after its chosen producer closes; candidate self-reported baseline scores are never used.'}


def main():
    p=argparse.ArgumentParser();p.add_argument('--mode',choices=['native','prediction'],required=True);p.add_argument('--submission',required=True);p.add_argument('--candidate-root',required=True);p.add_argument('--design-sha',required=True);p.add_argument('--trusted-manifest',required=True);p.add_argument('--trusted-sha',required=True);p.add_argument('--trusted-root',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    fresh_output(a.output);candidate_raw=read(a.submission,500000);candidate=submission(candidate_raw,a.mode,a.design_sha,SESSIONS if a.mode=='native' else FOLD_IDS)
    # Binding metadata is not an answer; numerical bodies remain unopened until all candidates admit.
    trusted_raw=read(a.trusted_manifest,32*1024**2);need(pin(trusted_raw)['sha256']==a.trusted_sha,'Root-selected trusted manifest pin')
    if a.mode=='native':
        c=native_admit(a.candidate_root,candidate)
        rmanifest=submission(trusted_raw,'native',a.design_sha,SESSIONS)
        refs={r['id']:r for r in rmanifest['files']}
        def get(s):return native_admit(a.trusted_root,{'files':[refs[s]]})[s]
        result=native_evaluate(c,get)
    else:
        b=binding_admit(decode(trusted_raw),a.design_sha);c=prediction_admit(a.candidate_root,candidate,b)
        def get(eid):
            r=b['episodes'][eid];return capture_arrays(a.trusted_root,r['target'],['target'])['target'],capture_arrays(a.trusted_root,r['baselines'],ARMS[1:])
        result=prediction_evaluate(c,b,get)
    result.update(protocol_sha256=PROTOCOL_SHA,design_sha256=a.design_sha,submission=pin(candidate_raw),trusted_manifest=pin(trusted_raw))
    put(a.output,result,8*1024**2)
if __name__=='__main__':main()
