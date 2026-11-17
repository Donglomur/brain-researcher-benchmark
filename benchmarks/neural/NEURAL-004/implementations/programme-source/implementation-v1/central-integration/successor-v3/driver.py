"""Complete fixed-parent phase driver and incremental signed-fact composition."""
import base64
from collections.abc import Mapping
from central_io import need,encoded,pin,cleanup_note
PHASES=('runtime','commit','prepare','hmp','references','prediction_actors','dispositions','prediction_closure','prediction_grade',
 'reconstruction_actors','reconstruction_grade','spatial','explanations','reasoning_grade','study_closeout')
class Envelopes(Mapping):
 """Complete source-owned keys; envelopes resolve only inside parent verification."""
 def __init__(self,keys,envelope):self.keys_=tuple(keys);need(len(set(self.keys_))==len(self.keys_),'Unique authority support');self.envelope=envelope
 def __iter__(self):return iter(self.keys_)
 def __len__(self):return len(self.keys_)
 def __getitem__(self,key):
  if key not in self.keys_:raise KeyError(key)
  return self.envelope
class BootstrapLedger:
 """Opaque seed delivery is charged to worker bootstrap, not a reset parent ledger."""
 def __init__(self,io,clock,live_cap):
  self.io=io;self.origin=clock['origin_ns'];self.scientific=clock['scientific_ns'];self.closeout=clock['closeout_ns'];self.outer=clock['outer_ns']
  self.live_cap=live_cap;self.live_now=0;self.failures=[];self.used={};self.limits={}
 def clock(self):
  import time
  return time.monotonic_ns()
 def tick(self,phase='scientific'):
  self.io.tick();now=self.clock();need(self.origin<=now<(self.scientific if phase=='scientific'else self.closeout),'Original bootstrap channel clock');return now
 def reserve(self,charges,label,cutoff='scientific'):
  self.tick(cutoff)
  for k,v in charges.items():
   need(type(v)is int and v>=0,'Exact bootstrap charge');self.used[k]=self.used.get(k,0)+v
  self.io.reads+=charges.get('read_bytes',0);self.io.writes+=charges.get('write_bytes',0)
  need(self.io.reads<=self.io.read_cap and self.io.writes<=self.io.write_cap,'Bootstrap complete channel charge')
 def live(self,n,label,cutoff='scientific'):
  from contextlib import contextmanager
  @contextmanager
  def guard():
   self.tick(cutoff);need(self.live_now+n<=self.live_cap,'Bootstrap live ceiling');self.live_now+=n
   try:yield
   finally:self.live_now-=n
  return guard()
 def fail(self,label,error):self.failures.append({'stage':label,'type':type(error).__name__})

def eligible(programme):
 """Same source facts as parent closeout; never a computed scientific score."""
 return bool(programme.hmp and programme.hmp['complete'] and programme.references and programme.references['full_closure'] and
  programme.prediction_grade and programme.prediction_grade['whole_prediction_complete'] and len(programme.reconstruction_grade)==2 and
  all(x['status']=='compared'for x in programme.reconstruction_grade.values()) and hasattr(programme,'reasoning_result') and programme.spatial_records)

