"""Full unchanged HM reference or own-run candidate API in one original W.

This is a concrete caller, not a callback or reference-only substitute. Future
activation still requires original source admission, actual H start, qualified
isolation and all original API gates. Nothing executes on import.
"""
import os,time
from pathlib import Path
from .stage_budget import ExclusiveBudget,state_valid,lease_scalars
from .reservations import ReservationPlan
from .identity_contract import decode,canonical,validate_chain_records,FIELDS,typed
from .fixed_tables import RECORD_FIELDS,RECORD_VERSIONS
from four_programmes.common import need,closed,pin,encode,failure,bounded_size,integer
from four_programmes.source_session import SourceSession
from four_programmes.channel import HostEvent
from four_programmes.roots import BoundRoots
from four_programmes.identity import process_identity

# Metadata carried by a qualified source bootstrap is finite and original.
# Neither these descriptors nor this structural join creates that bootstrap.
def _run(*,session,request,start_event,bootstrap_roots,terminal_store,plan,schemas,mapping):
 need(type(session)is SourceSession and session.programme=='PAPER-paper-method-replacement-016',
      'actual independently admitted full HM source session')
 need(type(plan)is ReservationPlan and type(bootstrap_roots)is BoundRoots and type(start_event)is HostEvent,
      'actual original plan, fixed bootstrap roots and H channel event')
 closed(request,('schema','lease','base_state','subject','root_selection','invocation_authority','scope','inputs','full_plan',
                 'original_authority','submission','package','root','output','terminal_name'))
 need(request['schema']=='hundred_models_original_worker_request_v2','fixed full worker request')
 meter=bootstrap_roots.meter;cap=16777216
 def doc(d):
  raw=bootstrap_roots.read(d,cap,metadata=True)
  # Source bootstrap metadata parser is fixed and refuses duplicate keys.
  from four_programmes.common import parse
  return parse(raw,cap)
 lease=doc(request['lease']);base=doc(request['base_state'])
 lease_scalars(lease)
 state_valid(base,plan);t=plan.stage(lease['sequence'])
 need(lease['base_state']==request['base_state'] and lease['reservation_plan']==plan.pin and
      lease['base_generation']==base['generation']==t['base_generation'] and
      lease['reservation_row']==t['row'] and lease['stage']==t['stage'] and lease['previous_return']==base['previous_return'] and
      lease['original_deadline_ns']==base['deadline_ns']==plan.body['run_deadline_ns'],
      'actual original serial generation/plan/window/caps')
 need(pin(encode(base))=={k:request['base_state'][k]for k in ('bytes','sha256')},'actual exact canonical frozen base')
 need(start_event.body['status']=='observed' and start_event.source==plan.body['observer_source'] and
      start_event.campaign==plan.body['campaign_id'],'actual H start source/campaign')
 closed(start_event.body['result'],('start',))
 start=doc(start_event.body['result']['start']);closed(start,RECORD_FIELDS['HMStart']);integer(start['issued_ns'],1)
 need(start['schema']==RECORD_VERSIONS['HMStart'] and start['lease']==request['lease'] and
      start['reservation_plan']==plan.pin and start['reservation_row']==t['row'] and
      start['invocation_authority']==lease['invocation_authority']==request['invocation_authority'] and
      start['authority']==lease['original_authority']==request['original_authority'] and start['controller']==lease['controller'],
      'same exact independently captured worker start and both authorities')
 worker=start['worker'];actual=process_identity(os.getpid(),launch_nonce=lease['worker_nonce'],source=worker['source'],
          parent_launch=worker['parent_launch'],mapping=mapping,meter=meter)
 need(actual==worker and worker!=start['controller'] and
      (worker['boot_id'],worker['pid'],worker['start_monotonic_ns'])!=
      (start['controller']['boot_id'],start['controller']['pid'],start['controller']['start_monotonic_ns']),
      'this actual W original boot/PID/start distinct from live C')
 need(start['observer_source']==plan.body['observer_source'],'same selected observer source')
 # Full source-owned metadata creates the identities. No result/reference body
 # is opened here; those stay inside the unchanged original API and later C04.
 scope=doc(request['scope']);inputs=doc(request['inputs']);full_plan=doc(request['full_plan'])
 need(type(full_plan)is dict and type(full_plan.get('jobs'))is list and len(full_plan['jobs'])==8223 and
      len({j['id']for j in full_plan['jobs']})==8223,'entire original 8223 ordered jobs, no subset')
 original_authority=doc(request['original_authority'])
 submission=None if request['submission'] is None else doc(request['submission'])
 original_codec=session.module('guard').encoded
 # The original codec remains authoritative for scientific-call metadata.
 inv={k:lease[k]for k in FIELDS if k in lease}
 inv['root_issuer_source']=plan.body['root_issuer_source']
 need(set(inv)==set(FIELDS),'all original invocation fields')
 need(inv['scope']==pin(original_codec(scope)) and inv['inputs']==pin(original_codec(inputs)) and
      inv['plan']==pin(original_codec(full_plan)) and
      inv['submission']==(None if submission is None else pin(original_codec(submission))) and
      inv['source_manifest']==plan.body['source_manifest'],'actual complete original call identities')
 # W independently checks the exact earlier canonical authority objects.
 # Actual C response timing belongs the H dispatcher/issuer token consumer,
 # not a new timestamp invented inside the unchanged HMStart wire record.
 captured={}
 for key,kind in [('subject','Subject'),('root_selection','RootSelection'),('invocation_authority','InvocationAuthority')]:
  raw=bootstrap_roots.read(request[key],cap,metadata=True)
  # Meter uses the actual H adapter category spelling, not a second programme charge.
  class DecodeMeter:
   def charge(self,kind,n):need(kind=='work','fixed identity parser work');meter.charge('work_units',n)
  captured[key]=decode(raw,kind,cap=cap,meter=DecodeMeter())
 authority=captured['invocation_authority'];selection=captured['root_selection']
 need(lease['authority_subject']==request['subject'] and authority['root_selection']==request['root_selection'],
      'unchanged exact earlier subject/root authority chain')
 validate_chain_records(invocation=inv,plan=plan,subject_body=captured['subject'],subject_pin=request['subject'],selection=selection,
    selection_pin=request['root_selection'],authority=authority,authority_pin=request['invocation_authority'])
 # H dispatcher must already have consumed the actual private issuer token;
 # a future source caller cannot replace that with this record-only check.
 # No ready_binding or C receipt timestamp is added to the closed HMStart.
 budget=ExclusiveBudget(base,plan=plan,owner='W',row=t['row'],lease=lease)
 result=None;terminal=None;primary=None;cleanup=[];terminal_pin=None
 try:
  budget.require_operation(t['stage'])
  # Full original compiler is called on original source, inputs and scope. Its
  # complete result must equal the immutable plan before either API executes.
  budget.charge('work',bounded_size(scope)+bounded_size(inputs)+bounded_size(full_plan))
  compiled=session.module('scope').compile_jobs(scope,inputs)
  need(original_codec(compiled)==original_codec(full_plan),'actual original full plan compiler matches entire selected plan')
  if t['stage']=='reference':
   need(submission is None and original_authority['plan']==inv['plan'],'full original reference authority')
   result=session.api('hm_reference')(request['package'],request['root'],scope,inputs,original_authority,budget,request['output'],
      {k:plan.body['source_manifest'][k]for k in ('bytes','sha256')})
  else:
   need(submission is not None and submission['arm']==t['stage'].split(':')[1] and
        original_authority['inputs']==inv['inputs'] and original_authority['plan']==inv['plan'],
        'actual own-run A/B invocation and complete original inputs/plan')
   result=session.api('hm_candidate')(request['root'],submission,original_authority,budget,request['output'])
  typed(result,'Descriptor')
 except BaseException as error:
  primary=error;budget._own(error);terminal_store.meter.own_error(error,'original_HM_stage_API')
 try:session.close()
 except BaseException as error:
  if primary is None:primary=error;budget._own(error)
  else:cleanup.append(failure(error));budget.secondary.append(error)
  terminal_store.meter.own_error(error,'original_HM_source_close')
 try:terminal=budget.export_terminal()
 except BaseException as error:
  if primary is None:primary=error;budget._own(error)
  else:cleanup.append(failure(error));budget.secondary.append(error)
  terminal_store.meter.own_error(error,'original_HM_terminal_prefix')
 prefix=None
 if primary is not None:
  attrs=BaseException.__getattribute__(primary,'__dict__')
  if type(attrs)is dict:
   prefix={k:attrs[k]for k in ('campaign_prefix','known_output_prefix')if k in attrs}
   terminal_store.meter.charge('work_units',bounded_size(prefix))
 body={'schema':'hundred_models_original_worker_terminal_v2','lease':request['lease'],'start':start_event.body['result']['start'],
       'invocation_authority':request['invocation_authority'],'stage':t['stage'],'reservation_plan':plan.pin,'reservation_row':t['row'],
       'result':result,'terminal_state':terminal,'original_failure':None if primary is None else failure(primary),
       'cleanup_errors':cleanup,'known_original_prefix':prefix,'H_original_exit_still_required':True}
 try:terminal_pin=terminal_store.publish(request['terminal_name'],body)
 except BaseException as error:
  if primary is None:primary=error
  else:cleanup.append(failure(error))
  terminal_store.meter.own_error(error,'original_HM_terminal_publication')
 if primary is not None:
  try:BaseException.__setattr__(primary,'four_HM_terminal',{'terminal':terminal_pin,'original_result':result,'state_known':terminal is not None})
  except BaseException as error:terminal_store.meter.cleanup_errors.append(failure(error))
  raise primary
 need(terminal_pin is not None,'actual original terminal publication')
 return terminal_pin

