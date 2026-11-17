"""Distinct original C close after its report; H never waits for C to read back.

The original C final notice is a source-owned descriptor, not completion. This
producer calls the actual HostObserver and captures that exact complete report
only after the original tree has closed. Native/source qualification is still
the independent HostObserver/channel constructor prerequisite.
"""
from .common import need,closed,pin,encode,parse,failure,Store,integer
from .observer import HostObserver,RunningProcess,OriginalProcessObservation
from .channel import HostEndpoint
from .resources import RootResources
from .source_session import SourceSession

def _last_actual_stage(*,source_session,stage_host,last_stage,host,controller,meter,schemas):
    """Recover the exact H-committed last return, never a caller-labelled pin."""
    need(type(source_session) is SourceSession and source_session.programme=='PAPER-FIND-050' and
         not source_session.closed,'actual live original H source session')
    host_module=source_session.modules.get('host_stage');budget_module=source_session.modules.get('stage_budget')
    need(host_module is not None and budget_module is not None and
         type(stage_host) is vars(host_module)['StageHost'] and
         type(last_stage) is vars(host_module)['CompletedStage'],
         'actual fixed source-owned H producer and its original completed value')
    need(stage_host.host is host and stage_host.controller is controller and
         any(value is last_stage for value in stage_host.committed.values()) and
         last_stage.status=='observed' and last_stage.failure is None,
         'same actual H/C and committed original last stage, not a later assertion')
    reader=Store(stage_host.store.root,meter)
    from pathlib import Path
    def document(d):
        raw=reader.read({**d,'path':Path(d['path']).relative_to(reader.root).as_posix()},4194304,metadata=True)
        return parse(raw,4194304)
    ret_pin=last_stage.result['budget_return'];ret=document(ret_pin)
    schemas.validate('ci','BudgetReturn',ret,meter)
    need(ret['sequence']==5 and ret['disposition']=='eligible_exact_successor' and ret['committed_once_by_observer'] is True and
         not ret['unknown_dimensions'] and ret['stage_completion']==last_stage.result['stage_completion'] and
         ret['lease']==last_stage.result['lease'] and ret['terminal_state'] is not None,
         'actual successful original fifth return and no unknown terminal')
    terminal=document(ret['terminal_state']);schemas.validate('ci','BudgetState',terminal,meter)
    vars(budget_module)['validate_state'](terminal)
    need(terminal['generation']==5,'actual original fifth terminal generation')
    return ret_pin,terminal,vars(budget_module)['extends']

