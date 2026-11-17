"""Protected collector: complete provenance and full support before release."""
from .contracts import need,closed,canonical,digest,descriptor,Custody
from .programme import expected_groups,group_id,allowed_references,CONDITIONS,bank_id,expected_jobs

class Collector:
 def __init__(self,spec,programme_sha,support,store,jobs):
  self.spec=spec;self.programme=programme_sha;self.support=support;self.store=store;self.jobs=jobs;self.products={};self.failures={};self.failure_owners={};self.closed=False
  self.expected=expected_jobs(spec)
 def add(self,job,product,observation,bindings):
  need(not self.closed and job in self.expected and job not in self.products and job not in self.failures,'one actual job outcome')
  # Invalid participant products become explicit outcomes without suppressing
  # other already-selected jobs; none can grant a partial target permit.
  try:
   need(observation.job==job and observation.dispatched and observation.reaped and observation.exit_code==0 and observation.absence is True,'original terminal identity')
   need(observation.custody.complete and observation.custody.first_error is None and all(observation.stream_eof.values()),'complete original custody')
   need(observation.costs['cpu_seconds']is not None and 'process'in observation.persistence and 'worker_result'in observation.persistence,'known costs and durable original result')
   need(bindings['programme']==self.programme and bindings['job']==job and bindings['role']==self.expected[job]['role'],'exact job source role')
   need(bindings['source']==self.jobs[job]['source']and bindings['inputs']==self.jobs[job]['input_manifests'],'original source/input binding')
   descriptor(product);raw=self.store.read(product,512*2**20)
   self.products[job]={'product':product,'terminal':observation.persistence['process'],'original_worker_result':observation.persistence['worker_result'],'bindings':bindings}
  except BaseException as e:
   owner=Custody('collector:'+job);self.failure_owners[job]=owner;owner.fail(e,'product_admission');diagnostic=owner.snapshot()['first_error']
   self.failures[job]={'classification':'participant_invalid'if self.expected[job]['role'].startswith('participant')else'producer_failed','type':diagnostic['type'],'reason':diagnostic['detail'],'original':None}
   try:self.failures[job]['original']=observation.public()
   except BaseException as secondary:owner.fail(secondary,'collector_original_projection')
   self.failures[job]['custody']=owner.snapshot()
 def record_failure(self,job,observation):
  need(job in self.expected and job not in self.products and job not in self.failures,'unique failed job');self.failure_owners[job]=observation.custody;self.failures[job]={'classification':'producer_failed','original':None}
  try:self.failures[job]['original']=observation.public()
  except BaseException as secondary:observation.custody.fail(secondary,'collector_failed_original_projection')
 def complete_predictions(self,load_product):
  """Called only by trusted numeric collection worker, before target mounting."""
  import numpy as np
  from .arrays import prediction,dump_arrays
  groups={};required=[]
  for g in expected_groups():
   gid=group_id(g)
   if g['mode']=='F':keys=[gid+'/programme']
   else:keys=[gid+'/case-%04d'%i for i in range(574)]
   required+=keys
   if any(k not in self.products for k in keys):continue
   try:
    parts=[prediction(load_product(self.products[k]['product']),self.support,None if g['mode']=='F'else i)for i,k in enumerate(keys)]
    full=dict(parts[0]);full['expected_counts']=np.concatenate([x['expected_counts']for x in parts],axis=0);full['trial_ids']=np.concatenate([x['trial_ids']for x in parts]);raw=dump_arrays(full,32*2**20)
    prediction(raw,self.support);groups[gid]=self.store.write('collection/'+digest(gid.encode())+'.npz',raw,32*2**20)
   except BaseException as e:
    owner=Custody('collector:'+gid);self.failure_owners[gid]=owner;owner.fail(e,'invalid_full_prediction');diagnostic=owner.snapshot()['first_error']
    self.failures[gid]={'classification':'invalid_full_prediction','type':diagnostic['type'],'reason':diagnostic['detail']}
  for c in CONDITIONS:
   for r in allowed_references(c):
    key=bank_id(c,r);required.append(key)
    if key in self.products:
     try:raw=load_product(self.products[key]['product']);prediction(raw,self.support);groups[key]=self.store.write('collection/'+digest(key.encode())+'.npz',raw,32*2**20)
     except BaseException as e:
      owner=Custody('collector:'+key);self.failure_owners[key]=owner;owner.fail(e,'invalid_reference_prediction');diagnostic=owner.snapshot()['first_error']
      self.failures[key]={'classification':'invalid_reference_prediction','type':diagnostic['type'],'reason':diagnostic['detail']}
  for key in('TOOL_ONLY_BATCH','TOOL_ONLY_CASE'):
   required.append(key)
   if key in self.products:
    try:raw=load_product(self.products[key]['product']);prediction(raw,self.support);groups[key]=self.store.write('collection/'+key+'.npz',raw,32*2**20)
    except BaseException as e:
      owner=Custody('collector:'+key);self.failure_owners[key]=owner;owner.fail(e,'invalid_tool_control');diagnostic=owner.snapshot()['first_error']
      self.failures[key]={'classification':'invalid_tool_control','type':diagnostic['type'],'reason':diagnostic['detail']}
  expected_group_count=100+sum(len(allowed_references(c))for c in CONDITIONS)+2
  need(not self.failures and set(self.products)==set(self.expected),'all planned actual producers')
  need(len(groups)==expected_group_count and all(k in self.products for k in required),'whole immutable prediction union')
  self.closed=True;body={'schema':'NLB017_collection_commit_v1','programme':self.programme,'support':self.support,'products':self.products,'prediction_groups':groups,'failures':{},'all_actual_jobs':sorted(self.expected),'complete':True}
  return self.store.write('collection/COMMIT.json',canonical(body),64*2**20)
 def abort_metadata(self):return {'schema':'NLB017_incomplete_collection_v1','programme':self.programme,'actual_products':self.products,'failed':self.failures,'missing':sorted(set(self.expected)-set(self.products)-set(self.failures)),'target_permission':False,'failure_custodies':{k:v.snapshot()for k,v in self.failure_owners.items()}}

