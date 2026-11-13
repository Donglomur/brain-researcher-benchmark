from ..contracts import Custody, diagnostic
"""Exact Elephant1.2.1 primitive state adapter; source-derived, not executed here.

The immutable contract fixes scientific implementations and every fitted field.
Independent runtime/native parity remains required; callers cannot supply easier
field lists, convergence predicates or alternate scientific dependency versions.
"""
from .common import require,primitive_state

CONTRACT_SHA256='bbf72d8d2a62a94efa9fc340a307a5ac05022826e4eb42b93469ae701e6e331d'
UNCHANGED=('bin_size','x_dim','min_var_frac','tau_init','eps_init','em_tol','em_max_iters','freq_ll','verbose','valid_data_names')
FITTED=('has_spikes_bool','params_estimated','fit_info','transform_info')

def qualification(config):
    import importlib.metadata
    import hashlib,json
    from pathlib import Path
    q=config.get('gpfa_qualification')
    require(type(q)is dict and set(q)=={'schema','source_contract_sha256','qualification_binding'},'exact GPFA runtime qualification contract')
    require(q['schema']=='NLB017_GPFA_runtime_qualification_v2'and q['source_contract_sha256']==CONTRACT_SHA256 and q['qualification_binding']==config['bindings']['dependencies'],'fixed GPFA source and independent dependency qualification identity')
    raw=Path(__file__).with_name('GPFA_SOURCE_CONTRACT.json').read_bytes()
    require(hashlib.sha256(raw).hexdigest()==CONTRACT_SHA256,'immutable built-in GPFA contract')
    contract=json.loads(raw)
    distributions={}
    for name,version in contract['distribution_versions'].items():
        dist=importlib.metadata.distribution(name);require(dist.version==version,'exact locked scientific distribution '+name);distributions[name]=dist
    for member in contract['installed_source_members']:
        path=Path(distributions[member['distribution']].locate_file(member['path']))
        require(not path.is_symlink()and path.is_file()and path.stat().st_size==member['bytes'],'exact ordinary operative native source')
        body=path.read_bytes();require(hashlib.sha256(body).hexdigest()==member['sha256'],'operative installed scientific source changed')
    return contract

def constructor(latent):
    from elephant.gpfa import GPFA
    import quantities as pq
    require(type(latent)is int and latent in(32,36,40,44,48,52),'original complete MC_Maze GPFA dimensions')
    return GPFA(bin_size=5*pq.ms,x_dim=latent,min_var_frac=.01,tau_init=100.*pq.ms,
                eps_init=.001,em_tol=1e-8,em_max_iters=500,freq_ll=5,verbose=False)

def likelihoods(native):
    """Encode scheduled native nonobservations only; no likelihood imputation."""
    import math
    require(type(native)is list and 1<=len(native)<=500,'complete native EM likelihood list')
    out=[]
    for iteration,value in enumerate(native,1):
        value=float(value);measured=iteration<=2 or iteration%5==0
        require(math.isfinite(value)if measured else math.isnan(value),'exact original likelihood observation schedule')
        out.append(value if measured else None)
    return out

def em_convergence(history):
    """Replay the exact source stop predicate, including its decrease behavior."""
    import math
    require(type(history)is list and 1<=len(history)<=500,'native EM history extent')
    previous=0.;old=0.;base=0.;stopped=False;decreases=[];last_measured=None
    for iteration,current in enumerate(history,1):
        measured=iteration<=2 or iteration%5==0
        require((type(current)is float and math.isfinite(current))if measured else current is None,'encoded native likelihood schedule')
        if previous is not None:old=previous
        if iteration<=2:base=current
        reached=iteration>2 and current is not None and (current-base)<(1+1e-8)*(old-base)
        require(not reached or iteration==len(history),'history continues after original native stop')
        if current is not None:
            if last_measured is not None and current<last_measured:decreases.append(iteration)
            last_measured=current
        stopped=reached;previous=current
    classification='native_relative_tolerance_reached'if stopped else'native_iteration_cap_exhausted'if len(history)==500 else'invalid_or_truncated_native_history'
    return {'classification':classification,'iterations':len(history),'measured_decrease_iterations':decreases,'monotone_or_stationary_not_proven':True,'native_tol':1e-8,'native_freq_ll':5,'native_max_iters':500}

