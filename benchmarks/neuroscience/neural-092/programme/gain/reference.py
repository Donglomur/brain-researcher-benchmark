"""Actual five-model producer stages; all-panel barriers separate grid/tune/refit."""
from dataclasses import dataclass
import math
from .authority import require_live
from .constants import MODELS,LAMBDAS,EXPOSURE
from .features import inspect_metadata,design,validate_counts,verify_fit_offset
from .solver import fit,prediction_deviance,predicted_mean,FitFailure,zeros

@dataclass
class ReferenceSession:
    session_id:str
    complete:bool
    predictions:dict
    coefficients:dict
    grid_coefficients:dict
    selection:dict
    slots:list
    output_failures:list
    info:dict

def make_reference_record(meta,info):
    slots=[{'unit':uid,'model':model,'phase':phase,'lambda':lam,'status':'not_attempted','reason':'earlier_failure_or_not_reached','fit_error':None,'validation_error':None,'loss':None,'updates':None}
      for model in MODELS for uid in info['unit_ids']for phase,lam in [('grid',v)for v in LAMBDAS]+[('refit',None)]]
    return ReferenceSession(meta['session_id'],False,{}, {m:{}for m in MODELS},{m:{}for m in MODELS},{m:{}for m in MODELS},slots,[],info)

def prepare(meta,fit_counts,validation_counts,record):
    info=inspect_metadata(meta);nf=len(info['rows']['FIT']);nv=len(info['rows']['VALIDATION']);u=len(info['unit_ids'])
    if type(record)is not ReferenceSession or record.info!=info or record.session_id!=meta['session_id']or record.complete:raise ValueError('original full reference record')
    validate_counts(fit_counts,nf,u);validate_counts(validation_counts,nv,u);verify_fit_offset(meta,fit_counts,nf)
    if len(record.slots)!=50*u:raise ValueError('complete fit-slot inverse')
    return info,nf,nv,u

def grid_session(meta,fit_counts,validation_counts,record,host,calls):
    require_live(host,'all required grid fits before validation scoring')
    info,nf,nv,u=prepare(meta,fit_counts,validation_counts,record)
    slots={(r['model'],r['unit'],r['lambda']):r for r in record.slots if r['phase']=='grid'}
    for model in MODELS:
        x,p=design(info,model,host,calls)
        for j,uid in enumerate(info['unit_ids']):
            calls.enter('log_scalar');offset=math.log(EXPOSURE*meta['baseline_rates'][j])
            record.grid_coefficients[model][uid]={}
            for lam in LAMBDAS:
                slot=slots[(model,uid,lam)]
                if slot['status']!='not_attempted':raise ValueError('no grid replay')
                slot.update(status='attempted',reason=None)
                result=fit(x,p,range(nf),lambda i:fit_counts[i*u+j],offset,lam,host,calls)
                slot.update(status=result.status,fit_error=result.error,updates=result.updates)
                record.grid_coefficients[model][uid][lam]=result.beta
        del x

def validation_session(meta,fit_counts,validation_counts,record,host,calls):
    require_live(host,'validation after genuine whole-grid freeze')
    info,nf,nv,u=prepare(meta,fit_counts,validation_counts,record)
    slots={(r['model'],r['unit'],r['lambda']):r for r in record.slots if r['phase']=='grid'}
    for model in MODELS:
        x,p=design(info,model,host,calls)
        for j,uid in enumerate(info['unit_ids']):
            calls.enter('log_scalar');offset=math.log(EXPOSURE*meta['baseline_rates'][j]);selected=None;all_ok=True
            for lam in LAMBDAS:
                slot=slots[(model,uid,lam)]
                if slot['status']!='success':all_ok=False;continue
                if slot['loss']is not None or slot['validation_error']is not None:raise ValueError('no validation replay')
                try:
                    beta=record.grid_coefficients[model][uid][lam]
                    if beta is None:raise ValueError('successful grid coefficient unavailable')
                    loss=prediction_deviance(x,p,range(nf,nf+nv),lambda i:validation_counts[i*u+j],beta,offset,host,calls)
                    if not math.isfinite(loss):raise FitFailure('nonfinite validation loss')
                    slot['loss']=loss
                    if selected is None or loss<selected[0]or(loss==selected[0]and lam>selected[1]):selected=(loss,lam)
                except (ArithmeticError,ValueError)as error:
                    slot.update(status='failed_validation',validation_error=error);calls.failure('validation',error);all_ok=False
            record.selection[model][uid]=selected if all_ok else None
        del x

def refit_session(meta,fit_counts,validation_counts,record,host,calls):
    require_live(host,'refit after genuine whole-panel method-selection freeze')
    info,nf,nv,u=prepare(meta,fit_counts,validation_counts,record)
    slots={(r['model'],r['unit']):r for r in record.slots if r['phase']=='refit'}
    for model in MODELS:
        x,p=design(info,model,host,calls)
        for j,uid in enumerate(info['unit_ids']):
            target=slots[(model,uid)]
            if target['status']!='not_attempted':raise ValueError('no refit replay')
            selected=record.selection[model][uid]
            if selected is None:
                target['reason']='one_or_more_required_grid_or_validation_failures';record.coefficients[model][uid]=None;continue
            calls.enter('log_scalar');offset=math.log(EXPOSURE*meta['baseline_rates'][j])
            target.update(status='attempted',reason=None,**{'lambda':selected[1]})
            def combined(i):return fit_counts[i*u+j]if i<nf else validation_counts[(i-nf)*u+j]
            result=fit(x,p,range(nf+nv),combined,offset,selected[1],host,calls)
            target.update(status=result.status,fit_error=result.error,updates=result.updates)
            record.coefficients[model][uid]=result.beta
        del x

def predict_session(meta,record,host,calls):
    require_live(host,'query prediction after genuine whole-refit freeze')
    info=inspect_metadata(meta)
    if record.info!=info or record.predictions:raise ValueError('exact original metadata and one prediction pass')
    nf=len(info['rows']['FIT']);nv=len(info['rows']['VALIDATION']);nq=len(info['rows']['QUERY']);u=len(info['unit_ids'])
    complete=all(r['status']=='success'for r in record.slots)
    for model in MODELS:
        record.predictions[model]=zeros(nq*u,calls);x,p=design(info,model,host,calls)
        for j,uid in enumerate(info['unit_ids']):
            beta=record.coefficients[model].get(uid)
            if beta is None:complete=False;continue
            try:
                calls.enter('log_scalar');offset=math.log(EXPOSURE*meta['baseline_rates'][j]);calls.enter('query_predict')
                for i in range(nq):record.predictions[model][i*u+j]=predicted_mean(x,p,nf+nv+i,beta,offset,calls)
            except (ArithmeticError,ValueError)as error:
                record.output_failures.append({'unit':uid,'model':model,'error':error});calls.failure('query_predict',error);complete=False
        del x
    record.complete=complete
    return record
