"""Exclusive original HM Budget and all eighteen source-owned row prefixes.

Original scientific methods keep the original Budget interface/snapshot. The
new state is a separate exact protocol record, never a maxima-based merge.
"""
import time
from .guard import Budget
from .fixed_tables import ROW_OWNERS,STAGE_TABLE,RECORD_FIELDS,RECORD_VERSIONS
from .reservations import ReservationPlan,LOGICAL,NAMES,validate_type
from four_programmes.common import need,closed,integer,encode,pin,same

_IMMUTABLE=('campaign_id','original_clock_binding','deadline_ns','limits','reservation_plan')
_MODES=('active_C','delegated_base','terminal_W','failed_C')

def state_valid(state,plan):
 need(type(plan)is ReservationPlan,'actual full fixed plan compiler')
 closed(state,RECORD_FIELDS['HMState']);need(state['schema']==RECORD_VERSIONS['HMState'],'exact HM v2 state')
 integer(state['generation']);need(state['generation']<=3 and state['mode'] in _MODES and type(state['failed'])is bool,'fixed generation/owner/failure')
 closed(state['limits'],LOGICAL);closed(state['used'],LOGICAL)
 for k in LOGICAL:integer(state['limits'][k],1);integer(state['used'][k])
 need(state['campaign_id']==plan.body['campaign_id'] and state['original_clock_binding']==plan.body['clock_binding'] and
      state['deadline_ns']==plan.body['run_deadline_ns'] and state['limits']==plan.body['programme_limits'] and
      state['reservation_plan']==plan.pin,'one original immutable full programme opportunity')
 if state['previous_return'] is not None:validate_type(state['previous_return'],'Descriptor')
 need((state['previous_return'] is None)==(state['generation']==0 or state['mode']=='terminal_W' and state['generation']==1),
      'null predecessor only original first generation/first W terminal')
 rows=state['row_usage'];need(type(rows)is list and [r['id']for r in rows]==list(NAMES),'all eighteen ordered row prefixes')
 for row in rows:
  closed(row,('id','logical'));closed(row['logical'],LOGICAL)
  for k in LOGICAL:
   n=row['logical'][k];integer(n)
   if plan.rows[row['id']]['owner']=='H':need(n==0,'H transport never duplicates programme logical usage')
   if not state['failed']:need(n<=plan.rows[row['id']]['logical'][k],'successful row fits own ceiling')
 for k in LOGICAL:
  need(sum(r['logical'][k]for r in rows)==state['used'][k],'exact row partition of original attempted usage')
  if not state['failed']:need(state['used'][k]<=state['limits'][k],'successful original global cap')
 return state

def lease_scalars(lease):
 """Exact adopted scalar identities; bool is never generation or sequence1."""
 closed(lease,RECORD_FIELDS['HMLease'])
 need(lease['schema']==RECORD_VERSIONS['HMLease'],'fixed original lease schema')
 integer(lease['sequence'],1);need(lease['sequence']<=3,'original three-stage sequence')
 integer(lease['base_generation']);need(lease['base_generation']<=2,'original pre-worker generation')
 integer(lease['original_deadline_ns'],1)
 return lease

def exact_successor(base,terminal,plan,*,sequence):
 state_valid(base,plan);state_valid(terminal,plan);t=STAGE_TABLE[sequence-1]
 need(base['mode']=='delegated_base' and terminal['mode']=='terminal_W' and
      base['generation']==t['base_generation'] and terminal['generation']==base['generation']+1,
      'exact original g to g+1 W terminal')
 need(all(same(base[k],terminal[k])for k in _IMMUTABLE) and base['previous_return']==terminal['previous_return'],
      'same original limits/clock/predecessor, no future-return hash')
 for a,b in zip(base['row_usage'],terminal['row_usage']):
  for k in LOGICAL:
   need(b['logical'][k]>=a['logical'][k] and (a['id']==t['row'] or b['logical'][k]==a['logical'][k]),
        'only this actual W row extends prior prefix')
 need(not base['failed'],'failed base cannot be delegated')
 return terminal

