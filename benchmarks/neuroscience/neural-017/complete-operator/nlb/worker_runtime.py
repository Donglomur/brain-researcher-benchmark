"""Shared finite worker protocol and original post-publication accounting.

Counters describe instrumented Store I/O, not physical kernel I/O. CPU/streams
and containment remain original supervisor observations, never worker assertions.
"""
import sys
from .contracts import Budget,Custody,Store,canonical,parse,closed,need,integer,digest

RECEIPT_MAX={'trace_bytes':32*2**20,'result_bytes':8*2**20,'terminal_bytes':8*2**20}

def receipt_limits(value):
 closed(value,RECEIPT_MAX)
 for key,maximum in RECEIPT_MAX.items():integer(value[key],1,maximum)
 return value

def io_snapshot(budget):
 return {key:{k:budget.snapshot()[key][k]for k in Budget.IO_KEYS}for key in('limits','used','reserved')}

def projected_terminal(job,source,bindings,custody,budget,maximum):
 """Encode an explicit final-write plan; never mislabel it a prior observation."""
 before=io_snapshot(budget);size=0
 for _ in range(32):
  final={key:dict(value)for key,value in before.items()}
  for key in('used','reserved'):
   final[key]['write_bytes']+=size;final[key]['created_files']+=1
  body={'schema':'NLB017_worker_terminal_v2','job':job,'source':source,'bindings':bindings,
        'terminal':custody.snapshot(),'before_terminal':before,'final_io':final,
        'publication_plan':{'bytes':size,'created_files':1,'successful_exact_write_and_close_required':True},
        'measurement_scope':'instrumented_store_IO; supervisor_owns_CPU_streams_and_native_absence'}
  raw=canonical(body)
  if len(raw)==size:
   need(size<=maximum,'bounded original terminal');return raw,body
  size=len(raw)
 raise ValueError('terminal byte-size fixed point did not converge')

def publish_worker(request,products,events,custody,budget,output_root,limits):
 """Publish RESULT before TERMINAL and validate actual counters afterwards.

Failure receipts use separate writer custody so an original scientific error
cannot prevent successful bounded terminal publication. No exception is erased.
"""
 def write(name,raw,cap):
  publication=Custody('worker_publish:'+name);writer=Store(output_root,budget,publication)
  try:return writer.write(name,raw,cap)
  finally:custody.fail(None,'original_worker_publication',publication)
 try:products['trace']=write('TRACE.json',canonical(events),limits['trace_bytes'])
 except BaseException as e:custody.fail(e,'trace_publication')
 if custody.first_error is None:
  try:write('RESULT.json',canonical({'schema':'NLB017_worker_result_v1','job':request['job'],'source':request['source'],'products':products,'bindings':request['bindings']}),limits['result_bytes'])
  except BaseException as e:custody.fail(e,'result_publication')
 custody.complete=custody.first_error is None
 original_raw=None
 try:
  original_raw,body=projected_terminal(request['job'],request['source'],request['bindings'],custody,budget,limits['terminal_bytes'])
  terminal=write('TERMINAL.json',original_raw,limits['terminal_bytes'])
  need(io_snapshot(budget)==body['final_io'],'actual final publication counters equal explicit original plan')
  custody.receipt=terminal
 except BaseException as e:custody.fail(e,'terminal_publication')
 custody.original_products=products;custody.original_trace=events;custody.original_terminal_bytes=original_raw
 return custody.receipt

def main(execute):
 c=Custody('worker');products={};events=[];request=None;budget=None;output_root=None;receipts=None
 try:
  raw=sys.stdin.buffer.readline(8*2**20+1);need(len(raw)<=8*2**20 and raw.endswith(b'\n'),'bounded single-line original envelope');envelope=parse(raw)
  if envelope['payload']['role']!='participant_F':need(sys.stdin.buffer.read(1)==b'','ordinary request has exact EOF')
  else:need('reference_service'in envelope['payload']['body'],'frozen program has source-owned live interface')
  closed(envelope,{'schema','job','source','io_limits','receipt_limits','deadline','payload'})
  need(envelope['schema']=='NLB017_executor_worker_envelope_v2','source-owned worker envelope');closed(envelope['io_limits'],Budget.IO_KEYS);receipts=receipt_limits(envelope['receipt_limits'])
  limits=dict.fromkeys(Budget.KEYS,0);limits.update(envelope['io_limits']);budget=Budget(limits,envelope['deadline'],custody=c)
  budget.charge('read_bytes',len(raw));budget.reserve('read_bytes',len(raw))
  request=envelope['payload'];need(request['job']==envelope['job']and request['source']==envelope['source'],'same original worker request');output_root=request['output_root']
  reserve=sum(receipts.values());need(limits['write_bytes']>=reserve and limits['created_files']>=3,'preselected terminal/trace/result capacity')
  ordinary=dict(limits);ordinary['write_bytes']-=reserve;ordinary['created_files']-=3
  body_budget=Budget(ordinary,budget.deadline,parent=budget,custody=c)
  inputs=Store(request['input_root'],body_budget,c);outputs=Store(output_root,body_budget,c)
  from .contracts import Authority
  closed(request,{'schema','job','source','role','stage','body','declared_inputs','input_root','output_root','deadline','authority','expected_root_source','bindings'})
  need(request['schema']=='NLB017_worker_request_v2'and request['deadline']==budget.deadline,'exact original worker deadline')
  authority=Authority.from_selected(inputs,request['authority'],request['expected_root_source']);budget.authority=authority;body_budget.authority=authority;authority.check(request['stage'],request['role'])
  for pin in request['declared_inputs']:inputs.read(pin,1024*2**20)
  def trace(event):
   events.append(event);body_budget.guard();need(len(events)<=request['body'].get('max_trace_events',100000),'complete worker trace limit');authority.check(request['stage'],request['role'])
  products=execute(request,inputs,outputs,trace);authority.check(request['stage'],request['role']);budget.guard();c.complete=True
 except BaseException as e:
  c.capture(e,'worker_execution')
 finally:
  if request is not None and budget is not None and output_root is not None and receipts is not None:publish_worker(request,products,events,c,budget,output_root,receipts)
 if c.first_error is not None:raise c.first_error
 return 0

def validate_terminal(raw,job,source,limits,bindings=None):
 d=parse(raw);closed(d,{'schema','job','source','bindings','terminal','before_terminal','final_io','publication_plan','measurement_scope'})
 need(d['schema']=='NLB017_worker_terminal_v2'and d['job']==job and d['source']==source,'original worker terminal identity')
 if bindings is not None:need(d['bindings']==bindings,'original worker terminal ancestry')
 need(d['before_terminal']['limits']==d['final_io']['limits']==limits,'original residual worker allowance')
 plan=d['publication_plan'];need(plan=={'bytes':len(raw),'created_files':1,'successful_exact_write_and_close_required':True},'exact original terminal publication extent')
 for field in('used','reserved'):
  before=d['before_terminal'][field];after=d['final_io'][field];closed(before,Budget.IO_KEYS);closed(after,Budget.IO_KEYS)
  for key in Budget.IO_KEYS:
   integer(before[key]);integer(after[key]);delta=len(raw)if key=='write_bytes'else 1 if key=='created_files'else 0
   need(after[key]==before[key]+delta and after[key]<=limits[key],'complete bounded terminal I/O including publication')
 return d
