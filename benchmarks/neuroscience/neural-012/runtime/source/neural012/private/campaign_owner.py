"""Full96 logical jobs/192 original phase invocations; actual lineage, no learning certificate."""
import hashlib,time
from pathlib import Path
import io_contract as io
from case_contract import validate_case
from job_plan import job_plan,prepare_job
from execution_boundary import programme_manifest,validate_selection,ExecutionBudget,digest
from container_owner import InvocationOwner,CapturedFit
from execution_boundary import stage
from scientific_contract import project_reference,profile_sha256
from source_validation import SourceValidationOwner
from protocol_policy import classify_programmes
from phase_provenance import validate_evidence
from analysis import ARMS
from merge_stream import merge

class CampaignOwner:
 def __init__(self,panel_raw,source_targets_raw,programmes,selection,workspace,signal_root,reference_raw,source_owner):
  io.need(type(panel_raw)is bytes and panel_raw==io.encoded(io.strict(panel_raw)),'canonical original prepared panel before effects')
  io.need(type(source_owner)is SourceValidationOwner,'original completed source-validation owner, not receipt')
  source_owner.require_original(panel_raw,reference_raw,source_targets_raw,profile_sha256(io.strict(panel_raw)['scientific_profile']))
  self.source_owner=source_owner;self.target_selection=source_owner.target_selection
  source_owner.require_target_selection(self.target_selection)
  self.target_owner=None;self.analysis_complete=False;self.analysis_first_error=None;self.analysis_secondary_errors=[]
  source_owner.require_qualified('full_panel_source_join',io.strict(panel_raw)['source_qualification_sha256'])
  self.selection=validate_selection(io.strict(io.encoded(selection)));self.budget=ExecutionBudget(self.selection);self.plan=job_plan(panel_raw)
  io.fields(programmes,ARMS);self.programmes={}
  for arm,value in programmes.items():
   io.fields(value,['manifest_raw','root']);programme_manifest(io.strict(value['manifest_raw']))
   self.programmes[arm]={'manifest_raw':value['manifest_raw'],'root':Path(value['root'])}
  self.comparison=classify_programmes(self.programmes)
  self.panel_raw=panel_raw;self.source_targets_raw=source_targets_raw
  self.plan_sha256=digest(io.encoded(self.plan));self.scientific_profile_sha256=self.plan['scientific_profile_sha256']
  self.root=Path(workspace);io.need(self.root.is_absolute()and not self.root.exists()and not self.root.is_symlink(),'fresh campaign original root')
  self.signal_root=signal_root;self.reference_raw=reference_raw;self.jobs=[];self.results={};self.fit_results={};self.fit_captures={};self.invocations={}
  self.complete=False;self.first_error=None;self.secondary_errors=[];self.receipt_write_completed=False
  self.stream_raw={};self.stream_pins={};self.started_ns=None;self.finished_ns=None
  self.read_demand=0;self.staging_demand=0;self.output_demand=0
  lim=self.selection['limits'];fit_cap=self.selection['fit_state_limits']['bytes']
  for job in self.plan['jobs']:
   raws,origin=prepare_job(panel_raw,source_targets_raw,self.plan,job['job_id'])
   io.fields(raws,['fit','predict'])
   prog=programme_manifest(io.strict(self.programmes[job['arm']]['manifest_raw']))
   for phase in ('fit','predict'):
    raw=raws[phase];case=validate_case(io.strict(raw));io.need(case['phase']==phase,'exact planned phase')
    rows=case['train'if phase=='fit'else'query'];timing=job['arm']=='timing'
    signals=[]if timing else[r['signal']for r in rows]
    reference_size=0 if timing else len(io.encoded(project_reference(io.strict(reference_raw),rows)))
    signal_bytes=sum(r['bytes']for r in signals);source_bytes=sum(r['bytes']for r in prog['files'])
    # Fit reserves its private immutable capture; predict reserves its separate state input.
    self.staging_demand+=len(raw)+source_bytes+signal_bytes+reference_size+fit_cap
    self.read_demand+=3*(signal_bytes+len(signals))
    self.output_demand+=fit_cap if phase=='fit'else lim['output_bytes']
   self.jobs.append((job,raws,origin))
  io.need(len(self.jobs)==96 and self.plan['planned_invocations']==192,'all96 complete logical jobs and192phases')
  io.need(self.staging_demand<=lim['campaign_staging_bytes']and self.read_demand<=lim['campaign_signal_read_bytes']and self.output_demand<=lim['campaign_output_bytes'],'full192 phase/state/output demands admitted, no subset')
  io.need(192*5*(lim['stdout_bytes']+1)<=lim['campaign_stdout_bytes']and 192*5*(lim['stderr_bytes']+1)<=lim['campaign_stderr_bytes'],'full960 command stream reservation')
 def retain(self,error):
  if self.first_error is None:self.first_error=error
  else:self.secondary_errors.append(error)
 def run(self):
  io.need(self.started_ns is None,'one original campaign');self.started_ns=self.budget.started_ns
  deadline=self.budget.deadline_ns
  try:
   self.source_owner.require_original(self.panel_raw,self.reference_raw,self.source_targets_raw,self.scientific_profile_sha256)
   self.source_owner.require_qualified('full_panel_source_join',io.strict(self.panel_raw)['source_qualification_sha256'])
   self.budget.check();self.root.mkdir(mode=0o700);io.write(self.root/'plan.json',self.plan)
   for index,(job,raws,origin)in enumerate(self.jobs):
    identity={'job_id':job['job_id'],'plan_sha256':self.plan_sha256}
    for phase in ('fit','predict'):
     remaining=(deadline-time.monotonic_ns())/1000000000
     io.need(remaining>0,'same original campaign deadline, no phase reset')
     effective=io.strict(io.encoded(self.selection));admin=effective['limits']['admin_wall_seconds']
     io.need(remaining>5*admin,'reserve original image/create/inspect/removal administration before phase')
     effective['limits']['wall_seconds']=min(effective['limits']['wall_seconds'],remaining-5*admin)
     programme=self.programmes[job['arm']];timing=job['arm']=='timing'
     capture=None if phase=='fit'else self.fit_captures[job['job_id']]
     staged=stage(raws[phase],programme['manifest_raw'],programme['root'],self.root/('job-'+str(index)+'-'+phase),effective,
      None if timing else self.signal_root,None if timing else self.reference_raw,self.budget,capture,identity,source_owner=self.source_owner)
     io.write(staged.root/'private/case-origin.json',origin);self.budget.check()
     owner=InvocationOwner(staged,effective);key=(job['job_id'],phase)
     io.need(key not in self.invocations,'one acquired original owner per logical job phase')
     self.invocations[key]=owner
     result=owner.run()
     io.need(result is owner and type(result)is InvocationOwner and result.complete and result.first_error is None and result.receipt_write_completed,'actual complete original phase invocation owner')
     if phase=='fit':
      self.fit_results[job['job_id']]=owner
      self.fit_captures[job['job_id']]=owner.capture_fit()
     else:self.results[job['job_id']]=owner
   io.need(len(self.fit_results)==len(self.fit_captures)==len(self.results)==96 and len(self.invocations)==192,'complete192-phase collection before merging')
   for arm in ARMS:
    self.budget.check();source=[];target=None
    for job,raws,origin in self.jobs:
     if job['arm']!=arm:continue
     owner=self.results[job['job_id']]
     io.need(type(owner)is InvocationOwner and owner.complete and owner.staged.case['phase']=='predict'and owner.staged.case['arm']==arm,'actual original prediction lineage')
     if job['held_source_patient']is None:target=owner.output
     else:source.append((job['held_source_patient'],owner.output))
    value=merge(self.panel_raw,source,target,arm);raw=io.encoded(value)
    self.stream_pins[arm]=io.write(self.root/(arm+'-stream.json'),value);self.stream_raw[arm]=raw
   io.need(time.monotonic_ns()<=deadline,'same complete campaign deadline')
   self.complete=True
  except BaseException as e:self.retain(e)
  finally:
   try:self.finished_ns=time.monotonic_ns()
   except BaseException as e:self.complete=False;self.retain(e)
   try:
    io.write(self.root/'campaign.json',{'schema':'neural012_actual_campaign_v3','plan_sha256':self.plan_sha256,
     'case_origins':[origin for _,_,origin in self.jobs],'actual_completed_jobs':list(self.results),'actual_completed_fit_jobs':list(self.fit_results),
     'actual_acquired_invocations':[{'job_id':job_id,'phase':phase,'custody':owner.custody_summary()}for(job_id,phase),owner in self.invocations.items()],
     'fit_captures':[self.fit_captures[j].observation()for j in self.fit_captures],'comparison':self.comparison,
     'started_ns':self.started_ns,'finished_ns':self.finished_ns,'complete':self.complete,'stream_pins':self.stream_pins,
     'first_error':None if self.first_error is None else repr(self.first_error),'secondary_errors':[repr(e)for e in self.secondary_errors],
     'fit_use_verified':False,'native_isolation_qualified':False,'scientifically_qualified':False,
     'whole_staging_demand':self.staging_demand,'whole_signal_read_demand':self.read_demand,'whole_output_demand':self.output_demand,
     'planned_logical_jobs':96,'planned_phase_invocations':192,'output_total_filesystem_quota_qualified':False})
    self.receipt_write_completed=True
   except BaseException as e:self.complete=False;self.retain(e)
  if self.first_error is not None:raise self.first_error
  return self
 def analysis_evidence(self,panel_raw,stream_raw):
  """Read-only observations from this actual complete owner, never from a receipt loader."""
  self.budget.check()
  self.source_owner.require_original(self.panel_raw,self.reference_raw,self.source_targets_raw,self.scientific_profile_sha256)
  self.source_owner.require_target_selection(self.target_selection)
  io.need(type(self)is CampaignOwner and self.complete and self.first_error is None and self.receipt_write_completed,'same completed original campaign')
  io.need(panel_raw==self.panel_raw and self.plan==job_plan(panel_raw),'same complete original panel and plan')
  io.fields(stream_raw,ARMS);io.need(set(self.stream_raw)==set(ARMS)and stream_raw==self.stream_raw,'all original emitted stream bytes')
  io.need(len(self.jobs)==len(self.results)==len(self.fit_results)==len(self.fit_captures)==96 and len(self.invocations)==192,'complete original phase roster')
  programme_pins={arm:digest(self.programmes[arm]['manifest_raw'])for arm in ARMS};lineages=[]
  for job,raws,origin in self.jobs:
   self.budget.check()
   jid=job['job_id'];fit=self.fit_results[jid];predict=self.results[jid];capture=self.fit_captures[jid]
   identity={'job_id':jid,'plan_sha256':self.plan_sha256}
   io.need(type(fit)is InvocationOwner and type(predict)is InvocationOwner and type(capture)is CapturedFit,'original phase owner types')
   io.need(self.invocations[(jid,'fit')]is fit and self.invocations[(jid,'predict')]is predict and capture.owner is fit and predict.staged.fit_capture is capture,'original fit-capture-predict occurrence chain')
   for phase,owner in [('fit',fit),('predict',predict)]:
    io.need(owner.complete and owner.first_error is None and owner.container_removed and owner.receipt_write_completed,'complete removed phase with original receipt')
    io.need(owner.staged.budget is self.budget and owner.staged.logical_job==identity and owner.staged.case_raw==raws[phase]and owner.staged.case['phase']==phase,'same original phase,case,job,budget')
    io.need(owner.staged.source_owner is self.source_owner,'same original validated source owner in every phase')
    io.need(owner.staged.manifest_raw==self.programmes[job['arm']]['manifest_raw'],'same actual selected programme')
   capture.require_lineage(job['arm'],digest(raws['fit']),self.programmes[job['arm']]['manifest_raw'],identity)
   io.need(predict.staged.fit_raw is capture.raw and predict.staged.case['fit_case_sha256']==capture.fit_case_sha256,'prediction staged the exact captured artifact')
   admitted=predict.staged.view['fit_capture_admitted_ns']
   io.need(capture.captured_ns<=admitted and predict.commands and admitted<=predict.commands[0]['started_ns'],'capture before original prediction input admission and commands')
   io.need(predict.output_raw is not None and io.strict(predict.output_raw)==predict.output,'same original prediction output')
   state=io.strict(capture.raw)
   lineages.append({'job_id':jid,'arm':job['arm'],'held_source_patient':job['held_source_patient'],
    'fit_case_sha256':digest(raws['fit']),'predict_case_sha256':digest(raws['predict']),'programme_sha256':programme_pins[job['arm']],
    'fit_state':{'bytes':len(capture.raw),'sha256':digest(capture.raw)},'prediction':{'bytes':len(predict.output_raw),'sha256':digest(predict.output_raw)},
    'fit_container_id':fit.container_id,'predict_container_id':predict.container_id,'fit_captured_ns':capture.captured_ns,
    'predict_admitted_ns':admitted,'training_use_declaration':state['training_use_declaration'],'complete':True})
  for arm in ARMS:
   self.budget.check()
   io.need(self.stream_pins[arm]=={'bytes':len(stream_raw[arm]),'sha256':digest(stream_raw[arm])},'same original output pins')
   source=[];target=None
   for job,_,_ in self.jobs:
    if job['arm']!=arm:continue
    out=self.results[job['job_id']].output
    if job['held_source_patient']is None:target=out
    else:source.append((job['held_source_patient'],out))
   io.need(io.encoded(merge(panel_raw,source,target,arm))==stream_raw[arm],'complete actual phase outputs reproduce emitted stream')
   self.budget.check()
  evidence={'schema':'neural012_phase_execution_evidence_v1','panel_sha256':digest(self.panel_raw),'source_targets_sha256':digest(self.source_targets_raw),
   'plan_sha256':self.plan_sha256,'scientific_profile_sha256':self.scientific_profile_sha256,'programme_sha256':programme_pins,
   'stream_pins':self.stream_pins,'comparison':self.comparison,'logical_jobs':96,'phase_invocations':192,'lineages':lineages,
   'operational_phase_order_observed':True,'semantic_fit_use_verified':False,'native_isolation_qualified':False,'scientifically_qualified':False}
  validated=validate_evidence(evidence,digest(self.panel_raw),self.scientific_profile_sha256)
  self.budget.check();return validated

