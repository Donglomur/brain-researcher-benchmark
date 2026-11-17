"""Full source-owned preparation→both arms→frozen references→score/panels.
The trusted coordinator remains alive through reporting. All numerical work is
inside fixed OCI workers; no result dictionary creates dispatch authority.
"""
from pathlib import Path
from .native.io import read,load,dump,write_new,identity,canonical,need,relative,authenticate_tree,tree
from .native.observation import Observation,ObservationError,snapshot
from .native.resources import Budget,ControllerMeter
from .native.contracts import Deployment
from .native import oci
from .selection import OperatorSelection
from .host_files import HostFiles
from .full_plan import validate,support_summary
from .full_artifacts import Artifacts,CapturedJob,TargetBarrier

class FullProgramme:
 def __init__(self,selection,controller,owner):
  need(type(selection)is OperatorSelection,'fixed original operator capture')
  need(type(controller)is ControllerMeter and controller.active and owner.children.get('controller')is controller.observation,'same already-active bootstrap controller owner')
  self.selection=selection;self.owner=owner;self.controller=controller;selection.transfer(self.owner)
  self.deployment=None;self.study=None;self.artifacts=None;self.states={};self.results={};self.errors={};self.targets={};self.preparation=None;self.barrier=TargetBarrier(self);self.report=None;self.host=HostFiles(selection.body['host_io_caps'],self.owner)
 def fail(self,stage,exc):
  self.owner.fail(exc,stage);self.errors.setdefault(stage,[]).append(exc)
 def capture_setup(self):
  body=self.selection.body;self.deployment=Deployment.capture(self.selection,self.host)
  from .study_compiler import compile_study
  self.study=compile_study(self.host.load(body['study']['path'],body['study']['bytes'],body['study']))
  self.frozen_programs={}
  for arm,program in body['programs'].items():
   self.frozen_programs[arm]=[(row['destination'],identity(self.host.read(row['path'],row['bytes'],row)))for row in program['files']]
   need(program['policy_source']in [row['destination']for row in program['files']],'candidate tuning policy is an actually pinned source file')
  source=body['evaluator_source'];need(self.host.tree(source['root'],**source['limits'])==source['selection'],'whole source identity')
  self.resource=Budget(self.study['resource_plan']['total'])
  operations=self.study['operations'];need(set(operations)=={'prepare','score'}|{j['id']for j in self.study['jobs']}|{p['id']for p in self.study['panels']}|{'literal_release'},'complete native operation census')
  for key,op in operations.items():self.resource.reserve(key,op['caps'],op['collection_bytes'],op['terminal_bytes'],op['terminal_files'])
  plan=self.study['resource_plan'];expected={k:plan['total'][k]-sum(op['caps'][k]for op in operations.values())for k in self.controller.cap}
  need(plan['controller_caps']==self.controller.cap==expected,'compiled residual equals independently preselected bootstrap allowance; no clock reset')
  self.controller.checkpoint('complete_setup_budget_binding')
  self.root=Path(body['output_root']);need(not self.root.exists(),'fresh complete original output');self.root.mkdir(parents=True,mode=0o700)
  self.artifacts=Artifacts(self.root/'captures',self.study['artifact_caps'],self.owner,self.host)
  self.states={j['id']:'pending'for j in self.study['jobs']};self.owner.record['states']=self.states
  self.artifacts.json('STUDY.json',self.study);self.artifacts.json('SUPPORT_DECLARATION.json',support_summary(self.study))
 def input_dir(self,key):
  root=self.root/'views'/relative(key);need(not root.exists(),'fresh reset per operation');root.mkdir(parents=True,mode=0o700);return root
 def copy_capture(self,capture,dest):
  self.artifacts.require(capture);body=self.artifacts.read(capture);self.host.write(dest,body,self.study['artifact_caps']['member_bytes']);return identity(body)
 def copy_selected(self,row,dest):
  body=self.host.read(row['path'],row['bytes'],row);self.host.write(dest,body,self.study['artifact_caps']['member_bytes']);return identity(body)
 def issue(self,key,request,view,source,arm='REFERENCE'):
  need(key not in self.resource.observations,'same original operation cannot replay');op=self.study['operations'][key];cap=op['caps']
  observation=Observation('trial_worker');self.owner.children[key]=observation;observation.bind_deadline(cap['wall_ms'])
  job={'public_id':'trial-'+key.replace('/','-'),'arm':arm};request=dict(request,input_bytes=self.host.tree(view,total=cap['input_bytes'],member=cap['member_bytes'],files=cap['files'])['bytes'])
  work=self.root/'workers'/key
  try:
   with self.controller.actor(key):
    record=oci.run(self.deployment.profile,job,request,source,view,None,work,cap,observation=observation)
   # Consume the actual same stopped-owner output, not a participant receipt.
   need(observation.completed is record and observation.first_error is None,'same original complete worker')
   self.resource.commit(key,record['resources'])
   expected=self.host.tree(work/'writable/output',total=cap['output_bytes'],member=cap['member_bytes'],files=cap['files'])
   original=[dict(r,path=r['path'][7:])for r in record['output_tree']['files']if r['path'].startswith('output/')]
   need(expected['files']==original,'actual stopped output subtree inverse')
   captures=self.artifacts.collect(work/'writable/output',expected,'results/'+key)
   return observation,captures
  except BaseException as exc:
   # Costs/handles and failed-prefix outputs remain with the original child.
   self.fail(key,exc);self.resource.observations[key]={'status':'failed','observed_prefix':observation.record.get('resources'),'complete':False};raise
 def worker_request(self,stage,**kw):
  return dict(stage=stage,entrypoint=[self.selection.body['worker_python'],'/source/worker_entry.py'],**kw)
 def prepare(self):
  view=self.input_dir('prepare');self.host.dump(view/'study.json',self.study);self.copy_selected(self.selection.body['definitions'],view/'definitions.json')
  definitions=self.host.load(view/'definitions.json')
  need(set(definitions)=={c['id']for c in self.study['cases']if c['status']=='available'},'complete original definition inverse')
  selected_raw={row['destination']:{k:row[k]for k in('bytes','sha256')}for row in self.selection.body['raw_inputs']}
  for definition in definitions.values():
   need(all(selected_raw.get(row['destination'])=={k:row[k]for k in('bytes','sha256')}for row in definition['original_files']),'native definition to actual selected raw input inverse')
   for field in('cache','path'):
    if field in definition:need(definition[field].startswith('/inputs/'),'fixed mounted native input path')
  # Complete selected local native inputs, including cache/source metadata, are
  # authenticated and copied before the protected preparation worker is issued.
  for row in self.selection.body['raw_inputs']:self.copy_selected(row,view/relative(row['destination']))
  o,captures=self.issue('prepare',self.worker_request('prepare'),view,self.selection.body['evaluator_source']['root'])
  manifest=next(c for c in captures if c.path=='results/prepare/PREPARATION.json');doc=self.artifacts.document(manifest)
  need(set(doc['cases'])=={c['id']for c in self.study['cases']},'all source-derived preparation dispositions')
  self.preparation=(o,captures,doc)
  self.targets={c.path:c for c in captures if c.path.startswith('results/prepare/private/')}
  self.artifacts.json('PREPARATION_DISPOSITIONS.json',doc)
 def source_view(self,job):
  if job['role']=='reference':return self.selection.body['evaluator_source']['root']
  program=self.selection.body['programs'][job['arm']];root=self.root/'sources'/job['id'];root.mkdir(parents=True)
  for row in program['files']:self.copy_selected(row,root/relative(row['destination']))
  need([(row['destination'],identity(self.host.read(root/row['destination'],row['bytes'],row)))for row in program['files']]==self.frozen_programs[job['arm']],'unchanged originally frozen candidate source/policy')
  # Exact published paper is an obligatory outside primary role in BOTH arms.
  self.copy_selected(self.selection.body['paper'],root/'paper.html')
  if job['arm']=='paper_data_author_code':
   for row in self.selection.body['author_sources']:self.copy_selected(row,root/'author-code'/relative(row['destination']))
  return root
 def execute_job(self,job):
  need(not self.barrier.sealed and not self.barrier.opened,'no new fit after any protected scoring access')
  key=job['id'];need(self.states[key]=='pending','one fixed job attempt');self.states[key]='attempted'
  if any(self.preparation[2]['cases'][c]['status']in('unavailable','unknown')for c in job['cases']):
   self.states[key]='unavailable';return
  try:
   need(all(self.states.get(d)=='complete'for d in job['depends_on']),'all genuine prior producers complete')
   need(all(self.preparation[2]['cases'][c]['status']=='complete'for c in job['cases']),'all intended job case support')
   view=self.input_dir(key)
   for cap in self.preparation[1]:
    sub=cap.path.removeprefix('results/prepare/')
    if any(sub.startswith('public/'+c+'/')for c in job['cases']):self.copy_capture(cap,view/sub)
   cfg=job['configuration'];self.copy_selected(cfg,view/'original-configuration.json')
   configuration=self.host.load(view/'original-configuration.json');configuration['original_configuration']=cfg
   query_sessions={c['session']for c in self.study['cases']if c['id']in job['cases']}
   training_cases=[c for c in self.study['cases']if c['id']in job['prior_training_cases']]
   need(all(self.preparation[2]['cases'][c['id']]['status']=='complete'for c in training_cases),'full intended non-target training support; no silently missing sessions')
   need(not query_sessions&{c['session']for c in training_cases},'full training sessions exclude held session')
   for cap in self.preparation[1]:
    sub=cap.path.removeprefix('results/prepare/')
    if any(sub.startswith(kind+'/'+c['id']+'/')for c in training_cases for kind in('public','private')):
     self.copy_capture(cap,view/'fold_training'/sub)
   self.host.dump(view/'FOLD_TRAINING.json',{'cases':training_cases,'query_sessions':list(query_sessions),'fold':job['fold'],'source':job['split'],'other_fold_feedback':False})
   configuration['base_predictions']={}
   for dep in job['depends_on']:
    result=self.results[dep].require()
    for cap in result.files:self.copy_capture(cap,view/'dependencies'/dep/cap.path.removeprefix('results/'+dep+'/'))
    d=self.artifacts.document(result.manifest)
    for row in d['predictions']:
     configuration['base_predictions'][row['case']]=dict(row['all_prediction'],path='dependencies/'+dep+'/'+row['all_prediction']['path'])
   self.host.dump(view/'configuration.json',configuration)
   source=self.source_view(job);cases=[c for c in self.study['cases']if c['id']in job['cases']]
   if job['role']=='reference':request=self.worker_request('reference',job=job,cases=cases)
   else:
    program=self.selection.body['programs'][job['arm']];request={'stage':'candidate','job':job,'cases':cases,'entrypoint':[self.selection.body['worker_python'],'/source/'+relative(program['entry'])]}
   o,files=self.issue(key,request,view,source,'REFERENCE'if job['role']=='reference'else'PARTICIPANT')
   manifest=next(c for c in files if c.path=='results/'+key+'/RESULT.json');doc=self.artifacts.document(manifest)
   need(doc['job']==key and doc['arm']==job['arm']and doc['cases']==job['cases'],'complete output envelope')
   result=CapturedJob(self,job,o,files,manifest);self.results[key]=result;result.require();self.states[key]='complete'
  except BaseException as exc:self.states[key]='failed';self.fail(key,exc)
 def select_references(self):
  selected={}
  for case in self.study['cases']:
   options=[]
   for j in self.study['jobs']:
    if j['role']!='reference'or j['method']not in('linear','single_rrr','mlp')or case['id']not in j['cases']or self.states[j['id']]!='complete':continue
    cap=next(c for c in self.results[j['id']].files if c.path.endswith('/SELECTION.json'));s=self.artifacts.document(cap)
    need(s['selection_domain']=='training/validation only'and s['query_tuning']is False,'reference frozen from validation only')
    options.append((s['candidates'][s['selected']]['validation_loss'],j['id'],j['method']))
   # No conveniently weak fallback may replace a missing competent family.
   if {x[2]for x in options}!={'linear','single_rrr','mlp'}:selected[case['id']]=None
   else:selected[case['id']]=min(options)[1]
  self.reference_selection=self.artifacts.json('FROZEN_REFERENCE_SELECTION.json',selected);return selected
 def score(self):
  self.barrier.seal();self.barrier.open();view=self.input_dir('score');self.host.dump(view/'study.json',self.study)
  index={'outputs':[],'case_metadata':{},'private_cases':{},'reference_selection':self.artifacts.document(self.reference_selection)}
  for cap in self.preparation[1]:
   sub=cap.path.removeprefix('results/prepare/')
   if sub.startswith(('private/','public/')):self.copy_capture(cap,view/sub)
   if sub.startswith('private/')and sub.endswith('/case.json'):
    key=sub[len('private/'):-len('/case.json')];index['private_cases'][key]=sub;index['case_metadata'][key]=sub
  for job in self.study['jobs']:
   if job['id']not in self.results:continue
   result=self.results[job['id']].require();doc=self.artifacts.document(result.manifest);prefix='jobs/'+job['id']+'/'
   for cap in result.files:self.copy_capture(cap,view/(prefix+cap.path.removeprefix('results/'+job['id']+'/')))
   for row in doc['predictions']:
    for key in('prediction','all_prediction'):
     if key in row:row[key]=dict(row[key],path=prefix+row[key]['path'])
   doc['original_manifest']=result.manifest.pin;dest=prefix+'SCORE_MANIFEST.json';self.host.dump(view/dest,doc);index['outputs'].append({'manifest':dest})
  self.host.dump(view/'SCORE_INPUTS.json',index)
  self.score_observation,self.score_files=self.issue('score',self.worker_request('score'),view,self.selection.body['evaluator_source']['root'])
 def panels(self):
  self.panel_states={}
  for panel in self.study['panels']:
   key=panel['id'];self.panel_states[key]='attempted'
   try:
    need(self.barrier.opened,'protected postcapture panel phase')
    recipe=self.selection.body['panel_recipes'][key];view=self.input_dir(key);self.copy_selected(recipe,view/'recipe.json')
    definition=self.host.load(view/'recipe.json')
    # Exact current source-capture selections. Original files/arrays are copied
    # from this invocation, never from archived answer tables.
    for row in definition['inputs']:
     cap=self.artifacts.by_path[relative(row['capture'])];self.copy_capture(cap,view/relative(row['destination']))
    _,files=self.issue(key,self.worker_request('panel',panel=panel),view,self.selection.body['evaluator_source']['root'])
    need(any(c.path.endswith('/PANEL.json')for c in files),'actual panel products');self.panel_states[key]='complete'
   except BaseException as exc:self.panel_states[key]='failed';self.fail(key,exc)
 def literal_release(self):
  need(self.barrier.opened,'literal released code only after all blind outputs frozen')
  view=self.input_dir('literal_release');recipe=self.selection.body['literal_release'];self.copy_selected(recipe['definition'],view/'release.json')
  for row in recipe['original_cache']:self.copy_selected(row,view/relative(row['destination']))
  return self.issue('literal_release',self.worker_request('literal_release'),view,self.selection.body['evaluator_source']['root'])
 def publish(self,name='FULL_REPORT.private.json'):
  # Snapshot failure cannot erase raw owners or already observed costs.
  report={'schema':'trial_full_campaign_report_v4','canonical':'PAPER-paper-method-replacement-009','states':self.states,
   'panel_states':getattr(self,'panel_states',{}),'support':None if self.study is None else support_summary(self.study),
   'preparation':None if self.preparation is None else self.preparation[2],
   'terminal_status':self.owner.record.get('terminal','report_prefix_before_terminal'),'report_accounting_cut':'observations before this publication; own publication/exit costs not certified',
   'first_failure':self.owner.failure(),'secondary_failures':self.owner.secondary(),
   'native_observations':{k:snapshot(v)for k,v in self.owner.children.items()},
   'qualification_gates_open':22,'scientifically_qualified':False,'whole_paper_reproduced':False,'meaningful_improvement':False,
   'host_io':self.owner.record['host_io'],'source_definition_status':'incomplete original definitions remain required',
   'own_process_future_exit':'UNKNOWN','historical_equivalence':'unqualified','complete_source_is_not_runtime_admission':True}
  self.report=self.artifacts.json(name,report);return self.report
 def run(self):
  need(self.controller.active,'whole setup is inside original controller scope')
  try:
   self.capture_setup()
   with self.deployment.activate():
    self.prepare()
    for job in self.study['jobs']:
     if self.controller.observation.first_error is not None:
      self.states[job['id']]='not_attempted_after_fatal_owner';continue
     self.execute_job(job)
    self.select_references()
    try:self.score()
    except BaseException as exc:self.fail('score',exc)
    self.panels()
    try:self.literal_release()
    except BaseException as exc:self.fail('literal_release',exc)
    self.owner.attempt('full_report',self.publish)
  except BaseException as exc:self.fail('full_driver',exc)
  finally:
   self.owner.record['terminal']='failed'if self.owner.first_error is not None else'completed_source_outputs'
   if self.artifacts is not None:self.owner.attempt('terminal_report_prefix',lambda:self.publish('TERMINAL_REPORT.private.json'))
  # Original invocation wrapper restores controller context before its final
  # accounting. Reports are explicitly prefixes, including publication costs.
  if self.owner.first_error is not None:self.owner.raise_failure()
  return self.report

