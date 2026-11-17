"""Small invented engineering controls, never authentic ACh evaluation."""
import copy
import hashlib
import json
import math
from pathlib import Path
import sys

HERE=Path(__file__).absolute().parent
sys.path.insert(0,str(HERE))
from common import STRATA, ACCESS, LogicalBudget, Refusal, pin
import study, history, nulls, grading, native_compare, reference_workflow as workflow
import numeric_backend as numeric

RESULTS=[]
def check(name,fn):
    fn(); RESULTS.append(name)

def refused(fn,fragment=''):
    try:fn()
    except (Refusal,numeric.NumericFailure) as error:
        assert fragment in str(error),(fragment,str(error))
    else:raise AssertionError('expected refusal')

def make_study():
    animals=['r%02d'%i for i in range(16)]; queries=[]; sessions={}; eligible={}; rows={}
    evidence={k:pin({'invented':k}) for k in ('original_members','producer_fields','biological_identity',
        'session_trial_identity','channel_grid','absolute_clocks','target_aliases','logical_history','full_support')}
    for a,animal in enumerate(animals):
        session='s%02d'%a;sessions[animal]=[session];eligible[animal]={k:[session] for k in STRATA}
        mask=[1,1] if a<4 else ([1,0] if a<10 else [0,1])
        for ki,k in enumerate(STRATA):
            for j in range(2):
                q=animal+'_'+k+'_'+str(j);grid=pin({'invented_grid':k})
                meta={'id':q,'animal':animal,'session':session,'stratum':k,'trial':ki*10+j,
                    'target_key':'t_'+q,'target_kind':'SLRT' if k=='side_on' else 'next_ITI',
                    'target_trial':ki*10+j+1,'observation_end_ns':100000+ki*30000+j*10000,
                    'target_available_ns':150000+ki*30000+j*10000,'channel_mask':mask.copy(),
                    'grid_pin':grid,'alias_pin':pin({'invented_alias':q})}
                queries.append(meta)
                times=[v/10 for v in range(-4,7)]
                epochs={name:({'times':times,'values':[scale*t+.1*a+.3*j for t in times]} if mask[i] else None)
                    for i,(name,scale) in enumerate((('D',1.0),('ACh',2.0)))}
                rows[q]={'id':q,'animal':animal,'session':session,'stratum':k,'seconds':math.exp(.1*a+.05*ki+.25*j),
                    'behavior':[.1*a+.3*j,1.0],'behavior_observed':[True,True],
                    'epochs':epochs,'channel_mask':mask.copy(),'grid_pin':grid,'persistence_seconds':None,
                    'history_schedule_pin':evidence['logical_history']}
    s={'task':'PAPER-ROOT-ADD-019','animals':animals,'paired_animals':animals[:4],'sessions':sessions,
       'queries':queries,'admission_evidence':evidence,'eligible_sessions':eligible,'feature_schema_pin':pin({'invented_features':2})}
    return s,rows

STUDY,ROWS=make_study()
PLAN=study.compile_plan(STUDY)

def counts():
    c=PLAN['counts'];assert(c['candidate_final_bundles'],c['reference_regularized_head_fits'],c['native_jobs'])==(160,80960,111)
    assert len(PLAN['panels'])==240 and len(PLAN['reference_inner_cells'])==4032
    bad=copy.deepcopy(STUDY);bad['animals'].pop();refused(lambda:study.validate_study(bad),'full16')
    bad=copy.deepcopy(STUDY);bad['queries'].pop();refused(lambda:study.validate_study({**bad,'queries':bad['queries']+bad['queries'][:1]}),'unique full query')
check('complete counts and no cohort/duplicate shortcut',counts)

def history_tests():
    obligations=[]
    for q,time,target in [('a',1000,'T'),('b',1000,'T'),('c',2000,'U'),('d',3000,'T'),('e',4000,'V')]:
        obligations.append({'id':q,'query_id':q,'target_key':target,'session':'s','trial':0,
            'stratum':'offer_CPIn','variant_ordinal':0,'observation_end_ns':time,'target_available_ns':900})
    h=history.HistoryBarrier(obligations,['s'])
    first=h.next_batch();assert first['obligation_ids']==['a','b'] and not first['released_target_keys']
    refused(lambda:h.close_batch({'a':{}}),'whole tied batch')
    def close(batch):
        h.close_batch({q:{'obligation_id':q,'prediction_pin':pin(q),'closure_pin':pin({'closed':q})} for q in batch['obligation_ids']})
    close(first);second=h.next_batch();assert 'T' not in second['released_target_keys'];close(second)
    third=h.next_batch();assert 'T' not in third['released_target_keys'];close(third)
    fourth=h.next_batch();assert 'T' in fourth['released_target_keys'];close(fourth);assert h.next_batch() is None;h.finish()
    logical=history.logical_training_schedule(obligations,['s']);assert not logical['labels_read'] and len(logical['batches'])==4
    broken=history.HistoryBarrier(obligations,['s']);broken.next_batch();broken.fail();refused(broken.next_batch)
