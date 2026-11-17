"""Source-owned Responses executable and existing S13 executor composition."""
import argparse,copy,sys,time
from .contracts import Budget,Custody,Store,Authority,need,closed,integer,finite,descriptor,relative,canonical,parse,digest
from .executor import Executor,ProcessModel
from .worker_runtime import publish_worker,receipt_limits
from .gateway_isolation import model_aware_sandbox,model_aware_run,selected_transport,BASE_KEYS
from .openai_transport import read_credential,post_once,TransportFailure,credential_metadata
from .openai_protocol import ENDPOINT,CONFIG_KEYS,model_identity,configuration,bounded_json,request_body,response_admission,normalize_output

class OpenAIExecutor(Executor):
 def __init__(self,authority,store,source_sha,selected_jobs,*,isolation_class=model_aware_sandbox,process_run=model_aware_run):
  super().__init__(authority,store,source_sha,selected_jobs,isolation_class=isolation_class,process_run=process_run)
 def _invoke(self,job,stage,role,payload,budget,custody):
  if role=='model_exchange':
   # This is inside the original consumed invocation/custody and before base
   # child lease, sandbox construction, process dispatch or credential access.
   self.authority.check(stage,role);budget.admit()
   need(job in self.selected and job not in self.originals,'fresh selected model invocation')
   selected=self.selected[job]
   need(selected['role']==role and selected['stage']==stage and stage in('S01','S08','S09','S15'),'model exchange/native stage join before dispatch')
   argv=selected['argv'];need(type(argv)is list and len(argv)==10 and argv[1:5]==['-B','-m','nlb.openai_gateway','--config']and argv[6]=='--config-bytes'and argv[8]=='--config-sha256','exact source-owned gateway command')
   need(type(argv[0])is str and argv[0].startswith('/')and type(argv[5])is str and argv[5].startswith('/inputs/'),'explicit gateway interpreter/configuration')
   need(type(argv[7])is str and argv[7].isdigit()and str(int(argv[7]))==argv[7],'canonical configuration extent operand')
   pin={'path':argv[5][len('/inputs/'):],'bytes':int(argv[7]),'sha256':argv[9]};descriptor(pin)
   sandbox=selected['sandbox'];need(sandbox['runtime_profile']=='model_gateway','model-only selected runtime')
   scoped=Store(self.store.root,budget,custody)
   def mounted(p,role):
    matches=[m for m in sandbox['mounts']if m['guest']=='/inputs/'+p['path']]
    need(len(matches)==1 and matches[0]['role']==role and matches[0]['access']=='ro'and matches[0]['host']==str(scoped.path(p['path'])),'exact source metadata mount '+role)
   need(sum(m['role']=='gateway_config'for m in sandbox['mounts'])==1,'one per-job gateway configuration')
   mounted(pin,'gateway_config')
   config=validate_config(scoped.json(pin,2**20),{'job':job,'source':selected['source']})
   need(config['stage']==stage==selected['stage'],'configuration/native/exchange stage identity before dispatch')
   closed(payload,{'schema','model','configuration','prompt','tokenizer','seed','messages','max_remaining_total_tokens'})
   need(payload['schema']=='NLB017_actual_model_request_v1','exact logical model payload')
   for key in('model','configuration','prompt','tokenizer'):
    descriptor(payload[key]);need(payload[key]==config[key],'selected model descriptor before dispatch '+key);mounted(config[key],'engine_source')
   need(config['result_prefix']+'/RESULT.json'==selected['result_path'],'original selected gateway output root')
   custody.facts['model_gateway_preflight']={'configuration':copy.deepcopy(pin),'stage':stage,'job':job,'source':copy.deepcopy(selected['source']),'operands':{k:copy.deepcopy(config[k])for k in('model','configuration','prompt','tokenizer')},'read_charged_to_original_budget':True}
   budget.admit()
  return super()._invoke(job,stage,role,payload,budget,custody)

class OpenAIProcessModel(ProcessModel):
 def exchange(self,job,stage,messages,seed,budget,remaining_tokens):
  # Base owns the original consumed attempt and exactly-once known/unknown token
  # settlement. A failed provider status with valid usage is still charged first.
  reply,receipt=super().exchange(job,stage,messages,seed,budget,remaining_tokens)
  owner=self.executor.model_attempts[job];o=owner.original
  try:
   pin=owner.original_exchange['provider_response'];reader=Store(self.executor.store.root,budget,owner)
   raw=reader.json(pin,8*2**20);model_spec=reader.json(self.identity,2**20);configuration_spec=reader.json(self.configuration,2**20);names=configuration(configuration_spec,stage)
   u,a,error=response_admission(raw,model_spec,names,100000)
   need(u==owner.original_exchange['usage']and a==reply,'raw provider output and normalized exchange join')
   need(raw['status']=='completed'and raw.get('error')is None and raw.get('incomplete_details')is None and error is None,'provider did not complete valid output; known usage retained')
   need(not raw.get('input_transformations'),'provider changed carried reasoning; no silent history loss')
   for item in raw['output']:
    if item['type']=='message'or(item['type']=='function_call'and'status'in item):need(item.get('status')=='completed','complete provider output item')
   h={'schema':'NLB017_OpenAI_full_output_history_v1','provider_response':pin,'response_id':raw['id'],'output':copy.deepcopy(raw['output']),'output_sha256':digest(bounded_json(raw['output'],8*2**20))}
   budget.admit();return {**reply,'provider_history':h},receipt
  except BaseException as error:
   owner.fail(error,'provider_history_and_completion');o.custody.fail(error,'provider_history_and_completion');budget.stop('invalid original provider completion '+job);owner.raise_if_failed()