def observe_fit(model,record,scope):
    """Keep every native returned EM history before any export/admission check."""
    import math
    fit=getattr(model,'fit_info',None)
    if not hasattr(record,'original_native_fit_observations'):record.original_native_fit_observations=[]
    record.original_native_fit_observations.append({'scope':scope,'original_fit_info':fit})
    if type(fit)is not dict or set(fit)!={'iteration_time','log_likelihoods'}:
        observation={'scope':scope,'native_history_available':False,'reason':'Native fit has not returned complete EM history; no history is invented.'}
    else:
        def number(value):
            try:
                value=float(value)
                if math.isfinite(value):return value
                return {'observed_nonfinite':'nan'if math.isnan(value)else'positive_infinity'if value>0 else'negative_infinity'}
            except BaseException as error:
                owner=Custody('native_fit_number:'+scope);record.custody.resources.append(owner);owner.fail(error,'native_observation_encoding')
                return {'observed_unencodable_type':'unencodable_native_value','diagnostic':diagnostic(error)}
        history=[]
        for iteration,value in enumerate(fit['log_likelihoods'],1):
            item=number(value)
            if iteration>2 and iteration%5!=0 and item=={'observed_nonfinite':'nan'}:item=None
            history.append(item)
        try:stopping=em_convergence(history)
        except BaseException as error:
            owner=Custody('native_fit_stopping:'+scope);record.custody.resources.append(owner);owner.fail(error,'native_stopping_observation')
            stopping={'classification':'invalid_or_truncated_native_history','original_error_type':diagnostic(error)['type'],'diagnostic':diagnostic(error)}
        observation={'scope':scope,'native_history_available':True,'log_likelihoods':history,'iteration_time':[number(v)for v in fit['iteration_time']],'original_stopping_observation':stopping,'telemetry_is_not_admission':True}
    record.event('original_gpfa_fit_history',**observation)
    return observation