check('shared-target embargo tie barrier and independent training schedule',history_tests)

def null_tests():
    groups=[]
    for animal in STUDY['animals']:
        for stratum in STRATA:
            ids=[q['id'] for q in STUDY['queries'] if q['animal']==animal and q['stratum']==stratum]
            groups.append({'ids':ids,'offset':1,'minimum_separation_ns':5000,'circular_period_ns':20000,
                           'maximum_circular_gap_ns':10000,'boundary':'declared_circular_wrap_no_exchangeability_claim'})
    policy={'id':'null_test','kind':'within_session_joint_neural_epoch_cyclic_shift_v1','refit':'full_graph',
            'groups':groups,'clock_support_evidence':pin('invented_clock'),'selection_evidence':pin('invented_selection')}
    m=nulls.validate_and_map(STUDY,policy);packet=nulls.shift_private_rows(ROWS,m);shifted=packet['rows']
    q=next(iter(ROWS));assert shifted[q]['seconds']==ROWS[q]['seconds'] and shifted[q]['epochs']==ROWS[m['mapping'][q]]['epochs']
    assert set(shifted[q])==set(ROWS[q]) and packet['lineage'][q]['donor']==m['mapping'][q]
    bad=copy.deepcopy(policy);bad['groups'][0]['offset']=0;refused(lambda:nulls.validate_and_map(STUDY,bad))
    bad=copy.deepcopy(policy);bad['groups'][0]['ids'][0]=bad['groups'][2]['ids'][0];refused(lambda:nulls.validate_and_map(STUDY,bad))
    refused(lambda:nulls.require_complete_null_results(PLAN,[],{}),'mandatory real null')
check('complete temporal donor mapping and unselected-null failure',null_tests)

SOURCES={a:pin({'invented_source':a}) for a in (*ACCESS,'operator')}
PANELS,FITTED={},{}
for key,spec in PLAN['panels'].items():
    model={'model_id':spec['bundle_fit_id'],'panel_key':key,'source_pin':SOURCES[spec['actor']],
        'training_animals':spec['training_animals'],'state_pin':pin({'invented_state':key}),
        'selection_pin':pin({'invented_selection':key}),'feature_schema_pin':STUDY['feature_schema_pin']}
    FITTED[spec['bundle_fit_id']]=model
    PANELS[key]={'panel_key':key,'model_id':spec['bundle_fit_id'],'model_record_pin':pin(model),
                 'source_pin':SOURCES[spec['actor']],
                 'predictions':{q:math.log(ROWS[q]['seconds']) for q in spec['query_ids']}}

def grading_tests():
    labels={q:r['seconds'] for q,r in ROWS.items()}
    # Arithmetic-only positive control; full 80,960-fit artifact replay is not performed.
    admitted=grading.validate_complete_predictions(PLAN,PANELS,FITTED,SOURCES)
    report=grading._score_admitted_panels(PLAN,STUDY,PANELS,labels,admitted)
    assert all(v['equal_animal_gain']==0 for v in report['summaries'].values())
    bad=copy.deepcopy(PANELS);key=next(iter(bad));bad[key]['predictions'].pop(next(iter(bad[key]['predictions'])))
    class NeverRead(dict):
        def __getitem__(self,k):raise AssertionError('protected label read before complete panel admission')
    refused(lambda:grading.grade(PLAN,STUDY,bad,FITTED,SOURCES,NeverRead(),programme_artifacts={}), 'all original query')
    refused(lambda:grading.grade(PLAN,STUDY,PANELS,FITTED,SOURCES,NeverRead(),programme_artifacts={}),
            'complete programme artifacts before private labels')
    altered=copy.deepcopy(PLAN);altered['counts']['author_contexts']=5
    refused(lambda:grading.grade(altered,STUDY,PANELS,FITTED,SOURCES,NeverRead(),programme_artifacts={}),
            'exact complete plan')
    badfit=copy.deepcopy(FITTED);mk=next(iter(badfit));badfit[mk]['training_animals']=STUDY['animals']
    refused(lambda:grading.validate_complete_predictions(PLAN,PANELS,badfit,SOURCES),'exact source/fold')
    table={'animals':['a','b'],'indices':[[0,0],[1,1],[0,1]],'selection_pin':pin('invented_table')}
    assert grading.conditional_resampling({'a':1.0,'b':3.0},table)['means']==[1.0,3.0,2.0]
    signs=grading.paired_sign_flips({'a':1,'b':2,'c':3,'d':4});assert len(signs['means'])==16 and signs['inferential_p_value'] is None
check('whole-panel and programme admission precede labels; private arithmetic and conditional summaries',grading_tests)

def weighting_test():
    q=[{'id':'a','stratum':'offer_CPIn','session':'s1'}, {'id':'b','stratum':'offer_CPIn','session':'s2'},
       {'id':'c','stratum':'offer_CPIn','session':'s2'}]
    allq=[];pred={};truth={}
    for k in STRATA:
        for row in q:
            v=dict(row,id=k+row['id'],stratum=k);allq.append(v);truth[v['id']]=1.0;pred[v['id']]=1.0 if row['session']=='s1' else 3.0
    out=grading.loss_for_animal(allq,pred,truth,{k:1.0 for k in STRATA})
    assert all(v['normalized_loss']==5.0 for v in out.values()) # (1 + mean(9,9))/2, not row mean19/3
