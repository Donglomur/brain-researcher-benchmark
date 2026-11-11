"""Exact adopted v4 issuer wire, actual C guard and one-use lease token.

Native C/H bridge attribution is a separate fixed source prerequisite. The
source-owned missing boundary refuses; records or tests cannot qualify it.
"""
import time
from .fixed_tables import RECORD_FIELDS,RECORD_VERSIONS,ISSUANCE_SCHEMA
from .identity_contract import FIELDS,decode,validate_chain
from .stage_budget import ExclusiveBudget
from four_programmes.common import need,closed,encode,parse,pin,integer,DependencyUnavailable
from four_programmes.schema import check
from four_programmes.channel import HostEvent,RootChannel
from four_programmes.hm_issuer_transport_v1 import (HMIssuerTransferV1,
    exchange_original_issuer_v1, require_original_issuer_physical_prefix_v1)

_ISSUED=object()
KINDS=('Subject','RootSelection','InvocationAuthority','PhysicalPrefix','IssuanceResponse')

def wire(value,kind):
 need(kind in ('IssuanceRequest','IssuanceResponse','ProcessIdentity'),'fixed adopted issuer wire type')
 return check(value,{'$ref':'#/$defs/'+kind,'$defs':ISSUANCE_SCHEMA['$defs']})

def require_actual_physical_prefix(*,raw,descriptor,response,request,budget,adapter_meter):
 return require_original_issuer_physical_prefix_v1(raw=raw,descriptor=descriptor,response=response,
     request=request,budget=budget,adapter_meter=adapter_meter)

class IssuanceAdmission:
 __slots__=('_token','budget','plan','slot','guard_raw','subject_pin','selection_pin','authority_pin','authority',
            'invocation','request','response','physical_prefix','event','received_ns','consumed','lease_pin','fingerprint','transport')
 def __init__(self,token,*,budget,slot,guard_raw,subject_pin,selection_pin,authority_pin,authority,invocation,request,response,event,received_ns,transport):
  need(token is _ISSUED,'only actual fixed qualified H response consumer')
  self._token=token;self.budget=budget;self.plan=budget.plan;self.slot=slot;self.guard_raw=guard_raw
  self.subject_pin=subject_pin;self.selection_pin=selection_pin;self.authority_pin=authority_pin
  self.authority=parse(encode(authority),131072);self.invocation=parse(encode(invocation),131072)
  self.request=parse(encode(request),131072);self.response=parse(encode(response),131072)
  self.physical_prefix=response['physical_observation_prefix'];self.event=event;self.received_ns=received_ns
  self.consumed=False;self.lease_pin=None;self.transport=transport
  self.fingerprint=pin(encode({'event':event.raw_pin,'request':pin(encode(request)),'guard':pin(guard_raw),
                              'subject':subject_pin,'selection':selection_pin,'authority':authority_pin}))
 def consume_for_lease(self,lease,lease_pin,budget):
  need(self._token is _ISSUED and not self.consumed,'one actual original issuer token')
  self.consumed=True
  try:
   need(type(self.transport)is HMIssuerTransferV1,'actual completed original issuer transport')
   self.transport.require_complete(self)
   need(budget is self.budget and budget.plan is self.plan and budget.guard is None and budget.active and
        budget.owner=='C' and budget.issuer_tokens.get(budget.row) is self,'same original postlude writer')
   closed(lease,RECORD_FIELDS['HMLease'])
   need(lease['schema']==RECORD_VERSIONS['HMLease'] and lease['authority_subject']==self.subject_pin and
        lease['invocation_authority']==self.authority_pin and lease['controller']==self.request['controller'],
        'same exact earlier authority, subject and actual original C')
   for key in FIELDS:
    if key=='root_issuer_source':continue
    need(lease[key]==self.invocation[key],'same original source-owned invocation '+key)
   self.lease_pin=lease_pin
  except BaseException as error:budget._own(error);raise