def validate_fields(fields,latent,solver_records):
    import numpy as np
    import math
    require(type(fields)is dict and set(fields)==set(FITTED),'all four concrete fitted GPFA fields')
    mask=fields['has_spikes_bool'];require(type(mask)is np.ndarray and mask.dtype==np.dtype('bool')and mask.shape==(137,),'complete source inactive-unit mask')
    active=int(mask.sum());require(latent<=active<=137,'native active-unit latent dimensions')
    params=fields['params_estimated'];require(type(params)is dict and set(params)=={'covType','gamma','eps','d','C','R','notes','Corth'},'all eight native parameter fields')
    require(params['covType']=='rbf'and params['notes']=={'learnKernelParams':True,'learnGPNoise':False,'RforceDiagonal':True},'unchanged native covariance/learning recipe')
    def array(value,shape):
        require(type(value)is np.ndarray and value.dtype==np.dtype('float64')and value.shape==shape and np.isfinite(value).all(),'exact native finite float64 parameter shape')
    for key,shape in(('gamma',(latent,)),('eps',(latent,)),('d',(active,)),('C',(active,latent)),('R',(active,active)),('Corth',(active,latent))):array(params[key],shape)
    require((params['gamma']>0).all()and(params['eps']==.001).all(),'native GP covariance parameter domains')
    require(np.array_equal(params['R'],np.diag(np.diag(params['R'])))and(np.diag(params['R'])>0).all(),'native positive diagonal private covariance')
    fit=fields['fit_info'];require(type(fit)is dict and set(fit)=={'iteration_time','log_likelihoods'},'complete native fit telemetry')
    convergence=em_convergence(fit['log_likelihoods']);m=len(fit['log_likelihoods'])
    require(type(fit['iteration_time'])is list and len(fit['iteration_time'])==m and all(type(x)is float and math.isfinite(x)for x in fit['iteration_time']),'actual complete original iteration times')
    require(convergence['classification']=='native_relative_tolerance_reached','native EM did not reach original tolerance; retain unavailable reference')
    transform=fields['transform_info'];require(type(transform)is dict and set(transform)=={'log_likelihood','num_bins','Corth'},'complete native transform telemetry')
    bins=transform['num_bins'];require(type(bins)is np.ndarray and bins.dtype.kind in'iu'and bins.ndim==1 and 1<=len(bins)<=1721 and(bins==140).all(),'all original 140-bin transform trials')
    require(type(transform['log_likelihood'])in(float,np.float64)and math.isfinite(float(transform['log_likelihood'])),'actual finite full training transform likelihood')
    array(transform['Corth'],(active,latent));require(np.array_equal(transform['Corth'],params['Corth']),'same complete native orthonormalization state')
    require(type(solver_records)is list and len(solver_records)==m*latent,'every original GP-kernel optimizer invocation')
    for index,row in enumerate(solver_records):
        require(set(row)=={'call_index','iteration','latent_index','success','status','nit','nfev','njev','fun','x','jac','message'},'complete original optimizer result schema')
        require(row['call_index']==index and row['iteration']==index//latent+1 and row['latent_index']==index%latent,'source-ordered inner optimizer census')
        require(row['success']is True and row['status']==0,'original native L-BFGS-B convergence required; no inferred success')
        for key in('nit','nfev','njev'):require(type(row[key])is int and row[key]>=0,'actual original optimizer counters')
        require(all(type(row[key])is float and math.isfinite(row[key])for key in('fun','x','jac'))and type(row['message'])is str,'actual finite optimizer observations')
    return convergence

def export(model,latent,config,solver_records):
    import numpy as np
    qualification(config);baseline=constructor(latent)
    require(set(vars(model))==set(UNCHANGED)|set(FITTED),'exact14 native GPFA attrs; no partial export')
    for name in UNCHANGED:
        require(name in vars(baseline)and bool(np.all(getattr(model,name)==getattr(baseline,name))),'source-fixed constructor field changed')
    # Only this known native missing-observation list may contain NaNs.
    native_fit=model.fit_info
    fields={'has_spikes_bool':model.has_spikes_bool,'params_estimated':model.params_estimated,
            'fit_info':{'iteration_time':[float(x)for x in native_fit['iteration_time']],
                        'log_likelihoods':likelihoods(native_fit['log_likelihoods'])},
            'transform_info':model.transform_info}
    require(set(native_fit)=={'iteration_time','log_likelihoods'},'no lost original fit fields')
    fields=primitive_state(fields,config);solvers=primitive_state(solver_records,config);convergence=validate_fields(fields,latent,solvers)
    return {'latent':latent,'source_contract_sha256':CONTRACT_SHA256,'qualification_binding':config['bindings']['dependencies'],
            'fields':fields,'original_optimizer_results':solvers,'native_convergence':convergence}

def restore(state,config):
    import numpy as np
    qualification(config)
    require(set(state)=={'latent','source_contract_sha256','qualification_binding','fields','original_optimizer_results','native_convergence'}and state['source_contract_sha256']==CONTRACT_SHA256 and state['qualification_binding']==config['bindings']['dependencies'],'exact frozen native source/dependency state')
    fields=primitive_state(state['fields'],config);solvers=primitive_state(state['original_optimizer_results'],config)
    require(validate_fields(fields,state['latent'],solvers)==state['native_convergence'],'unchanged original native convergence evidence')
    # The archive stays finite: restore uncomputed values only inside the native
    # object, which cannot escape this worker as executable/pickled state.
    fields['fit_info']['log_likelihoods']=[np.nan if v is None else v for v in fields['fit_info']['log_likelihoods']]
    model=constructor(state['latent'])
    for name in FITTED:setattr(model,name,fields[name])
    require(set(vars(model))==set(UNCHANGED)|set(FITTED),'complete native reconstruction closure')
    return model
