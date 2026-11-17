"""Focused independent controls; all identities, values and authorities invented."""
import sys, types, json, hashlib, math, copy, gc, tracemalloc
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent / 'successor-v2'
raw = (BASE/'SOURCE_PROPOSAL.json').read_bytes()
assert hashlib.sha256(raw).hexdigest() == '74ed261605ac10539afa953310172bfd897b6c863be47240145a01f833a365de'
proposal = json.loads(raw)
pins = {Path(r['path']).name:r for r in proposal['files']}
mods = {}
source_bytes = len(raw)
for name in ('common','study','history','native_compare','nulls','grading','numeric_backend','completion','reference_workflow'):
    path = BASE/('reference-math/core.py' if name=='numeric_backend' else name+'.py')
    raw = path.read_bytes(); source_bytes += len(raw)
    row = pins[path.name]
    assert len(raw)==row['bytes'] and hashlib.sha256(raw).hexdigest()==row['sha256']
    module = types.ModuleType(name); module.__file__ = str(path)
    sys.modules[name] = module
    exec(compile(raw,str(path),'exec'),module.__dict__)
    mods[name] = module
c,s,h,n,z,g,num,completion,workflow = (mods[name] for name in
    ('common','study','history','native_compare','nulls','grading','numeric_backend','completion','reference_workflow'))
encoded = 0
old_canonical = c.canonical
def meter(value):
    global encoded
    body = old_canonical(value); encoded += len(body)
    assert encoded <= 2097152
    return body
c.canonical = meter
PIN = {'bytes':1,'sha256':'a'*64}
BADPIN = {'bytes':1,'sha256':'b'*64}
checks = []
def refuses(fn):
    try: fn()
    except (c.Refusal,num.NumericFailure): return
    raise AssertionError('expected precise source refusal')

tracemalloc.start()
animals = ['a%02d'%i for i in range(16)]
queries = []
for animal in animals:
    for i,st in enumerate(c.STRATA):
        queries.append({'id':animal+'_'+st,'animal':animal,'session':'s','stratum':st,'trial':1,
            'target_key':animal+('_SLRT' if st=='side_on' else '_ITI'),
            'target_kind':'SLRT' if st=='side_on' else 'next_ITI','target_trial':2,
            'observation_end_ns':10*(i+1),'target_available_ns':15,
            'channel_mask':[1,1] if animal in animals[:4] else [1,0],
            'grid_pin':PIN,'alias_pin':PIN})
study = {'task':c.TASK,'animals':animals,'paired_animals':animals[:4],
    'sessions':{a:['s'] for a in animals},'queries':queries,'feature_schema_pin':PIN,
    'eligible_sessions':{a:{k:['s'] for k in c.STRATA} for a in animals},
    'admission_evidence':{k:PIN for k in ['original_members','producer_fields','biological_identity',
        'session_trial_identity','channel_grid','absolute_clocks','target_aliases','logical_history','full_support']}}
s.validate_study(study)
bad = copy.deepcopy(study); bad['queries'][1]['target_key']='second_alias'
refuses(lambda:s.validate_study(bad))
bad = copy.deepcopy(study); bad['queries'][1]['target_available_ns']=16
refuses(lambda:s.validate_study(bad)); del bad
# Every same-target obligation must close; all four strata are present.
obligations = [{'id':q['id'],'query_id':q['id'],'target_key':q['target_key'],'session':q['session'],
    'trial':q['trial'],'stratum':q['stratum'],'variant_ordinal':0,
    'observation_end_ns':q['observation_end_ns'],'target_available_ns':q['target_available_ns']}
    for q in queries if q['animal']=='a00']
b=h.HistoryBarrier(obligations,['s']); first=b.next_batch()
b.close_batch({q:{'obligation_id':q,'prediction_pin':PIN,'closure_pin':PIN} for q in first['obligation_ids']})
assert b.next_batch()['released_target_keys']==[]
checks.append('canonical_physical_alias_release_clock_and_shared_target_embargo')
del b,obligations

# Compile the full symbolic study, not the80,960 numerical fit artifact graph.
plan=s.compile_plan(study)
assert len(plan['panels'])==240 and len(plan['reference_inner_cells'])==4032
assert plan['counts']['candidate_final_bundles']==160
assert plan['counts']['reference_inner_head_fits']==80640
assert plan['counts']['reference_final_head_fits']==320
assert plan['counts']['reference_regularized_head_fits']==80960
del plan;gc.collect()
plan=s.compile_plan(study,('z_null','a_null')); order=list(plan['panels']); counts=plan['counts']
assert counts['reference_regularized_head_fits']==3*80960
del plan;gc.collect()
plan=s.compile_plan(study,('a_null','z_null'))
assert list(plan['panels'])==order and plan['counts']==counts
del plan,order;gc.collect()
checks.append('full160_80960_symbolic_scope_and_canonical_null_order')

rows=[{'id':'q'+str(i),'animal':'a','session':'s','stratum':'offer_CPIn',
    'channel_mask':[1,1],'grid_pin':PIN,'observation_end_ns':(i+1)*10} for i in range(4)]
