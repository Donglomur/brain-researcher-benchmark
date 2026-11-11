"""Concrete private preparation → fixed reference → capture → scorer joins.

This module is written source. Native qualification and the isolated participant
launcher are absent; run_reference_job is not a grant to execute scientific work.
"""
import io
from .domain import Refusal, MissingDefinition, Pin, closed, canonical
from .custody import finish
from .support import Preparation,PreparedCase
from .publication import PredictionRegistry,ResultBarrier
from .interchange import (read_ibl_manifest, capture_interchange, read_array, capture_array,
                          normalize_train_only, validate_trial_support)
from .references import (load_original_model_module, fit_linear, predict_linear,
                         fit_original_class, predict_original_class)

def prepare_case(preparation, case):
    if type(preparation) is not Preparation:raise Refusal('actual preparation owner')
    preparation.enter_case(case)
    try:
        if case.availability!='available':raise MissingDefinition('unavailable case remains a disposition')
        regional=preparation.select_region(case)
        converted=read_ibl_manifest(preparation.input_store,preparation.manifest(case.case_id),case.target,regional)
        capture=capture_interchange(preparation.store,'preparation/'+case.case_id,converted)[0]
        return preparation.complete_case(case,capture,regional)
    except BaseException as exc:
        preparation.case_states[case.case_id]='failed'
        preparation.fail('prepare:'+case.case_id,exc);raise

def prepare_training_view(store, prepared, case):
    if type(prepared) is not PreparedCase:raise Refusal('original prepared occurrence')
    prepared.require_original()
    if prepared.owner.store is not store or prepared.owner.case(case.case_id) is not case or prepared.case_id!=case.case_id:
        raise Refusal('training original case/store')
    d=prepared.document()
    if Pin.parse(d['full_support']['split_source'])!=prepared.owner.split.pin:raise Refusal('training common split')
    import numpy as np
    x=read_array(store,d['x']); y=read_array(store,d['y'])
    inverse=d['row_inverse']; full=d['full_support']
    labels=[full['partition'][i] for i in inverse]
    z,yy,normalization=normalize_train_only(x,y,labels,case.target=='choice')
    out={'session':case.session,'region':case.region,'case_id':case.case_id,'normalization':normalization,
         'support':full,'row_inverse':inverse}
    for part in ('train','validation','test'):
        idx=np.asarray([i for i,p in enumerate(labels) if p==part],dtype=np.int64)
        if len(idx)==0: raise Refusal('empty selected split '+part)
        out[part+'_x']=z[idx]
        if part!='test':
            value=yy[idx]
            if case.target=='choice': value=np.eye(2,dtype=float)[value.reshape(-1).astype(int)]
            out[part+'_y']=value
        out[part+'_trial_ids']=[full['trial_ids'][inverse[i]] for i in idx]
    return out

def capture_fit_state(output_store, prefix, model, normalization, native, trace):
    """Safe primitive array serialization; never pickle a fitted object."""
    import numpy as np
    leaves=[]
    if native:
        parameters={k:v.detach().cpu().numpy() for k,v in model.state_dict().items()}
    else:
        parameters={'coef':np.asarray(model.coef_),'intercept':np.asarray(model.intercept_)}
        if hasattr(model,'classes_'): parameters['classes']=np.asarray(model.classes_)
    for ordinal,(name,array) in enumerate(sorted(parameters.items())):
        cap,leaf=capture_array(output_store,prefix+'/parameters/'+str(ordinal)+'.npy',np.asarray(array),tuple('axis'+str(i) for i in range(array.ndim)))
        leaves.append({'name':name,'leaf':leaf.document()})
    normal=[]
    for ci,stats in enumerate(normalization):
        for name,a in stats.items():
            a=np.asarray(a); _,leaf=capture_array(output_store,prefix+'/normalization/'+str(ci)+'-'+name+'.npy',a,tuple('axis'+str(i) for i in range(a.ndim)))
            normal.append({'case_index':ci,'name':name,'leaf':leaf.document()})
    trace_capture=output_store.put_json(prefix+'/selection.json',trace)
    model_capture=output_store.put_json(prefix+'/model.json',{'schema':'trial_session_model_state_v1','parameters':leaves,'normalization':normal})
    return model_capture,trace_capture

