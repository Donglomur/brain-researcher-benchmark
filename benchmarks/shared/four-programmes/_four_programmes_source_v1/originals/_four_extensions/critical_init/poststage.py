"""Actual CI C collection -> both seals -> protected grade -> all76 panels.

The complete five original W admissions precede this caller. Original source
methods remain original; root events and the same cumulative Budget are used.
This does not supply the missing independent root issuer or parked-W profile.
"""
from pathlib import Path
from .stage_budget import ExclusiveBudget
from .stage_closure import StageAdmission,STAGES
from .output_contract import OutputContract
from .workflow_v4 import selected_plan,collect,protected_grade
from .custody import encode as original_encode,write_new,read_pin,parse as original_parse
from .scoring import report as original_report
from four_programmes.common import need,pin,encode,failure,bounded_size,Store
from four_programmes.source_session import SourceSession
from four_programmes.authority_files import RootAuthorityFiles,RootFileEvent
from four_programmes.resources import RootResources,Share
from four_programmes.ci_panels import seal_collections,project_panels,ARMS

class CompletionCoordinator:
    """The still-live original C; never claims its own original natural exit."""
    def __init__(self,*,session,root,budget,scope,census,census_pin,contract,stages,
                 authority_channel,bridge_store,projection_share,resources,output):
        need(type(session) is SourceSession and session.programme=='PAPER-FIND-050' and
             type(budget) is ExclusiveBudget and budget._owner=='C' and budget._active,
             'actual admitted original CI session and current exclusive C writer')
        need(type(contract) is OutputContract and type(authority_channel) is RootAuthorityFiles and
             type(bridge_store) is Store,'original full compiled output ABI and root event channel')
        need(len(stages)==len(STAGES) and all(type(s) is StageAdmission for s in stages),
             'all five actual source-owned stage admissions before collection')
        need(budget.generation==5 and budget._previous_return==stages[-1].return_pin and
             not budget._failure_only,'actual final successful exact return consumed')
        previous=None
        for sequence,(stage,operation) in enumerate(zip(stages,STAGES),1):
            need(stage.eligible and (stage.lease['operation'],stage.lease['condition'])==operation and
                 stage.lease['sequence']==sequence and stage.lease['previous_return']==previous and
                 stage.lease['census']==census_pin and stage.output_contract is contract and
                 stage.lease['campaign_id']==budget.campaign_id and
                 budget._consumed_returns.get(encode(stage.return_pin))==encode(stage.terminal),
                 'entire original stage order, exact predecessors and actually consumed returns')
            previous=stage.return_pin
        need(len(scope.panel_ids)==76 and census['scope_digest']==scope.digest and
             contract.body['scope_digest']==scope.digest and contract.body['census']==census_pin,
             'full original 76-panel source/census/output contract')
        need(type(resources) is RootResources and not resources.staged and resources.delegated and
             resources.terminal is None and resources.plan['programme']=='PAPER-FIND-050' and
             resources.plan['campaign_id']==budget.campaign_id and type(projection_share) is Share,
             'actual one delegated original root resource owner and source-selected C share')
        need(authority_channel.store.meter is bridge_store.meter and
             any(key[0]=='H' and share is bridge_store.meter for key,share in resources.shares.items()) and
             any(key[0]=='C' and share is projection_share for key,share in resources.shares.items()),
             'both exact cached shares belong the same original resource owner, no newly supplied allowance')
        limits=resources.plan['programme_budget']
        need(limits['kind']=='critical_init_exclusive_cumulative_budget_v3' and
             limits['read_bytes']==budget.read_cap and limits['write_bytes']==budget.write_cap and
             limits['array_bytes']==budget.array_cap and limits['seconds']==budget.deadline-budget.origin and
             limits['clock_binding']==budget.clock_binding,'same complete original programme delegation and clock')
        self.session=session;self.root=Path(root);self.budget=budget;self.scope=scope;self.census=census
        self.census_pin=census_pin;self.contract=contract;self.stages=tuple(stages)
        self.authority_channel=authority_channel;self.bridge=bridge_store;self.projection_share=projection_share
        self.resources=resources
        self.output=Path(output);self.collections={};self.seals={};self.grade=None;self.grade_pin=None
        self.reference_banks=None;self.report=None;self.report_pin=None;self.failures=[];self.primary=None
        self.events=[];self.phase='collect_A';self.last_prefix=None
        self.projection_pin=None;self.final_notice_attempted=False;self.final_notice_pin=None
        self.final_budget_state=None

    def publish_authority_prefix(self,name):
        """Bounded H bridge publication of this actual C prefix, before issuer work.

        Reading a supplied snapshot is never a budget restore. This method
        grants no issuer authority and does not change the programme counters.
        """
        need(self.budget._active and (self.primary is None or self.phase=='failed'),
             'actual current C prefix, including exact failure-only report prefix')
        self.budget.check();state=self.budget.snapshot()
        d=self.bridge.publish(name,state)
        self.last_prefix=({'path':str(self.bridge.root/d['path']),**{k:d[k] for k in ('bytes','sha256')}},encode(state))
        return self.last_prefix[0]

    def _authority(self,event,operation,required_causes):
        ch=self.authority_channel
        need(type(event) is RootFileEvent and event.root_binding==ch.binding_pin and
             ch.consumed.get(event.body['sequence']) is event and event not in self.events,
             'once-only actually captured independent root event')
        body=event.body
        need(body['verdict']=='admitted' and body['programme']=='PAPER-FIND-050' and
             body['campaign_id']==self.budget.campaign_id and body['legacy_authority'] is not None,
             'same original independently admitted operation authority')
        need(self.last_prefix is not None and body['original_budget_snapshot']==self.last_prefix[0] and
             encode(self.budget.snapshot())==self.last_prefix[1],
             'actual unchanged C prefix across root wait, no supplied budget replacement')
        causes=[row['identity'] for row in body['cause_artifacts']]
        need(all(d in causes for d in required_causes),
             'all locally required original stage/seal/grade identities in root cause chain')
        # Additional root causes are never dereferenced or treated as a result.
        self.events.append(event);self.last_prefix=None
        selection,scope,census=selected_plan(self.root,body['legacy_authority'],self.budget,operation)
        need(scope.digest==self.scope.digest and original_encode(census)==original_encode(self.census) and
             selection.body['census_pin']==self.census_pin,'same complete source plan on every original call')
        return body['legacy_authority'],selection

    def _own(self,error,operation):
        if self.primary is None:self.primary=error
        state=None;secondary=None
        try:state=self.budget.snapshot() if self.budget._active else None
        except BaseException as observed:secondary=failure(observed)
        self.failures.append({'whole_campaign':True,'operation':operation,'original_error':failure(error),
                              'same_primary':error is self.primary,'budget':state,'snapshot_failure':secondary})
        self.phase='failed';self.bridge.meter.own_error(error,'CI_'+operation)
        self.budget._failure_only=True

    def collect_arm(self,arm,event):
        expected='collect_A' if arm=='paper_data' else 'collect_B'
        need(arm in ARMS and self.phase==expected and self.primary is None,'both complete arms in fixed original order')
        try:
            causes=[s.completion_pin for s in self.stages]
            authority,_=self._authority(event,'collect',causes)
            stage=self.stages[3 if arm==ARMS[0] else 4]
            result=collect(self.root,authority,self.budget,arm,stage_admission=stage)
            need(result['condition']==arm and result['protected_targets_opened'] is False and
                 set(result['results'])=={j['id'] for j in self.census['jobs'] if j['operation']=='candidate'},
                 'full original arm collection, including every failed job')
            self.collections[arm]=result
            # Preserve exact original codec bytes. Actual managed write is
            # charged before the next prefix/authority; no self-hash cycle.
            raw=original_encode(result)
            name='COLLECTION_A.json' if arm==ARMS[0] else 'COLLECTION_B.json'
            descriptor=write_new(self.output/name,raw,self.budget)
            self.seals[arm]={'raw':raw,'identity':pin(raw),'descriptor':descriptor}
            self.phase='collect_B' if arm==ARMS[0] else 'both_sealed'
            return descriptor
        except BaseException as error:self._own(error,'collect_'+arm);raise

    def recapture_both_seals(self):
        need(self.phase=='both_sealed' and self.primary is None and set(self.seals)==set(ARMS),
             'actual complete paired publications precede any protected reference read')
        try:
            checked=seal_collections(self.collections,original_encode)
            for arm in ARMS:
                need(checked[arm]['raw']==self.seals[arm]['raw'] and
                     read_pin(self.root,self.seals[arm]['descriptor'],len(checked[arm]['raw']),self.budget)==checked[arm]['raw'],
                     'actual complete original collection bytes remain sealed')
            # The just-performed read changes the real Budget. The caller must
            # publish/wait for a root prefix after this preparatory verification.
            self.phase='seals_recaptured'
            return {'ready_for_grade_authority':True,'sealed_collections':{a:self.seals[a]['descriptor'] for a in ARMS}}
        except BaseException as error:self._own(error,'grade_seal_recapture');raise

    def protected_grade(self,event):
        need(self.phase=='seals_recaptured' and self.primary is None,'both original seal recaptures before root grade event')
        try:
            authority,selection=self._authority(event,'grade',[self.seals[a]['descriptor'] for a in ARMS])
            need(selection.body['sealed_collection_pins']=={a:self.seals[a]['descriptor'] for a in ARMS},
                 'exact both actual managed collection publications in grade authority')
            self.grade=protected_grade(self.root,authority,self.budget,self.collections)
            self.reference_banks=selection.body['protected_reference_banks']
            raw=original_encode(self.grade);self.grade_pin=write_new(self.output/'GRADE.json',raw,self.budget)
            self.phase='graded';return self.grade_pin
        except BaseException as error:self._own(error,'protected_grade');raise

    def report_all(self,event,*,gates,conflicts,context_admissions,whole_costs):
        need(self.phase=='graded' and self.primary is None,'full original paired grade precedes normal report')
        meter=self.projection_share;begun=False;primary=None;result=None
        try:
            self._authority(event,'report',[self.grade_pin])
            # Consume the full earlier selected common-work reservation before
            # building support/projection trees. This is a finite reservation,
            # not a fabricated measurement or an assertion of sufficient cost.
            meter.begin();begun=True
            for category in ('work_units','retained_bytes'):
                meter.charge(category,meter.limits[category]-meter.spent[category])
            need(set(gates)=={g['id'] for g in self.scope.gates} and
                 set(conflicts)=={c['id'] for c in self.scope.conflicts},'all original gate/conflict outcomes')
            support={}
            for job in self.census['jobs']:
                rows=[{'operation':s.lease['operation'],'condition':s.lease['condition'],
                       'stage_completion':s.completion_pin,'budget_return':s.return_pin,
                       'original_job_evidence':s.job_evidence[job['id']]}
                      for s in self.stages if job['id'] in s.job_evidence]
                support[job['id']]={'job_id':job['id'],'status':'admitted_complete' if rows and
                    all(r['original_job_evidence']['status']=='original_process_closed' for r in rows) else 'required_unscorable',
                    'all_original_stage_rows':rows}
            # Charge complete metadata before projection/report, retain original
            # programme array reservations through this entire source call.
            panels,metrics=project_panels(self.scope,self.census,self.census_pin,self.collections,self.grade,
                                         support,self.reference_banks,context_admissions,self.failures)
            result=original_report(self.scope,panels,metrics,gates=gates,conflicts=conflicts,
                                   costs=whole_costs,failures=self.failures)
            need(set(result['panels'])==set(self.scope.panel_ids) and result['mandatory_panel_count']==76,
                 'all original 76 mandatory panels retained')
            detail={'schema':'critical_init_full_original_panel_projection_v2','panels':panels,'metrics':metrics,
                    'source_stage_completions':[s.completion_pin for s in self.stages],
                    'sealed_collections':{a:self.seals[a]['descriptor'] for a in ARMS},'original_grade':self.grade_pin,
                    'original_C_natural_exit_observed':False,'whole_campaign_success':False}
            self.projection_pin=write_new(self.output/'PANEL_PROJECTION.json',original_encode(detail),self.budget)
            self.report_pin=write_new(self.output/'REPORT.json',original_encode(result),self.budget)
            self.report=result;self.budget.check();meter.check()
        except BaseException as error:primary=error;self._own(error,'whole_report')
        if begun:
            try:meter.end()
            except BaseException as error:
                if primary is None:primary=error;self._own(error,'whole_report_end')
                else:meter.cleanup_errors.append(failure(error))
        if primary is not None:raise primary
        self.phase='reported_provisional';return self.report_pin

    def report_failure_all(self,event,*,gates,conflicts,whole_costs):
        """Keep every mandatory panel when an original collection/grade failed.

        No missing collection, metric, qualified workspace or scientific result
        is constructed. Only an active known original Budget may publish this;
        an unknown worker return stays with the separate H attempt-failure path.
        """
        need(self.phase=='failed' and self.primary is not None and self.budget._active and
             self.budget._failure_only,'original known failed C prefix, report-only')
        primary=self.primary;meter=self.projection_share;begun=False
        try:
            self._authority(event,'report',[s.completion_pin for s in self.stages])
            meter.begin();begun=True
            for category in ('work_units','retained_bytes'):
                meter.charge(category,meter.limits[category]-meter.spent[category])
            panels={p:{'schema':'critical_init_panel_collection_v2','panel_id':p,'status':'required_unscorable',
                       'census':self.census_pin,'reason':'original whole campaign failure',
                       'original_failures':list(self.failures)} for p in self.scope.panel_ids}
            result=original_report(self.scope,panels,{p:None for p in self.scope.panel_ids},
                                   gates=gates,conflicts=conflicts,costs=whole_costs,failures=self.failures)
            self.report_pin=write_new(self.output/'FAILURE_REPORT.json',original_encode(result),self.budget)
            self.report=result
        except BaseException as secondary:
            self.bridge.meter.cleanup_errors.append(failure(secondary))
            try:BaseException.__setattr__(primary,'four_CI_failure_report',
                {'report':self.report_pin,'publication_error':failure(secondary),'whole_campaign_success':False})
            except BaseException as attachment:self.bridge.meter.cleanup_errors.append(failure(attachment))
        if begun:
            try:meter.end()
            except BaseException as secondary:self.bridge.meter.cleanup_errors.append(failure(secondary))
        # A failed campaign always preserves the original failure, even when
        # its complete bounded report happened to publish successfully.
        raise primary

    def send_final_notice(self,channel):
        """Send once, close this source session, and leave C free to exit.

        C must never wait for H's final response: H can authenticate original C
        exit only after this call returns and the actual coordinator exits.
        The outer entry must re-raise any retained original campaign failure.
        """
        from four_programmes.channel import RootChannel
        need(type(channel) is RootChannel and channel.binding['campaign']==self.budget.campaign_id and
             self.phase in ('reported_provisional','failed') and self.report_pin is not None and
             not self.final_notice_attempted,'one source-owned terminal report notice')
        self.final_notice_attempted=True;primary=self.primary
        try:
            self.session.close()
            terminal=self.budget.export_controller_terminal(failure_only=primary is not None)
            self.final_budget_state=terminal
            body={'schema':'four_original_coordinator_final_notice_v1','programme':'PAPER-FIND-050',
                  'campaign':self.budget.campaign_id,'report':self.report_pin,
                  'report_kind':'failure_path' if primary is not None else 'normal_path_provisional',
                  'terminal_budget_state':terminal,'last_stage_return':self.stages[-1].return_pin,
                  'original_C_exit_observed':False}
            self.final_notice_pin=channel.send('final_report',body)
        except BaseException as error:
            if primary is None:primary=error;self._own(error,'final_notice')
            else:self.bridge.meter.cleanup_errors.append(failure(error))
        try:channel.close()
        except BaseException as error:
            if primary is None:primary=error;self._own(error,'final_channel_close')
            else:self.bridge.meter.cleanup_errors.append(failure(error))
        if primary is not None:raise primary
        self.phase='final_notice_sent_C_exit_pending';return self.final_notice_pin

