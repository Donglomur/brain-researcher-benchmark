"""Invented report metadata only; no S8 import, target, array, fit or native call."""
import copy,json,types
from pathlib import Path
import claim_evidence as subject
from scope_contract import HANDLES,SCOPE

HERE=Path(__file__).absolute().parent
CELL='I_fixed_A';PROFILE='I_fixed';COHORTS={'search_event':['s1','s2','s3'],'modify_event':['m1','m2']}
METRIC='metrics.pooled_and_within_condition_metrics';GAIN='comparison.candidate_reference_summary';INTERVAL='uncertainty.paired_intervals'
GROUP={'cohort':'search_event','ROI':'invented_language_network','response_scale':'session_z_voxel_then_ROI','person':None}
def risk(value):
    return dict(status='valid',cohorts=[dict(cohort=c,status='valid',loss=value) for c in COHORTS],
        strata=[dict(cohort=c,person=p,condition=k,P=1,status='valid',loss=value,denominator=100) for c,ps in COHORTS.items() for p in ps for k in ('D','S')],aggregate=value,original_row_count=1000,equal_cohort_weight=True)
def fixture():
    points={m:risk(v) for m,v in [('REF',2.0),('A',3.0),('B',1.0)]}
    gains={m:dict(aggregate=2-v['aggregate'],cohorts={c:2-v['aggregate'] for c in COHORTS}) for m,v in points.items()}
    summary=dict(point=points,point_gains=gains,point_A_B={'paired':2.0},biological_people={c:len(v) for c,v in COHORTS.items()},
        draws=[dict(draw=i,joint_status='valid',losses=copy.deepcopy(points),gains={m:v['aggregate'] for m,v in gains.items()},A_B={'paired':2.0}) for i in range(2)],
        manifest=dict(B=2,support_identity='invented-response-blind-support',draws=[dict(draw=i) for i in range(2)]),planned_draws=2,valid_draws=2,interval_status='conditional_valid',
        intervals={m:dict(low=v['aggregate'],high=v['aggregate'],interpretation='conditional sensitivity interval; no calibrated population-coverage claim') for m,v in gains.items()},
        A_B_intervals={'paired':dict(low=2.0,high=2.0)},pvalue_status='unqualified_until_independent_calibration')
    metric=[dict(group=copy.deepcopy(GROUP),rows=600,metrics=dict(pooled=dict(status='valid',r=0.8),
        by_condition={'B':dict(status='valid',r=0.3),'D':dict(status='valid',r=0.0),'S':dict(status='valid',r=-0.1)},condition_centered=dict(status='valid',r=0.0)))]
    def product(operator,data,char):return dict(operator=operator,cell=CELL,profile=PROFILE,status='complete',scientific_execution=True,
        pin={'sha256':char*64},data=data,fixture_only='Hypothetical producer flags are invented metadata, not executed science or qualification.')
    products={'metrics':{'pooled_and_within_condition_metrics':product('O14',metric,'a')},
              'comparison':{'candidate_reference_summary':product('O27',summary,'b')},
              'uncertainty':{'paired_intervals':product('O28',copy.deepcopy(summary),'c')}}
    rows=[dict(family=h.split('/')[0],handle=h.split('/')[1],status='unavailable_dependency',claim=None) for h in HANDLES]
    for handle,key in [('F2/a',METRIC),('F3/main',GAIN),('F3/noise_inset',INTERVAL)]:
        node,role=key.split('.',1);row=rows[HANDLES.index(handle)];row.update(status='reference_complete',source_products={key:products[node][role]['pin']})
    report=dict(schema='language_complete_scientific_report_v2',scope=copy.deepcopy(SCOPE),scientific_qualification=False,
                full_scientific_completion=False,all_family_handle_statuses=rows)
    products['report']={'all_main_and_SI_obligation_reports':product('O26',report,'d')}
    inference=dict(method_roster=['REF','A','B'],cohort_people=copy.deepcopy(COHORTS),A_B_pairs={'paired':{'A':'A','B':'B'}},support_identity='invented-response-blind-support')
    nodes=[dict(id=n,operator=o,cell=CELL,profile=PROFILE,reference_selection_scope='fixed-reference',config={'inference':copy.deepcopy(inference),'global_resampling':{'B':2,'support_identity':'invented-response-blind-support'}}) for n,o in [('metrics','O14'),('comparison','O27'),('uncertainty','O28'),('report','O26')]]
    return types.SimpleNamespace(products=products,plan={'nodes':nodes},reference_selections={'fixed-reference':{'selection':{'reference_id':'REF'}}},targets_open=True,collector=types.SimpleNamespace(seal={'invented':True}),resampling={'manifest':copy.deepcopy(summary['manifest'])})