def run_reference_job(preparation, job, source_store):
    """A genuine fixed model caller, not candidate-reported baseline substitution."""
    if type(preparation) is not Preparation:raise Refusal('original reference preparation')
    prepared_rows=preparation.require_job(job)
    plan=preparation.plan;prepared=preparation.prepared
    input_store=preparation.input_store;output_store=preparation.store
    import numpy as np
    if job.role!='reference': raise Refusal('independent reference owner')
    if plan.profile!='prospective40':
        raise MissingDefinition('historical training/comparator/source parameter reconciliation remains required')
    cases=[next(c for c in plan.cases if c.case_id==key) for key in job.case_ids]
    if len({c.target for c in cases})!=1: raise Refusal('shared target')
    views=[prepare_training_view(output_store,prepared[c.case_id],c) for c in cases]
    config=input_store.json(job.configuration)
    prefix='references/'+job.job_id
    training=output_store.put_json(prefix+'/training-lineage.json',
          {'schema':'trial_session_training_lineage_v2','job':job.job_id,'condition':job.condition,
           'cases':list(job.case_ids),'interchange':[x.capture.pin.document() for x in prepared_rows],
           'regions':[x.regional.capture.pin.document() for x in prepared_rows],
           'split':job.split.document(),'split_binding':preparation.binding.pin.document(),
           'configuration':job.configuration.document(),'source':job.original_source.document()})
    if job.method=='linear':
        if len(views)!=1: raise Refusal('linear original per-session unit')
        closed(config,('schema','penalties','seed'),'linear config')
        if config['schema']!='trial_session_prospective_linear_v1': raise Refusal('linear version')
        v=views[0]; yy=v['train_y'][:,1:2] if cases[0].target=='choice' else v['train_y']
        vy=v['validation_y'][:,1:2] if cases[0].target=='choice' else v['validation_y']
        model,trace=fit_linear(v['train_x'],yy,v['validation_x'],vy,cases[0].target,config['penalties'],config['seed'])
        native=False
    elif job.method in ('single_rrr','mlp','multi_rrr','multi_region_rrr'):
        module=load_original_model_module(source_store,job.original_source)
        model,trace=fit_original_class(module,job.method,views,cases[0].target,config,
                                       lambda:output_store.budget.before('training-clock',0))
        native=True
    else:
        raise MissingDefinition('state/diagnostic caller requires the selected contiguous-sequence and empirical-prior producer')
    model_capture,selection=capture_fit_state(output_store,prefix,model,[v['normalization'] for v in views],native,trace)
    result=[]
    for c,v in zip(cases,views):
        p=(predict_original_class(model,job.method,v,v['test_x'],c.target) if native
           else predict_linear(model,v['test_x'],c.target))
        if c.target!='choice': p=p*v['normalization']['y_sd']+v['normalization']['y_mean']
        _,leaf=capture_array(output_store,prefix+'/'+c.case_id+'/prediction.npy',np.asarray(p),('original_trial','output'))
        cost=output_store.put_json(prefix+'/'+c.case_id+'/cost-prefix.json',output_store.budget.prefix())
        doc={'schema':'trial_session_prediction_v2','job':job.job_id,'condition':job.condition,'case_id':c.case_id,'trial_ids':v['test_trial_ids'],
             'output_columns':list(range(p.shape[1])),'prediction':leaf.document(),
             'prepared':prepared[c.case_id].capture.pin.document(),
             'unit_selection':prepared[c.case_id].regional.capture.pin.document(),
             'split':preparation.split.pin.document(),'split_binding':preparation.binding.pin.document(),
             'model':model_capture.pin.document(),'training':training.pin.document(),
             'selection':selection.pin.document(),'source':job.original_source.document(),'cost':cost.pin.document()}
        cap=output_store.put_json(prefix+'/'+c.case_id+'/prediction.json',doc)
        result.append({'case':c.case_id,'capture':cap,'leaf':leaf.document(),'trial_ids':v['test_trial_ids']})
    return result

def capture_reference_job(preparation, job, source_store):
    rows=run_reference_job(preparation,job,source_store)
    output_store=preparation.store
    if [x['case'] for x in rows]!=list(job.case_ids): raise Refusal('reference producer lost case')
    for row in rows: output_store.require_capture(row['capture'])
    return output_store.put_json('references/'+job.job_id+'/job-output.json',
         {'schema':'trial_session_job_output_v2','job':job.job_id,'condition':job.condition,
          'cases':list(job.case_ids),
          'outputs':[{'case':x['case'],'prediction':x['capture'].pin.document()} for x in rows],
          'configuration':job.configuration.document(),'split':job.split.document(),
          'source':job.original_source.document()})

