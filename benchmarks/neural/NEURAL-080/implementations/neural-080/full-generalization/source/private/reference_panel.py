"""Full six-person/five-arm reference producer with one live full/shift model.

Prospective fixed legacy ridge recipe; native execution/competence unqualified.
Only operator-prepared views are read. Query targets are never selected here.
"""
import hashlib
from pathlib import Path
from input_owner import need,integer,descriptor,capture,Writer
from source_pipeline import decode_json

SUBJECTS=tuple('sub-%02d'%i for i in range(1,7))
ARMS=('nuisance','nuisance_eye','nuisance_dynamic','full','full_shift500ms')
COLUMNS=(2630,3830,8390,9590,9590)

def validate_roster(rows):
    need(type(rows) is list and len(rows)==30,'Full six-person/five-arm view roster')
    expected=[(p,a) for p in SUBJECTS for a in ARMS]
    seen=[];roots=set()
    for row in rows:
        need(type(row) is dict and set(row)=={'subject','arm','root','scope'},'Closed view role')
        need(type(row['root']) is str and row['root'] not in roots,'Unique selected view roots')
        roots.add(row['root']);descriptor(row['scope'])
        need(row['scope']['path']=='SCOPE.json','Exact prepared scope')
        seen.append((row['subject'],row['arm']))
    need(seen==expected,'Complete ordered person/arm identity')
    return rows

def read_view(row,query_sha,owner,np,arrays):
    rec=owner.begin('reference_view:'+row['subject']+':'+row['arm']);answer=None
    try:
        root=Path(row['root']);scope=decode_json(capture(root,row['scope'],owner))
        need(scope['schema']=='neural080_scope_v1' and scope['subject']==row['subject'] and scope['arm']==row['arm'] and scope['query_sha256']==query_sha,'Original view coordinates')
        need(scope['fit_video_ids']==[i for i in range(1,1001) if i%10] and scope['validation_video_ids']==list(range(10,1001,10)) and scope['query_video_ids']==list(range(1001,1103)),'Exact fixed video partitions')
        columns=COLUMNS[ARMS.index(row['arm'])]
        need(type(scope['feature_columns']) is int and scope['feature_columns']==columns and scope['target_shape']==[127,150] and scope['query_targets_supplied'] is False,'View geometry and target barrier')
        files=scope['files'];need(type(files) is list and len(files)==5,'Exactly three designs/two permitted target arrays')
        mapped={r['path']:r for r in files};names={'x_fit.npy','x_validation.npy','x_query.npy','y_fit.npy','y_validation.npy'}
        need(set(mapped)==names and len(mapped)==len(files),'No query target or duplicate view role')
        result={}
        for split,n in (('fit',900),('validation',100),('query',102)):
            for axis in ('x','y'):
                if split=='query' and axis=='y':continue
                name=axis+'_'+split+'.npy';shape=(n,columns) if axis=='x' else (n,127,150)
                raw=capture(root,mapped[name],owner,max_bytes=160_000_000)
                owner.reserve('retained_bytes',n*(columns if axis=='x' else 127*150)*8)
                result[axis+'_'+split]=arrays.decode(raw,shape,max_bytes=160_000_000)
        answer=(result,mapped)
    except BaseException as exc:owner.failure(rec,exc)
    owner.complete(rec);return answer

def same_training(full,shift):
    for name in ('x_fit.npy','x_validation.npy','y_fit.npy','y_validation.npy'):
        need(full[name]['bytes']==shift[name]['bytes'] and full[name]['sha256']==shift[name]['sha256'],'Shift arm must reuse exact full FIT/validation arrays')

def select_model(values,np,fit,predict,alphas):
    x=values['x_fit'];y=values['y_fit'].reshape(900,-1)
    vx=values['x_validation'];vy=values['y_validation'].reshape(100,-1)
    losses=[]
    for alpha in alphas:
        loss=float(np.mean((predict(fit(x,y,alpha),vx)-vy)**2))
        need(np.isfinite(loss),'Finite complete validation loss');losses.append(loss)
    chosen=min(range(len(alphas)),key=lambda i:(losses[i],i))
    model=fit(np.concatenate((x,vx)),np.concatenate((y,vy)),alphas[chosen])
    return model,chosen,losses

def run(rows,query_sha,out,owner):
    rec=owner.begin('reference_complete_panel');answer=None
    try:
        validate_roster(rows)
        need(type(query_sha) is str and len(query_sha)==64 and all(c in '0123456789abcdef' for c in query_sha),'Selected query pin')
        import numpy as np
        import arrays
        need(np.__version__=='2.2.6','Selected NumPy source profile')
        from reference_model import fit,predict,ALPHAS
        writer=Writer(out,owner);predictions=[];selection=[]
        for p in SUBJECTS:
            full_model=None;full_files=None
            for arm in ARMS:
                row=rows[SUBJECTS.index(p)*5+ARMS.index(arm)]
                values,files=read_view(row,query_sha,owner,np,arrays)
                if arm=='full_shift500ms':
                    same_training(full_files,files)
                    model=full_model
                    need(model is not None,'Live full model retained before shifted-query prediction')
                else:
                    # Declared logical working reservation; LAPACK/native peak,
                    # BLAS threads and process memory remain deployment gates.
                    n=1000;cols=COLUMNS[ARMS.index(arm)];targets=127*150
                    owner.reserve('retained_bytes',8*(n*cols+3*n*targets+3*n*n+102*targets))
                    model,chosen,losses=select_model(values,np,fit,predict,ALPHAS)
                    selection.append({'subject':p,'arm':arm,'alpha':ALPHAS[chosen],'validation_losses':losses,'training_rows':1000,'scaling_rows':900})
                    if arm=='full':full_model=model;full_files=files
                result=predict(model,values['x_query']).reshape(102,127,150)
                r=writer.array(p+'_'+arm+'.npy',result)
                predictions.append({'subject':p,'arm':arm,'file':r['path'],'bytes':r['bytes'],'sha256':r['sha256']})
        writer.document('submission.json',{'schema':'neural080_submission_v1','query_sha256':query_sha,'predictions':predictions})
        answer={'schema':'neural080_reference_panel_v2','selection':selection,'predictions':30,'full_shift_reuses_live_full_model':True,'query_targets_read':0,'competence_qualified':False}
        writer.document('REFERENCE.json',answer)
    except BaseException as exc:owner.failure(rec,exc)
    owner.complete(rec);return answer