class ExclusiveBudget(Budget):
 def __init__(self,state,*,plan,owner,row,lease=None):
  state_valid(state,plan);need(owner in ('C','W') and row in plan.rows and plan.rows[row]['owner']==owner,'fixed source owner and row')
  self.plan=plan;self.owner=owner;self.row=row;self.generation=state['generation'];self.previous_return=state['previous_return']
  self.rows={r['id']:dict(r['logical'])for r in state['row_usage']};self.active=True;self.primary=None;self.secondary=[]
  self.pending=None;self.consumed={};self.guard=None;self.issuer_tokens={};self.lease=lease;self.score_reserved=False
  Budget.__init__(self,**state['limits'],deadline_ns=state['deadline_ns'])
  self.used=dict(state['used']);self.failed=state['failed']
  if owner=='C':
   need(state['mode']=='active_C' and row=='C'+str(self.generation).zfill(2),'C resumes in exact original row')
  else:
   need(type(lease)is dict,'worker requires exact original lease');lease_scalars(lease)
   need(lease['schema']==RECORD_VERSIONS['HMLease'],'fixed lease version')
   t=plan.stage(lease['sequence']);need(row==t['row'] and state['mode']=='delegated_base' and
      lease['base_generation']==state['generation']==t['base_generation'] and lease['previous_return']==state['previous_return'] and
      lease['reservation_plan']==plan.pin and lease['reservation_row']==row and lease['original_deadline_ns']==self.deadline_ns,
      'worker original lease/base/row predecessor')
  need(not self.failed,'failed original budget cannot bootstrap a writer')
  # Creation occurs under the earlier bootstrap share. W readiness is separately
  # observed before row start; check() never admits an early original API call.
 def _own(self,error):
  if self.primary is None:self.primary=error
  elif self.primary is not error:self.secondary.append(error)
  self.failed=True
 def _state(self,mode):
  s={'schema':RECORD_VERSIONS['HMState'],'campaign_id':self.plan.body['campaign_id'],
     'original_clock_binding':self.plan.body['clock_binding'],'deadline_ns':self.deadline_ns,
     'limits':dict(self.limits),'used':dict(self.used),'failed':self.failed,'generation':self.generation,
     'mode':mode,'previous_return':self.previous_return,'reservation_plan':self.plan.pin,
     'row_usage':[{'id':n,'logical':dict(self.rows[n])}for n in NAMES]}
  return state_valid(s,self.plan)
 def state(self):
  need(self.active and self.owner=='C','only active C current prefix')
  return self._state('failed_C'if self.failed else 'active_C')
 def check(self):
  try:
   need(self.active and self.guard is None,'sole original writer; issuer guard forbids programme work')
   Budget.check(self)
   now=time.monotonic_ns();win=self.plan.rows[self.row]['window']
   need(win['start_ns']<=now<win['stop_ns'],'fixed absolute row window, no early/late work')
   for k in LOGICAL:need(self.rows[self.row][k]<=self.plan.rows[self.row]['logical'][k],'original row attempt within cap')
  except BaseException as error:self._own(error);raise
 def charge(self,kind,n):
  before=self.used.get(kind);primary=None
  try:Budget.charge(self,kind,n)
  except BaseException as error:primary=error;self._own(error)
  # Preserve original increment-before-limit semantics, including attempted
  # overcap. A pre-effect check failure has delta zero, never invented usage.
  if kind in LOGICAL:
   delta=self.used[kind]-before;self.rows[self.row][kind]+=delta
   try:need(self.rows[self.row][kind]<=self.plan.rows[self.row]['logical'][kind],'row limit; attempted prefix retained')
   except BaseException as error:
    self._own(error)
    if primary is None:primary=error
  if primary is not None:raise primary
 def require_operation(self,operation):
  allowed={'C00':('prepare','subject','lease'),'C01':('subject','lease'),'C02':('capture_A','subject','lease'),
           'C03':('capture_B','seal'),'C04':('protected_reference',),'C05':('score','arms','report'),
           'WR':('reference',),'WA':('candidate:A',),'WB':('candidate:B',)}
  self.check()
  try:need(operation in allowed[self.row],'full fixed source operation belongs this row')
  except BaseException as error:self._own(error);raise
 def arm_issuer(self):
  self.require_operation('subject');need(self.owner=='C' and self.row in self.plan.issuer_by_C and self.guard is None,'one exact current C issuer prelude')
  alloc=self.plan.issuer_by_C[self.row];need(time.monotonic_ns()<alloc['window']['start_ns'],'ready with full prelude before original I start')
  state=self._state('active_C');self.guard={'phase':'armed','snapshot':encode(state),'allocation':alloc,'response':None}
  return state
 def enter_issuer_wait(self):
  need(self.active and self.guard is not None and self.guard['phase']=='armed' and not self.failed,'original armed prefix')
  a=self.guard['allocation'];now=time.monotonic_ns()
  need(a['window']['start_ns']<=now<a['window']['stop_ns'] and encode(self._state('active_C'))==self.guard['snapshot'],'exact fixed issuer interval and unchanged C prefix')
  self.guard['phase']='waiting'
  return self.guard['snapshot']
 def admit_issuer_response(self,admission):
  from .issuance import IssuanceAdmission
  need(type(admission)is IssuanceAdmission,'actual qualified source-owned issuer response only')
  need(self.guard is not None and self.guard['phase']=='waiting' and not self.failed,'one original issuer wait')
  a=self.guard['allocation'];now=time.monotonic_ns()
  need(a['window']['start_ns']<=now<a['window']['stop_ns'] and
       admission.plan is self.plan and admission.slot==a['slot'] and
       admission.guard_raw==self.guard['snapshot'] and not admission.consumed and
       encode(self._state('active_C'))==self.guard['snapshot'],'actual response before original stop with unchanged Budget')
  self.guard['response']=admission;self.guard['phase']='received'
 def finish_issuer_wait(self):
  need(self.guard is not None and self.guard['phase']=='received' and not self.failed,'complete actual response only')
  a=self.guard['allocation'];now=time.monotonic_ns()
  need(a['window']['stop_ns']<=now<self.plan.rows[self.row]['window']['stop_ns'] and
       encode(self._state('active_C'))==self.guard['snapshot'],'same unchanged prefix at original postlude')
  self.issuer_tokens[self.row]=self.guard['response'];self.guard=None
  return self.state()
 def freeze_base(self):
  self.require_operation('lease');need(self.row in self.issuer_tokens,'actual original issuer token before lease')
  return self._state('delegated_base')
 def suspend(self,lease,lease_pin,base,base_pin):
  self.require_operation('lease');lease_scalars(lease);validate_type(lease_pin,'Descriptor');validate_type(base_pin,'Descriptor')
  t=self.plan.stage(lease['sequence']);token=self.issuer_tokens.get(self.row)
  need(lease['schema']==RECORD_VERSIONS['HMLease'] and self.owner=='C' and self.pending is None and
       self.row==t['issue_from'] and self.generation==t['base_generation'],'one exact next serial lease')
  need(base==self._state('delegated_base') and pin(encode(base))=={k:base_pin[k]for k in ('bytes','sha256')} and
       pin(encode(lease))=={k:lease_pin[k]for k in ('bytes','sha256')},'actual fresh postlude base/lease bytes')
  need(lease['base_state']==base_pin and lease['base_generation']==self.generation and lease['previous_return']==self.previous_return and
       lease['reservation_plan']==self.plan.pin and lease['reservation_row']==t['row'] and
       lease['original_deadline_ns']==self.deadline_ns and lease['base_row']==self.row,'complete original lease lineage')
  need(token is not None and not token.consumed and lease['invocation_authority']==token.authority_pin and
       lease['authority_subject']==token.subject_pin,'one actual source issuer token for this lease')
  self.plan.future_feasible({name:self.rows[name] for name in self.plan.programme_rows})
  token.consume_for_lease(lease,lease_pin,self)
  self.pending={'lease':lease,'pin':dict(lease_pin),'base':base,'base_pin':dict(base_pin)};self.active=False
  return base
 def export_terminal(self):
  need(self.owner=='W' and self.active,'one actual original W terminal')
  if not self.failed:self.check()
  # No original managed operation is allowed after this state is frozen. Its
  # publication belongs the already selected H terminal share.
  self.generation+=1;state=self._state('terminal_W');self.active=False;return state
 def restore(self,admission):
  try:
   need(not self.failed,'failed original writer cannot be revived by a later return')
   return self._restore(admission)
  except BaseException as error:self._own(error);raise
 def _restore(self,admission):
  from .stage_closure import StageAdmission
  need(type(admission)is StageAdmission,'actual full H closure consumer only')
  key=encode(admission.return_pin);terminal=admission.terminal
  if key in self.consumed:
   old=self.consumed[key];need(old is admission or old.fingerprint==admission.fingerprint,'no conflicting original return replay')
   return {'already_consumed':True,'state_mutated':False}
  need(self.owner=='C' and not self.active and self.pending is not None,'only original suspended C')
  p=self.pending;lease=p['lease'];ret=admission.budget_return
  need(admission.plan is self.plan and admission.lease_pin==p['pin'] and ret['base_state']==p['base_pin']==ret['restore_parent'] and
       ret['previous_return']==self.previous_return==lease['previous_return'] and ret['invocation_authority']==lease['invocation_authority'],
       'same actual pending lease/base/invocation/predecessor')
  exact_successor(p['base'],terminal,self.plan,sequence=lease['sequence'])
  need(admission.eligible and ret['disposition']=='eligible_exact_successor' and ret['terminal_generation']==terminal['generation'] and
       not terminal['failed'] and not ret['unknown_dimensions'],'only complete known successful exact return may restore')
  self.used=dict(terminal['used']);self.rows={r['id']:dict(r['logical'])for r in terminal['row_usage']}
  self.generation=terminal['generation'];self.previous_return=dict(admission.return_pin)
  self.row=self.plan.stage(lease['sequence'])['restore_into'];self.pending=None;self.active=True;self.consumed[key]=admission
  return {'already_consumed':False,'state_mutated':True}
 def advance_final_row(self,next_row):
  self.check();need(self.owner=='C' and self.generation==3 and self.pending is None,'all three original W closures consumed')
  need((self.row,next_row) in (('C03','C04'),('C04','C05')),'full ordered final target/score rows')
  # The caller waits under its actual earlier H transport/physical reservation;
  # no programme work occurs across the fixed interval boundary.
  need(time.monotonic_ns()<self.plan.rows[next_row]['window']['start_ns'],'ready before next fixed row')
  self.row=next_row
 def reserve_complete_score(self):
  self.require_operation('score');need(not self.score_reserved,'one complete full-domain score reservation')
  self.score_reserved=True
  credit={k:self.plan.rows['C05']['logical'][k]-self.rows['C05'][k]for k in LOGICAL}
  for k in LOGICAL:self.charge(k,credit[k])
  return PrepaidScoreIO(self,credit)

class PrepaidScoreIO:
 """One C05 full reservation, consumed by actual report IO without double charge.

 Unmetered original score/arms use the full work reservation. Original later
 Publisher/capture calls consume only this same finite already-reserved credit.
 No stage export follows C05; underlying original used remains fully reserved.
 """
 def __init__(self,budget,credit):
  need(type(budget)is ExclusiveBudget and budget.row=='C05' and budget.score_reserved,'actual full original score reservation')
  self.budget=budget;self.remaining=dict(credit);self.attempted=dict.fromkeys(LOGICAL,0)
 def check(self):return self.budget.check()
 def snapshot(self):return self.budget.snapshot()
 def charge(self,kind,n):
  self.check();need(kind in LOGICAL,'closed original category');integer(n)
  self.attempted[kind]+=n
  if n>self.remaining[kind]:
   # Retain only the actual attempted amount beyond already reserved bytes.
   # The original global/row attempted-overcap semantics then stop the caller.
   extra=n-self.remaining[kind];self.remaining[kind]=0;self.budget.charge(kind,extra)
  else:self.remaining[kind]-=n