def claim(kind,asserted,selection=None):
    product=METRIC if kind in ('correlation','positive_within_condition_correlation') else INTERVAL if kind=='conditional_interval' else GAIN
    return dict(id='c1',kind=kind,handle={METRIC:'F2/a',GAIN:'F3/main',INTERVAL:'F3/noise_inset'}[product],product=product,selection=selection or {},asserted=asserted)
checks=[];observations=[]
def run(name,c,status,mutate=None,experts=()):
    e=fixture()
    if mutate:mutate(e)
    value=subject.adjudicate_engine(e,'report',[c],experts);actual=value['claim_results'][0]
    assert actual['status']==status,(name,actual)
    assert value['scope']==SCOPE and len(value['all184_handle_statuses'])==184 and value['scientific_qualification']is False
    assert value['upstream_table_agreement'] is False
    checks.append(name);observations.append(dict(case=name,result=actual));return value
def refusal(name,mutate):
    e=fixture();mutate(e)
    try:subject.adjudicate_engine(e,'report',[])
    except subject.ContractError as error:checks.append(name);observations.append(dict(case=name,refusal=str(error)));return
    raise AssertionError(name)
run('pooled numeric statement supported without expert approval',claim('correlation',0.8,dict(group=GROUP,metric='pooled')),'supported')
run('wrong quoted correlation contradicted',claim('correlation',0.7,dict(group=GROUP,metric='pooled')),'unsupported')
run('pooled success cannot establish positive D and S',claim('positive_within_condition_correlation',True,dict(group=GROUP)),'unsupported')
def within(e):
    m=e.products['metrics']['pooled_and_within_condition_metrics']['data'][0]['metrics'];m['by_condition']['D']['r']=0.2;m['by_condition']['S']['r']=0.1
run('both actual within-condition signs supported descriptively',claim('positive_within_condition_correlation',True,dict(group=GROUP)),'supported',within)
def undefined(e):e.products['metrics']['pooled_and_within_condition_metrics']['data'][0]['metrics']['condition_centered']=dict(status='undefined_constant',r=None)
run('undefined constant preserved',claim('correlation',None,dict(group=GROUP,metric='condition_centered')),'supported',undefined)
run('undefined is not zero',claim('correlation',0,dict(group=GROUP,metric='condition_centered')),'unsupported',undefined)
run('negative signed outcome is a valid supported statement',claim('point_gain',-1.0,dict(method='A')),'supported')
run('positive point gain is a valid supported statement',claim('point_gain',1.0,dict(method='B')),'supported')
run('negative outcome cannot be reported positive',claim('point_gain',1.0,dict(method='A')),'unsupported')
def null(e):
    s=e.products['comparison']['candidate_reference_summary']['data'];s['point']['B']=risk(2.0);s['point_gains']['B']=dict(aggregate=0.0,cohorts={c:0.0 for c in COHORTS})
run('zero outcome remains valid',claim('point_gain',0.0,dict(method='B')),'supported',null)
run('biological people are3and2',claim('biological_participant_counts',{'search_event':3,'modify_event':2}),'supported')
run('rows cannot be counted as people',claim('biological_participant_counts',{'search_event':600,'modify_event':400}),'unsupported')
run('A_B numeric difference supported only descriptively',claim('descriptive_A_B_difference',2.0,dict(contrast='paired')),'supported')
run('A_B sign cannot be reversed',claim('descriptive_A_B_difference',-2.0,dict(contrast='paired')),'unsupported')
run('conditional interval supported in current limited sense',claim('conditional_interval',dict(low=1.0,high=1.0,interpretation='conditional_sensitivity'),dict(method='B')),'supported')
run('population label cannot replace conditional label',claim('conditional_interval',dict(low=1.0,high=1.0,interpretation='population_95_percent'),dict(method='B')),'unsupported')
for kind in subject.KNOWN_UPGRADES:run('known unsupported upgrade '+kind,claim(kind,True),'unsupported')
def partial(e):e.products['uncertainty']['paired_intervals']['data']['draws'].pop()
run('planned draw deletion blocked',claim('conditional_interval',dict(low=1.0,high=1.0,interpretation='conditional_sensitivity'),dict(method='B')),'blocked',partial)
def coherent_partial(e):
    s=e.products['uncertainty']['paired_intervals']['data'];s['draws']=s['draws'][:1];s['manifest']['draws']=s['manifest']['draws'][:1];s['manifest']['B']=s['planned_draws']=s['valid_draws']=1
