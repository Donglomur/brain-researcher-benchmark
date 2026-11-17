"""Exact original prediction admission and separately sealed comparator channel."""
import hashlib,math

def candidate_parse(raw):
    # The exact original bounded lexical parser is injected below at freeze.
    return parse(raw)

def prediction(raw,phase):
    c.need(type(raw)is bytes and 0<len(raw)<=packet.PRED_CAP,'bounded complete output')
    v=candidate_parse(raw)
    fields={'tokens'} if phase['kind']=='prior' else {'id','tokens'}
    c.need(type(v)is dict and set(v)==fields,'exact prediction fields')
    if phase['kind']!='prior':c.need(v['id']==phase['case_id'],'same complete query ID')
    return science.normalize_tokens(v['tokens'])

def assemble(public,values):
    suite=packet.suite(public);contexts=science.suite_contexts(suite);answers={}
    expected={(s,a,i) for (s,a),r in contexts.items() for i in r['query_ids']}
    c.need(set(values)==expected,'every63 context and every shared query required')
    for (s,a),r in contexts.items():
        answers[r['context_id']]=dict(schema='neural014-predictions-v1',context_id=r['context_id'],predictions=[{'id':i,'tokens':values[(s,a,i)]} for i in r['query_ids']])
    science.admit(contexts,answers)
    c.need(len(c.encoded(answers))<=packet.JSON_CAP,'complete original answer bundle cap; never truncate')
    return answers

def compare(suite,candidate,independent_reference,load_gold):
    """Operator-only arithmetic source; no empirical call in construction.

    Call only on the two source-bound bundles returned by admit_collection.
    Candidate never supplies a reference/comparison field. Both are structurally
    admitted before the one private target callback, then original score kernels
    compute unchanged absolute PER and descriptive contrasts independently.
    """
    contexts=science.suite_contexts(suite)
    science.admit(contexts,candidate);science.admit(contexts,independent_reference)
    gold=load_gold()
    a=science.score(suite,candidate,lambda:gold);b=science.score(suite,independent_reference,lambda:gold)
    good=a['status']==b['status']=='scored'
    return dict(schema='neural014-independent-comparison-v1',candidate=a,independent_reference=b,
        independent_reference_minus_candidate_full_adapt_PER=(b['primary_PER']-a['primary_PER']) if good else None,
        comparison_available=good,qualified_improvement=None,reference_competence_verified=False,
        scientific_qualified=False,causal_drift_or_population_claim=False,within_panel_contrasts_remain_descriptive=True)

def cost_evidence(plan,phase_wall,producer_wall,selection):
    """Versioned fixed-program evidence; arbitrary optimizer counts stay unknown."""
    return dict(policy='neural014-fixed-program-cost-v2',original_collector_compatible=False,
        actual_phase_wall_seconds=phase_wall,actual_producer_wall_seconds=producer_wall,
        observed_native_profile=dict(image=selection['image'],cpus=1,memory_bytes=selection['memory_bytes'],producer_seconds_limits={k:selection[k+'_seconds'] for k in ('fit','adapt','infer','prior')}),
        invocations_per_panel=dict(fit=1,adapt=18,prior=9,infer=6*plan['query_count']),
        calibration_labels_per_session={s:len(rows) for s,rows in plan['calibration_by_session'].items()},
        adaptation_updates_observed=None,reference_updates_per_adaptation_declared_by_source=100,
        reference_logical_step_definition='One optimizer.step after one CTC loss/backward on one cyclically selected complete calibration trial; input-affine parameters only.',
        work_count_capture_status='optimizer_updates_not_observable_for_arbitrary_programs; optional_separate_attestation_only',
        shared_full_adaptation_counted_once=True,source_declared_steps_are_observed_counts=False)

