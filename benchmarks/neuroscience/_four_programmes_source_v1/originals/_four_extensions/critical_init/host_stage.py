"""Original H stage completion producer, after the actual W invocation.

The source owns HostObserver.finish and captures complete original artifacts.
It cannot accept supplied process-success booleans or numerical result objects.
Missing native/source qualification remains in HostObserver's construction.
"""
import time
from pathlib import Path
from .stage_budget import extends
from .output_contract import OutputContract,capture_job_report
from four_programmes.common import need,closed,integer,encode,pin,parse,failure,Store,bounded_size
from four_programmes.observer import HostObserver,RunningProcess,OriginalProcessObservation
from four_programmes.identity import process_identity
from four_programmes.channel import HostEndpoint

_CLOSED=object()

class CompletedStage:
    __slots__=('result','status','original','failure','_token')
    def __init__(self,token,result,status,original,error):
        need(token is _CLOSED,'actual complete H producer only')
        self.result=result;self.status=status;self.original=original;self.failure=error;self._token=token

class StageHost:
    """One source-owned H completion journal and once-only terminal commitment."""
    def __init__(self,*,host,controller,store,schemas,profile,profile_pin,clock,observer_source):
        need(type(host) is HostObserver and type(controller) is RunningProcess and
             type(store) is Store,'actual original H/C and bounded terminal store')
        need(controller.owner.whole_group is host.whole_group and
             controller.owner.active.get(controller.spec['nonce']) is controller,
             'actual still-open C under same whole host envelope')
        need(store.meter is host.meter,'same earlier H terminal observation/capture reservation')
        schemas.validate('ci','Profile',profile,store.meter)
        schemas.validate('ci','ClockBinding',clock,store.meter)
        need(profile['observer_source']==observer_source and profile['campaign_id']==clock['campaign_id'],
             'same exact selected source/profile/campaign')
        self.host=host;self.controller=controller;self.store=store;self.schemas=schemas
        self.profile=profile;self.profile_pin=profile_pin;self.clock=clock;self.source=observer_source
        self.committed={};self.attempted=set();self.prefixes=[];self.finish_started=set();self.errors={}
        self.observations={};self.failed_attempts={};self.failure_publication_attempted=set()

    def _absolute(self,d):return {**d,'path':str(self.store.root/d['path'])}
    def _publish(self,name,value,*,kind,evidence):
        raw=encode(value);d=self._absolute(self.store.write(name,raw))
        self.prefixes.append(d);self._carry(kind,d,raw,evidence);return d
    def _carry(self,kind,d,raw,evidence):
        # The full source-bound bridge frame later enforces its own cap before
        # transmission. These allocations also consume the earlier H share.
        self.store.meter.charge('work_units',len(raw)*2+4096)
        self.store.meter.charge('retained_bytes',len(raw)*2)
        need(pin(raw)=={k:d[k] for k in ('bytes','sha256')},'same complete original evidence bytes')
        evidence.append({'kind':kind,'descriptor':d,'hex':raw.hex()})
    def _capture(self,name,cap,*,kind,evidence):
        raw,d=self.store.capture_created(name,cap,metadata=True);d=self._absolute(d)
        self.prefixes.append(d);self._carry(kind,d,raw,evidence);return raw,d
    def _live_controller(self):
        c=self.controller
        need(c.child is not None and c.child.poll() is None,'original C still alive at W closure')
        actual=process_identity(c.child.pid,launch_nonce=c.spec['nonce'],source=c.spec['source'],
                                parent_launch=c.spec['parent_launch'],mapping=c.owner.mapping,meter=self.store.meter)
        need(actual==c.identity,'same actual original C boot/PID/start/nonce/source')
        return actual

    def finish(self,running,**selected):
        """Keep the first error and original handle even if metadata admission fails."""
        need(type(running) is RunningProcess and running.owner is self.host,'actual original W owner')
        identity=running.spec['nonce']
        self.errors.setdefault(identity,{'primary':None,'secondary':[]})
        try:
            return self._finish(running,**selected)
        except BaseException as error:
            journal=self.errors[identity]
            if journal['primary'] is None:journal['primary']=error
            elif journal['primary'] is not error:journal['secondary'].append(error)
            primary=journal['primary'];self.store.meter.own_error(primary,'original_H_stage_failure')
            observed=self.observations.get(identity)
            if identity not in self.finish_started and self.host.active.get(identity) is running:
                self.finish_started.add(identity)
                try:
                    observed=self.host.finish(running);self.observations[identity]=observed
                except BaseException as secondary:journal['secondary'].append(secondary)
            # Never blindly repeat a partially failed original finish. Preserve
            # its outstanding handle for the separately selected root cleanup.
            for secondary in journal['secondary']:self.store.meter.cleanup_errors.append(failure(secondary))
            # This branch never issues an eligible completion or restores C's
            # programme token. A missing/failed publication stays missing.
            if identity not in self.failure_publication_attempted:
                self.failure_publication_attempted.add(identity)
                try:
                    from .host_failure import publish_failure
                    self.failed_attempts[identity]=publish_failure(self,running,
                        lease=selected['lease'],lease_pin=selected['lease_pin'],primary=primary,
                        observation=observed,prefix=selected['evidence_prefix']+'_FAILED')
                except BaseException as secondary:
                    journal['secondary'].append(secondary)
                    self.store.meter.cleanup_errors.append(failure(secondary))
            try:BaseException.__setattr__(primary,'four_H_stage_failure',
                {'known_prefixes':list(self.prefixes),'original_finish_attempted':identity in self.finish_started,
                 'actual_cleanup_observation':None if observed is None else observed.record,
                 'outstanding_original_handle':identity in self.host.active,
                 'full_outstanding_delegation_retained':True,'dependent_science_allowed':False})
            except BaseException as secondary:self.store.meter.cleanup_errors.append(failure(secondary))
            raise primary

    def _finish(self,running,*,lease,lease_pin,start,start_pin,base,authority,authority_pin,
               contract,census,run_relative,terminal_relative,physical_limits,evidence_prefix):
        """Full original W -> original receipt/jobs/state -> typed complete return.

        The only child observation is the result of this function's call to the
        original host.finish. Every failure keeps the actual raw first error and
        complete captured prefix. Failed/unattempted jobs never become success.
        """
        need(type(running) is RunningProcess and running.owner is self.host and
             self.host.active.get(running.spec['nonce']) is running,'actual outstanding W handle')
        need(type(contract) is OutputContract,'actual complete compiled output contract')
        contract.require_executable()
        for name,value in [('Lease',lease),('StartBinding',start),('BudgetState',base)]:
            self.schemas.validate('ci',name,value,self.store.meter)
        key=encode(lease_pin);need(key not in self.attempted,'one original stage close attempt');self.attempted.add(key)
        need(start['lease']==lease_pin and start['authority']==authority_pin and
             start['authority_subject']==lease['authority_subject']==authority['pre_run_subject'] and
             authority['job_output_contract']==contract.pin and start['worker']==running.identity and
             start['controller']==lease['controller']==self.controller.identity and
             start['profile']==lease['profile']==self.profile_pin and start['observer_source']==self.source,
             'actual original authority/start/lease/output/source joins')
        need(lease['base_state']['bytes']==len(encode(base)) and
             lease['base_state']['sha256']==pin(encode(base))['sha256'] and
             lease['base_generation']==base['generation'],'same original cumulative base')
        jobs=[j for j in census['jobs'] if j['operation']==lease['operation']]
        need([j['id'] for j in jobs]==lease['ordered_job_ids'] and
             contract.body['census']==lease['census']==self.profile['full_census'] and
             contract.body['campaign_id']==lease['campaign_id']==self.clock['campaign_id'],
             'complete immutable original stage domain')
        need(running.spec['run_deadline_ns']==lease['original_run_deadline_ns']==self.clock['run_deadline_ns'] and
             running.spec['evidence_deadline_ns']==lease['original_evidence_deadline_ns']==self.clock['evidence_deadline_ns'],
             'one original unrenewed whole interval')
        from four_programmes.common import relative
        for n in (run_relative,terminal_relative,evidence_prefix):relative(n)
        need(physical_limits=={'cpu_ns':running.spec['limits']['whole_cpu_ns'],
                               'memory_peak':running.spec['limits']['whole_memory_bytes'],
                               'storage_bytes':running.spec['limits']['whole_storage_bytes']},
             'actual originally selected whole physical limits, never report-supplied allowances')
        cap=integer(authority['evidence_cap_bytes'],1)
        evidence=[];rows=[];receipt=None;state_pin=None;terminal=None;primary=None;cleanup=[];unknown=[]
        self.finish_started.add(running.spec['nonce'])
        actual=self.host.finish(running)
        self.observations[running.spec['nonce']]=actual
        need(type(actual) is OriginalProcessObservation,'actual H return after original finish')
        unknown.extend(actual.record['unknown_dimensions'])
        if running.primary is not None:primary=running.primary;self.errors[running.spec['nonce']]['primary']=primary
        # Start has an independently observed original producer; retain exact
        # earlier selected bytes, never rewrite its worker identity.
        self._carry('start_binding',start_pin,encode(start),evidence)
        def own(error,dimension):
            nonlocal primary
            if primary is None:primary=error;self.errors[running.spec['nonce']]['primary']=error
            else:cleanup.append(error);self.errors[running.spec['nonce']]['secondary'].append(error)
            self.store.meter.own_error(error,dimension)
            if dimension not in unknown:unknown.append(dimension)
        handoff=None;receipt_body=None;outcomes=[];prefix_complete=False
        try:
            raw,handoff_pin=self._capture(terminal_relative,cap,kind='stage_receipt',evidence=[])
            handoff=parse(raw,cap)
            closed(handoff,('schema','campaign_id','lease','start_binding','authority','operation','condition',
                            'stage_receipt','job_output_contract','terminal_budget_state','original_failure','cleanup_errors',
                            'complete_original_attempt_prefix','worker_natural_exit_observed','outer_H_observation_still_required'))
            need(handoff['schema']=='critical_init_worker_terminal_handoff_v4' and handoff['lease']==lease_pin and
                 handoff['start_binding']==start_pin and handoff['authority']==authority_pin and
                 handoff['job_output_contract']==contract.pin and handoff['campaign_id']==lease['campaign_id'] and
                 (handoff['operation'],handoff['condition'])==(lease['operation'],lease['condition']) and
                 handoff['worker_natural_exit_observed'] is False and handoff['outer_H_observation_still_required'] is True,
                 'actual original W terminal handoff, not W self-completion')
            if handoff['terminal_budget_state'] is not None:
                terminal=handoff['terminal_budget_state'];self.schemas.validate('ci','BudgetState',terminal,self.store.meter)
                extends(base,terminal,generation=base['generation']+1)
                need(terminal['array_live']==0,'original W released all owned arrays')
                state_pin=self._publish(evidence_prefix+'_BUDGET.json',terminal,kind='terminal_state',evidence=evidence)
            else:unknown.append('terminal_budget_state')
            if handoff['stage_receipt'] is not None:
                raw,receipt=self._capture(run_relative+'/STAGE_RECEIPT.json',cap,kind='stage_receipt',evidence=evidence)
                need(receipt==handoff['stage_receipt'],'actual exact original source receipt path and bytes')
                receipt_body=parse(raw,cap)
                need(receipt_body['census']==lease['census'] and receipt_body['scope_digest']==authority['scope_digest'] and
                     receipt_body['job_output_contract']==contract.pin and receipt_body['operation']==lease['operation'] and
                     receipt_body['whole_scope_job_count']==len(census['jobs']) and receipt_body['selected_stage_job_count']==len(jobs),
                     'same entire original receipt domain')
                outcomes=receipt_body['outcomes'];prefix_complete=True
            elif handoff['complete_original_attempt_prefix'] is not None:
                pre=handoff['complete_original_attempt_prefix']
                need(pre['authority']==authority_pin and Path(pre['run_root'])==self.store.root/run_relative,
                     'original partial outcome source root, never a receipt-directed new root')
                outcomes=pre['outcomes']
            need(type(outcomes) is list and len(outcomes)<=len(jobs) and
                 [x['job_id'] for x in outcomes]==[j['id'] for j in jobs[:len(outcomes)]],
                 'actual complete ordered original attempted prefix')
            if prefix_complete:need(len(outcomes)==len(jobs),'full original receipt includes every job')
            if handoff['original_failure'] is not None or handoff['cleanup_errors']:
                # Keep the actual W diagnostic body; do not invent its raw
                # exception identity in this different H process.
                if primary is None:
                    primary=RuntimeError('original W terminal reports failure; exact diagnostic retained')
                    self.errors[running.spec['nonce']]['primary']=primary
        except BaseException as error:own(error,'worker_terminal_capture')
        for index,job in enumerate(jobs):
            row={'job_id':job['id'],'original_process_record':None,'candidate_report':None,
                 'original_outcome':None,'known_prefixes':[],'status':'unknown'}
            if index<len(outcomes):
                outcome=outcomes[index]
                row['status']='failed' if outcome.get('status') in ('failed','required_unscorable') else 'unknown'
            else:
                # This is explicitly H's absence observation, not a fabricated
                # original W outcome or scientific result.
                outcome={'schema':'critical_init_H_missing_original_outcome_v1','job_id':job['id'],
                         'status':'unattempted' if handoff is not None and handoff['complete_original_attempt_prefix'] is not None else 'unknown',
                         'original_W_outcome_present':False,'original_terminal_handoff':handoff_pin if handoff is not None else None}
                row['status']=outcome['status']
            try:
                row['original_outcome']=self._publish(evidence_prefix+'_OUTCOME_'+str(index)+'.json',outcome,
                                                     kind='original_outcome',evidence=evidence)
                if index<len(outcomes) and outcome.get('status')=='process_finished_pending_independent_outer_completion' and actual.success:
                    captured=capture_job_report(actual,contract,job,run_root=run_relative,store=self.store,
                                                process_cap=cap,condition=lease['condition'])
                    row.update(captured)
                    raw=self.store.read({**captured['original_process_record'],
                                         'path':str(Path(captured['original_process_record']['path']).relative_to(self.store.root))},cap,metadata=True)
                    need(parse(raw,cap)==outcome['original_process'],'actual PROCESS equals original source outcome')
                    self._carry('original_process',captured['original_process_record'],raw,evidence)
                    row['status']='original_process_closed'
            except BaseException as error:
                row['status']='failed';own(error,'original_job_capture')
                attrs=BaseException.__getattribute__(error,'__dict__')
                pre=attrs.get('four_job_capture_prefix') if type(attrs) is dict else None
                if type(pre) is dict and pre.get('job_id')==job['id']:
                    for k in ('original_process_record','candidate_report'):
                        if pre.get(k) is not None:row[k]=pre[k];row['known_prefixes'].append(pre[k])
            rows.append(row)
        if any(r['original_outcome'] is None for r in rows):
            # The closed JobEvidence requires an actual outcome record. An
            # exhausted publication budget cannot produce a fictional row.
            error=RuntimeError('complete original stage evidence publication unavailable')
            own(error,'job_outcome_publication');self._raise_prefix(primary,rows,actual)
        controller_alive=False;physical=None
        try:
            controller=self._live_controller();controller_alive=True
            physical=actual.record['physical_final'];need(actual.record['physical_final_known'] is True and physical is not None,
                                                         'actual final whole physical observation')
            need(all(physical['whole'][k] is not None for k in ('cpu_ns','memory_peak')),'known final physical dimensions')
        except BaseException as error:own(error,'final_physical_or_controller')
        if not controller_alive or physical is None:
            # No StageCompletion with invented C/PID/physical resources.
            self._raise_prefix(primary,rows,actual)
        original_failure=None;cleanup_pins=[]
        if primary is not None:
            original_failure=self._publish(evidence_prefix+'_FAILURE.json',
                {'H_original_failure':failure(primary),'W_terminal_diagnostic':None if handoff is None else handoff['original_failure'],
                 'W_cleanup_diagnostics':[] if handoff is None else handoff['cleanup_errors']},kind='original_outcome',evidence=evidence)
        for i,error in enumerate(cleanup):
            cleanup_pins.append(self._publish(evidence_prefix+'_CLEANUP_'+str(i)+'.json',failure(error),kind='original_outcome',evidence=evidence))
        stream_pins={}
        for name,raw in [('stdout',actual.stdout),('stderr',actual.stderr)]:
            d=actual.record.get(name)
            if d is not None:
                d={**d,'path':str(self.host.outputs.root/d['path'])}
                self._carry(name,d,raw,evidence)
            stream_pins[name]=d
        comp={'schema':'critical_init_original_stage_completion_v3','campaign_id':lease['campaign_id'],'lease':lease_pin,
              'start_binding':start_pin,'controller':controller,'worker':running.identity,'observer_source':self.source,
              'operation':lease['operation'],'condition':lease['condition'],'stage_receipt':receipt,
              'ordered_job_evidence':rows,'terminal_budget_state':state_pin,'natural_exit':actual.record['natural_exit'],
              'exit_code':actual.record['exit_code'],'outer_streams_eof':all(actual.record['streams_eof'].values()),
              'worker_descendants_empty':actual.record['group_empty'],'worker_group_removed':actual.record['group_removed'],
              'timed_out':actual.record['timed_out'],'original_failure':original_failure,'cleanup_errors':cleanup_pins,
              'original_outer_stdout':stream_pins['stdout'],'original_outer_stderr':stream_pins['stderr'],
              'observed_physical_resources':None,'closed_ns':time.monotonic_ns(),'whole_campaign_still_open':True}
        subject={k:comp[k] for k in ('campaign_id','lease','start_binding','controller','worker','observer_source','operation','condition',
                                    'stage_receipt','ordered_job_evidence','terminal_budget_state')}
        physical_body={'schema':'four_original_stage_physical_observation_v1','observer':self.source,'worker':running.identity,
                       'controller':controller,'start_binding':start_pin,'stage_completion_subject':pin(encode(subject)),
                       'run_deadline_ns':self.clock['run_deadline_ns'],'evidence_deadline_ns':self.clock['evidence_deadline_ns'],
                       'cpu_ns':physical['whole']['cpu_ns'],'memory_peak':physical['whole']['memory_peak'],
                       'storage_bytes':physical['storage_bytes'],'whole_limits':physical_limits,
                       'final_observation_known':True,'controller_alive_at_close':True}
        for key in ('cpu_ns','memory_peak','storage_bytes'):
            integer(physical_body[key]);need(physical_body[key]<=physical_limits[key],'same original whole physical cap')
        physical_pin=self._publish(evidence_prefix+'_PHYSICAL.json',physical_body,kind='physical_observation',evidence=evidence)
        comp['observed_physical_resources']=physical_pin;self.schemas.validate('ci','StageCompletion',comp,self.store.meter)
        comp_pin=self._publish(evidence_prefix+'_COMPLETION.json',comp,kind='stage_completion',evidence=evidence)
        eligible=(actual.success and primary is None and receipt is not None and state_pin is not None and
                  all(r['status']=='original_process_closed' for r in rows))
        if state_pin is None and 'terminal_budget_state' not in unknown:unknown.append('terminal_budget_state')
        ret={'schema':'critical_init_exclusive_budget_return_v3','campaign_id':lease['campaign_id'],'lease':lease_pin,
             'base_state':lease['base_state'],'stage_completion':comp_pin,'terminal_state':state_pin,
             'previous_return':lease['previous_return'],'sequence':lease['sequence'],
             'disposition':'eligible_exact_successor' if eligible else ('terminal_unknown' if unknown else 'failure_only'),
             'unknown_dimensions':unknown,'evidence_capture_reservation':lease['terminal_channel_reservation'],
             'committed_once_by_observer':True}
        self.schemas.validate('ci','BudgetReturn',ret,self.store.meter)
        return_pin=self._publish(evidence_prefix+'_RETURN.json',ret,kind='budget_return',evidence=evidence)
        self.store.meter.check();need(time.monotonic_ns()<self.clock['evidence_deadline_ns'],'original final evidence cutoff')
        result={'lease':lease_pin,'start_binding':start_pin,'stage_completion':comp_pin,'budget_return':return_pin,
                'physical_observation':physical_pin,'evidence':evidence}
        status='observed' if eligible else ('unknown' if unknown else 'failed')
        completed=CompletedStage(_CLOSED,result,status,actual,primary);self.committed[key]=completed
        return completed

    def _raise_prefix(self,error,rows,actual):
        if error is None:error=RuntimeError('original H completion unavailable')
        self.store.meter.own_error(error,'stage_completion_unavailable')
        try:BaseException.__setattr__(error,'four_stage_capture_prefix',
            {'rows':rows,'known_prefixes':list(self.prefixes),'actual_original_observation':actual.record,
             'full_outstanding_delegation_retained':True,'dependent_science_allowed':False})
        except BaseException as secondary:self.store.meter.cleanup_errors.append(failure(secondary))
        raise error

    def respond(self,endpoint,request,completed):
        need(type(endpoint) is HostEndpoint and type(completed) is CompletedStage and
             completed in self.committed.values(),'same actual H completion and captured channel request')
        return endpoint.respond(request,status=completed.status,result=completed.result)

    def respond_failure(self,endpoint,request,running):
        from .host_failure import FailedStage
        need(type(endpoint) is HostEndpoint and type(running) is RunningProcess and running.owner is self.host,
             'same original H endpoint and attempted worker')
        failed=self.failed_attempts.get(running.spec['nonce'])
        need(type(failed) is FailedStage,'actual once-only failed-attempt publication required')
        return endpoint.respond(request,status='failed',result=failed.result)
