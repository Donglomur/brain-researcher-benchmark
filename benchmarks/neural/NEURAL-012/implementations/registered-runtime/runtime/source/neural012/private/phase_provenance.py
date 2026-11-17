"""Structural checks for observational192-phase evidence; this never issues execution authority."""
import re
import io_contract as io
from protocol_policy import validate_comparison
ARMS=('native','harmonized','normalized','timing')
SHA=re.compile(r'[0-9a-f]{64}\Z')
def sha(value):io.need(type(value)is str and SHA.fullmatch(value),'exact SHA256 observation')
def pin(value):
 io.fields(value,['bytes','sha256']);io.need(type(value['bytes'])is int and 0<value['bytes']<=io.MAX_JSON,'bounded observed artifact size');sha(value['sha256'])
def validate_evidence(value,panelpin,profilepin):
 io.fields(value,['schema','panel_sha256','source_targets_sha256','plan_sha256','scientific_profile_sha256','programme_sha256','stream_pins','comparison','logical_jobs','phase_invocations','lineages','operational_phase_order_observed','semantic_fit_use_verified','native_isolation_qualified','scientifically_qualified'])
 io.need(value['schema']=='neural012_phase_execution_evidence_v1','phase evidence schema')
 for k in ('panel_sha256','source_targets_sha256','plan_sha256','scientific_profile_sha256'):sha(value[k])
 io.need(value['panel_sha256']==panelpin and value['scientific_profile_sha256']==profilepin,'same panel and scientific policy observation')
 io.need(type(value['logical_jobs'])is int and value['logical_jobs']==96 and type(value['phase_invocations'])is int and value['phase_invocations']==192,'complete96jobs192phases')
 io.need(value['operational_phase_order_observed']is True and value['semantic_fit_use_verified']is False and value['native_isolation_qualified']is False and value['scientifically_qualified']is False,'observational process facts do not imply qualification')
 io.fields(value['programme_sha256'],ARMS);io.fields(value['stream_pins'],ARMS)
 for arm in ARMS:sha(value['programme_sha256'][arm]);pin(value['stream_pins'][arm])
 validate_comparison(value['comparison'])
 io.need(type(value['lineages'])is list and len(value['lineages'])==96,'full original lineage roster')
 jobs=set();containers=set();people={a:set()for a in ARMS};full={a:0 for a in ARMS}
 for r in value['lineages']:
  io.fields(r,['job_id','arm','held_source_patient','fit_case_sha256','predict_case_sha256','programme_sha256','fit_state','prediction','fit_container_id','predict_container_id','fit_captured_ns','predict_admitted_ns','training_use_declaration','complete'])
  arm=r['arm'];pid=r['held_source_patient'];io.need(arm in ARMS,'known arm')
  io.need(pid is None or(type(pid)is str and io.ID.fullmatch(pid)),'biological held-person identity')
  name=arm+':'+('full-target'if pid is None else pid)
  io.need(r['job_id']==name and name not in jobs,'unique exact logical job');jobs.add(name)
  if pid is None:full[arm]+=1
  else:io.need(pid not in people[arm],'one original held-person fold');people[arm].add(pid)
  for k in ('fit_case_sha256','predict_case_sha256','programme_sha256'):sha(r[k])
  io.need(r['programme_sha256']==value['programme_sha256'][arm],'same selected programme per arm')
  pin(r['fit_state']);pin(r['prediction'])
  for k in ('fit_container_id','predict_container_id'):
   sha(r[k]);io.need(r[k]not in containers,'distinct original phase containers');containers.add(r[k])
  io.need(type(r['fit_captured_ns'])is int and type(r['predict_admitted_ns'])is int and 0<=r['fit_captured_ns']<=r['predict_admitted_ns'],'capture before query admission')
  io.need(r['training_use_declaration']in('fit_attempted','no_fit')and r['complete']is True,'allowed declaration and complete phase pair')
 io.need(all(len(people[a])==23 and full[a]==1 and people[a]==people[ARMS[0]]for a in ARMS)and len(containers)==192,'same complete23sourcefolds plus fulltarget across all4arms')
 return value