def barrier(store,collection_pin,programme_sha,jobs,authority):
 authority.check('S12');store.budget.guard();d=store.json(collection_pin,64*2**20)
 need(d['schema']=='NLB017_collection_commit_v1'and d['programme']==programme_sha and d['complete']is True and not d['failures'],'complete original collection')
 need(set(d['all_actual_jobs'])==set(jobs)==set(d['products']),'exact complete job union')
 for job,row in d['products'].items():
  t=store.json(row['terminal']);need(t['job']==job,'original terminal job')
  if t.get('schema')=='NLB017_actual_broker_terminal_v1':
   need(t['programme']==programme_sha and t['complete']is True and t['children']and t['original']['first_error']is None,'complete actual broker')
   for child,pin in t['children'].items():
    need(pin is not None and child.startswith(job+'/'),'same actual case child');ct=store.json(pin);need(ct['job']==child and ct['exit_code']==0 and ct['reaped']and ct['absence']is True and all(ct['stream_eof'].values())and ct['terminal']['complete']and ct['terminal']['first_error']is None and ct['costs']['cpu_seconds']is not None,'complete original broker child')
  else:
   need(t['exit_code']==0 and t['reaped']and t['absence']is True and all(t['stream_eof'].values())and t['terminal']['complete']and t['terminal']['first_error']is None,'original terminal closure');need(t['costs']['cpu_seconds']is not None,'known original CPU')
   original=store.json(row['original_worker_result']);need(original['job']==job and original['bindings']==row['bindings'],'original complete producer result');prefix=row['original_worker_result']['path'].rsplit('/',1)[0]
   for pin in original['products'].values():store.read({**pin,'path':prefix+'/'+pin['path']},512*2**20)
  store.read(row['product'],512*2**20)
 for pin in d['prediction_groups'].values():store.read(pin,32*2**20)
 authority.check('S12');return store.write('evidence/RELEASE_PERMIT.json',canonical({'schema':'NLB017_global_release_v1','programme':programme_sha,'collection':collection_pin,'all_jobs':sorted(jobs),'one_complete_release':True}),2**20)
