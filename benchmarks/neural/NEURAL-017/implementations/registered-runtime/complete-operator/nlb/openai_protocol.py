"""Closed Responses conversion. No credentials, transport or tool execution."""
import copy,re
from .contracts import need,closed,integer,finite,canonical,parse,digest,descriptor

ENDPOINT={'scheme':'https','host':'api.openai.com','port':443,'path':'/v1/responses'}
CONFIG_KEYS={'schema','job','stage','source','result_prefix','model','configuration','prompt','tokenizer','authority','expected_root_source','transport_qualification','transport','credential','max_request_bytes','max_response_bytes','timeout_seconds','max_messages','max_items'}

def bounded_json(value,cap):
 integer(cap,1,8*2**20);active=set();nodes=0
 def size(x,depth):
  nonlocal nodes
  nodes+=1;need(nodes<=cap and depth<=32,'bounded JSON structure')
  if x is None:return 4
  if type(x)is bool:return 5
  if type(x)is int:need(abs(x)<2**63,'bounded JSON integer');return 21
  if type(x)is float:finite(x);return 32
  if type(x)is str:
   need(len(x)<=cap,'bounded JSON string');n=2
   for ch in x:
    v=ord(ch);need(not 0xD800<=v<=0xDFFF,'Unicode scalar')
    n+=2 if ch in('\\','"','\b','\f','\n','\r','\t')else 6 if v<32 else 1 if v<128 else 2 if v<2048 else 3 if v<65536 else 4
    need(n<=cap,'bounded escaped JSON string')
   return n
  need(type(x)in(dict,list),'closed JSON values');need(id(x)not in active,'JSON cycle');active.add(id(x))
  try:
   total=2
   it=x.items()if type(x)is dict else enumerate(x)
   for k,v in it:
    if type(x)is dict:need(type(k)is str,'JSON key');total+=size(k,depth+1)+1
    total+=size(v,depth+1)+1;need(total<=cap,'preventive JSON extent')
   return total
  finally:active.remove(id(x))
 need(size(value,0)+1<=cap,'preventive complete JSON extent');raw=canonical(value);need(len(raw)<=cap,'encoded JSON extent');return raw

def model_identity(value):
 closed(value,{'provider','api','model'});need(value['provider']=='openai'and value['api']=='responses','selected concrete provider')
 name=value['model'];need(type(name)is str and 0<len(name)<=256 and all(32<ord(c)<127 for c in name),'explicit model identity');return name

def _function(name,description,properties):
 return {'type':'function','name':name,'description':description,'parameters':{'type':'object','properties':properties,'required':list(properties),'additionalProperties':False},'strict':True}

INVESTIGATION_TOOLS=[
 _function('read_public','Read one already admitted public source member.',{'member':{'type':'string'}}),
 _function('run_python','Run source through the separately admitted tool process.',{'source_utf8':{'type':'string'},'state':{'type':['string','null']},'output_name':{'type':'string'}}),
 _function('reference_predict','Use one admitted reference through the separate tool process.',{'reference':{'type':'string'},'state':{'type':['string','null']},'output_name':{'type':'string'}}),
 _function('inspect_state','Inspect only an already visible same-context state.',{'state':{'type':'string'}}),
 _function('commit_prediction','Commit a prediction already produced by this case tool chain.',{'product':{'type':'object','properties':{'path':{'type':'string'},'bytes':{'type':'integer','minimum':0},'sha256':{'type':'string','pattern':'^[0-9a-f]{64}$'}},'required':['path','bytes','sha256'],'additionalProperties':False}}),
]

def _stages():
 return {'S01':{'tools':[],'tool_choice':'none'},'S15':{'tools':[],'tool_choice':'none'},'S08':{'tools':copy.deepcopy(INVESTIGATION_TOOLS[:-1]),'tool_choice':'auto'},'S09':{'tools':copy.deepcopy(INVESTIGATION_TOOLS),'tool_choice':'auto'}}

def configuration_document(parameters,parallel_tool_calls):
 value={'schema':'NLB017_OpenAI_Responses_configuration_v2','parameters':copy.deepcopy(parameters),'stage_tools':_stages(),'parallel_tool_calls':parallel_tool_calls,'seed_policy':'record_only_no_provider_seed'}
 configuration(value,'S01');return value

