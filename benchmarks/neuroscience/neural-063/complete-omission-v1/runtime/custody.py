"""Actual registered-job shutdown and target-last barrier; no asserted booleans."""
from __future__ import annotations
import hashlib
from pathlib import Path
import time
from owner.io import Artifact, ArtifactStore, ByteMeter, ContractError, canonical, capture, decode, ordinary
from .contracts import CONDITIONS, STAGES, digest, profile
from .engine import Engine
from .jobs import attempt_label, LABELS


def claims(root,p,attempt,stage=None,meter=None,deadline=None):
 root=ordinary(root,directory=True);base=root/'runtime-jobs';result={}
 deadline=deadline or time.monotonic()+p['cleanup_wall_seconds']
 if not base.exists():return result
 ordinary(base,directory=True)
 cap=p['aggregate']['runtime_capsules_max']
 for path in base.glob('*/*/*/claim.json'):
  if time.monotonic()>=deadline:raise ContractError('claim reconciliation wall allocation exceeded')
  if len(result)>=cap:raise ContractError('registered jobs exceed complete finite allocation')
  raw=decode(capture(path,65536,meter=meter))
  if raw.get('schema')!='neural063_runtime_job_claim_v1' or raw.get('attempt')!=attempt or raw.get('stage') not in STAGES or raw.get('profile_sha256')!=digest(p):raise ContractError('claim outside exact attempt/stage/profile')
  if path.parent.parent.parent.name!=raw['stage'] or path.parent.parent.name!=raw['controller'] or path.parent.name!=str(raw['ordinal']):raise ContractError('claim hierarchy mismatch')
  expected=dict(zip(LABELS,(attempt_label(attempt),raw['stage'],raw['controller'],raw['job'])))
  if raw['labels']!=expected or raw['name']!='n063-'+raw['job'][:48] or raw['name'] in result:raise ContractError('claim identity/label mismatch')
  if stage is None or raw['stage']==stage:result[raw['name']]=raw
 return result


def reconcile(root,p,attempt,stage,meter,*,stop,deadline=None):
 deadline=min(time.monotonic()+p['cleanup_wall_seconds'],deadline if deadline is not None else float('inf'))
 owned=claims(root,p,attempt,stage,meter,deadline)
 engine=Engine(p,meter,deadline=deadline)
 identity=engine.qualify();observations=[]
 listed=engine.list_attempt(attempt_label(attempt))
 if not isinstance(listed,list):raise ContractError('actual container roster unavailable')
 all_claims=claims(root,p,attempt,None,meter,deadline)
 for entry in listed:
  labels=entry.get('Labels',{});names={n.lstrip('/') for n in entry.get('Names',[])}
  matching=names&set(all_claims)
  if len(matching)!=1 or labels!=all_claims[next(iter(matching))]['labels']:raise ContractError('attempt has an unregistered or relabeled container; never stop it blindly')
 for name,claim in owned.items():
  actual=engine.inspect(name,absent=True)
  if actual and 'Id' in actual:
   if actual.get('Name')!='/'+name or actual.get('Config',{}).get('Labels')!=claim['labels']:raise ContractError('claim container identity changed')
   if actual.get('State',{}).get('Running'):
    if not stop:raise ContractError('target-last barrier found a live runtime writer')
    engine.request('POST','/containers/'+actual['Id']+'/kill',allowed=(204,409))
   job_deadline=min(deadline,time.monotonic()+min(p['cleanup_wall_seconds'],p['engine_timeout_seconds']))
   while True:
    actual=engine.inspect(actual['Id'])
    if not actual['State'].get('Running') and actual['State'].get('Pid',0)==0:break
    if time.monotonic()>=job_deadline:raise ContractError('registered runtime descendants remain after kill')
    time.sleep(0.02)
   observations.append({'name':name,'id':actual['Id'],'labels':claim['labels'],'state':actual['State'],'observed_ns':time.time_ns()})
  else:observations.append({'name':name,'absent':True,'labels':claim['labels'],'observed_ns':time.time_ns()})
 lock=Path(p['gpu_exclusive_lock'])
 if lock.absolute()!=Path(root)/'runtime-jobs'/'gpu.lock':raise ContractError('GPU lock outside attempt custody')
 if lock.exists():
  value=decode(capture(lock,4096,meter=meter))
  if value.get('attempt')!=attempt or value.get('name') not in all_claims or value.get('job')!=all_claims[value['name']]['job']:raise ContractError('unowned GPU lock cannot be removed')
  if stage is None or value.get('stage')==stage:
   if not stop:raise ContractError('target-last barrier found an unresolved GPU lease')
   actual=engine.inspect(value['name'],absent=True)
   if actual and actual.get('State',{}).get('Running'):raise ContractError('live GPU lease cannot be removed')
   lock.unlink()
 return {'schema':'neural063_runtime_reconciliation_v1','attempt':attempt,'stage':stage,'profile_sha256':digest(p),'engine':identity,'registered_jobs':len(owned),'observations':observations,'observed_ns':time.time_ns(),'mode':'stop_and_reinspect' if stop else 'observe_only'}