if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser(description=__doc__)
 for n in('panel','source-targets','runtime-selection','reference-binding','source-selection','source-roots','source-limits'):
  p.add_argument('--'+n,type=Path,required=True);p.add_argument('--'+n+'-sha256',required=True)
 p.add_argument('--signal-root',type=Path,required=True);p.add_argument('--workspace',type=Path,required=True)
 for arm in ARMS:
  p.add_argument('--'+arm+'-programme',type=Path,required=True);p.add_argument('--'+arm+'-programme-sha256',required=True);p.add_argument('--'+arm+'-root',type=Path,required=True)
 a=p.parse_args()
 # Explicit future source observation precedes campaign construction. It opens
 # no target_selection path and never turns observation into genuine authority.
 source_owner=SourceValidationOwner(io.read(a.source_selection,io.MAX_JSON,a.source_selection_sha256),io.strict(io.read(a.source_roots,1048576,a.source_roots_sha256)),io.strict(io.read(a.source_limits,1048576,a.source_limits_sha256)))
 source_owner.observe()
 # Held targets have no loose path/hash callback in this interface.
 panel=io.read(a.panel,io.MAX_JSON,a.panel_sha256);gold=io.read(a.source_targets,io.MAX_JSON,a.source_targets_sha256)
 selection=io.strict(io.read(a.runtime_selection,1048576,a.runtime_selection_sha256))
 programmes={arm:{'manifest_raw':io.read(getattr(a,arm+'_programme'),1048576,getattr(a,arm+'_programme_sha256')),'root':getattr(a,arm+'_root')}for arm in ARMS}
 reference=io.read(a.reference_binding,io.MAX_JSON,a.reference_binding_sha256)
 # Use the canonical module class, also required by the protected-target consumer.
 from campaign_owner import CampaignOwner as CanonicalCampaignOwner
 execution=CanonicalCampaignOwner(panel,gold,programmes,selection,a.workspace,a.signal_root,reference,source_owner)
 execution.run()
 from prepare_analysis import prepare_completed_campaign
 prepare_completed_campaign(execution)