def configuration(value,stage):
 closed(value,{'schema','parameters','stage_tools','parallel_tool_calls','seed_policy'})
 need(value['schema']=='NLB017_OpenAI_Responses_configuration_v2'and value['seed_policy']=='record_only_no_provider_seed','explicit Responses configuration/seed semantics')
 p=value['parameters'];need(type(p)is dict and set(p)<={'max_output_tokens','temperature','top_p','reasoning','text'}and'max_output_tokens'in p,'closed selected request parameters');integer(p['max_output_tokens'],1,2**31-1)
 for k,hi in [('temperature',2),('top_p',1)]:
  if k in p:finite(p[k]);need(0<=p[k]<=hi,'request parameter range')
 if 'reasoning'in p:
  need(type(p['reasoning'])is dict and set(p['reasoning'])<={'effort','summary','mode','context'},'explicit reasoning parameters')
  need(all(type(v)is str and 0<len(v)<=64 for v in p['reasoning'].values()),'reasoning parameter text')
 if 'text'in p:
  closed(p['text'],{'format'});closed(p['text']['format'],{'type'});need(p['text']['format']['type']=='text','plain text response only')
 need(type(value['parallel_tool_calls'])is bool,'explicit parallel-call setting')
 need(value['stage_tools']==_stages()and stage in value['stage_tools'],'one immutable exact stage tool table')
 # The table is source-owned from the actual Tools.call schema, not arbitrary
 # server tools or a hidden tool implementation. Every real call stays external.
 return {t['name']for t in value['stage_tools'][stage]['tools']}

def usage(raw):
 need(type(raw)is dict and type(raw.get('usage'))is dict,'provider usage unavailable')
 u=raw['usage'];closed(u,{'input_tokens','output_tokens','total_tokens','input_tokens_details','output_tokens_details'})
 for k in('input_tokens','output_tokens','total_tokens'):integer(u[k])
 i=u['input_tokens_details'];o=u['output_tokens_details'];need(type(i)is dict and set(i)in({'cached_tokens'},{'cached_tokens','cache_write_tokens'}),'unknown/missing input token classes');closed(o,{'reasoning_tokens'})
 for k,v in i.items():integer(v);need(v<=u['input_tokens'],'input detail subset')
 integer(o['reasoning_tokens']);need(o['reasoning_tokens']<=u['output_tokens']and u['total_tokens']==u['input_tokens']+u['output_tokens'],'actual usage arithmetic')
 return {'input_tokens':u['input_tokens'],'output_tokens':u['output_tokens'],'total_tokens':u['total_tokens'],'status':'provider_reported','reasoning_tokens':o['reasoning_tokens'],'cached_input_tokens':i['cached_tokens'],'unknown_token_classes':[]}

def normalize_output(items,names,max_items):
 need(type(items)is list and len(items)<=max_items,'complete bounded provider output');texts=[];calls=[];ids=set()
 for item in items:
  need(type(item)is dict,'provider output item');kind=item.get('type')
  if kind!='function_call'or'id'in item:
   need(type(item.get('id'))is str and item['id']not in ids,'unique complete provider item');ids.add(item['id'])
  if kind=='reasoning':
   need(type(item.get('encrypted_content'))is str and item['encrypted_content'],'stateless reasoning requires complete encrypted item')
  elif kind=='message':
   need(item.get('role')=='assistant'and item.get('status')in('completed','incomplete','in_progress')and type(item.get('content'))is list,'assistant message item')
   for c in item['content']:
    need(type(c)is dict and c.get('type')in('output_text','refusal'),'unsupported assistant content')
    if c['type']=='refusal':need(type(c.get('refusal'))is str,'provider refusal text');raise ValueError('provider refused; original response retained')
    need(type(c.get('text'))is str,'exact output text');texts.append(c['text'])
  elif kind=='function_call':
   need(item.get('async',False)is False and item.get('caller')in(None,{'type':'direct'})and item.get('namespace')is None,'direct synchronous selected function call only')
   need(item.get('name')in names and type(item.get('call_id'))is str and item['call_id']and type(item.get('arguments'))is str,'selected function call')
   need(item['call_id']not in {c['id']for c in calls},'unique call ID');a=parse(item['arguments'].encode());need(type(a)is dict,'function arguments object')
   calls.append({'id':item['call_id'],'name':item['name'],'arguments':a})
  else:raise ValueError('unsupported provider item; no hidden server tool execution')
 return {'content':''.join(texts),'tool_calls':calls}

def assistant_message(reply):
 closed(reply,{'content','tool_calls','provider_history'});return {'role':'assistant',**copy.deepcopy(reply)}

