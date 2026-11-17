"""Actual C lease/return caller over the adopted five-stage wire contracts.

The independently qualified H/root produces each Lease and later original
StartBinding. This module does not invent a parked-worker transport or PID.
Missing launch qualification is still a real refusal outside this C consumer.
"""
from pathlib import Path
from .stage_budget import ExclusiveBudget
from .stage_closure import consume_stage,STAGES,StageAdmission
from .output_contract import OutputContract
from .authorization_v4 import COMMON,EXTRA
from .poststage import CompletionCoordinator
from four_programmes.common import need,closed,encode,pin,parse,Store,failure,bounded_size
from four_programmes.schema import check
from four_programmes.source_session import SourceSession
from four_programmes.authority_files import RootAuthorityFiles,RootFileEvent
from four_programmes.resources import RootResources
from four_programmes.channel import HostEvent

class StageCoordinator:
    def __init__(self,*,session,root,budget,scope,census,census_pin,contract,
                 resources,bridge_store,authority_channel,schemas,profile,profile_pin,
                 clock,controller,bridge_reservations,physical_limits):
        need(type(session) is SourceSession and session.programme=='PAPER-FIND-050' and
             type(budget) is ExclusiveBudget and budget._owner=='C' and budget._active and
             budget.generation==0 and budget._previous_return is None and not budget._failure_only,
             'actual original C source and initial exclusive Budget')
        need(type(contract) is OutputContract and type(resources) is RootResources and
             not resources.staged and resources.delegated and resources.terminal is None and
             resources.plan['programme']=='PAPER-FIND-050' and resources.plan['campaign_id']==budget.campaign_id,
             'actual same delegated original whole opportunity')
        need(type(bridge_store) is Store and type(authority_channel) is RootAuthorityFiles and
             authority_channel.store.meter is bridge_store.meter and
             any(k[0]=='H' and share is bridge_store.meter for k,share in resources.shares.items()),
             'actual earlier root-owned bridge share and fixed authority channel')
        for name,value in (('Profile',profile),('ClockBinding',clock)):
            schemas.validate('ci',name,value,bridge_store.meter)
        bridge_store.meter.charge('work_units',bounded_size(controller))
        identity_schema=schemas.tables['ci']['Lease']
        check(controller,identity_schema['properties']['controller'],root=identity_schema)
        need(profile['campaign_id']==clock['campaign_id']==budget.campaign_id and
             profile['full_census']==census_pin==contract.body['census'] and
             profile['clock_binding']==budget.clock_binding and
             budget.origin==clock['origin_seconds'] and budget.deadline==clock['run_deadline_seconds'],
             'same complete original census and unrenewed clock')
        limits=resources.plan['programme_budget']
        need(limits['kind']=='critical_init_exclusive_cumulative_budget_v3' and
             limits['read_bytes']==budget.read_cap and limits['write_bytes']==budget.write_cap and
             limits['array_bytes']==budget.array_cap and limits['seconds']==budget.deadline-budget.origin and
             limits['clock_binding']==budget.clock_binding and limits['lifecycle_profile']==profile_pin,
             'exact original programme limits and admitted lifecycle profile')
        need(len(scope.panel_ids)==76 and census['scope_digest']==scope.digest==contract.body['scope_digest'],
             'whole original 76-panel census and report contract')
        # Each reservation is already selected in the independent root plan.
        # Actual shared H/C counter and process attribution remain a separate
        # qualified source boundary; this list does not manufacture that owner.
        need(type(bridge_reservations) is list and bridge_reservations,
             'earlier exact H bootstrap/terminal reservation descriptors')
        need(type(physical_limits) is dict and set(physical_limits)=={'cpu_ns','memory_peak','storage_bytes'},
             'same selected complete physical limit dimensions')
        hard=resources.plan['hard_envelope']
        need(physical_limits=={'cpu_ns':hard['cpu_ns'],'memory_peak':hard['memory_bytes'],
                               'storage_bytes':hard['retained_storage_bytes']},
             'physical allowances come from the original whole root plan')
        self.session=session;self.root=Path(root);self.budget=budget;self.scope=scope;self.census=census
        self.census_pin=census_pin;self.contract=contract;self.resources=resources;self.bridge=bridge_store
        self.authority_channel=authority_channel;self.schemas=schemas;self.profile=profile
        self.profile_pin=profile_pin;self.clock=clock;self.controller=controller
        self.bridge_reservations=bridge_reservations;self.physical_limits=physical_limits
        self.stages=[];self.pending=None;self.base=None;self.base_pin=None;self.events=[]
        self.primary=None;self.failures=[];self.phase='ready';self._base_bytes=None
        self.reservation_rows={}
        for reservation in bridge_reservations:
            key=encode(reservation);need(key not in self.reservation_rows,'unique original H reservation pin')
            row=self._document(reservation,4194304)
            need(row['owner_role']=='H' and resources.rows.get(('H',row['stage']))==row,
                 'captured exact earlier original root H row, not caller-asserted extra capacity')
            self.reservation_rows[key]=row

    def _own(self,error,where):
        if self.primary is None:self.primary=error
        self.bridge.meter.own_error(error,'CI_serial_'+where)
        self.failures.append({'where':where,'original_error':failure(error),
            'same_first_error':error is self.primary,'known_generation':self.budget.generation,
            'programme_writer_active':self.budget._active,'pending_lease':None if self.pending is None else self.pending['lease_pin'],
            'all_later_stage_and_panel_obligations_retained':True})
        if self.budget._active:self.budget._failure_only=True
        self.phase='failed'

    def _document(self,d,cap):
        # Translate only against the already selected original bridge root.
        # A receipt or later document cannot choose a new filesystem base.
        q=Path(d['path'])
        translated={**d,'path':q.relative_to(self.bridge.root).as_posix()} if q.is_absolute() else d
        return self.bridge.document(translated,cap)

    def publish_base(self):
        need(self.phase=='ready' and self.primary is None and self.pending is None and len(self.stages)<len(STAGES),
             'next full original stage with no outstanding delegation')
        try:
            self.budget.require_operation('stage')
            need(self.budget.generation==len(self.stages) and self.budget.array_live==0,
                 'one serial C generation, never release protected arrays for transfer')
            state=self.budget.snapshot();raw=encode(state)
            local=self.bridge.publish('C_STAGE_'+str(len(self.stages)+1)+'_BASE.json',state)
            self.base=state;self._base_bytes=raw
            self.base_pin={**local,'path':str(self.bridge.root/local['path'])}
            self.phase='awaiting_root_lease';return self.base_pin
        except BaseException as error:self._own(error,'base_publication');raise

    def suspend_for_lease(self,event,lease_pin):
        """Consume the actual root event and frozen Lease before H dispatch.

        The event must carry this exact lease as an original cause artifact.
        No root label/boolean alone grants launch, and no W has been started by
        this function. A failed or unknown downstream dispatch retains this
        entire suspended delegation without a refund or fresh generation.
        """
        need(self.phase=='awaiting_root_lease' and self.primary is None,'one pending C base')
        try:
            ch=self.authority_channel
            need(type(event) is RootFileEvent and event.root_binding==ch.binding_pin and
                 ch.consumed.get(event.body['sequence']) is event and event not in self.events,
                 'actual once-only independently captured root event')
            body=event.body;operation,condition=STAGES[len(self.stages)]
            need(body['verdict']=='admitted' and body['programme']=='PAPER-FIND-050' and
                 body['campaign_id']==self.budget.campaign_id and body['original_budget_snapshot']==self.base_pin and
                 encode(self.budget.snapshot())==self._base_bytes and body['legacy_authority'] is not None,
                 'exact unchanged original C prefix across issuer work')
            causes=[r['identity']for r in body['cause_artifacts']]
            need(lease_pin in causes,'root event binds the exact original lease')
            lease=self._document(lease_pin,4194304)
            self.schemas.validate('ci','Lease',lease,self.bridge.meter)
            authority_pin=body['legacy_authority'];authority=self._document(authority_pin,2000000)
            closed(authority,COMMON|EXTRA[operation])
            need(authority['schema']=='critical_init_root_operation_selection_v4' and
                 authority['selected_operations']==[operation] and authority['condition']==condition and
                 authority['canonical_id']=='PAPER-FIND-050' and authority['issuer_role']=='independent_root_controller' and
                 authority['campaign_id']==self.budget.campaign_id and authority['scope_digest']==self.scope.digest and
                 authority['census_pin']==self.census_pin and authority['job_output_contract']==self.contract.pin and
                 authority['lifecycle_profile']==self.profile_pin,
                 'complete exact operation/arm/output contract in original root authority')
            subject=self._document(authority['pre_run_subject'],2000000)
            closed(subject,('schema','campaign_id','operation','authority_projection'))
            need(subject['schema']=='critical_init_pre_run_authority_subject_v3' and
                 subject['campaign_id']==self.budget.campaign_id and subject['operation']==operation and
                 subject['authority_projection']==pin(encode({k:v for k,v in authority.items() if k!='pre_run_subject'})),
                 'acyclic exact existing pre-run authority subject')
            seq=len(self.stages)+1
            need(lease['sequence']==seq and lease['base_generation']==self.budget.generation and
                 lease['base_state']==self.base_pin and lease['campaign_id']==self.budget.campaign_id and
                 lease['previous_return']==self.budget._previous_return and lease['controller']==self.controller and
                 lease['observer_source']==self.profile['observer_source'] and lease['profile']==self.profile_pin and
                 lease['authority_subject']==authority['pre_run_subject'] and
                 (lease['operation'],lease['condition'])==(operation,condition) and
                 lease['census']==self.census_pin and
                 lease['ordered_job_ids']==[j['id']for j in self.census['jobs'] if j['operation']==operation] and
                 lease['original_run_deadline_ns']==self.clock['run_deadline_ns'] and
                 lease['original_evidence_deadline_ns']==self.clock['evidence_deadline_ns'] and
                 lease['bootstrap_reservation'] in self.bridge_reservations and
                 lease['terminal_channel_reservation'] in self.bridge_reservations,
                 'all original stage domains, owners, predecessor and same selected reservations')
            need(self.reservation_rows[encode(lease['terminal_channel_reservation'])]==self.bridge.meter.row,
                 'actual C terminal reader uses that exact already-reserved original H Share')
            self.contract.require_executable()
            self.events.append(event)
            self.pending={'lease':lease,'lease_pin':lease_pin,'authority':authority,'authority_pin':authority_pin,
                          'operation':operation,'condition':condition,'base':self.base,'base_pin':self.base_pin}
            self.budget.suspend(lease_pin,lease,self.base_pin)
            self.phase='suspended_H_start_and_return_pending'
            return self.pending
        except BaseException as error:self._own(error,'lease_admission');raise

    def consume_return(self,event):
        need(self.phase=='suspended_H_start_and_return_pending' and self.pending is not None and
             self.primary is None,'one exact suspended original stage return')
        try:
            p=self.pending
            need(type(event) is HostEvent,'actual original H terminal channel event')
            stage=consume_stage(event,bridge_meter=self.bridge.meter,schemas=self.schemas,profile=self.profile,
                profile_pin=self.profile_pin,clock=self.clock,base=p['base'],base_pin=p['base_pin'],
                lease=p['lease'],lease_pin=p['lease_pin'],authority_pin=p['authority_pin'],scope_digest=self.scope.digest,
                census=self.census,previous_return=self.budget._previous_return,controller=self.controller,
                expected_operation=p['operation'],expected_condition=p['condition'],
                bridge_reservations=self.bridge_reservations,physical_limits=self.physical_limits,
                output_contract=self.contract,authority_body=p['authority'])
            self.budget.restore(stage)
            self.stages.append(stage);self.pending=None
            if not stage.eligible:
                error=RuntimeError('original stage failed; exact independent evidence remains attached')
                BaseException.__setattr__(error,'original_stage_admission',stage.audit)
                raise error
            self.base=None;self.base_pin=None;self._base_bytes=None
            self.phase='stages_complete' if len(self.stages)==len(STAGES) else 'ready'
            return stage
        except BaseException as error:self._own(error,'return_admission');raise

    def completion_caller(self,*,projection_share,output):
        need(self.phase=='stages_complete' and self.primary is None and self.pending is None,
             'all five original stages closed before collect, never C final exit')
        try:
            result=CompletionCoordinator(session=self.session,root=self.root,budget=self.budget,scope=self.scope,
                census=self.census,census_pin=self.census_pin,contract=self.contract,stages=self.stages,
                authority_channel=self.authority_channel,bridge_store=self.bridge,
                projection_share=projection_share,resources=self.resources,output=output)
            self.phase='delegated_same_C_poststage';return result
        except BaseException as error:self._own(error,'poststage_transfer');raise

