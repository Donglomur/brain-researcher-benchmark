"""Protected patient-macro metrics; invoked only after complete target barrier."""
from core import need
from schema import cohort,validate_prediction

def score_cell(prediction,rows):
    import numpy as np
    eligible=[r for r in rows if r['eligibility']]
    pred=validate_prediction(prediction,[r['identity']['trial'] for r in eligible]);byid={r['id']:r['p_high'] for r in pred}
    people=sorted({r['identity']['patient'] for r in rows});result=[]
    for person in people:
        selected=[r for r in eligible if r['identity']['patient']==person]
        y=np.asarray([int(r['load']==3) for r in selected]);p=np.asarray([byid[r['identity']['trial']] for r in selected])
        need(len(selected)>0 and set(y.tolist())=={0,1},'complete patient with both classes required; no silent patient or class deletion')
        decision=p>=.5
        ba=float(((decision[y==1]==1).mean()+(decision[y==0]==0).mean())/2)
        q=np.clip(p,1e-15,1-1e-15);ll=float(-np.mean(y*np.log(q)+(1-y)*np.log1p(-q)))
        result.append({'patient':person,'trials':len(y),'low':int((y==0).sum()),'high':int((y==1).sum()),'balanced_accuracy':ba,'log_loss':ll})
    return {'patient_macro_balanced_accuracy':float(np.mean([r['balanced_accuracy'] for r in result])),
        'patient_macro_log_loss':float(np.mean([r['log_loss'] for r in result])),'patients':result,
        'threshold':.5,'log_loss_clip':1e-15,'trial_unit':'one original maintenance interval','replication_unit':'patient'}

def run(barrier,predictions,private):
    barrier.target_access();cohort(private['rows'])
    result={}
    for family,values in predictions.items():
        combined={'schema':'n041_predictions_v1','probabilities':[r for v in values for r in v['probabilities']]}
        result[family]=score_cell(combined,private['rows'])
    return result
