"""Physical role projections; restricted conditions never mount hidden arrays."""
from .contracts import need,canonical,digest
from .programme import allowed_references,SHUFFLE_RULE
BASE_T=('train_counts_heldin','train_counts_heldout','train_trial_ids','heldin_unit_ids','heldout_unit_ids','train_condition_ids','bin_left_edges_ms')
BASE_Q=('eval_counts_heldin','eval_trial_ids','heldin_unit_ids','heldout_unit_ids','eval_condition_ids','bin_left_edges_ms','eval_valid_mask')

def project(public,condition,*,shuffle=None):
 import numpy as np
 need(condition in('intact','within_condition_shuffle','context_only','training_rate_only','metadata_neutral'),'condition')
 if condition=='context_only':
  t={k:public[k].copy()for k in BASE_T if k not in('train_counts_heldin','heldin_unit_ids')};q={k:public[k].copy()for k in BASE_Q if k not in('eval_counts_heldin','heldin_unit_ids')}
 elif condition=='training_rate_only':
  t={'train_count_totals':np.asarray(public['train_counts_heldout'],dtype=np.float64).sum(axis=(0,1)),'train_bin_opportunities':np.asarray(1721*140),'heldout_unit_ids':public['heldout_unit_ids'].copy()};q={k:public[k].copy()for k in('eval_trial_ids','heldout_unit_ids','bin_left_edges_ms','eval_valid_mask')}
 else:
  t={k:public[k].copy()for k in BASE_T};q={k:public[k].copy()for k in BASE_Q}
  if condition=='within_condition_shuffle':
   need(shuffle is not None and sorted(shuffle.tolist())==list(range(574)),'exact protected permutation');need(np.array_equal(public['eval_condition_ids'][shuffle],public['eval_condition_ids']),'within-condition donors');q['eval_counts_heldin']=public['eval_counts_heldin'][shuffle].copy()
 return t,q,allowed_references(condition)

def shuffle_map(seed,planned,commitment):
 import numpy as np,hashlib,json
 need(type(seed)is bytes and len(seed)==32 and digest(seed)==commitment['seed_sha256'],'original 256-bit seed commitment')
 from .programme import planned_support
 planned_support(planned);support_sha=digest(canonical(planned));need(commitment['schema']=='NLB017_target_free_shuffle_commitment_v2'and commitment['planned_support_sha256']==support_sha and commitment['rule']==SHUFFLE_RULE,'pre-activity exact prospective rule and support identity')
 need(commitment['numpy_version']==np.__version__,'pinned PCG64 source version');conditions=planned['eval_condition_ids'];permutation=np.arange(574)
 # Preserve exact public JSON identity/type without array dtype coercion.
 groups={}
 for position,condition in enumerate(conditions):
  key=canonical(condition);groups.setdefault(key,{'condition':condition,'positions':[]})['positions'].append(position)
 for key in sorted(groups):
  condition=groups[key]['condition'];group=np.asarray(groups[key]['positions'],dtype=np.int64);body=json.dumps([*SHUFFLE_RULE['tuple_prefix'],support_sha,condition],ensure_ascii=False,separators=(',',':'),allow_nan=False).encode('utf8');derived=int.from_bytes(hashlib.sha256(seed+body).digest(),'big')
  order=np.random.Generator(np.random.PCG64(derived)).permutation(len(group))
  for j in range(len(group)):permutation[group[order[j]]]=group[order[(j+1)%len(group)]]
 return permutation

def case_query(query,index):
 need(type(index)is int and 0<=index<574,'case index');return{k:(v[index:index+1].copy()if k in('eval_counts_heldin','eval_trial_ids','eval_condition_ids','eval_valid_mask')else v.copy())for k,v in query.items()}

def admissible_state(metadata,condition,query_pin):
 need(metadata['reference_id']in allowed_references(condition),'reference not visible in condition')
 need(metadata['information_condition']==condition or (metadata['query']is None and metadata['reference_id']in allowed_references(condition)),'query-dependent state condition')
 if metadata['query']is not None:need(metadata['query']==query_pin,'no intact query-adapted state in shuffle')
 need(metadata['lineage']in('training_only','training_and_observed_query'),'forbidden state lineage')