class _IssuerMeter:
 def __init__(self,adapter):self.adapter=adapter
 def charge(self,kind,n):
  need(kind=='work','fixed canonical identity parser category');self.adapter.charge('work_units',n)

def request_body(budget,*,subject_pin,invocation,guard_state_pin,controller,adapter_meter):
 """The exact v4 request; guard snapshot publication was paid in C prelude."""
 need(type(budget)is ExclusiveBudget and budget.owner=='C' and budget.guard is not None and
      budget.guard['phase']=='waiting' and 'request' not in budget.guard,'one actual original guarded C request')
 need(set(invocation)==set(FIELDS),'exact twelve original invocation fields')
 t=budget.plan.stage(invocation['sequence']);a=budget.guard['allocation']
 need(t['issue_from']==budget.row and a['slot']==t['issuer_slot'] and
      invocation['reservation_plan']==budget.plan.pin,'same original stage/row/plan')
 guard=budget.guard['snapshot'];need(encode(budget._state('active_C'))==guard,'unchanged original C prefix')
 from .reservations import validate_type
 validate_type(guard_state_pin,'Descriptor');wire(controller,'ProcessIdentity')
 need({k:guard_state_pin[k]for k in ('bytes','sha256')}==pin(guard),'exact actually frozen full guard snapshot identity')
 adapter_meter.charge('work_units',a['maximum_frame_bytes']*64+4096)
 body={'schema':'hundred_models_prelease_issuer_request_v4','campaign_id':budget.plan.body['campaign_id'],
       'sequence':invocation['sequence'],'stage':t['stage'],'reservation_plan':budget.plan.pin,'issuer_slot':a['slot'],
       'controller':controller,'subject':subject_pin,'guard_state':guard_state_pin}
 wire(body,'IssuanceRequest');need(len(encode(body))<=a['maximum_frame_bytes'],'whole earlier-bounded exact request')
 budget.guard['request']=parse(encode(body),a['maximum_frame_bytes'])
 budget.guard['request_identity']=pin(encode(body))
 return body