def run(*,session,request,start_event,bootstrap_roots,terminal_store,plan,schemas,mapping):
 """Own the original bootstrap failure even before a Budget or result exists."""
 try:
  return _run(session=session,request=request,start_event=start_event,bootstrap_roots=bootstrap_roots,
     terminal_store=terminal_store,plan=plan,schemas=schemas,mapping=mapping)
 except BaseException as primary:
  # No replay, fabricated successful terminal or second programme attempt.
  # If the normal stage path already retained a terminal, preserve that exact
  # prefix. Otherwise H's original outer observer receives the actual nonzero
  # exit and the source-owned missing/unknown terminal disposition.
  cleanup=[]
  if type(bootstrap_roots)is BoundRoots:
   try:bootstrap_roots.meter.own_error(primary,'original_HM_bootstrap_or_stage')
   except BaseException as error:cleanup.append(failure(error))
  if type(session)is SourceSession and not getattr(session,'closed',True):
   try:session.close()
   except BaseException as error:cleanup.append(failure(error))
  try:
   attrs=BaseException.__getattribute__(primary,'__dict__')
   terminal=attrs.get('four_HM_terminal')if type(attrs)is dict else None
   BaseException.__setattr__(primary,'four_HM_bootstrap_failure',
     {'known_terminal':terminal,'cleanup_errors':cleanup,'same_original_failure_retained':True,
      'dependent_science_allowed':False,'full_outstanding_delegation_retained':True,
      'missing_terminal_is_unknown':terminal is None})
  except BaseException as error:
   if type(bootstrap_roots)is BoundRoots:bootstrap_roots.meter.cleanup_errors.append(failure(error))
  raise