def _next_original_authority(owner,label):
    """Actual source-owned prefix -> selected file event, without a callback.

    Event names come from the already admitted finite private channel. Their
    labels do not determine a scientific operation: _authority independently
    admits the exact original operation and all actual causes at the consumer.
    """
    channel=owner.authority_channel
    need(not channel.closed and channel.position<len(channel.binding['ordered_stages']),
         'one remaining original root event within the fixed selected channel')
    owner.publish_authority_prefix('C_POST_'+label+'_PREFIX.json')
    return channel.next(channel.binding['ordered_stages'][channel.position])

def current_costs(owner):
    """Original snapshots, not caller-supplied costs or final physical proof.

    The record precedes report writes and final H observation. Those later
    prefixes remain in the actual terminal BudgetState and outer H record;
    they are never presented as already included in this earlier document.
    """
    need(type(owner) is CompletionCoordinator,'actual complete CI C owner')
    return {'schema':'four_CI_original_pre_report_cost_prefix_v1',
            'programme':owner.budget.record(),'root_resources':owner.resources.record(),
            'stage_admissions':[s.audit for s in owner.stages],
            'same_cumulative_programme_lineage':True,
            'overlapping_physical_observations_are_not_summed':True,
            'later_report_write_and_final_H_costs_not_in_this_prefix':True,
            'original_C_exit_observed':False,'whole_physical_cost_known_here':False}