def validate_config(c,envelope):
 closed(c,CONFIG_KEYS);need(c['schema']=='NLB017_OpenAI_gateway_config_v1','gateway configuration')
 need(c['job']==envelope['job']and c['source']==envelope['source'],'acyclic selected job/source configuration');relative(c['result_prefix'])
 for k in('source','authority','transport_qualification'):descriptor(c[k])
 
 for k in('model','configuration','prompt','tokenizer'):descriptor(c[k])
 credential_metadata(c['credential']);need(c['transport']==ENDPOINT,'one source-owned endpoint')
 for k in('max_request_bytes','max_response_bytes'):integer(c[k],1,8*2**20)
 integer(c['max_messages'],1,100000);integer(c['max_items'],1,100000);finite(c['timeout_seconds']);need(0<c['timeout_seconds']<=3600,'finite selected transport timeout')
 need(type(c['expected_root_source'])is str and len(c['expected_root_source'])==64,'explicit root source')
 return c

def run_gateway(envelope,config_pin,input_root,output_root,*,stdin_bytes,transport=post_once,credential_reader=read_credential,clock=time.monotonic):
 """One actual gateway body; tests replace only transport/credential effect leaves."""
 c=Custody('openai_gateway');products={};events=[];budget=None;receipts=None;bindings=None;req=None;config=None
 try:
  closed(envelope,{'schema','job','source','io_limits','receipt_limits','deadline','payload'});need(envelope['schema']=='NLB017_executor_worker_envelope_v2','original executor envelope');closed(envelope['io_limits'],Budget.IO_KEYS);receipts=receipt_limits(envelope['receipt_limits'])
  limits=dict.fromkeys(Budget.KEYS,0);limits.update(envelope['io_limits']);budget=Budget(limits,envelope['deadline'],clock=clock,custody=c);integer(stdin_bytes,1,8*2**20+1);budget.charge('read_bytes',stdin_bytes);budget.reserve('read_bytes',stdin_bytes)
  bindings={'schema':'NLB017_OpenAI_gateway_binding_v1','request_sha256':digest(canonical(envelope['payload'])),'configuration':config_pin}
  req={'job':envelope['job'],'source':envelope['source'],'bindings':bindings}
  reserve=sum(receipts.values());need(limits['write_bytes']>=reserve and limits['created_files']>=3,'complete terminal/result/trace reserve')
  ordinary=dict(limits);ordinary['write_bytes']-=reserve;ordinary['created_files']-=3
  work=Budget(ordinary,budget.deadline,parent=budget,clock=clock,custody=c);inputs=Store(input_root,work,c);outputs=Store(output_root,work,c)
  config=validate_config(inputs.json(config_pin,2**20),envelope);inputs.read(config['source'],16*2**20)
  authority=Authority.from_selected(inputs,config['authority'],config['expected_root_source']);budget.authority=authority;work.authority=authority;authority.check(config['stage'],'model_exchange')
  need(config['transport_qualification']in list(authority.input_pins),'exact live gateway transport selection')
  q=inputs.json(config['transport_qualification']);closed(q,{'schema','source','transport','credential','live_api_authorized','scope'})
  need(q['live_api_authorized'] is True,'explicit boolean live gateway authorization')
  need(q=={'schema':'NLB017_OpenAI_transport_qualification_v1','source':config['source'],'transport':config['transport'],'credential':config['credential'],'live_api_authorized':True,'scope':'model_exchange_only_no_participant_credentials'},'current exact transport/secret authorization')
  model_spec=inputs.json(config['model'],2**20);configuration_spec=inputs.json(config['configuration'],2**20)
  for key in('prompt','tokenizer'):inputs.read(config[key],2**20)
  payload=envelope['payload'];encoded,names=request_body(payload,config,model_spec,configuration_spec)
  products['provider_request']=outputs.write('PROVIDER_REQUEST.json',encoded,config['max_request_bytes'])
  c.facts['gateway_artifacts']=products
  authority.check(config['stage'],'model_exchange');work.admit();key=credential_reader(config['credential'],work,c)
  raw=None;observation=None
  try:raw,observation=transport(encoded,key,config['transport'],config['max_response_bytes'],config['timeout_seconds'],budget.deadline,clock=clock)
  except TransportFailure as error:
   raw=error.raw;observation=error.observation;c.fail(None,'provider_transport',error.owner)
  finally:key=None
  # A failed original HTTP attempt still retains its complete known raw prefix,
  # observations and original failure. Write custody is separate from failure.
  def retain(name,value,cap):
   wc=Custody('gateway_retain:'+name);writer=Store(output_root,work,wc)
   try:return writer.write(name,value,cap)
   finally:c.fail(None,'gateway_retention',wc)
  if raw is not None:products['provider_response']=retain('PROVIDER_RESPONSE.json',raw,config['max_response_bytes']+1)
  if observation is not None:products['transport']=retain('TRANSPORT.json',bounded_json(observation,2**20),2**20)
  c.raise_if_failed();need(raw is not None,'original provider bytes unavailable');body=parse(raw)
  u,a,output_error=response_admission(body,model_spec,names,config['max_items']);c.facts['provider_usage']=u;c.facts['provider_status']=body['status'];c.facts['output_error']=output_error
  # This terminal means completed local transport/accounting, not model success.
  # OpenAIProcessModel authenticates these bytes and refuses failed/incomplete
  # output after the original known usage has been charged exactly once.
  provider={**products['provider_response'],'path':config['result_prefix']+'/'+products['provider_response']['path']}
  exchange={'schema':'NLB017_actual_model_exchange_v1','request_sha256':digest(canonical(payload)),'model':payload['model'],'configuration':payload['configuration'],'tokenizer':payload['tokenizer'],'provider_response':provider,'usage':u,'assistant':a}
  products['exchange']=outputs.write('EXCHANGE.json',bounded_json(exchange,8*2**20),8*2**20)
  events.append({'kind':'original_provider_exchange','provider_status':body['status'],'provider_usage':u,'output_error':output_error,'agent_seed_recorded_only':payload['seed'],'application_transport':observation})
  authority.check(config['stage'],'model_exchange');work.admit();c.complete=True
 except BaseException as error:c.capture(error,'gateway_execution')
 finally:
  if req is not None and budget is not None and receipts is not None:
   c.facts['gateway_artifacts']=products
   publish_worker(req,products,events,c,budget,output_root,receipts)
 c.raise_if_failed();return {'products':products,'custody':c,'budget':budget}