check('equal-session loss rather than trial-count weighting',weighting_test)

def native_test():
    roots=['root%02d'%i for i in range(37)];policies={};panels={};sourcepins={}
    for root in roots:
        support=pin({'invented_support':root})
        policies[root]={'x':{'kind':'float','units':'seconds','shape':[2],'support_pin':support,
                            'absolute_tolerance':0.01,'relative_tolerance':0.0,'nonfinite':'reject'}}
        for role in native_compare.ROLES:
            key=role+'/'+root;sourcepins[key]=pin({'invented_native_source':key})
            panels[key]={'source_pin':sourcepins[key],'quantities':{'x':{'units':'seconds','support_pin':support,
                'values':[1.0,2.0],'status':'complete'}}}
    policy={'selection_pin':pin('invented_policy'),'root_source_pin':pin('invented37'),
            'producer_source_pins':sourcepins,'roots':policies}
    assert native_compare.compare(policy,roots,panels)['all_declared_quantities_match']
    missing=dict(panels);missing.pop(next(iter(missing)));refused(lambda:native_compare.compare(policy,roots,missing),'all111')
    bad=copy.deepcopy(panels);bad[next(iter(bad))]['quantities']['x']['units']='milliseconds'
    refused(lambda:native_compare.compare(policy,roots,bad),'same original units/support')
check('all111 native quantity policy and units',native_test)

LIMITS={'numeric':{'max_rows':20,'max_features':128,'max_pairs':200,'max_matrix_elements':20000,'max_live_float_slots':200000},
        'max_behavior_features':8,'max_epoch_samples':32}
BUDGET=LogicalBudget({'head_fits':16,'row_uses':1000,'feature_cells':100000,'epoch_samples':100000,'predictions':1000},0,1000,lambda:1)

def reference_composition():
    cohort='paired';animals=STUDY['paired_animals'][1:];variant='B';heads={}
    training={q['id']:ROWS[q['id']] for q in study.cohort_queries(STUDY,cohort) if q['animal'] in animals}
    workflow.validate_rows(STUDY,training,['continuous','indicator'],cohort,animals)
    refused(lambda:workflow.validate_rows(STUDY,ROWS,['continuous','indicator'],cohort,animals),'fitting-partition')
    for k in STRATA:
        heads[k]=workflow.fit_one(STUDY,training,cohort,animals,k,variant,numeric.settings()[3],
                                  ['continuous','indicator'],LIMITS,BUDGET,'invented-fit-'+k)
    query=next(q for q in STUDY['queries'] if q['animal']==STUDY['paired_animals'][0])
    row=ROWS[query['id']]
    view={k:row[k] for k in ('id','stratum','behavior','behavior_observed','epochs','channel_mask','grid_pin',
                            'history_schedule_pin','persistence_seconds')}
    # A withheld neural operand is not read, normalized or included in distances.
    view['epochs']={'D':{'times':'DO_NOT_READ','values':'DO_NOT_READ'},'ACh':{'times':'DO_NOT_READ','values':'DO_NOT_READ'}}
    fit={'panel_key':'invented_panel','fitted_state':heads,'pending_query_ids':[query['id']],
         'history_schedule_pin':STUDY['admission_evidence']['logical_history']}
    entitlement={'panel_key':'invented_panel','query_id':query['id'],'view_pin':pin(view),
                 'active_obligation':'invented_obligation','batch_pin':pin('invented_batch'),'view_admission_pin':pin('invented_view')}
    result=workflow.infer_reference_query(fit,view,entitlement,LIMITS,BUDGET)
    assert math.isfinite(result['prediction']) and result['diagnostics']['persistence_status']=='unavailable_history'
    leaked=dict(view,seconds=1.0);refused(lambda:workflow.infer_reference_query(fit,leaked,entitlement,LIMITS,BUDGET),'minimal single-query')
check('real four-head numeric composition and target-free one-query inference',reference_composition)

def budget_tests():
    b=LogicalBudget({'a':1,'b':3},0,2,lambda:1)
    refused(lambda:b.reserve({'a':2,'b':2},'failed'),'allocation')
    assert b.used=={'a':2,'b':2} and b.failures
    refused(lambda:LogicalBudget({'a':1},0,1,lambda:1),'strict scientific deadline')
check('failed attempt counters retained atomically and strict deadline',budget_tests)

print(json.dumps({'schema':'ach_owner_invented_core_controls_v1','passed':True,'groups':RESULTS,
    'groups_count':len(RESULTS),'actual_authentic_science_or_native_operations':0,
    'full80960_fit_replay':False,'actual_reference_head_fits_on_invented_values':4,
    'logical_test_budget':BUDGET.report(),'physical_RSS_or_IO_measured':False},sort_keys=True))
