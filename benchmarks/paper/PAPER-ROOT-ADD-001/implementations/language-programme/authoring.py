"""Four independent global source commitments, before any numerical view."""
from common import *
ARMS=('A','B')
PROGRAMS={'reproduction':8388608,'prediction':8388608}
def authoring_files(b,bodies,arm):
 rows=b['materials']['common']+(b['materials']['author_code'] if arm=='B' else [])
 files={r['target']:descriptor(r,100000000,allow_empty=True) for r in rows if r['target']!='transcription.zip'} # timing archive enters runtime only after global freeze
 files.update({n:pin(bodies[n]) for n in ('CANDIDATE_ABI.md','RESOURCE_PLAN.json')});return files

def global_commit(v,b,bodies,out,budget):
 pairraw=capture(v['pair']['path'],v['pair'],META_CAP,budget);pair=parse(pairraw)
 keys={'schema','task_id','programs','authorship','authoring_protocol','root_attests_separate_contexts','root_attests_records_are_authentic','root_attests_no_cross_arm_feedback'}
 need(type(pair)is dict and set(pair)==keys and pair['schema']=='language_building_blocks_independent_program_pair_v1' and pair['task_id']==TASK and set(pair['programs'])==set(pair['authorship'])==set(ARMS) and all(pair[k]is True for k in keys if k.startswith('root_attests')),'complete independently attested four-context pair')
 apraw=capture(pair['authoring_protocol']['path'],pair['authoring_protocol'],META_CAP,budget);ap=parse(apraw)
 need(type(ap)is dict and set(ap)=={'schema','model','model_revision','system_instructions_sha256','tool_policy_sha256','time_seconds','max_tokens','max_program_revisions','seed_policy'} and ap['schema']=='language_building_blocks_matched_authoring_protocol_v1','same prespecified authoring controls')
 need(all(type(ap[k])is int and 0<ap[k]<=10**9 for k in ('time_seconds','max_tokens','max_program_revisions')) and all(type(ap[k])is str and 0<len(ap[k])<=512 for k in ('model','model_revision','seed_policy')) and all(type(ap[k])is str and re.fullmatch('[a-f0-9]{64}',ap[k]) for k in ('system_instructions_sha256','tool_policy_sha256')),'bounded matched authoring controls')
 save(out/'authorship/PROTOCOL.json',apraw,budget);programs={};records={};seen=set()
 for arm in ARMS:
  need(set(pair['programs'][arm])==set(pair['authorship'][arm])==set(PROGRAMS),'both independent purposes in each access arm');programs[arm]={};records[arm]={}
  for purpose,cap in PROGRAMS.items():
   d=pair['programs'][arm][purpose];raw=capture(d['path'],d,cap,budget);need(raw and '\0' not in raw.decode('utf-8'),'nonempty UTF8 program');programs[arm][purpose]=save(out/'programs'/arm/(purpose+'.py'),raw,budget,cap)
   recordraw=capture(pair['authorship'][arm][purpose]['path'],pair['authorship'][arm][purpose],META_CAP,budget);r=parse(recordraw)
   fields={'schema','arm','purpose','context_id','program','interface','resources','authoring_protocol','generation_seed','image','versions','authoring_view','original_or_prepared_numeric_inputs_seen','operator_private_seen','cross_arm_feedback','other_program_seen','interface_supplied_before_finalization','prior_exposure_statement'}
   role='native' if purpose=='reproduction' else 'strict'
   need(type(r)is dict and set(r)==fields and r['schema']=='language_building_blocks_independent_authorship_v1' and r['arm']==arm and r['purpose']==purpose and r['program']==programs[arm][purpose] and r['interface']==pin(bodies['CANDIDATE_ABI.md']) and r['resources']==pin(bodies['RESOURCE_PLAN.json']) and r['authoring_protocol']==pin(apraw) and r['image']==v['images'][role] and r['versions']==v['versions'][role],'exact independent program/interface/environment record')
   need(type(r['context_id'])is str and 0<len(r['context_id'])<=160 and r['context_id'] not in seen and type(r['generation_seed'])is int and 0<=r['generation_seed']<2**64 and all(r[k]is False for k in ('original_or_prepared_numeric_inputs_seen','operator_private_seen','cross_arm_feedback','other_program_seen')) and r['interface_supplied_before_finalization']is True and type(r['prior_exposure_statement'])is str and 0<len(r['prior_exposure_statement'])<=4096,'four separate authoring histories and no numeric exposure')
   seen.add(r['context_id']);vr=capture(r['authoring_view']['path'],r['authoring_view'],META_CAP,budget);view=parse(vr)
   need(view=={'schema':'language_building_blocks_authoring_view_v1','task_id':TASK,'arm':arm,'purpose':purpose,'files':authoring_files(b,bodies,arm),'numeric_data_files':0,'private_files':0,'construction_custody_attested_by_root':True},'exact common paper/specification plus B-only author code')
   save(out/'authorship'/arm/(purpose+'.json'),recordraw,budget);save(out/'authorship'/arm/(purpose+'-VIEW.json'),vr,budget);records[arm][purpose]=pin(recordraw)
 result={'schema':'language_building_blocks_global_four_program_commitment_v1','task_id':TASK,'programs':programs,'authorship':records,'authoring_protocol':pin(apraw),'pair':pin(pairraw),'interface':pin(bodies['CANDIDATE_ABI.md']),'resources':pin(bodies['RESOURCE_PLAN.json']),'data_or_native_phase_started':False,'attestation_is_independent_history_proof':False}
 return result,save(out/'PAIR_COMMITMENT.json',canonical(result),budget)
