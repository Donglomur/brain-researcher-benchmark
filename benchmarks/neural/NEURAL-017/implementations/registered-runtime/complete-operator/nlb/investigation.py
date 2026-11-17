"""Fresh real model/tool case loops and shared preparation with no answer reuse."""
from .contracts import need,closed,canonical,digest,parse

class Tools:
 def __init__(self,executor,store,policy,context):
  self.executor=executor;self.store=store;self.policy=policy;self.context=context;self.events=[];self.prediction=None;self.serial=0
 def call(self,call,budget):
  closed(call,{'id','name','arguments'});need(type(call['id'])is str and call['name']in self.policy,'actual allowed tool call');self.serial+=1;name=call['name'];a=call['arguments'];result=None
  self.executor.authority.check(self.context['stage']);budget.admit()
  if name=='read_public':
   closed(a,{'member'});need(a['member']in self.context['public_members'],'exact public source member');kind=self.context['public_member_roles'][a['member']];need(kind in('licensed_primary','method_description','schema','tool_API','exposure_disclosure','curated_code_B','source'),'closed public member role')
   if kind=='curated_code_B':need(self.context['binding']['code_view']=='B','paper-only context cannot inspect GitHub code')
   pin=self.context['public_members'][a['member']];raw=self.store.read(pin,128*2**10);result={'source':pin,'utf8':raw.decode('utf-8')}
  elif name=='inspect_state':
   closed(a,{'state'});need(a['state']in self.context['states'],'visible same-context state');result=self.context['states'][a['state']]['public_metadata']
  elif name in('run_python','reference_predict'):
   closed(a,{'source_utf8','state','output_name'}if name=='run_python'else{'reference','state','output_name'})
   need(type(a['output_name'])is str and a['output_name'].isalnum(),'plain declared output');need(a['state']is None or a['state']in self.context['states'],'same frozen state domain')
   if name=='reference_predict':need(a['reference']in self.context['references'],'reference excluded by condition')
   if name=='run_python':
    raw=a['source_utf8'].encode();need(len(raw)<=128*2**10,'source cap');a={**a,'source_sha256':digest(raw)}
   payload={'schema':'NLB017_tool_request_v1','tool':name,'arguments':a,'context':self.context['binding'],'query':self.context['query'],'training':self.context['training'],'state':None if a['state']is None else self.context['states'][a['state']]['source'],'case_index':self.context['case_index']}
   job=self.context['job_prefix']+'/tool-%03d'%self.serial;o=self.executor.invoke(job,self.context['stage'],'participant_tool',payload,budget)
   if o.custody.complete:result=self.executor.product(o)
   else:result={'status':'tool_failed','original':o.public()}
   def stream(raw):
    try:return {'encoding':'utf-8','text':bytes(raw).decode('utf-8')}
    except UnicodeDecodeError:
     import base64
     return {'encoding':'base64','data':base64.b64encode(bytes(raw)).decode('ascii')}
   result={**result,'actual_stdout':stream(o.stdout),'actual_stderr':stream(o.stderr),'original_process':o.persistence.get('process')}
  else:
   need(name=='commit_prediction','tool surface');closed(a,{'product'});need(self.context['case_index']is not None,'preparation cannot submit case answer');need(self.prediction is None,'one irreversible answer');need(a['product']in self.context['produced_predictions'],'answer must originate in this actual case tool chain');self.prediction=a['product'];result={'status':'prediction_committed','product':a['product']}
  raw=canonical(result);need(len(raw)<=128*2**10,'no silent tool observation truncation');event={'call':call,'result':result};self.events.append(event)
  if name in('run_python','reference_predict')and result.get('schema')=='NLB017_worker_result_v1':
   if 'prediction'in result['products']:self.context['produced_predictions'].append(result['products']['prediction'])
   if 'state'in result['products']:
    need(self.context['case_index']is None and a['output_name']not in self.context['states'],'fresh preparation state name');self.context['states'][a['output_name']]={'kind':'participant_numeric_state','reference':None,'source':{'arrays':result['products']['state'],'producer_source':result['products']['actual_source']},'public_metadata':{'numeric_state':result['products']['state'],'actual_source':result['products']['actual_source'],'information_condition':self.context['binding']['condition']},'group_binding':self.context['binding']['group'],'original_process':result['original_process']}
  return result

def investigate(model,tools,initial_messages,context,budget,max_exchanges):
 need(context['mode']=='I'and context['case_index']is not None and context['shared_preparation_frozen'],'fresh I case after shared freeze')
 need(context['prior_case_answers']==[]and context['initial_context_sha256']==digest(canonical(initial_messages)),'no prior answer context')
 messages=[dict(x)for x in initial_messages];history=[];start_tokens=budget.used['model_tokens'];need(max_exchanges>0,'finite model calls')
 for n in range(max_exchanges):
  budget.admit();remaining=3072-(budget.used['model_tokens']-start_tokens);need(remaining>0,'fixed per-case token partition')
  reply,original=model.exchange(context['job_prefix']+'/model-%03d'%n,'S09',messages,context['agent_seed'],budget,remaining);history.append(original);messages.append({'role':'assistant',**reply})
  need(type(reply['tool_calls'])is list,'tool-call array')
  ids=set()
  for call in reply['tool_calls']:
   need(call['id']not in ids,'duplicate model tool ID');ids.add(call['id']);result=tools.call(call,budget);messages.append({'role':'tool','tool_call_id':call['id'],'content':canonical(result).decode()})
  if tools.prediction is not None:return {'prediction':tools.prediction,'messages':messages,'actual_model_exchanges':history,'actual_tools':tools.events,'case_binding':context,'tokens':budget.used['model_tokens']-start_tokens}
 raise ValueError('incomplete investigation: no prediction within original finite envelope')

def prepare(model,tools,initial_messages,context,budget,max_exchanges):
 need(context['mode']=='I'and context['case_index']is None,'shared preparation only');messages=[dict(x)for x in initial_messages];history=[];start=budget.used['model_tokens']
 for n in range(max_exchanges):
  budget.admit()
  remaining=333824-(budget.used['model_tokens']-start);need(remaining>0,'fixed shared token partition')
  reply,original=model.exchange(context['job_prefix']+'/model-%03d'%n,'S08',messages,context['agent_seed'],budget,remaining);history.append(original);messages.append({'role':'assistant',**reply})
  if not reply['tool_calls']:
   return {'schema':'NLB017_shared_preparation_v1','policy':reply['content'],'visible_states':tools.context['states'],'messages':messages,'actual_model_exchanges':history,'actual_tools':tools.events,'frozen':True,'case_answers':[]}
  for call in reply['tool_calls']:
   need(call['name']!='commit_prediction','preparation cannot submit future answer');result=tools.call(call,budget);messages.append({'role':'tool','tool_call_id':call['id'],'content':canonical(result).decode()})
 raise ValueError('shared preparation did not freeze within original envelope')