def group(ids):
    return {'ids':ids,'offset':1,'minimum_separation_ns':1,'circular_period_ns':100,
        'maximum_circular_gap_ns':100,'boundary':'declared_circular_wrap_no_exchangeability_claim'}
policy={'id':'n1','kind':'within_session_joint_neural_epoch_cyclic_shift_v1','refit':'full_graph',
    'clock_support_evidence':PIN,'selection_evidence':PIN,'groups':[group(['q0','q1']),group(['q2','q3'])]}
refuses(lambda:z.validate_and_map({'queries':rows},policy))
policy['groups']=[group(['q0','q1','q2','q3'])]
mapping=z.validate_and_map({'queries':rows},policy)['mapping']
assert mapping=={'q0':'q1','q1':'q2','q2':'q3','q3':'q0'}
checks.append('null_whole_identity_refusal_and_complete_cyclic_mapping')
del rows,mapping

roots=['r'+str(i) for i in range(37)]
policy={'selection_pin':PIN,'root_source_pin':PIN,
    'producer_source_pins':{role+'/'+r:PIN for role in n.ROLES for r in roots},
    'roots':{r:{'q':{'kind':'exact','units':'unit','shape':[], 'support_pin':PIN,
        'absolute_tolerance':0,'relative_tolerance':0,'nonfinite':'reject'}} for r in roots}}
native_panels={role+'/'+r:{'source_pin':PIN,'quantities':{'q':{'units':'unit','support_pin':PIN,
    'values':1.,'status':'complete'}}} for role in n.ROLES for r in roots}
native_panels['A_clarified/r0']['quantities']['q']['values']=float('inf')
refuses(lambda:n.compare(policy,roots,native_panels))
policy['roots']['r0']['q']['nonfinite']='same_position_nan_and_signed_inf'
for role in n.ROLES:native_panels[role+'/r0']['quantities']['q']['values']=float('inf')
assert n.compare(policy,roots,native_panels)['all_declared_quantities_match'] is True
for role in n.ROLES:native_panels[role+'/r0']['quantities']['q']['values']=1.
policy['roots']['r0']['q']['nonfinite']='reject'
native_panels['A_clarified/r0']['quantities']['q']['values']=2.
native=n.compare(policy,roots,native_panels)
assert native['all_declared_quantities_match'] is False
assert native['comparisons']['A_clarified/r0']['q']['mismatches']==1
checks.append('native_nonfinite_policy_and_complete_recorded_mismatch')

qs=[{'id':st,'session':'s','stratum':st} for st in c.STRATA]
refuses(lambda:g.loss_for_animal(qs,{st:1e150 for st in c.STRATA},
    {st:1. for st in c.STRATA},{st:1e-30 for st in c.STRATA}))
refuses(lambda:g.loss_for_animal(qs,{st:1e-200 for st in c.STRATA},
    {st:1. for st in c.STRATA},{st:1. for st in c.STRATA}))
tiny={'animals':['a'],'paired_animals':['a'],'queries':[
    {'id':'q'+str(i),'animal':'a','session':'s','stratum':'offer_CPIn','channel_mask':[1,1]} for i in range(3)]}
refuses(lambda:g.group_variance(tiny,'full',['a'],'offer_CPIn',{'q0':3.,'q1':3.,'q2':3.}))
refuses(lambda:g.conditional_resampling({'a':1e308,'b':1e308},{'animals':['a','b'],'indices':[[0,1]],'selection_pin':PIN}))
valid=g.loss_for_animal(qs,{st:2. for st in c.STRATA},{st:1. for st in c.STRATA},{st:2. for st in c.STRATA})
assert all(v['normalized_loss']==2 for v in valid.values())
checks.append('constant_overflow_underflow_refusal_and_finite_analytic_loss')

# Small structural final bundle; this is not a complete nested fit or execution proof.
pk=s.panel_key('operator','full','a00','F'); spec={'actor':'operator','cohort':'full','animal':'a00','variant':'F',
    'training_animals':animals[1:],'bundle_fit_id':pk+'|final',
    'query_ids':[q['id'] for q in queries if q['animal']=='a00']}
chosen={'setting':num.settings()[0]}; state={};records={}
for st in c.STRATA:
    ids=sorted(q['id'] for q in queries if q['animal'] in spec['training_animals'] and q['stratum']==st)
    phase=spec['bundle_fit_id']+'|refit|'+st
    resource={'invented_structural_record':True}
    head={'model':{'setting':chosen['setting'],'row_ids':ids,'feature_count':1,'fit_resource_plan':resource},
        'transform':{'variant':'F','stratum':st,'feature_count':1},'training_animals':spec['training_animals'],
        'training_row_ids':ids,'training_sessions':{},'phase':phase,'resource_plan':resource}
    state[st]=head
    records[phase]={'model_pin':c.pin(head['model']),'transform_pin':c.pin(head['transform']),
        'training_rows_pin':c.pin(ids),'resource_plan':resource}
