"""Original HM stage closure and exact C restoration admission.

No protected reference result or candidate scientific body is read here. The
actual qualified H event carries only original stage/process/stream metadata.
All scientific products are consumed by the unchanged later original callers.
"""
from .fixed_tables import RECORD_FIELDS,RECORD_VERSIONS
from .reservations import ReservationPlan,LOGICAL,PHYSICAL,PEAKS,validate_type
from .stage_budget import ExclusiveBudget,state_valid,exact_successor,lease_scalars
from .guard import encoded as original_encoded
from four_programmes.common import need,closed,integer,pin,encode,parse,bounded_size
from four_programmes.channel import HostEvent,TerminalEvidence

_ADMITTED=object()

def _record(value,name):
 closed(value,RECORD_FIELDS[name]);need(value['schema']==RECORD_VERSIONS[name],'exact original '+name+' version')
 # Equality alone admits True as generation/sequence1. These exact integers
 # are original causal identities, not truth flags; validate before any join.
 if name=='HMReturn':
  integer(value['sequence'],1);need(value['sequence']<=3,'same exact original sequence1..3')
  if value['terminal_generation'] is not None:
   integer(value['terminal_generation'],1);need(value['terminal_generation']<=3,'exact committed original generation')
 elif name=='HMReceiptAdmission':
  if value['generation'] is not None:
   integer(value['generation'],1);need(value['generation']<=3,'same committed original generation')
 elif name=='HMStart':integer(value['issued_ns'],1)
 elif name=='HMCompletion':
  integer(value['closed_ns'],1)
  need(value['exit_code'] is None or type(value['exit_code']) is int,'exact integer exit or unknown null')
 return value

def _process_observation_types(process):
 need(type(process)is dict,'original process observation record')
 for key in ('spawn_attempted','spawn_acknowledged','natural_exit','forced','timed_out',
             'group_empty','group_removed','physical_final_known','publication_complete'):
  need(type(process[key])is bool,'exact original process truth flag '+key)
 need(process['exit_code'] is None or type(process['exit_code'])is int,
      'original process exit is integer or unknown, never bool')
 closed(process['streams_eof'],('stdout','stderr'))
 need(all(type(x)is bool for x in process['streams_eof'].values()),'both original EOF truth flags')
 need(type(process['cleanup_errors'])is list and type(process['unknown_dimensions'])is list,
      'original ordered cleanup and unknown collections, not false-shaped objects')
 need(all(type(x)is str for x in process['unknown_dimensions']),'original unknown dimension names')
 return process

def _process_identity(value):
 from .issuance import wire
 wire(value,'ProcessIdentity')
 _descriptor(value['source']);_descriptor(value['parent_launch'])
 return value

def _descriptor(value):return validate_type(value,'Descriptor')
def _nullable_descriptor(value):
 if value is not None:_descriptor(value)

def _physical_rows(rows,plan,stage):
 """Closed actual H partition; declarations alone are never a producer."""
 h0=stage['issuer_host_row'];w=stage['row'];h1={'WR':'HR1','WA':'HA1','WB':'HB1'}[w]
 need(type(rows)is list and [r['row']for r in rows]==[h0,w,h1],
      'complete original bootstrap/issuer-monitor, worker and terminal partition')
 known=True
 for record in rows:
  closed(record,('row','reservation_plan','intervals','logical','physical','peaks','known','original_owner','prefix_status'))
  r=plan.rows[record['row']]
  need(record['reservation_plan']==plan.pin and record['original_owner']==r['owner'] and
       record['prefix_status'] in ('actual_complete','actual_prefix_full_reservation_retained'),
       'exact original physical/accounting owner and complete-prefix disposition')
  expected=[r['window']]
  if record['row']==h0:
   expected=[r['issuance']['window'],{'start_ns':r['window']['start_ns'],'stop_ns':plan.rows[w]['window']['stop_ns']}]
  need(record['intervals']==expected,'all and only original source-selected disjoint accounting intervals')
  need(type(record['known'])is bool,'known observation is exact bool')
  for name,keys in (('logical',LOGICAL),('physical',PHYSICAL),('peaks',PEAKS)):
   closed(record[name],keys)
   for key in keys:
    value=record[name][key]
    if value is None:
     known=False;need(record['known'] is False,'unknown physical cost cannot be zero or known')
    else:
     integer(value);need(value<=r[name][key],'actual original '+record['row']+' '+name+' ceiling')
  if not record['known']:known=False
 return known