run('coherently shortened summary cannot change actual global draw plan',claim('conditional_interval',dict(low=1.0,high=1.0,interpretation='conditional_sensitivity'),dict(method='B')),'blocked',coherent_partial)
def failed(e):e.products['uncertainty']['paired_intervals']['data']['draws'][0]['global_joint_status']='unavailable'
run('failed joint draw cannot be ignored',claim('conditional_interval',dict(low=1.0,high=1.0,interpretation='conditional_sensitivity'),dict(method='B')),'blocked',failed)
def badgain(e):e.products['comparison']['candidate_reference_summary']['data']['point_gains']['A']['aggregate']=8.0
run('source gain inconsistent with losses blocked',claim('point_gain',8.0,dict(method='A')),'blocked',badgain)
def removed_method(e):
    s=e.products['comparison']['candidate_reference_summary']['data'];del s['point']['B'];del s['point_gains']['B']
run('complete planned method roster mandatory',claim('point_gain',-1.0,dict(method='A')),'blocked',removed_method)
def wrongpeople(e):e.products['comparison']['candidate_reference_summary']['data']['biological_people']['modify_event']=200
run('source biological count inconsistent with strata blocked',claim('point_gain',-1.0,dict(method='A')),'blocked',wrongpeople)
def support(e):e.products['comparison']['candidate_reference_summary']['data']['point']['A']['original_row_count']=999
run('method support deletion blocked',claim('point_gain',-1.0,dict(method='A')),'blocked',support)
def wrongpin(e):e.products['metrics']['pooled_and_within_condition_metrics']['pin']={'sha256':'z'*64}
run('uncited replacement product blocked',claim('correlation',0.8,dict(group=GROUP,metric='pooled')),'blocked',wrongpin)
def engineering(e):e.products['metrics']['pooled_and_within_condition_metrics']['scientific_execution']=False
run('marker not credited as scientific evidence',claim('correlation',0.8,dict(group=GROUP,metric='pooled')),'blocked',engineering)
refusal('full184 roster cannot be reduced',lambda e:e.products['report']['all_main_and_SI_obligation_reports']['data']['all_family_handle_statuses'].pop())
refusal('full8cells cannot be narrowed',lambda e:e.products['report']['all_main_and_SI_obligation_reports']['data']['scope']['cells'].pop())
refusal('actual global barrier required',lambda e:setattr(e,'targets_open',False))
refusal('actual report plan/cell join required',lambda e:e.plan['nodes'][-1].update(cell='I_fixed_B'))
expert=[dict(criterion='signed_outcome',status='supported',reviewer_ref='invented-independent-reviewer',rationale='This metadata record cannot override numeric contradiction.',handles=['F3/main'])]
v=run('expert supported flag cannot turn negative into positive',claim('point_gain',1.0,dict(method='A')),'unsupported',experts=expert)
assert v['recorded_external_expert_assessments']==expert and v['expert_criteria_not_recorded']
v=run('expert flag cannot turn A_B association into causality',claim('causal_code_benefit',True),'unsupported',experts=expert)
assert 'External' in v['scientific_task_completion']
e=fixture();c=claim('biological_participant_counts',{'search_event':3,'modify_event':2});r=subject.adjudicate_engine(e,'report',[c],expert)
r['scope']['cells'].clear();r['claim_results'][0]['observed']['search_event']=999;r['recorded_external_expert_assessments'][0]['handles'].clear()
assert len(SCOPE['cells'])==8 and e.products['comparison']['candidate_reference_summary']['data']['biological_people']['search_event']==3 and expert[0]['handles']==['F3/main']
assert subject.adjudicate_engine(e,'report',[c])['claim_results'][0]['status']=='supported';checks.append('returned scope observations and expert citations do not alias source state')
result=dict(schema='language_claim_evidence_invented_controls_v1',status='PASS',check_count=len(checks),checks=checks,observations=observations,
    scope='Actual additive Engine-products caller using invented complete184-handle report and source-shaped scalar metadata. No S8 import, array/target/header/checkpoint read, model fit, RNG, native process or empirical result. Hypothetical producer execution fields are inert fixture values and establish no qualification.',
    full_scope=SCOPE,scientific_execution=False)
out=HERE/'CONTROL_RESULT_V3.json'
with out.open('x') as f:json.dump(result,f,indent=2,sort_keys=True,allow_nan=False);f.write('\n')
print(json.dumps(dict(status='PASS',check_count=len(checks),full_handles=184,cells=8,scientific_execution=False),indent=2))
