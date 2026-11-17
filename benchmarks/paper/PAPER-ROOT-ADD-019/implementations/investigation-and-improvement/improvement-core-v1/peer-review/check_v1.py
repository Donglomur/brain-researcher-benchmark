"""Independent tiny RAM counterexamples, no actual scientific inputs or execution."""
import sys, types, json, hashlib, math, tracemalloc
from pathlib import Path
BASE = Path(__file__).resolve().parent.parent
PINS = {
 'common': 'ec86ed521415f7aad10677d41f900d285d683605752a640bcb23fec5c6a3b749',
 'study': '1bb6fdab6e63172decbef9054d3a62b1962b9ef117d316f2647aef3652e51282',
 'history': 'ba782f66d4fb3cdbf51d5fda44a647a1d1340065c46d1c65b41725f8362d8334',
 'native_compare':'adea4459ada7a99979360dca0450c57d3072753db3819a045570730dd2b65456',
 'nulls':'259a56ec43bb82e7167d9266eb74446622ee51abec364bb21a27620d3eccbb0c',
 'grading':'5346ccc4d0e3f3104d6b9477887e9b5255abab4b166422973d68ed693df0ad1e',
}
modules = {}; source_reads = 0; encoded = 0
for name, expected in PINS.items():
    raw = (BASE/(name+'.py')).read_bytes(); source_reads += len(raw)
    assert hashlib.sha256(raw).hexdigest() == expected
    module=types.ModuleType(name); module.__file__=str(BASE/(name+'.py'))
    sys.modules[name]=module
    exec(compile(raw,module.__file__,'exec'), module.__dict__)
    modules[name]=module
common=modules['common']; study=modules['study']; hist=modules['history']
raw_canonical=common.canonical

def meter(value):
    global encoded
    raw=raw_canonical(value); encoded += len(raw)
    assert encoded <= 1048576
    return raw
common.canonical=meter
PIN={'bytes':1,'sha256':'a'*64}
tracemalloc.start()
results=[]

def record(name, **details):
    results.append({'group':name,'counterexample_confirmed':True,**details})

# A complete native111 scalar comparison may not ignore an explicit reject rule.
n=modules['native_compare']; roots=['r'+str(i) for i in range(37)]
policy={'selection_pin':PIN,'root_source_pin':PIN,
 'producer_source_pins':{role+'/'+r:PIN for role in n.ROLES for r in roots},
 'roots':{r:{'q':{'kind':'exact','units':'unit','shape':[], 'support_pin':PIN,
 'absolute_tolerance':0,'relative_tolerance':0,'nonfinite':'reject'}} for r in roots}}
panels={role+'/'+r:{'source_pin':PIN,'quantities':{'q':{'units':'unit','support_pin':PIN,
 'values':float('inf') if r=='r0' else 1, 'status':'complete'}}} for role in n.ROLES for r in roots}
r=n.compare(policy,roots,panels)
assert r['all_declared_quantities_match'] is True
record('exact_native_nonfinite_reject_bypass',records=r['records'])
del r,panels,policy

# One declared identity must not be silently split into smaller null groups.
rows=[{'id':'q'+str(i),'animal':'a','session':'s','stratum':'offer_CPIn',
 'channel_mask':[1,1],'grid_pin':PIN,'observation_end_ns':(i+1)*10} for i in range(4)]
def group(ids):
 return {'ids':ids,'offset':1,'minimum_separation_ns':1,'circular_period_ns':100,
 'maximum_circular_gap_ns':100,'boundary':'declared_circular_wrap_no_exchangeability_claim'}
policy={'id':'n1','kind':'within_session_joint_neural_epoch_cyclic_shift_v1','refit':'full_graph',
 'clock_support_evidence':PIN,'selection_evidence':PIN,
 'groups':[group(['q0','q1']),group(['q2','q3'])]}
r=modules['nulls'].validate_and_map({'queries':rows},policy)
assert r['mapping']=={'q0':'q1','q1':'q0','q2':'q3','q3':'q2'}
record('fragmented_null_identity_accepted',groups=2,identities=1)
del r,policy,rows

