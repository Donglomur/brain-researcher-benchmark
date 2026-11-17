"""Complete adopted eighteen-row HM partition; structural admission only.

This compiler cannot qualify native enforcement, issuer custody, physical
attribution, full scientific capacity or matched runtime opportunity.
"""
from four_programmes.common import need,closed,integer,pin,encode,same,bounded_size
from four_programmes.schema import check
from .fixed_tables import RESERVATION_SCHEMA,ROW_OWNERS,STAGE_TABLE,ROOT_RESOURCE_SCHEMA

LOGICAL=('read_bytes','write_bytes','work')
PHYSICAL=('cpu_ns','retained_storage_bytes','process_starts','stream_bytes')
PEAKS=('memory_bytes','pids')
NAMES=tuple(x[0] for x in ROW_OWNERS)
_PROGRAMME=tuple(x[0] for x in ROW_OWNERS if x[1]!='H')
_PLAN=object()

def duration(row):return row['window']['stop_ns']-row['window']['start_ns']
def validate_type(value,name):return check(value,{'$ref':'#/$defs/'+name,'$defs':RESERVATION_SCHEMA['$defs']})
def exact_descriptor(body,descriptor):
 validate_type(descriptor,'Descriptor');need(pin(encode(body))=={k:descriptor[k]for k in ('bytes','sha256')},'exact canonical original metadata bytes')

class ReservationPlan:
 def __init__(self,token,body,descriptor,resource_body,resource_pin):
  need(token is _PLAN,'complete fixed plan compiler only');self.body=body;self.pin=descriptor
  self.root=resource_body;self.root_pin=resource_pin;self.rows={r['id']:r for r in body['rows']}
  self.programme_rows=_PROGRAMME;self.issuer_by_C={t['issue_from']:self.rows[t['issuer_host_row']]['issuance']for t in STAGE_TABLE}
 def stage(self,sequence):
  integer(sequence,1);need(sequence<=3,'three entire original stages');return STAGE_TABLE[sequence-1]
 def future_feasible(self,used_rows,*,completed=()):
  """No borrowing: used + unused locked current/future ceilings stay reserved."""
  need(type(used_rows)is dict and set(used_rows)==set(_PROGRAMME),'all C/W actual prefixes')
  need(set(completed)<=set(_PROGRAMME),'only source-completed original rows')
  for kind in LOGICAL:
   total=0
   for name in _PROGRAMME:
    used=used_rows[name][kind];integer(used)
    cap=self.rows[name]['logical'][kind];need(used<=cap,'attempted row overcap remains failure')
    # Completed rows retain observed usage; all other rows retain full ceiling.
    # This is a feasibility check, not permission to transfer unused allowance.
    total+=used if name in completed else cap
   need(total<=self.body['programme_limits'][kind],'all later full commitments protected '+kind)
  return True

