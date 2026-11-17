"""Concrete caller observation of the complete unchanged I supervisor."""
import argparse
import math
import os
from pathlib import Path
import resource
import signal
import sys
import time
from paper_i_central_safety import IO, ReceiptStore, need, pin, parse, encode, ordinary, typed_equal, cleanup, fsync_dir
from paper_i_central_source import capture_parent, clone_parent, LoadedParent
from paper_i_central_binding import bind, GATE_READ_RESERVATION
from paper_i_central_receipts import validate


def clone_central(io, context, root):
    root=io.mkdir(root)
    for name,raw in sorted(context['bodies'].items()):
        need(io.save(root/name,raw,0o444)==context['own_files'][name], 'Exact caller-source clone')
    manifest_pin=io.save(root/'SOURCE_MANIFEST.json',context['own_manifest_raw'],0o444)
    os.chmod(root,0o555);fsync_dir(root);fsync_dir(root.parent)
    return root,manifest_pin


def enforce_memory(profile):
    need(type(profile)is dict and all(type(profile.get(k))is int and 0<profile[k]<=2**63-1 for k in ('observer_memory_bytes','worker_memory_bytes')),'Explicit bounded qualified process memory')
    soft,hard=resource.getrlimit(resource.RLIMIT_AS)
    needed=max(profile['observer_memory_bytes'],profile['worker_memory_bytes'])
    need(hard==resource.RLIM_INFINITY or hard>=needed,'Inherited hard memory ceiling permits both qualified processes')
    resource.setrlimit(resource.RLIMIT_CORE,(0,0))
    resource.setrlimit(resource.RLIMIT_AS,(profile['observer_memory_bytes'],hard))


def final_body(report,budget,io):
    before=budget.snapshot()
    report['cost']={'snapshot_before_result':before,'caller_io_read_charge':io.reads,
        'caller_io_write_charge_before_result':io.writes,'final_result_bytes':0,
        'whole_operation_plus_caller_is_conservative_not_RSS_or_native_IO':True}
    for _ in range(12):
        raw=encode(report);size=len(raw)
        if report['cost']['final_result_bytes']==size:return raw
        report['cost']['final_result_bytes']=size
    raise ValueError('Stable bounded final-result extent')


