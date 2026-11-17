"""Physical A/B source boundary, independent of public tool-name filtering."""
from .contracts import need
PARTICIPANT_ENGINE=frozenset({'nlb/__init__.py','nlb/contracts.py','nlb/arrays.py','nlb/worker.py','nlb/worker_runtime.py','nlb/reference_service.py'})
PROFILES=frozenset({'participant_A','participant_B','reference_tool','reference_producer','raw_operator','protected_score','model_gateway'})
def tool_variant_profile(tool,participant_profile,selected):
 need(participant_profile in('participant_A','participant_B'),'actual code-view profile')
 need(tool in('run_python','reference_predict'),'closed tool variant')
 need(selected==(participant_profile if tool=='run_python'else'reference_tool'),'actual kind requires its exact separate physical source profile')
def source_mount(profile,role,paths):
 need(profile in PROFILES,'closed runtime profile')
 if profile.startswith('participant_'):
  need(role not in('reference_method_source','protected_scorer_source','raw_operator_source'),'no hidden algorithm tree in learner runtime')
  if role=='engine_source':need(set(paths)==PARTICIPANT_ENGINE,'minimal learner harness; no vendor/scientific module bodies')
  if profile=='participant_A':need(role!='curated_code_B','paper/data arm cannot mount GitHub code')
def rootfs_qualification(profile,doc,rootfs):
 need(doc['schema']=='NLB017_immutable_rootfs_qualification_v1'and doc['runtime_profile']==profile and doc['rootfs']==rootfs,'exact runtime/source profile')
 need(doc['immutable_image_digest']and doc['complete_filesystem_census']and doc['original_terminal'],'current complete image provenance')
 if profile.startswith('participant_'):need(doc['task_source_absent_from_base_image']is True,'no authentic algorithm code hidden in base image')
 need(doc['source_profiles_separately_qualified']is True,'reference/scoring source is separate from arbitrary learner runtime')