def capture_issuer_response(event,*,budget,invocation,subject_pin,adapter_meter):
 """Exact adopted response plus bounded raw original documents; no C file reads."""
 need(type(budget)is ExclusiveBudget and type(event)is HostEvent,'actual C writer and qualified H event')
 try:
  need(budget.guard is not None and budget.guard['phase']=='waiting' and not budget.failed and budget.active and
       'request' in budget.guard,'actual original C request and frozen guard')
  plan=budget.plan;a=budget.guard['allocation'];t=plan.stage(invocation['sequence']);request=budget.guard['request']
  received_ns=time.monotonic_ns();integer(received_ns,1)
  need(event.source==plan.body['root_issuer_source'] and event.campaign==plan.body['campaign_id'] and
       event.body['status']=='observed' and event.raw_pin['bytes']<=a['maximum_frame_bytes'],
       'same actual original H source/campaign and full response extent')
  transport=event.body['result'];closed(transport,('schema','response','documents'))
  need(transport['schema']=='hundred_models_issuer_document_transport_v1','fixed transport, never an alternate issuer schema')
  rows=transport['documents'];need(type(rows)is list and len(rows)==5,'all five original complete bounded documents')
  captured={};descriptors={}
  for kind,row in zip(KINDS,rows):
   closed(row,('kind','descriptor','hex'));need(row['kind']==kind,'fixed whole original document order')
   d=row['descriptor'];from .reservations import validate_type
   validate_type(d,'Descriptor');n=integer(d['bytes']);need(n<=a['metadata_member_cap'],'earlier full selected metadata extent')
   text=row['hex'];need(type(text)is str and len(text)==2*n and all(c in '0123456789abcdef'for c in text),'canonical complete original bytes')
   adapter_meter.charge('work_units',2*n+4096);adapter_meter.charge('retained_bytes',n)
   raw=bytes.fromhex(text);need(pin(raw)=={k:d[k]for k in ('bytes','sha256')},'actual complete H-captured raw pin')
   captured[kind]=raw;descriptors[kind]=d
  response=parse(captured['IssuanceResponse'],a['metadata_member_cap'])
  need(captured['IssuanceResponse']==encode(response),'exact canonical original v4 response bytes')
  wire(response,'IssuanceResponse')
  need(transport['response']==descriptors['IssuanceResponse'] and
       response['request']==budget.guard['request_identity']==pin(encode(request)),
       'exact original request body and actual published response identity')
  for key in ('campaign_id','sequence','stage','reservation_plan','issuer_slot','controller','subject','guard_state'):
   need(response[key]==request[key],'same complete original request field '+key)
  need(response['issuer_source']==plan.body['root_issuer_source'] and response['disposition']=='issued' and
       response['original_failure'] is None and not response['cleanup_errors'] and not response['unknown_dimensions'],
       'only issued complete exact response may create a private token')
  need(response['root_selection']==descriptors['RootSelection'] and response['invocation_authority']==descriptors['InvocationAuthority'] and
       response['physical_observation_prefix']==descriptors['PhysicalPrefix'] and response['subject']==subject_pin==descriptors['Subject'],
       'all exact linked original subject/authority/physical products')
  need(len(response['issued_objects'])==3 and {encode(x)for x in response['issued_objects']}==
       {encode(descriptors[k])for k in ('RootSelection','InvocationAuthority','PhysicalPrefix')},
       'complete earlier issued products; response never asserts its own publication')
  for kind in ('read_bytes','write_bytes','work'):
   used=response['issuer_logical_attempted_prefix'][kind];parent=response['parent_logical_attempted_prefix'][kind]
   need(used==parent and used<=a['logical'][kind] and parent<=plan.rows[t['issuer_host_row']]['logical'][kind],
        'same single original H counter before dispatch; locked future allowance not borrowed')
  stamp=response['response_prefix_observed_ns']
  need(a['window']['start_ns']<=stamp<=received_ns<a['window']['stop_ns'],'actual prefix and complete C capture inside original issuer interval')
  parsed={kind:decode(captured[kind],kind,cap=a['metadata_member_cap'],meter=_IssuerMeter(adapter_meter)) for kind in KINDS[:3]}
  validate_chain(invocation=invocation,plan=plan,subject_body=parsed['Subject'],subject_pin=subject_pin,
      selection=parsed['RootSelection'],selection_pin=descriptors['RootSelection'],authority=parsed['InvocationAuthority'],
      authority_pin=descriptors['InvocationAuthority'],received_ns=received_ns)
  need(parsed['RootSelection']['issued_monotonic_ns']<=stamp,'actual root issuance precedes response prefix')
  require_actual_physical_prefix(raw=captured['PhysicalPrefix'],descriptor=descriptors['PhysicalPrefix'],response=response,
                                request=request,budget=budget,adapter_meter=adapter_meter)
  need(encode(budget._state('active_C'))==budget.guard['snapshot'],'C original programme prefix remains unchanged')
  token=IssuanceAdmission(_ISSUED,budget=budget,slot=a['slot'],guard_raw=budget.guard['snapshot'],subject_pin=subject_pin,
        selection_pin=descriptors['RootSelection'],authority_pin=descriptors['InvocationAuthority'],authority=parsed['InvocationAuthority'],
        invocation=invocation,request=request,response=response,event=event,received_ns=received_ns,transport=adapter_meter.transfer)
  budget.admit_issuer_response(token)
  return token
 except BaseException as error:
  budget._own(error)
  try:adapter_meter.own_error(error,'HM_original_issuer_response')
  except BaseException as cleanup:budget.secondary.append(cleanup)
  raise

def exchange_issuer(*,custody,budget,invocation,subject_pin,guard_state_pin,controller):
 """Actual original two-ended credit/response/return exchange; no callback seam."""
 return exchange_original_issuer_v1(custody=custody,budget=budget,invocation=invocation,
     subject_pin=subject_pin,guard_state_pin=guard_state_pin,controller=controller)