def run_preparation_and_references(campaign,input_store,source_store):
    """Actual fixed component orchestration; candidate/panel stages remain separate holds."""
    campaign.begin()
    preparation=Preparation(campaign.plan,input_store,campaign.store).begin()
    campaign.bind_preparation(preparation)
    preparation_failures={}
    for case in campaign.plan.cases:
        if case.availability!='available':continue
        try:prepare_case(preparation,case)
        except BaseException as exc:
            preparation_failures[case.case_id]={'type':type(exc).__name__,'message':str(exc)[:4096]}
    campaign.store.put_json('campaign/preparation-dispositions.json',
                 {'captured':{k:v.capture.pin.document() for k,v in preparation.prepared.items()},
                  'failed':preparation_failures,
                  'unavailable':[c.case_id for c in campaign.plan.cases if c.availability!='available']})
    for job in campaign.plan.jobs:
        if job.role!='reference':continue
        campaign.enter(job.job_id)
        try:
            result=capture_reference_job(preparation,job,source_store)
            campaign.complete(job.job_id,result)
        except BaseException as exc:
            if campaign.states[job.job_id]=='attempted':campaign.fail(job.job_id,exc)
    return campaign

class Campaign:
    """Owned job census and final error custody, independent of array calculations."""
    def __init__(self,plan,output_store):
        self.plan=plan; self.store=output_store; self.states={j.job_id:'pending' for j in plan.jobs}
        self.outputs={}; self.failures={}; self.started=False
        self.preparation=None;self.registry=None;self.barrier=None
    def bind_preparation(self,preparation):
        if not self.started or self.preparation is not None:raise Refusal('preparation binding order')
        registry=PredictionRegistry(self,preparation)
        self.preparation=preparation;self.registry=registry;self.barrier=ResultBarrier(self,registry)
    def begin(self):
        if self.started: raise Refusal('campaign retry')
        self.started=True
        return self.store.put_json('campaign/plan-census.json',{'jobs':[j.job_id for j in self.plan.jobs],
                 'cases':[c.case_id for c in self.plan.cases],'profile':self.plan.profile,
                 'cohort':self.plan.cohort.document(),'source_selection':self.plan.source_selection.document()})
    def enter(self,job_id):
        if not self.started or self.states.get(job_id)!='pending': raise Refusal('job already attempted/foreign')
        self.states[job_id]='attempted'
    def complete(self,job_id,capture):
        if self.states.get(job_id)!='attempted':raise Refusal('job completion order')
        try:
            if self.registry is None:raise Refusal('original preparation missing')
            job=next(j for j in self.plan.jobs if j.job_id==job_id)
            if job.role not in ('candidate','reference'):raise MissingDefinition('diagnostic output producer remains separate')
            self.registry.admit(job,capture)
            self.outputs[job_id]=capture;self.states[job_id]='complete'
        except BaseException as exc:
            self.fail(job_id,exc);raise
    def fail(self,job_id,exc):
        if self.states.get(job_id)!='attempted': raise Refusal('job failure order')
        self.store.budget.fail(job_id,exc); self.states[job_id]='failed'
        self.failures[job_id]={'type':type(exc).__name__,'message':str(exc)[:4096]}
    def finish(self):
        products=[]
        try:
            report={'schema':'trial_session_campaign_report_v1','canonical':'PAPER-paper-method-replacement-009',
                    'profile':self.plan.profile,'states':self.states,'failures':self.failures,
                    'products':{k:v.pin.document() for k,v in self.outputs.items()},
                    'case_dispositions':[{'id':c.case_id,'availability':c.availability,'reason':c.reason} for c in self.plan.cases],
                    'panels':list(self.plan.panels),'unresolved':list(self.plan.unresolved),
                    'scientifically_qualified':False,'source_complete_claim':False}
            products.append(self.store.put_json('campaign/full-report.private.json',report))
        except BaseException as exc: self.store.budget.fail('campaign-report',exc)
        return finish(self.store,'complete_source_outputs' if all(x=='complete' for x in self.states.values()) else 'incomplete',products,self.store.budget)

def candidate_invocation(plan,job,program_pin,input_view_pin,output_relative):
    """Fixed argv planning only. Actual isolated native launcher is a required source gap.

    No shell/PATH lookup, arbitrary provider callback, supplied qualification record,
    or input-view pathname becomes an execution authority through this function.
    """
    if job.role!='candidate': raise Refusal('candidate call owner')
    if job.condition not in ('paper_data','paper_data_author_code'): raise Refusal('condition')
    from .domain import relative
    relative(output_relative)
    return {'schema':'trial_session_candidate_call_v1','job':job.job_id,'condition':job.condition,
            'program':program_pin.document(),'view':input_view_pin.document(),'output':output_relative,
            'argv':['--input-view',input_view_pin.path,'--output',output_relative],
            'limits':plan.limits.__dict__,'launch_authority':None,
            'missing':'qualified same-resource isolated process owner and complete source closure'}

def execute_candidate(*args,**kwargs):
    raise MissingDefinition('no selected genuine isolation/native admission issuer; call planning is not a runner')
