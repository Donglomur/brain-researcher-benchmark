"""Strict all39-class probabilities and independent complete-collection admission."""
import hashlib,math,json

def candidate_parse(raw):return c.parse(raw)

def prediction(raw,phase):
    c.need(type(raw)is bytes and 0<len(raw)<=packet.PRED_CAP,'bounded prediction')
    v=candidate_parse(raw);fields={'probabilities'} if phase['arm']=='PRIOR' else {'query_id','probabilities'}
    c.need(type(v)is dict and set(v)==fields,'exact one-query output')
    if phase['arm']!='PRIOR':c.need(v['query_id']==phase['case_id'],'same opaque query')
    p=v['probabilities'];c.need(type(p)is list and len(p)==39,'all39 classes')
    try:ok=all(type(x)in(int,float) and math.isfinite(x) and 0<=x<=1 for x in p)
    except OverflowError:ok=False
    c.need(ok and abs(math.fsum(p)-1)<=1e-6,'finite simplex, no booleans');return p

def query_panel(public):return dict(schema_version=1,task_id='NEURAL-089',query_ids=[q['id'] for q in packet.admit(public)['queries']])

def assemble(public,values):
    panel=query_panel(public);ids=panel['query_ids'];c.need(set(values)=={(a,q) for a in packet.ARMS for q in ids},'allfour arms and full original query support')
    out={}
    for arm in packet.ARMS:
        out[arm]=dict(schema_version=1,task_id='NEURAL-089',predictions=[dict(query_id=q,probabilities=values[(arm,q)]) for q in ids])
        science.predictions(out[arm],panel);c.need(len(c.encoded(out[arm]))<=256000000,'original complete output cap')
    c.need(len(c.encoded(out))<=packet.OUTPUT_CAP,'complete fourarm output cap');return out

def admit_answers(public,answers):
    c.need(type(answers)is dict and set(answers)==set(packet.ARMS),'full fourarm answer set');panel=query_panel(public)
    return {a:science.predictions(answers[a],panel) for a in packet.ARMS}

def compare(public,candidate,reference,load_gold):
    # Caller must first admit both source-bound collections and original targetpin.
    a=admit_answers(public,candidate);b=admit_answers(public,reference);panel=query_panel(public);ids=panel['query_ids']
    target=load_gold();truth=science.labels(target,panel,hashlib.sha256(c.encoded(panel)).hexdigest())
    scores={role:{arm:science.metrics(pred[arm],truth,ids) for arm in packet.ARMS} for role,pred in [('candidate',a),('independent_reference',b)]}
    return dict(schema='neural089-independent-comparison-v1',scores=scores,primary='MEG.macro_f1_39',candidate_minus_reference_MEG_macro_f1=scores['candidate']['MEG']['macro_f1_39']-scores['independent_reference']['MEG']['macro_f1_39'],descriptive_signal_contrasts={role:{'MEG_minus_'+arm:vals['MEG']['macro_f1_39']-vals[arm]['macro_f1_39'] for arm in packet.ARMS if arm!='MEG'} for role,vals in scores.items()},independent_people=1,query_recordings=1,confidence_intervals=None,scientific_qualified=False,reference_competence_verified=False,qualified_improvement=None)

def cost_evidence(plan,phase_wall,producer_wall,selection):
    return dict(policy='neural089-pointwise-program-cost-v1',original_collector_compatible=False,actual_phase_wall_seconds=phase_wall,actual_producer_wall_seconds=producer_wall,observed_native_profile=dict(image=selection['image'],cpus=1,memory_bytes=selection['memory_bytes'],producer_seconds_limits={k:selection[k+'_seconds'] for k in ('fit','infer')}),invocations_per_panel=dict(fit=3,infer=3*plan['query_count']+1),reference_neural_fits=2,reference_training_passes_per_neural_fit=5,reference_separate_scaler_passes_per_neural_fit=1,optimizer_steps_observed=None,source_declared_steps_are_observed_counts=False,actual_query_count=plan['query_count'],host_managed_IO_only=True,native_payload_reads_observed=None,native_model_mount_bytes_upper=selection['limits']['native_model_mount_bytes_upper'],mounted_model_bytes_are_not_measured_reads=True,reference_pickle_loads_per_infer_declared=1)