class InvocationResult:
 """Strong source-owned result, retaining final cost owner as well as report."""
 def __init__(self,owner,report):self.owner=owner;self.report=report

def run_selected(path,pin,*,controller_caps):
 # The operator supplies these two positive limits independently of the file
 # about to be read. No default, candidate-supplied clock or retrospective reset.
 owner=Observation('trial_full_invocation',sample_clock=False);controller=None;report=None
 try:
  need(type(controller_caps)is dict and set(controller_caps)=={'wall_ms','cpu_usec'}and all(type(v)is int and v>0 for v in controller_caps.values()),'independent exact bootstrap wall/CPU allowance')
  caps=dict(controller_caps)
  controller=ControllerMeter({'body':{'resource_plan':{'controller_caps':caps,'total':dict(caps)},'jobs':[]}})
  owner.children['controller']=controller.observation
  with controller.activate('whole_trial_invocation'):
   selection=OperatorSelection.capture(path,pin)
   programme=FullProgramme(selection,controller,owner)
   report=programme.run()
 except BaseException as exc:owner.fail(exc,'whole_trial_invocation')
 finally:
  # This executes after activation restoration and all report/cleanup attempts.
  if controller is not None:owner.attempt('final_controller_accounting',lambda:controller.final('whole_trial_final_outward'))
 owner.record['terminal']='failed'if owner.first_error is not None else'completed_source_outputs'
 owner.record['own_process_future_exit']='UNKNOWN'
 if owner.first_error is not None:owner.raise_failure()
 owner.completed=report
 return InvocationResult(owner,report)
