"""One-request local IPC consumer for an already issued live operator context.

The deployment issuer is a native qualification dependency. This service never
creates an authority from the incoming JSON, a copied receipt or matching pins.
No service is started during ordinary source construction.
"""
import socket,struct
from .core import *
from .runner import execute_one
from .scoring import reproduction
from .sandbox import QualifiedHost
from .lifecycle import Custody,failure_snapshot
from .completion import CompletionSlot
MAX=262144
def receive(connection,cap=MAX):
 head=b""
 while len(head)<8:
  b=connection.recv(8-len(head));need(bool(b),"closed frame header");head+=b
 n=struct.unpack("!Q",head)[0];need(0<n<=cap,"bounded IPC frame");body=b""
 while len(body)<n:
  b=connection.recv(min(65536,n-len(body)));need(bool(b),"closed frame");body+=b
 return body
def send(connection,body):
 need(0<len(body)<=MAX,"bounded reply");connection.sendall(struct.pack("!Q",len(body))+body)
def finish_service_connection(connection,reply,lifecycle):
 """The real service publication/close consumer, also checked with inert leaves."""
 lifecycle.publish('service_wire_reply',lambda:send(connection,encode(reply)))
 lifecycle.attempt('service_socket_close',connection.close)
 reply['failure_custody']=lifecycle.snapshot()
 if lifecycle.first is not None:reply['status']='failed';reply['unknown_native_effects']=True
 reply['completion_cutoff']='after sole wire publication and service socket close; in-memory final owner'
 return reply
def serve_one(connection,owned_request,host,vault,cost,completion):
 first=None;reply=None;incoming={};hosts=list(host) if type(host) is tuple else [host]
 lifecycle=Custody('operator_service');transaction=None
 try:
  need(all(type(h) is QualifiedHost for h in hosts) and len({id(h) for h in hosts})==len(hosts),'distinct actual hosts')
  need(type(completion) is CompletionSlot,'existing operator completion slot, not a receipt dictionary')
  incoming=decode(completion.dispatch)
  need(owned_request['dispatch']==incoming,'selected owned request dispatch')
  transaction=completion.begin(hosts,incoming,lifecycle)
  actual=decode(receive(connection))
  exact(actual,("schema","nonce","request_sha256","source_sha256","operation"),"IPC dispatch")
  need(actual==incoming,"same one-use preselected operator transaction")
  if incoming['operation']=='complete':
   need(len(hosts)==len(vault)==len(cost)==4,'four actual full-programme arms')
   requests=owned_request['runs'];need(len(requests)==4,'full paired programme')
   expected=[('reproduction','paper-data'),('reproduction','paper-data-author'),('improvement','paper-data'),('improvement','paper-data-author')]
   need([(r['design']['kind'],r['condition']) for r in requests]==expected,'fixed four arm denominator')
   for i in (0,2):
    need(requests[i]['design']==requests[i+1]['design'] and requests[i]['common']==requests[i+1]['common'],'paired common scientific support')
   vaults=vault;costs=cost
  else:
   need(incoming['operation'] in ('reproduction','improvement') and len(hosts)==1,'explicit operation')
   requests=[owned_request['run']];vaults=[vault];costs=[cost]
   need(requests[0]['design']['kind']==incoming['operation'],'operation matches scientific design')
  need(all(type(c) is Costs for c in costs),'actual ordinary cost owners')
  records=[]
  for req,h,v,c in zip(requests,hosts,vaults,costs):
   try:
    h.require('IPC_dispatch',incoming['source_sha256'])
    run,body=execute_one(req,h,c)
    if req['design']['kind']=='reproduction':score=reproduction(body,req['design'],run,v)
    else:
     from .improvement import score as improvement_score
     score=improvement_score(body,req['design'],run,v)
    records.append({'operation':req['design']['kind'],'condition':req['condition'],'status':'completed','run_id':run.identifier,
     'result':{'bytes':run.output_bytes,'sha256':run.output_sha256},'score':score,'costs':c.report()})
   except BaseException as exc:
    lifecycle.capture(exc,'arm:'+req['condition']+':'+req['design']['kind'])
    failure=failure_snapshot(exc,'arm_failure',owner=lifecycle)
    if first is None:first=failure
    records.append({'operation':req['design']['kind'],'condition':req['condition'],'status':'failed','first_error':failure,'known_cost_prefix':c.report()})
  reply={'status':'completed' if first is None else 'failed','records':records,'planned_arm_denominator':len(requests)}
 except BaseException as exc:
  lifecycle.capture(exc,'service_body');reply={'status':'failed'}
 # Close all actual owners before any completed reply. Preserve each failure.
 closed_hosts=set()
 for i,h in enumerate(hosts):
  if type(h) is QualifiedHost and id(h) not in closed_hosts:
   closed_hosts.add(id(h));lifecycle.attempt('host_close:'+str(i),h.close)
 selected_costs=list(cost) if type(cost) in (tuple,list) else [cost]
 ok,final_costs=lifecycle.attempt('final_known_cost_prefix',lambda:[c.report() for c in selected_costs if type(c) is Costs])
 reply['final_known_costs']=final_costs if ok else None
 reply['native_consumption']='UNKNOWN unless independently retained by the original live issuer; these are ordinary logical prefixes'
 if lifecycle.first is not None:reply['status']='failed'
 reply.update({k:incoming[k] for k in ('nonce','request_sha256','source_sha256') if k in incoming})
 reply.update({'failure_custody':lifecycle.snapshot(),'qualification_granted':False,'unknown_native_effects':lifecycle.first is not None,
  'completion_cutoff':'provisional wire reply; post-send/socket-close outcome must be consumed from the existing operator completion slot'})
 finish_service_connection(connection,reply,lifecycle)
 if transaction is None:
  lifecycle.raise_first();raise Refusal('no service transaction')
 ok,outcome=lifecycle.attempt('completion_owner_return',lambda:completion.finish(transaction,reply))
 if not ok:lifecycle.raise_first()
 return outcome
