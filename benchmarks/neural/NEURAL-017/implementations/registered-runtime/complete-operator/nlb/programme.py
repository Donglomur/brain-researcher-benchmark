"""Finite pre-exposure programme identities; no learner or numerical imports."""
from .contracts import closed,need,integer,descriptor,digest,canonical,relative
def streaming_identity(value):
 """Exact original canonical bytes, without a duplicate full JSON buffer."""
 from .operator_wire import identity
 return identity(value)

SHUFFLE_RULE={'schema': 'NLB017_target_free_shuffle_rule_v2', 'tuple_prefix': ['NLB017-target-free-shuffle-v2', 'NEURAL-017'], 'planned_support_encoding': 'canonical UTF8 sorted-key compact finite JSON plus exactly one LF', 'tuple_encoding': 'UTF8 compact finite JSON array ensure_ascii=False separators=(comma,colon) without LF', 'derived_integer': 'SHA256(seed_bytes || tuple_bytes), unsigned big endian', 'donor_cycle': 'original query order; recipient group[order[j]] receives group[order[(j+1)%m]]; singleton identity', 'rng': 'NumPy Generator(PCG64), exact version pinned in commitment', 'adopted_selection_sha256': '8624fecac8037615e520d5e097bb5d0a956341bec725ead6255946a459fd2537'}

CONDITIONS=('intact','within_condition_shuffle','context_only','training_rate_only','metadata_neutral')
REFERENCES=tuple('R'+str(i) for i in range(9))
P4H={'cpu_seconds':14400,'wall_seconds':172800,'cpus':4,'memory_bytes':16*2**30,'scratch_bytes':2*2**30,'retained_bytes':512*2**20,'model_tokens':2097152,'tool_result_bytes':128*2**10,'processes':64}
def group_id(g):return '%s/%s-%s/seed-%d'%(g['condition'],g['mode'],g['code_view'],g['agent_seed'])
def group_key(condition,mode,view,seed):return '%s/%s-%s/seed-%d'%(condition,mode,view,seed)
def expected_groups():return [dict(condition=c,mode=m,code_view=v,agent_seed=s,cases=574,primary=c=='intact',numeric_predictions_required=True) for c in CONDITIONS for m in('F','I')for v in('A','B')for s in range(1,6)]
def allowed_references(c):return REFERENCES if c in('intact','within_condition_shuffle','metadata_neutral')else ('R0','R1','R2')if c=='context_only'else ('R0',)
def bank_id(c,r):return 'reference/'+c+'/'+r
def programme(spec,roster,contrasts):
 closed(spec,{'schema','canonical_id','source','design','roster','contrasts','planned_support','groups','code_views','model','tool_policy','budgets','reference_budget','shuffle_commitment','split','rubric','qualification_schedule','exposure','created_before_activity','execution_plan_sha256'})
 need(spec['schema']=='NLB017_programme_v1'and spec['canonical_id']=='NEURAL-017','programme identity')
 for k in('source','design','roster','contrasts','planned_support','shuffle_commitment','split','rubric','qualification_schedule','exposure'):descriptor(spec[k])
 need(spec['created_before_activity']is True,'pre-activity source selection required')
 want={group_id(x):x for x in expected_groups()};got={group_id(x):x for x in roster['all_groups']};need(got==want and len(roster['all_groups'])==100,'complete fixed roster')
 need(spec['groups']==sorted(want),'exact group union');need(len(contrasts['contrasts'])==65 and len({x['id']for x in contrasts['contrasts']})==65,'65 contrasts')
 need(spec['budgets']==P4H,'matched primary P4H envelope; L20 is separate')
 need(spec['reference_budget']=={'cpu_seconds':720000,'wall_seconds':259200,'cpus':4,'memory_bytes':16*2**30,'gpu':False},'full expert construction envelope')
 closed(spec['code_views'],{'A','B'})
 for k in('A','B'):descriptor(spec['code_views'][k])
 closed(spec['model'],{'runtime','model_identity','configuration','prompt','tokenizer','service_qualification'})
 for x in spec['model'].values():descriptor(x)
 need(spec['tool_policy']==['read_public','run_python','reference_predict','inspect_state','commit_prediction'],'fixed actual tool surface')
 return digest(canonical(spec))