def input_content(value,role,max_items):
 if type(value)is str:return
 need(role=='user'and type(value)is list and 1<=len(value)<=max_items,'explicit user content blocks')
 for block in value:
  need(type(block)is dict,'content block')
  if block.get('type')=='input_text':
   closed(block,{'type','text'});need(type(block['text'])is str,'exact text block')
  else:
   closed(block,{'type','filename','file_data'});need(block['type']=='input_file','only exact inline PDF source')
   name=block['filename'];need(type(name)is str and re.fullmatch(r'[A-Za-z0-9_.-]{1,128}',name)and name.lower().endswith('.pdf'),'plain PDF filename')
   data=block['file_data'];prefix='data:application/pdf;base64,';need(type(data)is str and data.startswith(prefix),'inline PDF data only; no external file ID/URL')
   body=data[len(prefix):];need(body and len(body)%4==0 and len(body)-len(body.rstrip('='))<=2,'exact base64 framing')
   need(all(ch in 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/' for ch in body.rstrip('=')),'exact base64 alphabet')

def request_body(payload,config,model_spec,configuration_spec):
 closed(payload,{'schema','model','configuration','prompt','tokenizer','seed','messages','max_remaining_total_tokens'})
 need(payload['schema']=='NLB017_actual_model_request_v1','original model request');integer(payload['seed']);integer(payload['max_remaining_total_tokens'],1)
 for key in('model','configuration','prompt','tokenizer'):need(payload[key]==config[key],'exact selected model operand '+key)
 name=model_identity(model_spec);names=configuration(configuration_spec,config['stage']);messages=payload['messages'];need(type(messages)is list and 1<=len(messages)<=config['max_messages'],'complete finite message history')
 items=[];outstanding=set();seen_calls=set()
 for m in messages:
  need(type(m)is dict and m.get('role')in('system','developer','user','assistant','tool'),'closed message role')
  if m['role']in('system','developer','user'):
   closed(m,{'role','content'});need(not outstanding,'text after complete tool outputs');input_content(m['content'],m['role'],config['max_items']);items.append(copy.deepcopy(m))
  elif m['role']=='assistant':
   closed(m,{'role','content','tool_calls','provider_history'});need(not outstanding,'previous tool calls must close before next assistant')
   h=m['provider_history'];closed(h,{'schema','provider_response','response_id','output','output_sha256'});descriptor(h['provider_response']);need(h['schema']=='NLB017_OpenAI_full_output_history_v1'and type(h['response_id'])is str,'source-owned full output history')
   need(digest(bounded_json(h['output'],config['max_response_bytes']))==h['output_sha256'],'complete history item bytes');a=normalize_output(h['output'],names,config['max_items']);need(a=={'content':m['content'],'tool_calls':m['tool_calls']},'history normalized/raw agreement')
   for call in a['tool_calls']:need(call['id']not in seen_calls,'global call identity');seen_calls.add(call['id']);outstanding.add(call['id'])
   items.extend(copy.deepcopy(h['output']))
  else:
   closed(m,{'role','tool_call_id','content'});need(m['tool_call_id']in outstanding and type(m['content'])is str,'exact pending function output');outstanding.remove(m['tool_call_id']);items.append({'type':'function_call_output','call_id':m['tool_call_id'],'output':m['content']})
  need(len(items)<=config['max_items'],'complete carried item cap')
 need(not outstanding,'all preceding function outputs required')
 p=copy.deepcopy(configuration_spec['parameters']);p['max_output_tokens']=min(p['max_output_tokens'],payload['max_remaining_total_tokens'])
 body={'model':name,'input':items,'store':False,'stream':False,'include':['reasoning.encrypted_content'],'truncation':'disabled','tools':copy.deepcopy(configuration_spec['stage_tools'][config['stage']]['tools']),'tool_choice':configuration_spec['stage_tools'][config['stage']]['tool_choice'],'parallel_tool_calls':configuration_spec['parallel_tool_calls'],**p}
 return bounded_json(body,config['max_request_bytes']),names

def response_admission(raw,model_spec,names,max_items):
 need(type(raw)is dict and raw.get('object')=='response'and type(raw.get('id'))is str,'actual Responses object')
 need(raw.get('model')==model_identity(model_spec),'returned exact selected model; no alias guessing')
 need(raw.get('status')in('completed','incomplete','failed','cancelled'),'terminal provider status')
 u=usage(raw)
 # Keep known usage even when a later output/status validation fails.
 try:a=normalize_output(raw.get('output'),names,max_items);error=None
 except BaseException as e:a={'content':'','tool_calls':[]};error=type(e).__name__
 return u,a,error
