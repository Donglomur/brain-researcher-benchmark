"""Exact original pre-exposure F authoring consumer, never a fabricated author.

The chosen service and independent reviewer produce these external records.
This consumer authenticates original exchanges/source/costs and joins them once;
it cannot create a model response, authoring receipt or qualification.
"""
import math,time
from .contracts import need,closed,descriptor,canonical,digest,parse,finite,integer,Budget

def terminal(store,pin,source,seen):
 descriptor(pin);need(pin['sha256']not in seen,'original authoring process cannot be reused');seen.add(pin['sha256'])
 t=store.json(pin,8*2**20)
 need(t['request']['source']==source and t['dispatched']and t['reaped']and t['exit_code']==0 and t['absence']is True and all(t['stream_eof'].values()),'actual original authoring process')
 need(t['terminal']['complete']is True and t['terminal']['first_error']is None,'complete original authoring custody')
 finite(t['started']);finite(t['ended']);need(t['started']<=t['ended'],'original authoring process clock')
 finite(t['costs']['cpu_seconds']);need(t['costs']['cpu_seconds']>=0,'known actual authoring CPU')
 w=t['costs']['worker_io'];closed(w,{'limits','used','reserved'})
 for field in w:
  closed(w[field],Budget.IO_KEYS)
  for value in w[field].values():integer(value)
 need(all(max(w['used'][k],w['reserved'][k])<=w['limits'][k]for k in Budget.IO_KEYS),'complete bounded original worker counters')
 for field in('stdin','stdout','stderr'):
  raw=store.read(t['persistence'][field],8*2**20)
  observed=t['request']['stdin']if field=='stdin'else t[field]
  need(observed=={'bytes':len(raw),'sha256':digest(raw)},'original complete authoring stream')
 return t

def consume(store,authority,selection,expected,budget,seen):
 """Run at S01 before S04 and all empirical exposure, under the original clock."""
 closed(selection,{'record','review','plan','clock_identity'})
 for pin in selection.values():descriptor(pin);need(pin in list(authority.input_pins),'exact current original F authoring input')
 key=selection['record']['sha256'];need(key not in seen,'one consumed original F authoring record');seen.add(key)
 try:return _consume(store,selection,expected,budget,seen)
 except BaseException as original:
  store.custody.fail(original,'F_authoring_admission');budget.stop('unresolved original F authoring '+expected['group']);raise