def run(context,repo,here,origin,argv):
    p=argparse.ArgumentParser();p.add_argument('--program',required=True);p.add_argument('--output',required=True)
    p.add_argument('--review',required=True);p.add_argument('--other-reserve-bytes',type=int,required=True)
    args=p.parse_args(argv)
    need(sys.platform.startswith('linux'),'Reviewed Linux pidfd/process/monotonic environment')
    enforce_memory(context['document'].get('paper_i_central_runtime_profile'))
    io=IO(origin);io.read_charge(context['bootstrap_read_bytes']+GATE_READ_RESERVATION)
    bindings=context['bindings'];parent_ref=bindings['parent_manifest']
    parent_pin={k:parent_ref[k]for k in('bytes','sha256')}
    bundle=capture_parent(io,repo/bindings['parent_root'],repo/parent_ref['path'],parent_pin)
    preflight=LoadedParent(bundle,bundle['root']);primary=None
    try:
        bound=bind(io,repo,args.program,args.review,args.output,args.other_reserve_bytes,context,preflight)
    except BaseException as error:primary=error;raise
    finally:cleanup(primary,[('preflight_source.close',preflight.close)])
    profile=bound['profile'];end=bound['original_end'];cutoff=bound['worker_cutoff'];operation=bound['operation']
    need(sys.platform.startswith('linux'),'Reviewed Linux pidfd/process/monotonic environment')
    need(ordinary(sys.executable)==ordinary(operation['host']['python']['path']),'Exact qualified installed host interpreter')
    python_ref=operation['host']['python']
    io.read_cap=profile['caller_limits']['read_bytes'];io.write_cap=profile['caller_limits']['write_bytes']
    io.deadline=end;io.tick();enforce_memory(profile)
    signal.setitimer(signal.ITIMER_REAL,max(.001,min(origin+120,end)-time.monotonic()))
    io.read(python_ref['path'],{k:python_ref[k]for k in('bytes','sha256')},python_ref['bytes'])
    output=io.mkdir(bound['output']);io.mkdir(output/'journal')
    clone_bytes=sum(len(v)for v in context['bodies'].values())+len(context['own_manifest_raw'])+437883+6012
    need(clone_bytes<=profile['source_copy_retained_bytes'],'Actual complete source clones fit declared source partition')
    parent_root=clone_parent(io,bundle,output/'parent_source')
    central_root,central_manifest=clone_central(io,context,output/'caller_source')
    parent=LoadedParent(bundle,parent_root);primary=None
    try:
        Budget=parent.modules['budget'].Budget
        budget=Budget({'wall_seconds':end-origin,**profile['caller_limits']},origin,output/'journal')
        io.attach(budget)
        budget.event({'event':'central_full_operation_intent','task':'PAPER-FIND-REP-014','origin':origin,
            'deadline':end,'worker_cutoff':cutoff,'operation':bound['operation_pin'],
            'root_authority':bound['root_authority'],'selection':bound['selection_pin'],'work':bound['work_pin'],
            'parent_source':parent_pin,'central_source':central_manifest,'qualified_source':context['freeze_pin'],
            'operator_host_custody_externally_qualified':True,'parent_operation_paths_rebased':False})
        worker_read_cap=profile['source_copy_retained_bytes']+3*1048576
        budget.reserve_producer('central_worker_bootstrap',worker_read_cap,65536,65536)
        request={'schema':'paper_i_central_worker_request_v1','operation_path':bound['operation_path'],
            'operation_pin':bound['operation_pin'],'parent_source_root':str(parent_root),
            'parent_manifest_path':operation['source_manifest']['path'],'parent_manifest_pin':parent_pin,
            'central_root':str(central_root),'central_manifest':central_manifest,
            'parent_output':str(output/'parent'),'worker_return':str(output/'WORKER_RETURN.json'),
            'origin':origin,'original_end':end,'worker_cutoff':cutoff,
            'read_cap':worker_read_cap,'write_cap':65536}
        request_raw=encode(request);need(len(request_raw)<=65536,'Bounded exact worker launch metadata')
        request_pin=io.save(output/'WORKER_REQUEST.json',request_raw)
        argv=[python_ref['path'],'-I','-S','-B',str(central_root/'caller_worker.py'),
            '--request',str(output/'WORKER_REQUEST.json'),'--request-bytes',str(request_pin['bytes']),
            '--request-sha256',request_pin['sha256'],'--cutoff',repr(cutoff)]
        parent.verify()
        need(io.tick()<min(origin+120,cutoff),'Complete caller startup before original startup/work cutoff')
        signal.setitimer(signal.ITIMER_REAL,max(.001,end-time.monotonic()))
        watched=parent.modules['supervisor'].watch(argv,parent_root,cutoff,budget,
            profile['worker_grace_seconds'],profile['worker_log_bytes'],profile['worker_memory_bytes'])
        logs=watched.pop('logs_data');publication_errors=[];log_pins={}
        for name,raw in logs.items():
            try:
                value=io.save(output/('WORKER_'+name+'.log'),raw)
                need(value==watched['logs'][name],'Exact observed worker logs');log_pins[name]=value
            except BaseException as error:publication_errors.append({'artifact':name,'type':type(error).__name__})
        close_pin=None
        try:close_pin=io.save(output/'WORKER_CLOSE.json',encode(watched))
        except BaseException as error:publication_errors.append({'artifact':'WORKER_CLOSE.json','type':type(error).__name__})
        good=(watched['natural_exit'] is True and watched['forced'] is False and watched['exit_code']==0 and
              watched['reaped'] is True and watched['process_group_absent'] is True and
              watched['error_type'] is None and watched['cleanup_errors']==[] and not publication_errors)
        if not good:
            failure={'schema':'paper_i_central_failure_v1','operation':bound['operation_pin'],
                'origin':origin,'deadline':end,'worker_close':close_pin,'publication_errors':publication_errors,
                'transitive_parent_cli_daemon_custody_unknown':True,'automatic_retry':False,
                'outputs_and_costs_retained':True,'runtime_qualified':False,'scientific_qualified':False}
            try:io.save(output/'FAILED.json',encode(failure))
            except BaseException as error:failure['failure_publication_error']=type(error).__name__
            raise RuntimeError('Observed worker did not naturally close the complete operation; custody unresolved')
        io.tick()
        returned_raw=io.read(output/'WORKER_RETURN.json',cap=65536);returned=parse(returned_raw)
        expected={'schema':'paper_i_central_worker_return_v1','request':request_pin,'operation':bound['operation_pin'],
            'parent_source':parent_pin,'central_source':central_manifest,'origin':origin,'deadline':end,
            'worker_cutoff':cutoff,'parent_output':str(output/'parent')}
        need(all(typed_equal(returned.get(k),v)for k,v in expected.items()),'Exact closed worker return identity')
        need(returned.get('parent_result_provisional_until_caller_observes_natural_exit')is True and
             returned.get('scientific_qualified')is False and type(returned.get('bootstrap_read_bytes'))is int and
             0<=returned['bootstrap_read_bytes']<=worker_read_cap and returned.get('worker_write_reservation')==65536,
             'Bounded worker bootstrap cost and provisional-result semantics')
        store=ReceiptStore(output/'parent',io,profile['metadata_cap_bytes'],profile['outer_receipt_cap_bytes'])
        admitted=validate(str(output/'parent'),returned['outer_receipt'],operation,bound['operation_pin'],origin,
            parent.modules,store)
        parent.verify();io.tick()
        result={'schema':'paper_i_full_central_observed_v1','task':'PAPER-FIND-REP-014','source_only_interface':True,
            'operation':bound['operation_pin'],'authority':bound['root_authority'],'selection':bound['selection_pin'],
            'current_work':bound['work_pin'],'other_future_bytes':bound['other_future_bytes'],
            'origin':origin,'deadline':end,'worker_cutoff':cutoff,'worker_close':close_pin,'worker_logs':log_pins,
            'worker_return_observed_pin':pin(returned_raw),'parent_outer':returned['outer_receipt'],
            'parent_manifest':parent_pin,'central_manifest':central_manifest,'qualified_source':context['freeze_pin'],
            'admitted':admitted,'resource_upper':bound['resource'],'observer_own_exit_independently_observed':False,
            'provisional_until_higher_caller_natural_zero':True,'campaign_returncode_is_not_daemon_custody':True,
            'actual_native_IO_or_RSS_certified':False,'runtime_qualified':False,'scientific_qualified':False,
            'whole_paper_reproduced':False,'protected_grade_was_inside_original_programme':True,
            'additional_scientific_grader_called':False,'automatic_retry':False}
        raw=final_body(result,budget,io)
        result_pin=io.save(output/'OBSERVED.json',raw);io.tick()
        return {'deadline':end,'observed':result_pin,'output':str(output)}
    except BaseException as error:primary=error;raise
    finally:cleanup(primary,[('captured_parent.close',parent.close)])