def run(io,bound,parent):
 entry=parent.module('entry');authority=parent.module('authority');common=parent.module('common')
 op=bound['operation'];config=bound['config'];out=bound['output'];phase_rows=[];programme=None
 bootstrap=BootstrapLedger(io,config['clock'],bound['profile']['worker_live_bytes'])
 channel=authority.MetadataChannel(op['channel'],bootstrap)
 seed_reply=channel.exchange('operator','operator_seed',{'config_pin':common.pin(config,16*1048576)},secret=True)
 common.fields(seed_reply,('seed_base64','delivery_pin'));common.check_pin(seed_reply['delivery_pin'])
 channel.audit[-1]['delivery_pin']=seed_reply['delivery_pin']
 seed=base64.b64decode(seed_reply['seed_base64'],validate=True);need(len(seed)==32,'Exact externally delivered opaque seed')
 programme=entry.construct(config,common.pin(config,16*1048576),bound['repository'],seed);seed=None;seed_reply=None
 channel.bind_parent(programme.ledger,programme.bodies)
 programme.bodies.put_json('BOOTSTRAP_CHANNEL_COST.json',{'known':bootstrap.used,'failed':bootstrap.failures,'audit':channel.audit})
 token=authority.IncrementalEnvelope(channel);access=authority.ProviderAccess(channel,op['provider_deployments'])
 def phase(name,dependencies,action,source_predicates=()):
  need(name in PHASES and name not in {r['phase']for r in phase_rows},'One fixed full phase')
  prior={r['phase']:r for r in phase_rows};blocked=[d for d in dependencies if prior.get(d,{}).get('status')!='completed']
  blocked.extend(name for name,admitted in source_predicates if admitted is not True)
  row={'phase':name,'status':'blocked'if blocked else'attempted','blocked_by':blocked,'started_ns':bootstrap.clock()}
  phase_rows.append(row);io.save(out/('phase-'+name+'-start.json'),encoded(row))
  if not blocked:
   try:
    io.tick();value=action();io.tick();row['status']='completed'
    # The result is already retained by the fixed parent. This is phase custody,
    # never a replacement numerical prediction/scorer return.
    row['result_kind']=type(value).__name__
   except BaseException as error:
    row['status']='failed';row['failure']={'type':type(error).__name__,'message':str(error)[:1000],
     'secondary':list(getattr(error,'ach_cleanup_errors',[])),'exchange':getattr(error,'neural004_exchange_metadata',None)}
    try:programme.ledger.fail('central/'+name,error)
    except BaseException as secondary:
     cleanup_note(error,'phase failure ledger',secondary);row['failure']['secondary'].extend(getattr(error,'cleanup_errors',[]))
  row['finished_ns']=bootstrap.clock();io.save(out/('phase-'+name+'-end.json'),encoded(row));return row
 def admit_runtime():
  value=programme.admit_runtime(token)
  need(value['facts']['environment_pin']==bound['environment_pin'],'Signed runtime admission binds the actual selected worker import environment')
  return value
 phase('runtime',[],admit_runtime)
 phase('commit',['runtime'],lambda:programme.commit(token))
 phase('prepare',['commit'],lambda:programme.prepare(op['original_root'],op['source_roster'],token))
 phase('hmp',['prepare'],lambda:programme.numerical_hmp(bound['repository'],op['hmp_environment'],op['hmp_limits']))
 phase('references',['prepare'],lambda:programme.numerical_references(op['reference_budget']))
 exposures=Envelopes(programme.contexts.values(),token)
 phase('prediction_actors',['prepare'],lambda:programme.prediction_actors(None,None,access,exposures))
 # Partial reference/actor work may still have honest dispositions. The parent
 # decides whether its actual graph is closable; this driver cannot invent it.
 phase('dispositions',['prediction_actors'],programme.dispositions)
 def close_predictions():
  jobs={r['binding_digest']for r in programme.transport.records}
  return programme.close_predictions(Envelopes(programme.closed_dispositions,token),Envelopes(jobs,token),token)
 phase('prediction_closure',['dispositions'],close_predictions)
 phase('prediction_grade',['prediction_closure'],lambda:programme.grade(token))
 views=parent.module('views')
 recon_keys=[views.opaque(programme.seed,'context','reconstruction',[m,p])for m in common.MODES for p in common.PEOPLE]
 phase('reconstruction_actors',['prepare'],lambda:programme.reconstruction_actors(None,None,access,Envelopes(recon_keys,token)),
  [('original_prediction_release',programme.barrier.release is not None)])
 phase('reconstruction_grade',['reconstruction_actors'],lambda:programme.reconstruction_grades(token))
 phase('spatial',['prepare'],programme.spatial_descriptions,
  [('original_prediction_release',programme.barrier.release is not None),('retained_HMP_state',programme.hmp is not None)])
 phase('explanations',['prediction_grade','reconstruction_grade','spatial'],lambda:programme.explanation_actors(None,None,access))
 phase('reasoning_grade',['explanations'],lambda:programme.reasoning_grade(token))
 def final_close():
  full=all(r['status']=='completed'for r in phase_rows if r['phase']!='study_closeout')
  return programme.closeout(token if full else None,token if full and eligible(programme)and op['request_scientific_qualification']else None)
 phase('study_closeout',[],final_close)
 need(len(programme.bodies.records)<=bound['profile']['max_output_files'],'Complete retained parent inventory within admitted return bound')
 need(len(programme.transport.records)<=bound['max_jobs'],'All actual attempted jobs within complete policy ceilings')
 result={'schema':'neural004_complete_worker_return_v1','task':'NEURAL-004','source_pin':config['source_pin'],
  'config_pin':common.pin(config,16*1048576),'operation_pin':bound['operation_pin'],'parent_manifest_pin':bound['parent_manifest_pin'],
  'original_clock':config['clock'],'phases':phase_rows,'full_phase_roster':list(PHASES),
  'all_phases_completed':all(r['status']=='completed'for r in phase_rows),'parent_body_inventory':dict(programme.bodies.records),
  'actual_transport_records':list(programme.transport.records),'parent_logical_costs':programme.ledger.report(),'bootstrap_costs':bootstrap.used,'authority_exchange_audit':channel.audit,
  'actual_outer_exit_known':False,'provisional_until_original_outer_observation':True,'actual_scientific_qualification_inferred':False,
  'whole_parent_qualification_requires_retained_parent_closeout':True,'unknown_physical_costs_not_zero':True}
 io.tick();return result