def run_to_original_exit(owner,channel,*,gates,conflicts,context_admissions):
    """Complete still-live C poststage caller, then one-way original exit.

    All five stage admissions must already be real source admissions accepted
    by CompletionCoordinator. The root issuer, protected scientific methods,
    and final outer observer keep their independent boundaries. A failure in
    an issuer wait, publication or cleanup cannot be hidden by a later report.
    """
    from four_programmes.channel import RootChannel
    need(type(owner) is CompletionCoordinator and type(channel) is RootChannel,
         'fixed full C and original H channel, never supplied operation callbacks')
    need(owner.phase=='collect_A' and owner.primary is None and not owner.final_notice_attempted,
         'one complete poststage caller entry after all five original stages')
    need(channel.meter is owner.bridge.meter and
         channel.binding['campaign']==owner.budget.campaign_id,
         'same original pre-reserved H transport share and campaign')
    primary=None;operation='collect_A';notice=None
    try:
        owner.collect_arm(ARMS[0],_next_original_authority(owner,'COLLECT_A'))
        operation='collect_B'
        owner.collect_arm(ARMS[1],_next_original_authority(owner,'COLLECT_B'))
        operation='both_seal_recapture';owner.recapture_both_seals()
        operation='protected_grade'
        owner.protected_grade(_next_original_authority(owner,'GRADE'))
        operation='complete_76_panel_report'
        event=_next_original_authority(owner,'REPORT')
        owner.report_all(event,gates=gates,conflicts=conflicts,
                         context_admissions=context_admissions,whole_costs=current_costs(owner))
        operation='one_way_final_notice'
        notice=owner.send_final_notice(channel)
    except BaseException as error:
        # Inner source methods may already own the same raw exception. Do not
        # replace it, invent a second failure, or turn an inactive Budget into
        # a new reporting allowance after an unknown transfer/terminal seal.
        primary=owner.primary if owner.primary is not None else error
        if owner.primary is None:owner._own(primary,operation)
        elif error is not primary:owner.bridge.meter.cleanup_errors.append(failure(error))
    if primary is not None:
        # A missing later report authority is not guessed or skipped to. This
        # ordinary H-share diagnostic retains all mandatory panel identities,
        # exact completed prefixes and missing report/grade/seals explicitly.
        # It is not an original scoring.report or a new scientific result.
        diagnostic=None;diagnostic_error=None
        try:
            known=owner.budget.snapshot() if owner.budget._active else None
            diagnostic=owner.bridge.publish('C_POSTSTAGE_FAILURE.json',{
                'schema':'four_CI_original_poststage_failure_diagnostic_v1',
                'campaign':owner.budget.campaign_id,'all_panel_ids':list(owner.scope.panel_ids),
                'failed_operation':operation,'original_failure':failure(primary),
                'earlier_failures':owner.failures,
                'stage_completions':[s.completion_pin for s in owner.stages],
                'collections':{a:owner.seals[a]['descriptor'] for a in ARMS if a in owner.seals},
                'grade':owner.grade_pin,'original_report':owner.report_pin,
                'known_active_budget_prefix':known,'programme_writer_active':owner.budget._active,
                'known_sealed_terminal_budget_prefix':owner.final_budget_state,
                'root_resources':owner.resources.record(),
                'all_76_panels_remain_mandatory':True,'scientific_results_fabricated':False,
                'report_authority_not_inferred':True,'original_C_exit_observed':False})
        except BaseException as secondary:
            diagnostic_error=failure(secondary);owner.bridge.meter.cleanup_errors.append(diagnostic_error)
        for close in (owner.session.close,channel.close):
            try:close()
            except BaseException as secondary:owner.bridge.meter.cleanup_errors.append(failure(secondary))
        try:BaseException.__setattr__(primary,'four_CI_complete_poststage_failure',
            {'diagnostic':diagnostic,'diagnostic_error':diagnostic_error,
             'original_report':owner.report_pin,'final_notice':owner.final_notice_pin,
             'full_outstanding_reservation_retained':True,'original_H_closure_still_required':True})
        except BaseException as secondary:owner.bridge.meter.cleanup_errors.append(failure(secondary))
        raise primary
    # No receive/wait-for-own-exit occurs here. The enclosing original C entry
    # must now return naturally, allowing the separately owned H to observe it.
    return {'schema':'four_CI_poststage_return_C_exit_pending_v1','report':owner.report_pin,
            'notice':notice,'whole_campaign_success':False,'original_C_exit_observed':False}
