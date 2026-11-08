"""Pooled-session probability metrics; no cross-metric synthetic score."""
import numpy as np
from common import need

def accumulator(columns):
    return {'counts':np.zeros(2,dtype=np.int64),'correct':np.zeros((2,columns),dtype=np.int64),'confusion':np.zeros((columns,2,2),dtype=np.int64),'brier':np.zeros(columns,dtype=np.float64),'logloss':np.zeros(columns,dtype=np.float64)}

def add(state,y,p,budget=None):
    need(y.dtype==np.dtype('int64')and y.ndim==1 and p.dtype==np.dtype('float64')and p.ndim==2 and len(y)==len(p),'exact metric arrays')
    for start in range(0,len(y),128):
        if budget is not None:budget.reading(y[start:start+128].nbytes+p[start:start+128].nbytes)
        a=y[start:start+128];b=p[start:start+128];need(np.isin(a,[0,1]).all()and np.isfinite(b).all()and(b>=0).all()and(b<=1).all(),'complete binary targets and finite probabilities');pred=b>=.5
        for cls in (0,1):
            m=a==cls;state['counts'][cls]+=int(m.sum());state['correct'][cls]+=(pred[m]==cls).sum(axis=0,dtype=np.int64)
            for guess in (0,1):state['confusion'][:,cls,guess]+=(pred[m]==guess).sum(axis=0,dtype=np.int64)
        state['brier']+=np.square(b-a[:,None]).sum(axis=0);clipped=np.clip(b,1e-15,1-1e-15);state['logloss']+=(-a[:,None]*np.log(clipped)-(1-a[:,None])*np.log1p(-clipped)).sum(axis=0)
    return state

def finish(state):
    c=state['counts'];need((c>0).all(),'pooled complete session contains both classes');recall=state['correct']/c[:,None];n=int(c.sum());result=[]
    for j in range(state['brier'].size):result.append({'balanced_accuracy':float(.5*(recall[0,j]+recall[1,j])),'avoidance_recall':float(recall[0,j]),'escape_recall':float(recall[1,j]),'brier':float(state['brier'][j]/n),'reporting_log_loss':float(state['logloss'][j]/n),'confusion_counts':state['confusion'][j].tolist(),'class_counts':c.tolist(),'rows':n})
    return result

def fidelity(p,q,budget=None):
    need(p.shape==q.shape and p.ndim==2,'complete matched native panels');total=np.zeros(p.shape[1]);largest=np.zeros(p.shape[1])
    for start in range(0,len(p),128):
        if budget is not None:budget.reading(p[start:start+128].nbytes+q[start:start+128].nbytes)
        delta=np.abs(p[start:start+128]-q[start:start+128]);total+=delta.sum(axis=0);largest=np.maximum(largest,delta.max(axis=0))
    return {'mean_absolute_error_by_column':(total/len(p)).tolist(),'max_absolute_error_by_column':largest.tolist()}