def admit_collection(s,source,bodies,result,root,read):
    """Independent outer readback joins every phase and both complete panels."""
    c.need(type(result)is dict and set(result)=={'schema','status','source','complete','phase_count'} and result['schema']=='neural089-worker-result-v1' and result['status']=='complete_unqualified' and result['source']==source,'worker result identity')
    complete=c.parse(read(root/'COMPLETE.json',packet.JSON_CAP,result['complete']))
    c.need(complete.get('schema')=='neural089-complete-v1' and complete.get('source')==source and complete.get('status')=='complete_unqualified','complete source identity')
    commitment=c.parse(read(root/'COMMITMENT.json',65536,complete['commitment']))
    reference=c.pin(bodies['reference/reference_program.py']);programs=dict(candidate=c.only_pin(s['candidate_program']),independent_reference=reference)
    c.need(c.encoded(commitment)==c.encoded(dict(schema='neural089-commitment-v1',source=source,programs=programs,public_manifest=s['public_manifest'],image=s['image'],plan=s['plan'],limits=s['limits'],private_grading_authorized=False)),'exact global independent-source/program/input/resource commitment')
    for panel,pin in programs.items():read(root/'programs'/f'{panel}.py',131072,pin)
    public=c.parse(read(s['public_manifest']['path'],packet.JSON_CAP,c.only_pin(s['public_manifest'])));plan=packet.admit(public)
    c.need({k:plan[k] for k in packet.PLAN_FIELDS}==s['plan'],'outer complete prepared plan')
    expected_count=6*plan['query_count']+8;schedule=packet.phases(public,plan);c.need(all(type(x)is int for x in (complete['phase_count'],result['phase_count'],s['limits']['phase_count'])) and complete['phase_count']==result['phase_count']==s['limits']['phase_count']==expected_count,'complete exact phase count')
    c.need(set(complete['panels'])==set(packet.PANELS),'exact candidate and independent reference panel set')
    model_exposure=0;models={};values={name:{} for name in packet.PANELS};costs={name:dict(fit_seconds=0.,infer_seconds=0.) for name in packet.PANELS};producer_costs={name:dict(fit_seconds=0.,infer_seconds=0.) for name in packet.PANELS}
    for phase in schedule:
        d=root/'phases'/phase['phase_id'];closed=c.parse(read(d/'CLOSED.json',65536))
        c.need(set(closed)=={'schema','phase','request','native','model','view_retired'} and closed['schema']=='neural089-phase-closed-v1' and c.encoded(closed['phase'])==c.encoded(phase) and closed['view_retired']is True,'exact closed phase/role chronology')
        req=c.parse(read(d/'REQUEST.json',65536,closed['request']))
        expected_model=None if phase['model_key']is None else models[phase['model_key']]['pin']
        c.need(set(req)=={'schema','source','phase','program','image','seconds','model','input','view_members'} and req['schema']=='neural089-phase-request-v1' and req['source']==source and c.encoded(req['phase'])==c.encoded(phase) and req['program']==programs[phase['panel']] and req['image']==s['image'] and type(req['seconds'])is int and req['seconds']==s[phase['kind']+'_seconds'] and req['model']==expected_model,'phase exact program/role/image/model/resource join')
        c.exact_pin(req['input']);c.exact_pin(req['view_members'])
        if expected_model is not None:model_exposure+=expected_model['bytes']
        native=c.parse(read(d/'NATIVE.json',packet.NATIVE_CAP,closed['native']))
        c.need(native.get('schema')=='neural089-native-phase-v1' and native.get('kind')==phase['kind'] and type(native.get('ordinal'))is int and native['ordinal']==phase['ordinal'] and native.get('source')==source and native.get('status')=='captured' and native.get('all_native_resources_closed')is True and native.get('producer_closed_before_capture')is True and native.get('cli_reaped')is True and native.get('error_type')is None,'independent natural native closure join')
        c.need(native.get('image')==s['image'] and type(native.get('memory_bytes'))is int and native['memory_bytes']==s['memory_bytes'] and type(native.get('producer_seconds_limit'))is int and native['producer_seconds_limit']==s[phase['kind']+'_seconds'] and native.get('private_scoring_called')is False,'actual native image/resources/unscored join')
        wall=native.get('producer_wall_seconds');c.need(type(wall)in(int,float) and math.isfinite(wall) and 0<=wall<=s[phase['kind']+'_seconds'],'actual producer interval within selected phase limit')
        c.validate_natural_exit(native['natural_exit']);c.validate_cli_commands(native['command_metadata'],357920000 if phase['kind']=='fit' else 131072)
        c.need(len(native['closures'])==3 and all(x.get('closed')is True for x in native['closures']),'all native resources closed')
        seconds=native['elapsed_seconds'];c.need(type(seconds)in(int,float) and math.isfinite(seconds) and seconds>=0,'finite observed phase costs')
        costs[phase['panel']][phase['kind']+'_seconds']+=seconds
        producer_costs[phase['panel']][phase['kind']+'_seconds']+=wall
        if phase['kind']=='fit':
            c.need(closed['model']==dict(key=phase['result_key'],pin=native['output']),'same captured model seal')
            modelpath=root/'models'/f"{phase['phase_id']}.bin";read(modelpath,packet.MODEL_CAP,native['output'])
            seal=c.parse(read(d/'MODEL_SEAL.json',65536))
            c.need(c.encoded(seal)==c.encoded(dict(schema='neural089-model-seal-v1',source=source,phase=phase,program=programs[phase['panel']],input_model=expected_model,model=native['output'],native=closed['native'],input=req['input'],view_retired=True)),'independent model provenance/seal')
            models[phase['result_key']]=dict(pin=native['output'],path=modelpath)
        else:
            c.need(closed['model']is None,'prediction creates no model')
            raw=read(d/'prediction.json',packet.PRED_CAP,native['output']);prob=prediction(raw,phase)
            ids=[r['id'] for r in plan['queries']] if phase['arm']=='PRIOR' else [phase['case_id']]
            for i in ids:values[phase['panel']][(phase['arm'],i)]=prob
    for panel in packet.PANELS:
        expected=assemble(public,values[panel]);actual=candidate_parse(read(root/f'{panel}.json',packet.OUTPUT_CAP,complete['panels'][panel]))
        c.need(c.encoded(actual)==c.encoded(expected),'full bundle equals independently admitted raw predictions')
    c.need(type(complete['model_count'])is int and complete['model_count']==len(models)==6 and complete['all_views_retired']is True and complete['private_targets_opened']is False and complete['scoring_performed']is False and complete['runtime_qualified']is False and complete['scientific_qualified']is False,'full unchanged source-only status')
    return dict(schema='neural089-outer-join-v1',status='complete_unqualified',source=source,programs=programs,phase_count=expected_count,query_count=plan['query_count'],answers_per_panel=4,model_count=len(models),panels=complete['panels'],cost_evidence=cost_evidence(plan,costs,producer_costs,s),observed_mounted_model_bytes=model_exposure,mounted_bytes_are_payload_reads=False,scoring_performed=False,runtime_qualified=False,scientific_qualified=False)