def connect(review,dispatch,completion):
 need(type(completion) is CompletionSlot and completion.dispatch==encode(dispatch),'actual preselected post-close completion slot required; JSON wire metadata cannot issue one')
 exact(review,("socket","peer_uid","peer_pid","timeout_seconds","source_sha256","request_sha256","nonce"),"selected live IPC endpoint")
 need(review["source_sha256"]==dispatch["source_sha256"] and review["request_sha256"]==dispatch["request_sha256"] and review["nonce"]==dispatch["nonce"],"review/dispatch exact join")
 path=ordinary(review["socket"]);info=path.lstat()
 import stat,os
 need(stat.S_ISSOCK(info.st_mode) and info.st_uid==review["peer_uid"] and info.st_mode&0o077==0,"operator-owned private socket")
 need(type(review["timeout_seconds"]) in (int,float) and 0<review["timeout_seconds"]<=604800,"finite IPC deadline")
 reply,lifecycle=socket_exchange(review,path,dispatch)
 ok,outcome=lifecycle.attempt('consume_post_close_service_outcome',lambda:completion.take(dispatch,review['timeout_seconds']))
 if ok:
  if outcome.custody.first is not None:
   local=lifecycle;local.attach();lifecycle=Custody('operator_client_joined')
   lifecycle.propagate(outcome.custody,'service_post_publication_tail')
   if local.first is not None:lifecycle.propagate(local,'local_transport_and_close_tail')
   lifecycle.attempted.extend(local.attempted);lifecycle.publications.extend(local.publications)
  try:
   final=decode(outcome.reply)
   need(all(final.get(k)==dispatch[k] for k in ('nonce','source_sha256','request_sha256')),'final actual service identity')
  except BaseException as exc:lifecycle.capture(exc,'final_service_admission');final=None
 else:final=None
 lifecycle.raise_first()
 need(final is not None,'actual terminal outcome required')
 final['client_failure_custody']=lifecycle.snapshot()
 return final
def socket_exchange(review,path,dispatch):
 """Owned socket from creation through connect/send/receive/close, no authority."""
 lifecycle=Custody('operator_client');s=None;reply=None
 try:
  s=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
  s.settimeout(review["timeout_seconds"]);s.connect(str(path))
  # Linux deployment is selected for peer credentials; Mac research host is not
  # silently treated as a qualified execution deployment.
  need(hasattr(socket,"SO_PEERCRED"),"native peer credential support absent")
  pid,uid,gid=struct.unpack("3i",s.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,12))
  need((pid,uid)==(review["peer_pid"],review["peer_uid"]),"actual server process identity")
  send(s,encode(dispatch));reply=decode(receive(s))
  need(all(reply.get(k)==dispatch[k] for k in ("nonce","source_sha256","request_sha256")),"actual operator reply identity")
 except BaseException as exc:lifecycle.capture(exc,'client_socket_body')
 if s is not None:lifecycle.attempt('client_socket_close',s.close)
 return reply,lifecycle