def gateway_job(*,job,stage,source,config_pin,sandbox,stream_limit,max_product_bytes,process_limit,parent_group,result_path,worker_io_limits,completion_io_limits,worker_receipt_limits,python_executable):
 """Pure source-owned builder. Inputs, qualification and resource sizes explicit."""
 for p in(source,config_pin):descriptor(p)
 need(stage in('S01','S08','S09','S15'),'closed selected model stage');relative(result_path);need(result_path.endswith('/RESULT.json'),'fixed gateway result name');integer(stream_limit,1);integer(max_product_bytes,1);integer(process_limit,1)
 need(type(python_executable)is str and python_executable.startswith('/')and '\0'not in python_executable,'explicit guest interpreter')
 closed(sandbox,BASE_KEYS|{'gateway_transport'});need(sandbox['runtime_profile']=='model_gateway','model gateway profile');selected_transport(sandbox['gateway_transport'])
 need(sandbox['runtime_environment'].get('PYTHONPATH')=='/programme','gateway authenticated module import path')
 needed={'gateway_config':config_pin};config_matches=[m for m in sandbox['mounts']if m['role']=='gateway_config']
 need(len(config_matches)==1 and config_matches[0]['guest']=='/inputs/'+config_pin['path'],'exact mounted gateway config')
 pins=[]
 for m in sandbox['mounts']:
  if m['manifest']not in pins:pins.append(copy.deepcopy(m['manifest']))
 for k in Budget.IO_KEYS:integer(worker_io_limits[k]);integer(completion_io_limits[k])
 closed(worker_io_limits,Budget.IO_KEYS);closed(completion_io_limits,Budget.IO_KEYS);receipt_limits(worker_receipt_limits)
 need(worker_io_limits['created_files']>=7,'complete gateway creates four products plus trace/result/terminal')
 argv=[python_executable,'-B','-m','nlb.openai_gateway','--config','/inputs/'+config_pin['path'],'--config-bytes',str(config_pin['bytes']),'--config-sha256',config_pin['sha256']]
 return {'stage':stage,'role':'model_exchange','source':copy.deepcopy(source),'input_manifests':pins,'argv':argv,'sandbox':copy.deepcopy(sandbox),'stream_limit':stream_limit,'max_product_bytes':max_product_bytes,'process_limit':process_limit,'parent_group':parent_group,'result_path':result_path,'worker_io_limits':dict(worker_io_limits),'completion_io_limits':dict(completion_io_limits),'worker_receipt_limits':dict(worker_receipt_limits)}

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--config',required=True);parser.add_argument('--config-bytes',required=True,type=int);parser.add_argument('--config-sha256',required=True);a=parser.parse_args()
 need(a.config.startswith('/inputs/'),'exact configuration mount');pin={'path':a.config[len('/inputs/'):],'bytes':a.config_bytes,'sha256':a.config_sha256};descriptor(pin)
 raw=sys.stdin.buffer.readline(8*2**20+1);need(len(raw)<=8*2**20 and raw.endswith(b'\n'),'bounded original model envelope');need(sys.stdin.buffer.read(1)==b'','exact original model EOF')
 run_gateway(parse(raw),pin,'/inputs','/output',stdin_bytes=len(raw));return 0

if __name__=='__main__':main()