def _finish_coordinator(*,host,controller,endpoint,request,resources,report_store,
                       expected_programme,expected_adapter,expected_launch,evidence_prefix,schemas,
                       source_session,stage_host,last_stage):
    need(type(host) is HostObserver and type(controller) is RunningProcess and controller.owner is host and
         type(endpoint) is HostEndpoint and request is endpoint.pending and request is not None and
         type(resources) is RootResources and type(report_store) is Store,
         'actual original independent H, C, channel, resource owner and bounded report store')
    need(not resources.staged and resources.delegated and resources.terminal is None and
         resources.plan['programme']==expected_programme=='PAPER-FIND-050',
         'same complete CI delegation, never N098 staged owner or a new budget')
    need(host.active.get(controller.spec['nonce']) is controller and controller.spec['mode']=='coordinator' and
         controller.spec['source']==expected_adapter and controller.spec['parent_launch']==expected_launch,
         'same actual independently selected original C source and launch')
    meter=host.meter;hard=resources.plan['hard_envelope']
    need(any(s is meter and key[0]=='H' for key,s in resources.shares.items()) and
         host.outputs.meter is meter and report_store.meter is meter and endpoint.meter is meter,
         'one actual earlier cached H final capture share, no fresh allowance')
    need(controller.spec['run_deadline_ns']==hard['run_deadline_ns'] and
         controller.spec['evidence_deadline_ns']==hard['evidence_deadline_ns']==meter.deadline_ns,
         'same original full run/evidence cutoffs')
    message=request['body'];need(message['operation']=='final_report','actual terminal notice operation')
    body=message['body'];closed(body,('schema','programme','campaign','report','report_kind','original_C_exit_observed',
                                    'terminal_budget_state','last_stage_return'))
    need(body['schema']=='four_original_coordinator_final_notice_v1' and body['programme']==expected_programme and
         body['campaign']==resources.plan['campaign_id']==controller.spec['campaign']==endpoint.binding['campaign'] and
         body['report_kind'] in ('normal_path_provisional','failure_path') and body['original_C_exit_observed'] is False,
         'notice explicitly predates original C exit, never a self-completion')
    terminal=body['terminal_budget_state'];schemas.validate('ci','BudgetState',terminal,meter)
    last_stage_return,previous_terminal,extends=_last_actual_stage(source_session=source_session,
        stage_host=stage_host,last_stage=last_stage,host=host,controller=controller,meter=meter,schemas=schemas)
    extends(previous_terminal,terminal,generation=5)
    limits=resources.plan['programme_budget']
    need(terminal['campaign_id']==body['campaign'] and terminal['generation']==5 and
         terminal['read_cap']==limits['read_bytes'] and terminal['write_cap']==limits['write_bytes'] and
         terminal['array_cap']==limits['array_bytes'] and terminal['clock_binding']==limits['clock_binding'] and
         terminal['deadline_seconds']-terminal['origin_seconds']==limits['seconds'] and
         body['last_stage_return']==last_stage_return,'original final logical prefix and actually selected last return')
    d=body['report'];closed(d,('path','bytes','sha256'));integer(d['bytes'],1)
    from pathlib import Path
    report_relative=Path(d['path']).relative_to(report_store.root).as_posix()
    need(report_relative in ('REPORT.json','FAILURE_REPORT.json') and
         (report_relative=='FAILURE_REPORT.json')==(body['report_kind']=='failure_path'),
         'fixed full original report path in independently selected output root')
    need(not getattr(controller,'final_capture_attempted',False),'one original C final observation attempt')
    controller.final_capture_attempted=True
    primary=None;secondary=[];observed=None;report=None;report_pin=None;closure_pin=None
    def own(error):
        nonlocal primary
        if primary is None:primary=error
        elif primary is not error:secondary.append(error);meter.cleanup_errors.append(failure(error))
        meter.own_error(error,'original_C_final_capture')
    try:
        observed=host.finish(controller)
        need(type(observed) is OriginalProcessObservation and observed.identity==controller.identity,
             'actual one original C wait/tree/stream/resource observation')
        if controller.primary is not None:own(controller.primary)
        if not observed.success and primary is None:own(RuntimeError('original C did not complete successfully'))
        # A nonzero closed process may still have a valid failure report. An
        # unclosed/unknown original tree may still mutate it and cannot pass.
        if observed.record['group_empty'] is True and observed.record['group_removed'] is True:
            raw=report_store.read({**d,'path':report_relative},d['bytes'],metadata=True)
            report=parse(raw,d['bytes']);report_pin=d
            need(report['canonical_id']=='PAPER-FIND-050' and report['mandatory_panel_count']==76 and
                 len(report['panels'])==76,'complete original 76-panel report retained')
            if body['report_kind']=='failure_path':
                need(report['qualified_whole_benchmark'] is False,'original failed report cannot qualify the whole benchmark')
        else:own(RuntimeError('original C tree closure unknown; report body remains unread'))
    except BaseException as error:own(error)
    # There is no response to the now-exited C. Requiring that acknowledgement
    # would recreate the lifecycle cycle this separate outer was designed to fix.
    try:endpoint.close()
    except BaseException as error:own(error)
    if observed is not None:
        try:resources.close(observed.record)
        except BaseException as error:own(error)
    record={'schema':'four_distinct_original_C_closure_v1','programme':expected_programme,
            'campaign':resources.plan['campaign_id'],'original_final_notice':request['raw_identity'],
            'original_C_observation':None if observed is None else observed.record,
            'terminal_C_budget_state':terminal,'last_stage_return':body['last_stage_return'],
            'original_report':report_pin,'resource_custody':resources.record(),
            'original_failure':None if primary is None else failure(primary),
            'secondary_failures':[failure(e) for e in secondary],
            'original_C_closed':observed is not None and observed.success,
            'final_report_captured':report_pin is not None,'publication_complete':False,
            'whole_host_qualification_remains_independent':True,'scientific_qualification':False}
    try:
        closure_pin=host.outputs.publish(evidence_prefix+'_C_CLOSURE.json',record)
        meter.check()
    except BaseException as error:own(error)
    result={'record':record,'descriptor':closure_pin,'original_observation':observed,'report':report,
            'publication_complete':closure_pin is not None and primary is None,'primary':primary}
    if primary is not None:
        try:BaseException.__setattr__(primary,'four_original_C_closure',result)
        except BaseException as error:meter.cleanup_errors.append(failure(error))
        raise primary
    need(closure_pin is not None,'actual final H publication')
    return result

def finish_coordinator(*,host,controller,endpoint,request,resources,report_store,
                       expected_programme,expected_adapter,expected_launch,evidence_prefix,schemas,
                       source_session,stage_host,last_stage):
    """Own early admission failures before attempting bounded original cleanup."""
    try:
        return _finish_coordinator(host=host,controller=controller,endpoint=endpoint,request=request,
            resources=resources,report_store=report_store,expected_programme=expected_programme,
            expected_adapter=expected_adapter,expected_launch=expected_launch,evidence_prefix=evidence_prefix,
            schemas=schemas,source_session=source_session,stage_host=stage_host,last_stage=last_stage)
    except BaseException as primary:
        secondary=[];observed=None
        owned=(type(host) is HostObserver and type(controller) is RunningProcess and controller.owner is host)
        if owned:
            host.meter.own_error(primary,'original_C_final_primary')
            if host.active.get(controller.spec['nonce']) is controller and not getattr(controller,'final_capture_attempted',False):
                controller.final_capture_attempted=True
                try:observed=host.finish(controller)
                except BaseException as error:secondary.append(failure(error));host.meter.cleanup_errors.append(failure(error))
        if type(endpoint) is HostEndpoint:
            try:endpoint.close()
            except BaseException as error:
                secondary.append(failure(error))
                if owned:host.meter.cleanup_errors.append(failure(error))
        try:BaseException.__setattr__(primary,'four_original_C_final_failure',
            {'secondary':secondary,'actual_cleanup_observation':None if observed is None else observed.record,
             'outstanding_original_handle':owned and host.active.get(controller.spec['nonce']) is controller,
             'no_blind_finish_retry':True,'full_reservation_retained':True,'scientific_qualification':False})
        except BaseException as error:
            if owned:host.meter.cleanup_errors.append(failure(error))
        raise primary