class StageAdmission:
 __slots__=('_token','plan','lease','lease_pin','start','start_pin','completion','completion_pin','budget_return','return_pin',
   'terminal','terminal_pin','eligible','record','record_pin','fingerprint','complete','subject','original_child_completion',
   'original_child_streams','candidate_receipt_pin','candidate_receipt_raw','event')
 def __init__(self,token,**fields):
  need(token is _ADMITTED,'actual fixed source-owned H closure consumer only')
  self._token=token
  need(set(fields)==set(self.__slots__)-{'_token'},'complete private original stage admission')
  for k,v in fields.items():setattr(self,k,v)

def admit(event,*,budget,plan,full_plan,adapter_meter,selected_submission=None):
 """Reachable consumer for the exact suspended C's original pending lease.

 The H source must itself implement actual process/row observation and complete
 publication. A nominal HostEvent constructed in an invented control never
 qualifies that missing runtime producer or establishes scientific results.
 """
 need(type(budget)is ExclusiveBudget and type(plan)is ReservationPlan and type(event)is HostEvent,
      'actual C original writer/plan and qualified H response')
 try:
  need(budget.plan is plan and budget.owner=='C' and not budget.active and budget.pending is not None,
       'actual same original suspended controller')
  pending=budget.pending;lease=lease_scalars(pending['lease']);base=pending['base'];stage=plan.stage(lease['sequence'])
  need(event.source==plan.body['observer_source'] and event.campaign==plan.body['campaign_id'] and
       event.body['status'] in ('observed','failed','unknown'),'same actual original observer and explicit disposition')
  result=event.body['result']
  closed(result,('schema','lease','start','completion','budget_return','receipt_admission','candidate_receipt','evidence'))
  need(result['schema']=='hundred_models_original_stage_response_v2' and result['lease']==pending['pin'],
       'same exact one pending original stage')
  carrier=TerminalEvidence(event,adapter_meter)
  def doc(d,name):
   _descriptor(d);raw=carrier.read(d,16777216,metadata=True);value=parse(raw,16777216)
   need(raw==encode(value),'exact complete canonical original '+name+' bytes')
   return raw,value
  _,start=doc(result['start'],'start');_record(start,'HMStart')
  _,completion=doc(result['completion'],'completion');_record(completion,'HMCompletion')
  _,ret=doc(result['budget_return'],'return');_record(ret,'HMReturn')
  _,receipt=doc(result['receipt_admission'],'receipt admission');_record(receipt,'HMReceiptAdmission')
  for record in (start,completion,ret,receipt):
   need(record['lease']==pending['pin'] and record['reservation_plan']==plan.pin and
        record['reservation_row']==stage['row'] and record['invocation_authority']==lease['invocation_authority'],
        'every actual original completion object belongs to same lease/authority/row')
  need(start['authority']==lease['original_authority'] and start['observer_source']==plan.body['observer_source'] and
       start['controller']==completion['controller']==lease['controller'] and start['worker']==completion['worker'],
       'actual original C and W source/PID/clock identities')
  need(completion['start']==receipt['start']==result['start'] and receipt['completion']==ret['completion']==result['completion'] and
       receipt['budget_return']==result['budget_return'],'complete original start/closure/return chain')
  _process_identity(start['controller']);_process_identity(start['worker'])
  c,w=start['controller'],start['worker']
  need((c['boot_id'],c['pid'],c['start_monotonic_ns'])!=(w['boot_id'],w['pid'],w['start_monotonic_ns']) and
       w['launch_nonce']==lease['worker_nonce'],'actual W is distinct from live original C, not a C checkpoint')
  integer(start['issued_ns'],1);integer(completion['closed_ns'],1)
  boot=plan.rows[stage['issuer_host_row']]['window'];terminalrow=plan.rows[{'WR':'HR1','WA':'HA1','WB':'HB1'}[stage['row']]]
  need(boot['start_ns']<=start['issued_ns']<boot['stop_ns'] and
       terminalrow['window']['start_ns']<=completion['closed_ns']<terminalrow['window']['stop_ns'],
       'original actual bootstrap and terminal clocks; no new deadline')
  need(type(full_plan)is dict and type(full_plan.get('jobs'))is list and len(full_plan['jobs'])==8223 and
       len({j['id']for j in full_plan['jobs']})==8223,'entire fixed original reference plan, no subset')
  adapter_meter.charge('work_units',bounded_size(full_plan))
  need(pin(original_encoded(full_plan))==lease['plan'],'exact entire original plan content, not caller labels')
  domain=[j['id']for j in full_plan['jobs']] if stage['stage']=='reference' else [lease['submission']]
  need(completion['ordered_domain']==receipt['full_domain']==domain and
       completion['stage']==receipt['stage']==stage['stage']==lease['stage'],
       'full original ordered 8223 reference or exact own-run candidate domain')
  for key in ('scope','inputs','submission'):
   need(receipt[key]==lease[key],'same original scientific invocation '+key)
  need(receipt['predecessor']==ret['previous_return']==lease['previous_return']==budget.previous_return and
       ret['base_state']==ret['restore_parent']==pending['base_pin'] and ret['sequence']==lease['sequence'],
       'actual original base/generation/predecessor restoration edge')
  for key in ('stdout','stderr','terminal_state','result','original_failure'):_nullable_descriptor(completion[key])
  need(type(completion['cleanup_errors'])is list and len(completion['cleanup_errors'])<=256 and
       type(completion['known_prefixes'])is list and len(completion['known_prefixes'])<=65536,'complete bounded original failures/prefixes')
  for d in completion['cleanup_errors']+completion['known_prefixes']:_descriptor(d)
  for key in ('natural_exit','streams_eof','descendants_empty','group_removed','timed_out'):
   need(type(completion[key])is bool,'exact original closure flag '+key)
  if completion['exit_code'] is not None:need(type(completion['exit_code'])is int,'actual exit code including failure')
  need(type(ret['committed_once'])is bool and type(receipt['complete'])is bool and
       ret['disposition'] in ('eligible_exact_successor','failed_known_stop','terminal_unknown') and
       type(ret['unknown_dimensions'])is list and len(ret['unknown_dimensions'])<=256 and
       all(type(x)is str and 0<len(x)<=256 for x in ret['unknown_dimensions']),'complete original return disposition')
  _,physical=doc(completion['physical_observation'],'physical observation')
  closed(physical,('schema','lease','start','reservation_plan','reservation_row','original_envelope','original_process','row_observations'))
  need(physical['schema']=='hundred_models_original_stage_physical_v2' and physical['lease']==pending['pin'] and
       physical['start']==result['start'] and physical['reservation_plan']==plan.pin and physical['reservation_row']==stage['row'] and
       physical['original_envelope']==start['original_envelope'] and physical['row_observations']==completion['row_observations'],
       'same actual whole enforcement and named original row observations')
  rows_known=_physical_rows(physical['row_observations'],plan,stage)
  process=_process_observation_types(physical['original_process'])
  need(type(process)is dict and process.get('schema')=='four_original_process_observation_v1' and
       process.get('identity')==w and process.get('source')==w['source'] and process.get('campaign')==plan.body['campaign_id'],
       'actual original H process observation, same W and complete campaign')
  need(process['natural_exit']==completion['natural_exit'] and process['exit_code']==completion['exit_code'] and
       (process['streams_eof']=={'stdout':True,'stderr':True})==completion['streams_eof'] and
       process['group_empty']==completion['descendants_empty'] and process['group_removed']==completion['group_removed'] and
       process['timed_out']==completion['timed_out'],'same original physical outcome, never supplied unrelated success')
  stream_known=True
  for name in ('stdout','stderr'):
   d=completion[name]
   if d is None:stream_known=False;continue
   integer(process.get(name+'_bytes'))
   raw=carrier.read(d,plan.rows[stage['row']]['physical']['stream_bytes'])
   need(d==process.get(name) and len(raw)==process.get(name+'_bytes'),'same whole original H stream bytes')
  terminal=None
  need(ret['terminal_state']==completion['terminal_state'],'same actual terminal state or same honest absence')
  if completion['terminal_state'] is not None:
   _,terminal=doc(completion['terminal_state'],'terminal state');exact_successor(base,terminal,plan,sequence=lease['sequence'])
   need(ret['terminal_generation']==receipt['generation']==terminal['generation'],'exact base plus one committed terminal generation')
  else:need(ret['terminal_generation'] is None and receipt['generation'] is None,'unknown terminal generation stays null')
  need(receipt['original_result']==completion['result'],'exact original API result descriptor, never inferred from zero exit')
  known_success=(process['spawn_attempted'] is True and process['spawn_acknowledged'] is True and terminal is not None and not terminal['failed'] and completion['result'] is not None and rows_known and stream_known and
    completion['natural_exit'] and type(completion['exit_code'])is int and completion['exit_code']==0 and completion['streams_eof'] and
    completion['descendants_empty'] and completion['group_removed'] and not completion['timed_out'] and completion['original_failure'] is None and
    not completion['cleanup_errors'] and process['forced'] is False and process['original_failure'] is None and not process['cleanup_errors'] and
    not process['unknown_dimensions'] and process['physical_final_known'] is True and process['publication_complete'] is True)
  eligible=(known_success and ret['disposition']=='eligible_exact_successor' and ret['committed_once'] and
            not ret['unknown_dimensions'] and event.body['status']=='observed')
  need(receipt['complete']==eligible,'receipt may claim complete iff entire actual original admission holds')
  child=None;child_streams=None;candidate_raw=None
  if stage['stage']=='reference':
   need(selected_submission is None and result['candidate_receipt'] is None,'reference remains descriptor-only until both seals and C04')
  else:
   need(type(selected_submission)is dict and pin(original_encoded(selected_submission))==lease['submission'],'actual exact earlier selected own-run invocation')
   if eligible:
    need(result['candidate_receipt']==completion['result'],'same actual original candidate API receipt')
    candidate_raw,candidate=doc(result['candidate_receipt'],'candidate own-run receipt')
    closed(candidate,('submission','result','completion','stdout_hex','stderr_hex','scientific_qualification'))
    need(candidate['submission']==lease['submission'],'same exact original candidate invocation')
    child=candidate['completion'];closed(child,('returncode','natural_completion','pid','forced'))
    need(type(child['returncode'])is int and child['returncode']==0 and child['natural_completion'] is True and
         child['forced'] is False and type(child['pid'])is int and child['pid']>0,'original source-owned complete candidate child')
    child_streams={}
    for name in ('stdout','stderr'):
     value=candidate[name+'_hex'];need(type(value)is str and len(value)%2==0 and len(value)<=2*selected_submission['stream_limit_bytes'] and
          all(c in '0123456789abcdef' for c in value),'complete bounded original candidate stream')
     adapter_meter.charge('work_units',len(value)+4096);adapter_meter.charge('retained_bytes',len(value)//2)
     child_streams[name]=pin(bytes.fromhex(value))
  fingerprint=pin(encode({'event':event.raw_pin,'lease':pending['pin'],'completion':result['completion'],'return':result['budget_return']}))
  return StageAdmission(_ADMITTED,plan=plan,lease=lease,lease_pin=pending['pin'],start=start,start_pin=result['start'],completion=completion,
    completion_pin=result['completion'],budget_return=ret,return_pin=result['budget_return'],terminal=terminal,terminal_pin=completion['terminal_state'],
    eligible=eligible,record=receipt,record_pin=result['receipt_admission'],fingerprint=fingerprint,complete=eligible,
    subject='reference' if stage['stage']=='reference' else 'candidate',original_child_completion=child,original_child_streams=child_streams,
    candidate_receipt_pin=result['candidate_receipt'],candidate_receipt_raw=candidate_raw,event=event)
 except BaseException as error:
  budget._own(error);adapter_meter.own_error(error,'HM_original_stage_closure');raise
