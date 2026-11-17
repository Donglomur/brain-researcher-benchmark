"""Protected current-request rendezvous; external publishers own all facts.

No signer, scientific result producer or credential store. Failed nonsecret
framing is retained privately, while secret replies never enter the journal.
"""
import os,socket,stat,struct,time
from pathlib import Path
from central_io import need,encoded,parse,pin,cleanup_note
ROLE_KINDS={'operator':('operator_seed','global_commitment','input_admission','context_exposure','target_release','reconstruction_tolerances','study_scientific_qualification'),
 'environment':('runtime_profile',),'observer':('operation_closure','operator_phase_closure','study_closure'),
 'provider':('provider_credential',),'human_review':('human_reviews',)}
def peer(sock,expected):
 need(hasattr(socket,'SO_PEERCRED'),'Full Linux peer identity required');pid,uid,gid=struct.unpack('3i',sock.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,12))
 need(pid==expected['pid']and uid==expected['uid'],'Exact independently selected rendezvous peer')
def receive(sock,n,io,end,capture=None):
 parts=[];left=n
 while left:
  io.tick();need(time.monotonic()<end,'Original rendezvous clock');wanted=min(left,65536);io.reads+=wanted;need(io.reads<=io.read_cap,'Complete precharged rendezvous input')
  sock.settimeout(end-time.monotonic());raw=sock.recv(wanted);need(raw,'Complete framed rendezvous input');parts.append(raw);left-=len(raw)
  if capture is not None:capture.append(raw)
 return b''.join(parts)
def framed(sock,io,cap,end,capture=None):
 n=struct.unpack('!Q',receive(sock,8,io,end,capture))[0];need(n<=cap,'Extent before protected reply allocation');return receive(sock,n,io,end,capture)
def send(sock,raw,io,end):
 io.tick();io.writes+=len(raw)+8;need(io.writes<=io.write_cap and time.monotonic()<end,'Whole protected response allocation/cutoff');sock.settimeout(end-time.monotonic());sock.sendall(struct.pack('!Q',len(raw))+raw);io.tick()
def attempt(actions,primary=None):
 first=primary
 for label,fn in actions:
  try:fn()
  except BaseException as extra:
   if first is None:first=extra
   else:cleanup_note(first,label,extra)
 return first
def cleanup(actions,primary=None):
 first=attempt(actions,primary)
 if primary is None and first is not None:raise first

def failure_metadata(error,stage,sequence,secret,io):
 return {'schema':'neural004_authority_phase_failure_v1','stage':stage,'sequence':sequence,'error_type':type(error).__name__,
  'secret_reply_unretained':secret,'cleanup_errors':[{'action':x.get('action'),'type':x.get('type')}for x in getattr(error,'cleanup_errors',[])],
  'no_fact_or_signature_produced':True,
  'logical_costs_before_this_failure_publication':io.snapshot(),'physical_completion_known':False}

