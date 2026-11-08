import sys,types,json,hashlib,tracemalloc
from pathlib import Path
P=Path(__file__).resolve().parent;BASE=P.parent
expected={'common':'ec86ed521415f7aad10677d41f900d285d683605752a640bcb23fec5c6a3b749','study':'1bb6fdab6e63172decbef9054d3a62b1962b9ef117d316f2647aef3652e51282','history':'ba782f66d4fb3cdbf51d5fda44a647a1d1340065c46d1c65b41725f8362d8334'}
for name,h in expected.items():
 raw=(BASE/(name+'.py')).read_bytes();assert hashlib.sha256(raw).hexdigest()==h
 m=types.ModuleType(name);sys.modules[name]=m;exec(compile(raw,name,'exec'),m.__dict__)
c=sys.modules['common'];s=sys.modules['study'];h=sys.modules['history'];PIN={'bytes':1,'sha256':'a'*64}
encoded=0;original=c.canonical
def meter(v):
 global encoded
 raw=original(v);encoded+=len(raw);assert encoded<=131072;return raw
c.canonical=meter
tracemalloc.start()
animals=['a%02d'%i for i in range(16)];rows=[]
for a in animals:
 for i,k in enumerate(c.STRATA):
  rows.append({'id':a+'_'+k,'animal':a,'session':'s','stratum':k,'trial':1,
   'target_key':a+('_SLRT' if k=='side_on' else '_ITI'),
   'target_kind':'SLRT' if k=='side_on' else 'next_ITI','target_trial':2,
   'observation_end_ns':10*(i+1),'target_available_ns':15,'channel_mask':[1,1] if a in animals[:4] else [1,0],
   'grid_pin':PIN,'alias_pin':PIN})
for i in (1,3):rows[i]['target_key']='a00_other_alias'
study={'task':c.TASK,'animals':animals,'paired_animals':animals[:4],'sessions':{a:['s'] for a in animals},
 'queries':rows,'feature_schema_pin':PIN,'eligible_sessions':{a:{k:['s'] for k in c.STRATA} for a in animals},
 'admission_evidence':{k:PIN for k in ['original_members','producer_fields','biological_identity','session_trial_identity','channel_grid','absolute_clocks','target_aliases','logical_history','full_support']}}
s.validate_study(study)
obligations=[{'id':q['id'],'query_id':q['id'],'target_key':q['target_key'],'session':q['session'],
 'trial':q['trial'],'stratum':q['stratum'],'variant_ordinal':0,'observation_end_ns':q['observation_end_ns'],
 'target_available_ns':q['target_available_ns']} for q in rows if q['animal']=='a00']
b=h.HistoryBarrier(obligations,['s']);first=b.next_batch();b.close_batch({q:{'obligation_id':q,'prediction_pin':PIN,'closure_pin':PIN} for q in first['obligation_ids']});second=b.next_batch()
assert len(obligations)==4 and second['released_target_keys']==['a00_ITI']
assert second['obligation_ids']==['a00_reward_SideOff']
_,peak=tracemalloc.get_traced_memory();tracemalloc.stop();assert peak<8388608
print(json.dumps({'schema':'ach_peer_complete_alias_counterexample','full_study_queries':len(rows),'full_study_animals':16,
 'complete_animal_obligations':len(obligations),'released_target_keys':second['released_target_keys'],
 'active_same_physical_target_alias':'a00_other_alias','encoded_bytes_before_summary':encoded,
 'traced_peak_after_source_load':peak,'reserved_cumulative_bytes':262144,'physical_fixture_writes':0,
 'actual_input_or_execution':False},sort_keys=True,indent=2))