def cleanup_stage(spec,admitted):
 """Trusted parent hook, called on success/failure before completion signing.

Raises on any unresolved writer or missing physical observation. It stops only
containers whose names and labels match durable claims in this attempt/stage.
Interrupted claims remain. The separate container PID1 expiry handles parent
abrupt death; this hook closes the eventual recovery and evidence route.
"""
 p=profile(spec['parameters']['runtime_profile']);root=ordinary(spec['output_root'],directory=True)
 meter=ByteMeter(p['cleanup_read_bytes'],p['cleanup_write_bytes'])
 result=reconcile(root,p,spec['attempt'],spec['stage'],meter,stop=True,deadline=admitted['deadline']['stage_deadline'])
 store=ArtifactStore(root,meter);store.mkdir('runtime-parent-cleanup')
 receipt=store.json('runtime-parent-cleanup/'+spec['stage']+'.json',result,role='runtime_parent_cleanup',visibility='operator',producer=spec['stage'])
 return {'receipt':receipt.object(),'observed_registered_jobs':result['registered_jobs'],'usage':meter.snapshot(),'physical_os_io_bytes':None}


def verify_scoring_barrier(ctx):
 ctx.require_scientific();p=profile(ctx.parameters['runtime_profile'])
 capture_bundle=ctx.read_input('prediction_capture',roles={'prediction_capture'},cap=100_000_000)
 life=ctx.read_input('lifecycle_custody',roles={'lifecycle_custody'},cap=100_000_000)
 narratives=ctx.read_input('narrative_receipts',roles={'narrative_receipts'},cap=100_000_000)
 if (capture_bundle.get('schema')!='neural063_prediction_capture_v1' or life.get('schema')!='neural063_lifecycle_custody_v1' or life.get('attempt')!=ctx.attempt or life.get('profile_sha256')!=digest(p) or life.get('prediction_capture_sha256')!=ctx.inputs['prediction_capture'].sha256 or life.get('narrative_receipts_sha256')!=ctx.inputs['narrative_receipts'].sha256):raise ContractError('lifecycle barrier belongs to another attempt/capture/profile')
 if capture_bundle.get('candidate_predictions_sha256')!=ctx.inputs['candidate_predictions'].sha256 or set(narratives.get('reports',{}))!=set(CONDITIONS):raise ContractError('all immutable candidates/eight narrative outcomes required before target access')
 for name,record in narratives['reports'].items():
  if record.get('status') not in {'complete','failed'}:raise ContractError('report has not reached a terminal outcome')
  for key in ('controller_receipt','transcript'):
   ref=Artifact.parse(record[key]);capture(ref.path,min(ref.bytes,100_000_000),descriptor=ref,meter=ctx.store.meter)
  if record['status']=='complete':
   ref=Artifact.parse(record['narrative']);capture(ref.path,min(ref.bytes,8*2**20),descriptor=ref,meter=ctx.store.meter)
 # Authenticate already admitted prediction capture body again. No query target,
 # private binding or score is opened in this function.
 ref=ctx.inputs['candidate_predictions'];capture(ref.path,1_500_000_000,descriptor=ref,meter=ctx.store.meter)
 actual=reconcile(ctx.store.root,p,ctx.attempt,None,ctx.store.meter,stop=False)
 if actual['registered_jobs']!=life.get('registered_jobs'):raise ContractError('new runtime jobs appeared after report closure')
 return {'schema':'neural063_scoring_barrier_v1','prediction_capture_sha256':ctx.inputs['prediction_capture'].sha256,'narrative_receipts_sha256':ctx.inputs['narrative_receipts'].sha256,'lifecycle_custody_sha256':ctx.inputs['lifecycle_custody'].sha256,'actual_reconciliation':actual,'target_body_reads':0}