def serve(selection,io):
 need(set(selection)=={'schema','selected','role','source_pin','run_id','authority_selection_pin','controller_endpoint','publisher_endpoint','controller_peer','publisher_peer','max_message_bytes','max_requests','journal_root','original_clock'},'Exact independently installed rendezvous policy')
 need(selection['schema']=='neural004_authority_rendezvous_v1'and selection['selected']is True and selection['role']in ROLE_KINDS,'No shipped actual service deployment')
 need(selection['controller_endpoint']!=selection['publisher_endpoint']and selection['controller_peer']['pid']!=selection['publisher_peer']['pid'],'Separate protected request/publisher processes')
 for k in ('max_message_bytes','max_requests'):need(type(selection[k])is int and selection[k]>0,'Finite exact rendezvous bounds')
 clock=selection['original_clock'];need(io.origin==clock['origin_ns']/1e9 and io.end<=clock['outer_ns']/1e9,'Original inherited service interval')
 listeners=[];owned=[];primary=None;last_sequence=0;stage='listener_setup';journal=Path(selection['journal_root'])
 def remove_owned(path,identity):
  try:now=os.stat(path,follow_symlinks=False)
  except FileNotFoundError:return
  need(stat.S_ISSOCK(now.st_mode)and (now.st_dev,now.st_ino)==identity,'Never unlink a replaced rendezvous socket');os.unlink(path)
 try:
  for key in ('controller_endpoint','publisher_endpoint'):
   path=Path(selection[key]);need(path.is_absolute()and not os.path.lexists(path)and not any(p.is_symlink()for p in path.parents),'Fresh exact protected socket')
   sock=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);listeners.append(sock);sock.bind(str(path))
   st=os.stat(path,follow_symlinks=False);owned.append((path,(st.st_dev,st.st_ino)));os.chmod(path,0o600);sock.listen(1)
  for ordinal in range(selection['max_requests']):
   stage='controller_accept';io.tick();listeners[0].settimeout(io.end-time.monotonic());client,_address=listeners[0].accept();publisher=None;current=None
   request_chunks=[];publisher_chunks=[];secret=None
   try:
    stage='controller_request';peer(client,selection['controller_peer']);request_raw=framed(client,io,selection['max_message_bytes'],io.end,request_chunks);request=parse(request_raw)
    need(set(request)=={'schema','sequence','role','kind','source_pin','run_id','subject','authority_selection_pin','clock'},'Exact original authority request')
    need(request['schema']=='neural004_incremental_request_v1'and request['role']==selection['role']and request['kind']in ROLE_KINDS[selection['role']]and
     request['source_pin']==selection['source_pin']and request['run_id']==selection['run_id']and request['authority_selection_pin']==selection['authority_selection_pin']and request['clock']==clock,'Current independently selected request/source/role/clock')
    need(type(request['sequence'])is int and request['sequence']>last_sequence,'Strict sequence without replay');last_sequence=request['sequence']
    secret=request['kind']in ('operator_seed','provider_credential')
    cutoff=clock['closeout_ns']if request['kind']in ('operation_closure','operator_phase_closure','study_closure','study_scientific_qualification','human_reviews')else clock['scientific_ns'];end=min(io.end,cutoff/1e9)
    stage='request_retention';io.save(journal/('request-'+str(last_sequence)+'.json'),request_raw)
    stage='publisher_accept';listeners[1].settimeout(end-time.monotonic());publisher,_address=listeners[1].accept();peer(publisher,selection['publisher_peer'])
    stage='publisher_exchange';send(publisher,request_raw,io,end);publication_raw=framed(publisher,io,selection['max_message_bytes'],end,None if secret else publisher_chunks);publication=parse(publication_raw)
    need(set(publication)=={'request_pin','payload'}and publication['request_pin']==pin(request_raw),'One exact independently produced response')
    value=publication['payload']
    if not secret:
     need(type(value)is dict and set(value)=={'payload','signature_base64'},'External signed envelope only')
     signed=value['payload'];need(all(signed[k]==request[k]for k in ('role','kind','source_pin','run_id','subject')),'Current role/source/subject before forwarding')
    stage='controller_response';response={'schema':'neural004_incremental_response_v1','request_pin':pin(request_raw),'sequence':last_sequence,'role':request['role'],
     'source_pin':request['source_pin'],'run_id':request['run_id'],'payload':value};raw=encoded(response)
    need(len(raw)<=selection['max_message_bytes'],'Complete response before forwarding')
    if not secret:io.save(journal/('response-'+str(last_sequence)+'.json'),raw)
    send(client,raw,io,end)
    if secret:publication_raw=raw=None;publication=value=response=None
   except BaseException as error:current=error
   finally:
    actions=[]
    if publisher is not None:actions.append(('publisher socket close',publisher.close))
    actions.append(('controller socket close',client.close));current=attempt(actions,current)
   if current is not None:
    # Connection cleanup precedes failure metadata so all secondary close
    # errors survive. Prefix/publication failures are independently attempted.
    prefix='failure-'+str(ordinal)+'-'+str(last_sequence)
    actions=[('retain request framing prefix',lambda:io.save(journal/(prefix+'-request.bin'),b''.join(request_chunks)))]
    if secret is False:actions.append(('retain nonsecret publisher framing prefix',lambda:io.save(journal/(prefix+'-publisher.bin'),b''.join(publisher_chunks))))
    actions.append(('retain request failure metadata',lambda:io.save(journal/(prefix+'.json'),encoded(failure_metadata(current,stage,last_sequence,secret,io)))))
    attempt(actions,current);raise current
 except BaseException as error:primary=error
 finally:
  actions=[('listener close',s.close)for s in listeners]
  actions.extend(('owned socket unlink',lambda p=p,i=i:remove_owned(p,i))for p,i in owned);primary=attempt(actions,primary)
  if primary is not None:
   attempt([('retain complete service failure',lambda:io.save(journal/'SERVICE_FAILURE.json',encoded(failure_metadata(primary,stage,last_sequence,None,io))))],primary)
 if primary is not None:raise primary
 io.tick()