def _consume(store,selection,expected,budget,seen):
 d=store.json(selection['record'],16*2**20)
 # Strong caller custody retains the original before any later validation fails.
 store.custody.original_F_authoring_record=d
 store.custody.facts['original_F_authoring_record_source']=selection['record']
 closed(d,{'schema','group','plan','clock_identity','captured_source','model_exchanges','engineering_feedback','original_terminal','resource_snapshot','original_started','original_deadline','source_producer'})
 need(d['schema']=='NLB017_original_F_authoring_v1'and d['group']==expected['group']and d['plan']==selection['plan']and d['clock_identity']==selection['clock_identity'],'exact original F authoring identity')
 need(d['captured_source']==expected['captured_source'],'same immutable submitted programme')
 clock=store.json(selection['clock_identity'],2**20)
 closed(clock,{'schema','monotonic_domain','current_operator_source','independent_currentness_review'})
 need(clock['schema']=='NLB017_current_authoring_clock_domain_v1'and clock['monotonic_domain']==expected['monotonic_domain']and clock['current_operator_source']==expected['root_source'],'same independently qualified current monotonic clock domain')
 store.read(clock['independent_currentness_review'],2**20)
 finite(d['original_started']);finite(d['original_deadline'])
 need(d['original_started']==expected['original_started']and d['original_deadline']==expected['original_deadline'],'no renewed authoring clock')
 need(0<d['original_started']<=time.monotonic()<d['original_deadline']<=d['original_started']+172800,'original full F wall envelope continues')
 need(budget.deadline<=d['original_deadline'],'consumer and execution inside original deadline')
 plan=store.json(selection['plan'],4*2**20)
 closed(plan,{'schema','group','seed','model','configuration','prompt','tokenizer','runtime','service_qualification','code_view','public_context','feedback_policy','clock_identity','created_before_activity'})
 need(plan['schema']=='NLB017_pre_exposure_F_authoring_plan_v1'and plan['group']==expected['group']and plan['seed']==expected['seed']and plan['code_view']==expected['code_view']and plan['public_context']==expected['public_context']and plan['clock_identity']==selection['clock_identity']and plan['created_before_activity']is True,'same pre-exposure F source/context/seed')
 for key in('model','configuration','prompt','tokenizer'):need(plan[key]==expected[key],'same selected model authoring '+key)
 for key in('runtime','service_qualification'):
  need(plan[key]==expected[key],'same actual selected F/I runtime/service');store.read(plan[key],8*2**20)
 need(plan['feedback_policy']=='source_syntax_static_schema_only_no_empirical_execution','closed training-independent engineering feedback')
 review=store.json(selection['review'],4*2**20)
 closed(review,{'schema','record','plan','captured_source','reviewer','verdict','unresolved','pre_activity_and_full_context_verified','complete_original_usage_through_publication_verified','clock_domain_verified'})
 need(review['schema']=='NLB017_independent_original_F_authoring_review_v1'and review['record']==selection['record']and review['plan']==selection['plan']and review['captured_source']==d['captured_source'],'independent review binds exact original authoring')
 need(type(review['reviewer'])is str and review['reviewer'].strip()and review['verdict']=='accepted'and review['unresolved']==[]and all(review[k]is True for k in('pre_activity_and_full_context_verified','complete_original_usage_through_publication_verified','clock_domain_verified')),'actual independent complete authoring review required')
 descriptor(d['source_producer']);store.read(d['source_producer'],16*2**20)
 need(type(d['model_exchanges'])is list and 1<=len(d['model_exchanges'])<=1024,'finite actual original authoring exchanges')
 cpu=0.0;tokens=0;lower=dict.fromkeys(Budget.IO_KEYS,0);process_pins=[];last=None
 for i,row in enumerate(d['model_exchanges']):
  closed(row,{'index','request','exchange','process','worker_result'});need(row['index']==i,'complete ordered original authoring exchange sequence')
  t=terminal(store,row['process'],d['source_producer'],seen);process_pins.append(row['process'])
  need(d['original_started']<=t['started']<=t['ended']<=d['original_deadline'],'exchange inside original F clock')
  request_raw=store.read(row['request'],8*2**20);request=parse(request_raw)
  stdin=parse(store.read(t['persistence']['stdin'],8*2**20))
  need(stdin['payload']==request and stdin['job']==t['job']and stdin['source']==d['source_producer'],'actual captured original model request')
  closed(request,{'schema','model','configuration','prompt','tokenizer','seed','messages','max_remaining_total_tokens'})
  need(request['schema']=='NLB017_actual_model_request_v1'and request['seed']==expected['seed'],'same original F model seed')
  for key in('model','configuration','prompt','tokenizer'):need(request[key]==plan[key],'actual exchange selected '+key)
  need(type(request['messages'])is list and request['messages'],'complete actual original authoring context')
  body=store.json(row['exchange'],8*2**20)
  closed(body,{'schema','request_sha256','model','configuration','tokenizer','provider_response','usage','assistant'})
  need(body['schema']=='NLB017_actual_model_exchange_v1'and body['request_sha256']==digest(canonical(request)),'original provider roundtrip identity')
  for key in('model','configuration','tokenizer'):need(body[key]==plan[key],'same original provider '+key)
  result=store.json(row['worker_result'],8*2**20)
  need(result['job']==t['job']and result['source']==d['source_producer'],'original authoring result producer')
  prefix=row['worker_result']['path'].rsplit('/',1)[0]
  need({**result['products']['exchange'],'path':prefix+'/'+result['products']['exchange']['path']}==row['exchange'],'exchange from actual original worker product')
  store.read(body['provider_response'],8*2**20)
  u=body['usage'];closed(u,{'input_tokens','output_tokens','total_tokens','status','reasoning_tokens','cached_input_tokens','unknown_token_classes'})
  need(u['status']=='provider_reported'and u['unknown_token_classes']==[],'no unknown authoring usage')
  for k in('input_tokens','output_tokens','total_tokens','reasoning_tokens','cached_input_tokens'):integer(u[k])
  need(u['total_tokens']==u['input_tokens']+u['output_tokens']and u['reasoning_tokens']<=u['output_tokens']and u['cached_input_tokens']<=u['input_tokens'],'complete original token classes')
  tokens+=u['total_tokens'];cpu+=t['costs']['cpu_seconds']
  for k in lower:lower[k]+=t['costs']['worker_io']['used'][k]
  closed(body['assistant'],{'content','tool_calls'});last=body['assistant']
 need(type(d['engineering_feedback'])is list and len(d['engineering_feedback'])<=1024,'finite original feedback census')
 for row in d['engineering_feedback']:
  closed(row,{'kind','process','source'});need(row['kind']in('source_syntax','source_static','schema_only'),'no empirical F-authoring feedback')
  t=terminal(store,row['process'],row['source'],seen);process_pins.append(row['process']);store.read(row['source'],16*2**20)
  need(d['original_started']<=t['started']<=t['ended']<=d['original_deadline'],'feedback inside same original clock')
  cpu+=t['costs']['cpu_seconds']
  for k in lower:lower[k]+=t['costs']['worker_io']['used'][k]
 captured=store.read(d['captured_source'],128*2**10)
 need(last['tool_calls']==[]and type(last['content'])is str and last['content'].encode()==captured,'actual final model response equals complete captured F Python source')
 original=store.json(d['original_terminal'],8*2**20)
 closed(original,{'schema','group','plan','captured_source','processes','original_started','original_deadline','resources','complete','first_error','unresolved','closed_before_empirical_activity'})
 need(original['schema']=='NLB017_original_F_authoring_terminal_v1'and original['group']==d['group']and original['plan']==d['plan']and original['captured_source']==d['captured_source']and original['processes']==process_pins,'original complete authoring terminal census')
 need(original['complete']is True and original['first_error']is None and original['unresolved']==[]and original['closed_before_empirical_activity']is True,'original F authoring closed before data')
 need(original['original_started']==d['original_started']and original['original_deadline']==d['original_deadline']and original['resources']==d['resource_snapshot'],'same original counters and clock')
 snapshot=d['resource_snapshot'];closed(snapshot,{'limits','used','reserved','held','deadline','stops','child_accounting','unknown_is_not_zero'})
 need(snapshot['limits']==budget.limits and snapshot['deadline']==d['original_deadline']and snapshot['stops']==[]and snapshot['unknown_is_not_zero']is True,'same original full matched F budget')
 for field in('limits','used','reserved','held'):
  closed(snapshot[field],Budget.KEYS)
  for k,v in snapshot[field].items():finite(v);need(v>=0,'known original nonnegative usage');integer(v)if k!='cpu_seconds'else None
 need(all(snapshot['held'][k]==0 and max(snapshot['used'][k],snapshot['reserved'][k])<=snapshot['limits'][k]for k in Budget.KEYS),'no unjoined or exceeded authoring resource')
 need(snapshot['child_accounting']['unknown_or_unresolved']==0 and snapshot['child_accounting']['allocated']==snapshot['child_accounting']['joined']==len(process_pins),'all original authoring processes joined')
 need(math.isclose(snapshot['used']['cpu_seconds'],cpu,rel_tol=1e-12,abs_tol=1e-9)and snapshot['used']['model_tokens']==tokens,'actual original CPU/token sum')
 need(all(snapshot['used'][k]>=lower[k]for k in lower)and snapshot['used']['tool_calls']==len(process_pins),'original usage includes all worker costs and complete invocation census')
 # Record the exact admitted observation before charging. Any later excess
 # stops the original pool; it can never be rejoined or retried as a new budget.
 store.custody.facts['admitted_original_F_usage']=snapshot
 for k in Budget.KEYS:budget.reserve(k,snapshot['reserved'][k]);budget.charge(k,snapshot['used'][k])
 budget.admit()
 return {'schema':'NLB017_F_authoring_join_v1','group':d['group'],'selection':selection,'captured_source':d['captured_source'],'original_terminal':d['original_terminal'],'original_processes':process_pins,'original_usage':snapshot,'consumed_once':True,'actual_model_source_bytes_bound':True,'budget_after_join':budget.snapshot()}