# Finite numerator and denominator can still produce a nonfinite normalized loss.
queries=[{'id':s,'session':'s','stratum':s} for s in common.STRATA]
r=modules['grading'].loss_for_animal(queries,{s:1e150 for s in common.STRATA},
 {s:1 for s in common.STRATA},{s:1e-30 for s in common.STRATA})
assert all(math.isinf(v['normalized_loss']) for v in r.values())
record('normalized_loss_overflow_accepted',strata=len(r))
del r

# Full16/paired4/four-stratum schema, but one physical target gets two keys.
animals=['a%02d'%i for i in range(16)]; queries=[]
for a in animals:
 for j,s in enumerate(common.STRATA):
  queries.append({'id':a+'_'+s,'animal':a,'session':'s','stratum':s,'trial':1,
   'target_key':a+('_slrt' if s=='side_on' else '_iti'),
   'target_kind':'SLRT' if s=='side_on' else 'next_ITI','target_trial':2,
   'observation_end_ns':10*(j+1),'target_available_ns':15,
   'channel_mask':[1,1] if a in animals[:4] else [1,0],'grid_pin':PIN,'alias_pin':PIN})
queries[1]['target_key']='a00_second_alias'
s={'task':common.TASK,'animals':animals,'paired_animals':animals[:4],
 'sessions':{a:['s'] for a in animals},'queries':queries,'feature_schema_pin':PIN,
 'admission_evidence':{k:PIN for k in ['original_members','producer_fields','biological_identity',
 'session_trial_identity','channel_grid','absolute_clocks','target_aliases','logical_history','full_support']},
 'eligible_sessions':{a:{k:['s'] for k in common.STRATA} for a in animals}}
study.validate_study(s)
# The small barrier exposes the first alias while the later alias is still active.
obligations=[]
for q in queries[:2]:
 obligations.append({'id':q['id'],'query_id':q['id'],'target_key':q['target_key'],'session':'s',
  'trial':q['trial'],'stratum':q['stratum'],'variant_ordinal':0,
  'observation_end_ns':q['observation_end_ns'],'target_available_ns':q['target_available_ns']})
b=hist.HistoryBarrier(obligations,['s']); first=b.next_batch()
b.close_batch({q:{'obligation_id':q,'prediction_pin':PIN,'closure_pin':PIN} for q in first['obligation_ids']})
second=b.next_batch()
assert second['released_target_keys']==['a00_iti']
record('contradictory_target_alias_passes_and_releases',same_physical_target_two_keys=True,
 released_before_second_alias_prediction=second['released_target_keys'])
del b,obligations,first,second,s,queries

# Independent denominator must preserve exact-constant zero, not manufacture variance.
found=None
for count in range(2,65):
 for seconds in (1.1,2.0,3.0,7.0,math.e,10.0):
  qs=[{'id':'q'+str(i),'animal':'a','session':'s','stratum':'offer_CPIn','channel_mask':[1,1]} for i in range(count)]
  tiny={'animals':['a'],'paired_animals':['a'],'queries':qs}
  try: result=modules['grading'].group_variance(tiny,'full',['a'],'offer_CPIn',{q['id']:seconds for q in qs})
  except common.Refusal: continue
  assert result['variance']>0
  found={'rows':count,'constant_seconds':seconds,'positive_variance':result['variance']};break
 if found:break
assert found is not None
record('constant_target_spurious_positive_variance',**found)
del qs,tiny
current,peak=tracemalloc.get_traced_memory();tracemalloc.stop()
assert peak<=8388608
summary={'schema':'ach_peer_v1_counterexamples','source_pins':PINS,'groups':results,
 'all_expected_counterexamples_confirmed':True,'measured_encoded_bytes_before_summary':encoded,
 'source_bytes_read':source_reads,'traced_peak_after_source_load':peak,
 'prospective_cumulative_reservation':2097152,'encoded_subcap':1048576,
 'nonserialized_scaffold_reservation':1048576,'physical_fixture_writes':0,
 'retained_fixture_files':0,'actual_scientific_inputs_or_execution':False}
# Output is small control metadata, never scientific data.
print(json.dumps(summary,sort_keys=True,indent=2,allow_nan=False))