def execution_plan_identity(selection):
 """Acyclic source/recipe precommitment; late review hashes are not recipes."""
 fixed={k:selection[k]for k in('native_jobs','worker_contexts','participant_groups','initial_artifacts','original_deadline','reference_limits','reference_original_deadline','reporting')}
 fixed['stages']={stage:{'jobs':row['jobs'],'evidence':{key:({'qualification_product':key}if 'qualification'in value else value)for key,value in row['evidence'].items()}}for stage,row in selection['stages'].items()}
 return streaming_identity(fixed)
def bind_programme(value,identity):
 if value=='@programme':return identity
 if type(value)is dict:return{k:bind_programme(v,identity)for k,v in value.items()}
 if type(value)is list:return[bind_programme(v,identity)for v in value]
 return value
def planned_support(doc):
 closed(doc,{'schema','source_release','split_identity','shape','train_trial_ids','eval_trial_ids','train_condition_ids','eval_condition_ids','heldin_unit_ids','heldout_unit_ids','bin_left_edges_ms','chronological_eval_trial_ids'})
 need(doc['schema']=='NLB017_target_free_planned_support_v2','target-free support schema')
 closed(doc['source_release'],{'dandiset','version','asset_id','raw_bytes','raw_sha256'});need(doc['source_release']=={'dandiset':'000128','version':'0.220113.0400','asset_id':'26e85f09-39b7-480f-b337-278a8f034007','raw_bytes':690612247,'raw_sha256':'a27f84f9c31f077011062fd99a6ced199fdf19e656151f056c3c6244a408a3c4'},'exact release metadata')
 descriptor(doc['split_identity']);need(doc['shape']=={'training':[1721,140,137,45],'query':[574,140,137,45]},'complete planned shape')
 for key,n in(('train_trial_ids',1721),('eval_trial_ids',574),('heldin_unit_ids',137),('heldout_unit_ids',45),('bin_left_edges_ms',140)):
  need(type(doc[key])is list and len(doc[key])==n and len(set(doc[key]))==n,'complete unique '+key)
 need(not set(doc['train_trial_ids'])&set(doc['eval_trial_ids']),'train/query disjoint')
 need(not set(doc['heldin_unit_ids'])&set(doc['heldout_unit_ids']),'unit roles disjoint')
 for k,n in(('train_condition_ids',1721),('eval_condition_ids',574)):need(len(doc[k])==n,'condition support')
 need(doc['bin_left_edges_ms']==list(range(-250,450,5)),'exact 700ms source window')
 chrono=doc['chronological_eval_trial_ids'];need(chrono is None or (len(chrono)==574 and set(chrono)==set(doc['eval_trial_ids'])),'chronology is original order, never ID sort')
 return doc

def expected_jobs(spec):
 """Every actual invocation has an exact, unique role and no favourable subset."""
 out={}
 for r in REFERENCES:out['train/'+r]={'stage':'S05','role':'reference_train','reference':r}
 out['development/R0-R1']={'stage':'S05','role':'reference_development','reference':'R0'}
 out['development/R3']={'stage':'S05','role':'reference_development','reference':'R3'}
 for c in CONDITIONS:
  for r in allowed_references(c):out[bank_id(c,r)]={'stage':'S06','role':'reference_predict','condition':c,'reference':r}
 for g in expected_groups():
  gid=group_id(g)
  if g['mode']=='F':out[gid+'/programme']={'stage':'S07','role':'participant_F',**g}
  else:
   out[gid+'/preparation']={'stage':'S08','role':'participant_I_prepare',**g}
   for i in range(574):out[gid+'/case-%04d'%i]={'stage':'S09','role':'participant_I_case','case_index':i,**g}
 for route in('TOOL_ONLY_BATCH','TOOL_ONLY_CASE'):out[route]={'stage':'S06','role':'tool_only','route':route}
 return out