def compile_plan(body,descriptor,*,resource_body,resource_pin,source_manifest,meter):
 meter.charge('work_units',bounded_size(body)+bounded_size(resource_body))
 validate_type(body,'ReservationPlan');check(resource_body,ROOT_RESOURCE_SCHEMA)
 exact_descriptor(body,descriptor);exact_descriptor(resource_body,resource_pin)
 need(body['root_resource_plan']==resource_pin and body['source_manifest']==source_manifest,
      'same complete independently selected original root/source')
 need(resource_body['programme']=='PAPER-paper-method-replacement-016' and body['campaign_id']==resource_body['campaign_id'],
      'one original full HM campaign')
 budget=resource_body['programme_budget'];hard=resource_body['hard_envelope']
 need(body['capacity_qualification']==resource_body['capacity_qualification'] and
      body['observer_source']==hard['independent_observer'] and body['native_qualification']==hard['environment_qualification'],
      'same selected root capacity/observer/native descriptors, not qualification by schema')
 need(budget['kind']=='hundred_models_shared_budget_v2' and
      body['programme_limits']=={k:budget[k]for k in LOGICAL} and
      body['matched_arm_policy']==budget['matched_arm_policy'],'same unchanged original programme limits/policy')
 need(body['origin_ns']==hard['origin_monotonic_ns'] and
      body['run_deadline_ns']==hard['run_deadline_ns']==budget['deadline_ns'] and
      body['evidence_deadline_ns']==hard['evidence_deadline_ns'] and
      body['origin_ns']<body['run_deadline_ns']<=body['evidence_deadline_ns'],'original absolute whole interval')
 need(body['whole_additive_limits']['cpu_ns']==hard['cpu_ns'] and
      body['whole_additive_limits']['retained_storage_bytes']==hard['retained_storage_bytes'] and
      body['whole_peak_limits']=={'memory_bytes':hard['memory_bytes'],'pids':hard['pids']},'original complete physical limits')
 rows=body['rows'];need([(r['id'],r['owner'],r['stage'])for r in rows]==list(ROW_OWNERS),'exact all eighteen row owners and order')
 by={r['id']:r for r in rows};adapters=resource_body['adapter_reservations']
 need(len({r['reservation_id']for r in adapters})==len(adapters),'unique earlier root adapter identities')
 adapter_by={r['reservation_id']:r for r in adapters};seen=set()
 for i,r in enumerate(rows):
  start,stop=r['window']['start_ns'],r['window']['stop_ns'];need(start<stop,'finite nonempty fixed row interval')
  if r['id']=='HF':need(start==body['origin_ns'] and stop==body['evidence_deadline_ns'],'immediate already reserved failure window')
  else:
   need(start==(body['origin_ns']if i==0 else rows[i-1]['window']['stop_ns']),'all success time has one fixed serial owner')
   need(stop<=(body['evidence_deadline_ns']if r['id']=='H01'else body['run_deadline_ns']),'fixed original cutoff')
  for k in PEAKS:need(r['peaks'][k]<=body['whole_peak_limits'][k],'whole peak bounds')
  if r['owner']=='W':
   need(r['peaks']['memory_bytes']+r['host_monitor_memory_bytes']+r['controller_idle_memory_bytes']<=body['whole_peak_limits']['memory_bytes'],'full W/H/inactive C memory')
   need(r['peaks']['pids']+r['host_monitor_pids']+r['controller_idle_pids']<=body['whole_peak_limits']['pids'],'full W/H/inactive C process peaks')
  if r['owner']=='H':
   aid=r['adapter_reservation_id'];need(aid in adapter_by and aid not in seen,'one original H adapter row');seen.add(aid);a=adapter_by[aid]
   need(a['owner_role']=='H' and a['stage']==r['stage'],'exact original H owner/stage')
   need(r['logical']=={'read_bytes':a['read_bytes'],'write_bytes':a['write_bytes'],'work':a['work_units']} and
        r['physical']['cpu_ns']==a['cpu_ns'] and r['physical']['process_starts']==a['process_starts'] and
        r['physical']['retained_storage_bytes']==a['retained_bytes'],'H original additive reservation equality')
   if r['issuance'] is None:need(a['wall_ns']==duration(r),'same original H finite interval')
  else:need(r['adapter_reservation_id'] is None and r['issuance'] is None,'C/W no extra adapter or issuer allowance')
 for k in LOGICAL:need(sum(r['logical'][k]for r in rows if r['owner']!='H')<=body['programme_limits'][k],'all C/W reservations fit original '+k)
 for k in PHYSICAL:need(sum(r['physical'][k]for r in rows)<=body['whole_additive_limits'][k],'all eighteen whole reservations fit '+k)
 need({r['id']for r in rows if r['issuance'] is not None}=={'HR0','HA0','HB0'},'exact three earlier issuer allocations')
 for t in STAGE_TABLE:
  c,h,w=by[t['issue_from']],by[t['issuer_host_row']],by[t['row']];iss=h['issuance'];win=iss['window']
  need(iss['controller_row']==c['id'] and iss['slot']==t['issuer_slot'],'fixed issuer stage mapping')
  need(c['window']['start_ns']<win['start_ns']<win['stop_ns']<c['window']['stop_ns']==h['window']['start_ns']<h['window']['stop_ns']==w['window']['start_ns']<w['window']['stop_ns'],'full prelude/issuer/postlude/dispatch/worker schedule')
  for k in LOGICAL:
   need(iss['logical'][k]>0 and iss['logical'][k]+iss['dispatch_logical'][k]==h['logical'][k],'issuer+dispatch partition once '+k)
  for k in PHYSICAL:need(iss['physical'][k]+iss['dispatch_physical'][k]==h['physical'][k],'exact physical parent partition '+k)
  need(iss['physical']['cpu_ns']>0 and iss['physical']['retained_storage_bytes']>0 and
       iss['physical']['process_starts']==0 and iss['physical']['stream_bytes']==0,'issuer has no new child or stdout budget')
  need(w['host_monitor_cpu_ns']<=iss['dispatch_physical']['cpu_ns'],'monitor inside dispatch only')
  need(iss['logical']['read_bytes']>=2*iss['maximum_frame_bytes'] and
       iss['logical']['write_bytes']>=2*iss['maximum_frame_bytes'],'full two-ended exchange extents before source traversal')
  for k in PEAKS:need(iss['peaks'][k]<=min(c['peaks'][k],h['peaks'][k],body['whole_peak_limits'][k]),'whole conservative issuer peak')
  a=adapter_by[h['adapter_reservation_id']]
  need(a['wall_ns']==win['stop_ns']-win['start_ns']+w['window']['stop_ns']-h['window']['start_ns'],'two disjoint original H wall windows, no gap or reset')
 for left,right in [('WA','WB'),('HA0','HB0'),('HA1','HB1')]:
  a,b=by[left],by[right]
  for k in ['logical','physical','peaks','host_monitor_cpu_ns','host_monitor_memory_bytes','host_monitor_pids','controller_idle_memory_bytes','controller_idle_pids']:
   need(same(a[k],b[k]),'exact protected A/B '+k)
  need(duration(a)==duration(b),'same fixed full candidate duration')
 a,b=by['HA0']['issuance'],by['HB0']['issuance']
 for k in a:
  if k not in ('slot','controller_row','window'):need(same(a[k],b[k]),'equal issuer source/cap '+k)
 need(duration(a)==duration(b),'equal issuer duration')
 # Ordinary schema/source checks above are not an invented qualification of
 # total start/stream opportunity, per-process attribution or actual capacity.
 return ReservationPlan(_PLAN,body,descriptor,resource_body,resource_pin)