def admit_collection(s,source,bodies,result,root,read):
    """Independent outer readback joins every phase and both complete panels."""
    c.need(type(result)is dict and set(result)=={'schema','status','source','complete','phase_count'} and result['schema']=='neural014-worker-result-v1' and result['status']=='complete_unqualified' and result['source']==source,'worker result identity')
    complete=c.parse(read(root/'COMPLETE.json',packet.JSON_CAP,result['complete']))
    c.need(complete.get('schema')=='neural014-complete-v1' and complete.get('source')==source and complete.get('status')=='complete_unqualified','complete source identity')
    commitment=c.parse(read(root/'COMMITMENT.json',65536,complete['commitment']))
    reference=c.pin(bodies['reference/reference_program.py']);programs=dict(candidate=c.only_pin(s['candidate_program']),independent_reference=reference)
    c.need(c.encoded(commitment)==c.encoded(dict(schema='neural014-commitment-v1',source=source,programs=programs,public_manifest=s['public_manifest'],image=s['image'],plan=s['plan'],limits=s['limits'],private_grading_authorized=False)),'exact global independent-source/program/input/resource commitment')
    for panel,pin in programs.items():read(root/'programs'/f'{panel}.py',131072,pin)
    public=c.parse(read(s['public_manifest']['path'],packet.JSON_CAP,c.only_pin(s['public_manifest'])));plan=packet.admit(public)
    c.need({k:plan[k] for k in packet.PLAN_FIELDS}==s['plan'],'outer complete prepared plan')
    schedule=packet.phases(public,plan);c.need(complete['phase_count']==result['phase_count']==s['limits']['phase_count']==len(schedule),'complete exact phase count')
    c.need(set(complete['panels'])==set(packet.PANELS),'exact candidate and independent reference panel set')
    models={};values={name:{} for name in packet.PANELS};costs={name:dict(fit_seconds=0.,adapt_seconds=0.,infer_seconds=0.,prior_seconds=0.) for name in packet.PANELS};producer_costs={name:dict(fit_seconds=0.,adapt_seconds=0.,infer_seconds=0.,prior_seconds=0.) for name in packet.PANELS}
    for phase in schedule:
        d=root/'phases'/phase['phase_id'];closed=c.parse(read(d/'CLOSED.json',65536))
        c.need(set(closed)=={'schema','phase','request','native','model','view_retired'} and closed['schema']=='neural014-phase-closed-v1' and c.encoded(closed['phase'])==c.encoded(phase) and closed['view_retired']is True,'exact closed phase/role chronology')
        req=c.parse(read(d/'REQUEST.json',65536,closed['request']))
        expected_model=None if phase['model_key']is None else models[phase['model_key']]['pin']
        c.need(set(req)=={'schema','source','phase','program','image','seconds','model','input','view_members'} and req['schema']=='neural014-phase-request-v1' and req['source']==source and c.encoded(req['phase'])==c.encoded(phase) and req['program']==programs[phase['panel']] and req['image']==s['image'] and type(req['seconds'])is int and req['seconds']==s[phase['kind']+'_seconds'] and req['model']==expected_model,'phase exact program/role/image/model/resource join')
        c.exact_pin(req['input']);c.exact_pin(req['view_members'])
        native=c.parse(read(d/'NATIVE.json',packet.NATIVE_CAP,closed['native']))
        c.need(native.get('schema')=='neural014-native-phase-v1' and native.get('kind')==phase['kind'] and type(native.get('ordinal'))is int and native['ordinal']==phase['ordinal'] and native.get('source')==source and native.get('status')=='captured' and native.get('all_native_resources_closed')is True and native.get('producer_closed_before_capture')is True and native.get('cli_reaped')is True and native.get('error_type')is None,'independent natural native closure join')
        c.need(native.get('image')==s['image'] and type(native.get('memory_bytes'))is int and native['memory_bytes']==s['memory_bytes'] and type(native.get('producer_seconds_limit'))is int and native['producer_seconds_limit']==s[phase['kind']+'_seconds'] and native.get('private_scoring_called')is False,'actual native image/resources/unscored join')
        wall=native.get('producer_wall_seconds');c.need(type(wall)in(int,float) and math.isfinite(wall) and 0<=wall<=s[phase['kind']+'_seconds'],'actual producer interval within selected phase limit')
        c.validate_natural_exit(native['natural_exit']);c.validate_cli_commands(native['command_metadata'],357920000 if phase['kind']in('fit','adapt') else 131072)
        c.need(len(native['closures'])==3 and all(x.get('closed')is True for x in native['closures']),'all native resources closed')
        seconds=native['elapsed_seconds'];c.need(type(seconds)in(int,float) and math.isfinite(seconds) and seconds>=0,'finite observed phase costs')
        costs[phase['panel']][phase['kind']+'_seconds']+=seconds
        producer_costs[phase['panel']][phase['kind']+'_seconds']+=wall
        if phase['kind']in('fit','adapt'):
            c.need(closed['model']==dict(key=phase['result_key'],pin=native['output']),'same captured model seal')
            modelpath=root/'models'/f"{phase['phase_id']}.bin";read(modelpath,packet.MODEL_CAP,native['output'])
            seal=c.parse(read(d/'MODEL_SEAL.json',65536))
            c.need(c.encoded(seal)==c.encoded(dict(schema='neural014-model-seal-v1',source=source,phase=phase,program=programs[phase['panel']],input_model=expected_model,model=native['output'],native=closed['native'],input=req['input'],view_retired=True)),'independent model provenance/seal')
            models[phase['result_key']]=dict(pin=native['output'],path=modelpath)
        else:
            c.need(closed['model']is None,'prediction creates no model')
            raw=read(d/'prediction.json',packet.PRED_CAP,native['output']);tokens=prediction(raw,phase)
            ids=[r['id'] for r in plan['queries'] if r['session']==phase['session']] if phase['kind']=='prior' else [phase['case_id']]
            for i in ids:values[phase['panel']][(phase['session'],phase['arm'],i)]=tokens
    for panel in packet.PANELS:
        expected=assemble(public,values[panel]);actual=candidate_parse(read(root/f'{panel}.json',packet.JSON_CAP,complete['panels'][panel]))
        c.need(c.encoded(actual)==c.encoded(expected),'full bundle equals independently admitted raw predictions')
    c.need(complete['model_count']==len(models)==38 and complete['all_views_retired']is True and complete['private_targets_opened']is False and complete['scoring_performed']is False and complete['runtime_qualified']is False and complete['scientific_qualified']is False,'full unchanged source-only status')
    return dict(schema='neural014-outer-join-v1',status='complete_unqualified',source=source,programs=programs,phase_count=len(schedule),query_count=plan['query_count'],answers_per_panel=63,model_count=len(models),panels=complete['panels'],cost_evidence=cost_evidence(plan,costs,producer_costs,s),scoring_performed=False,runtime_qualified=False,scientific_qualified=False)

import json
def parse(body):
    text = body.decode("utf-8")
    depth, quoted, escape = 0, False, False
    for c in text:
        if quoted:
            if escape: escape = False
            elif c == "\\": escape = True
            elif c == '"': quoted = False
        elif c == '"': quoted = True
        elif c in "[{":
            depth += 1
            if depth > 48: raise ValueError("JSON nesting bound")
        elif c in "]}": depth -= 1
    def pairs(rows):
        out = {}
        for k, v in rows:
            if k in out: raise ValueError("Duplicate JSON field")
            out[k] = v
        return out
    def integer(s):
        if len(s) > 18: raise ValueError("JSON integer bound")
        return int(s)
    def number(s):
        x = float(s)
        if not math.isfinite(x): raise ValueError("Nonfinite JSON number")
        return x
    def reject(s): raise ValueError("Nonfinite JSON constant")
    return json.loads(text, object_pairs_hook=pairs, parse_int=integer, parse_float=number, parse_constant=reject)