model={'panel_key':pk,'model_id':spec['bundle_fit_id'],'training_animals':spec['training_animals'],
    'selection_pin':c.pin(chosen),'state_pin':c.pin(state),'source_pin':PIN,'feature_schema_pin':PIN}
completion.validate_final_reference_bundle(study,pk,spec,chosen,state,model,records)
bad=copy.deepcopy(state); bad[c.STRATA[0]]['model']['feature_count']=2
changed_model=dict(model,state_pin=c.pin(bad))
refuses(lambda:completion.validate_final_reference_bundle(study,pk,spec,chosen,bad,changed_model,records))
changed_model=dict(model,selection_pin=BADPIN)
refuses(lambda:completion.validate_final_reference_bundle(study,pk,spec,chosen,state,changed_model,records))
receipts={q['id']:{'panel_key':pk,'query_id':q['id'],'stratum':q['stratum'],'prediction':0.,
    'bundle_state_pin':model['state_pin'],'head_state_pin':c.pin(state[q['stratum']]),'entitlement_pin':PIN,
    'diagnostics':{},'actual_view_custody_or_process_closure_qualified':False}
    for q in queries if q['animal']=='a00'}
workflow.reference_prediction_panel(study,spec,model,state,receipts)
receipts[spec['query_ids'][0]]['head_state_pin']=BADPIN
refuses(lambda:workflow.reference_prediction_panel(study,spec,model,state,receipts))
checks.append('final_model_selection_head_and_query_join_mutations')
del state,records,receipts,bad,changed_model;gc.collect()

# Exercise the real grade call chain with explicitly stubbed unrelated full-fit gates.
# Native111 comparison and prerequisite function are real. No80,960-record fixture,
# complete-grading performance, native authenticity or scientific accuracy is claimed.
toy_plan={'panels':{'candidate':{'actor':'A_clarified','realization':'n1'},
    'operator':{'actor':'operator','realization':'n1'}},
    'counts':{'reference_regularized_head_fits':1,'reference_final_bundles':1}}
artifacts={'native_policy':policy,'native_roots':roots,'native_panels':native_panels,
    'reference_fit_records':{},'reference_selections':{},'reference_final_states':{},'diagnostics':{},
    'ed_dispositions':{str(i):{'status':'unresolved_producer','evidence_pin':PIN} for i in range(1,11)},
    'null_reports':{'n1':{'policy_pin':PIN,'generation_pin':PIN,'complete_fit_query_graph_pin':PIN}},
    'candidate_method_admission':{'candidate':{'method_conformance_evidence':PIN,'fit_search_ledger_pin':PIN,'source_state_lineage_pin':PIN}}}
calls=[]
saved=(g.compile_plan,g.validate_complete_predictions,g._score_admitted_panels,
    completion.validate_reference_fit_records,completion.validate_diagnostics)
g.compile_plan=lambda *_:toy_plan
g.validate_complete_predictions=lambda *_:{'explicitly_stubbed_for_order_test':True}
g._score_admitted_panels=lambda *args:(calls.append('labels') or {'control_only':True})
completion.validate_reference_fit_records=lambda *args:{'required_fits':1,'all_declared_records_joined':True}
completion.validate_diagnostics=lambda *args:{'diagnostic_panels':1}
try:
    result=g.grade(toy_plan,study,{}, {},{}, {},programme_artifacts=artifacts)
    assert calls==['labels']
    prereq=result['programme_prerequisites']
    assert prereq['native_reproduction_success_under_declared_policy'] is False
    assert prereq['native_quantity_comparison']['comparisons']['A_clarified/r0']['q']['mismatches']==1
    assert prereq['whole_paper_reproduced'] is False
    calls.clear();artifacts['native_panels']=dict(native_panels);artifacts['native_panels'].pop('A_clarified/r0')
    refuses(lambda:g.grade(toy_plan,study,{}, {},{}, {},programme_artifacts=artifacts))
    assert calls==[]
finally:
    (g.compile_plan,g.validate_complete_predictions,g._score_admitted_panels,
        completion.validate_reference_fit_records,completion.validate_diagnostics)=saved
checks.append('grade_mismatch_outcome_visible_and_missing_native_prelabels_refusal_explicit_stubs')
_,peak=tracemalloc.get_traced_memory();tracemalloc.stop()
assert peak<=8388608,peak
out={'schema':'ach_peer_v2_focused_controls','passed':len(checks),'groups':checks,
    'encoded_before_summary':encoded,'traced_peak_after_source_load':peak,'source_bytes_read':source_bytes,
    'prospective_cumulative_reservation':8388608,'canonical_subcap':2097152,
    'nonserialized_scaffold_reservation':6291456,'physical_fixture_writes':0,
    'retained_fixture_files':0,'full_protected_grade_or80960_fit_graph_executed':False,
    'actual_data_or_native_science':False}
print(json.dumps(out,indent=2,sort_keys=True,allow_nan=False))
