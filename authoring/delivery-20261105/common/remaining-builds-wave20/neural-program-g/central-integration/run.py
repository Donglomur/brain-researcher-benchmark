"""Source-complete central collection caller. No science or daemon action at import."""
import os
from pathlib import Path
import resource
import shutil
import signal
import sys
import time
import types
from .core import (need, integer, number, pin, descriptor, encode, decode, path, capture,
                   read_json, publish, directory, inventory, Meter)
from . import caller_observer, readback, resources

REL='authoring/delivery-20261105/common/remaining-builds-wave20/neural-program-g/central-integration'
REGISTRY='benchmarks/neuroscience/neural-007-whole-night-sleep-scoring/manifest.json'
NAMED='full153_two_modes_four_views_v4'


def helper(raw,name,filename):
    module=types.ModuleType(name); module.__file__=str(filename)
    exec(compile(raw,str(filename),'exec'),module.__dict__); return module


def locator(d):
    need(type(d) is dict and set(d)=={'path','bytes','sha256'},'Exact operator metadata locator')
    descriptor({k:d[k] for k in ('bytes','sha256')}); return path(d['path'])


def read_operand(d,meter):
    return decode(capture(locator(d),{k:d[k] for k in ('bytes','sha256')},meter,1048576),meter.depth,meter.nodes)


def repeat_authority(repo,review,doc,manifest_raw,freeze_raw,entry_raw,base,gate,meter):
    from .bootstrap import route_identity
    raw=capture(repo/REGISTRY,review['registry'],meter,131072)
    need(decode(raw)==doc,'Unchanged actual installed full registry')
    route_identity(doc,manifest_raw,freeze_raw,entry_raw)
    selected=doc
    need(review['condition'] in (None,NAMED),'Only same complete default/named routes')
    if review['condition'] is not None:
        need(doc.get('program_conditions',{}).get(NAMED)=='default','Named route is exactly complete default')
        condition_helper=helper(capture(repo/'tools/neurobench_condition_campaign.py',
            {'bytes':8300,'sha256':'e1c54c6fb9e577898e69d7d832d155131c13d82df3148ef1dcd42a35537d7e2f'},meter),
            '_sleep_central_conditions',repo/'tools/neurobench_condition_campaign.py')
        selected=condition_helper.condition_document(doc,review['condition'])
        need(selected['program_execution']==doc['program_execution'],'Real helper resolves identical full programme')
    meter.read(80*1024*1024)  # explicit upper charge for uninstrumented exact helper qualification reads
    need(base.verified_program_runtime(repo/REGISTRY,selected,repo),'Exact full runtime qualification still required')
    request=review['campaign_request']
    first=gate.admit(repo,'NEURAL-007','run',review['condition'],request['path'],request['sha256'],review['work']['sha256'])
    route=gate.preferred_route(repo,'NEURAL-007','run',review['condition'],review['work']['sha256'],registered=(repo/REGISTRY,doc))
    meter.read(first['metadata_read_charge_bytes']+route['metadata_read_charge_bytes'])
    need(route['status']=='preferred_source_bound','Actual full preferred route')
    first['preferred_program_route']=route
    return first


def qualification(review,source,meter):
    q=decode(capture(locator(review['environment_qualification']),{k:review['environment_qualification'][k] for k in ('bytes','sha256')},meter,1048576))
    need(q['schema']=='sleep_full153_central_environment_qualification_v1' and q['status']=='qualified'
         and q['source']==source and q['independent_of_candidate'] is True,'Separate exact independently reviewed environment evidence')
    required={'linux_proc_and_wait_ownership','isolated_interpreter_and_stdlib','literal_entry_argv',
        'complete_parent_native_and_model_runtime','source_owned_journal_integrity','no_external_creator_or_remote_request',
        'daemon_peer_and_namespace_identity','host_resource_enforcement','candidate_private_target_exclusion',
        'nonidentifying_mount_prefixes'}
    need(type(q['evidence']) is dict and set(q['evidence'])==required,'Complete external qualification domains')
    for name,operand in q['evidence'].items():
        evidence=decode(capture(locator(operand),{k:operand[k] for k in ('bytes','sha256')},meter,131072))
        need(evidence['status']=='passed' and evidence['source']==source and evidence['domain']==name,
             'Pinned domain-specific qualification evidence; no candidate booleans')
    need(q['clock']==review['clock'] and q['resource_profile']==pin(encode(review['resources']))
         and q['endpoints']==review['endpoints'] and q['bundle']==review['bundle']
         and q['output']==review['output'] and q['environment']==review['environment']
         and q['semantic_intake']==review['semantic_intake']
         and q['qualified_dependency_roots']==review['qualified_dependency_roots'],
         'Exact selected operation qualification')
    need(type(q['qualified_before_origin']) in (int,float) and q['qualified_before_origin']<review['clock']['origin'],
         'Pre-operation qualified environment')
    return q


def validate_operands(bundle,configuration,grant,review,parent_source,output):
    need(bundle['schema']=='sleep_full153_central_bundle_v1' and set(bundle)=={'schema','grant','configuration','index'},'Exact full collection bundle')
    need(grant['schema']=='neural007_full153_campaign_grant_v1' and grant['authorized'] is True
         and grant['source']==parent_source and grant['clock']==review['clock'], 'Explicit unchanged full collection authority')
    need(grant['configuration']=={k:bundle['configuration'][k] for k in ('bytes','sha256')}
         and grant['index']=={k:bundle['index'][k] for k in ('bytes','sha256')}, 'Exact original programme operands')
    need(configuration['frozen_profile'] in ('generic_current_person','training_only_reuse'), 'Declared complete frozen treatment')
    need(configuration['root']==str(output/'campaign'),'Original campaign uses exact chosen fresh child')
    native=configuration['native']
    for key,name in [('control_root','native-control'),('job_root','native-jobs'),('quarantine_root','native-quarantine')]:
        need(native[key]==str(output/name),'Exact disjoint newly provisioned native child')
    need(native['source']==configuration['model']['source']==parent_source,'Same source across actual transports')
    need(configuration['model']['docker_socket'] in {x['path'] for x in review['endpoints']}
         and native['docker_socket'] in {x['path'] for x in review['endpoints']},'All actual daemon endpoints observed')
    # Semantic intake is separately operator-owned and never mounted by the
    # candidate/model. Its unchanged parent policy handles post-seal responses.
    need(review['semantic_intake']==configuration['semantic_intake'],'Exact separately selected semantic intake')
    need(grant['qualified_dependency_roots']==review['qualified_dependency_roots'],'Exact external scientific dependency inventory')


def stage_parent(parent_bodies,output,meter):
    stage=directory(output/'captured-parent',True)
    for name,raw in sorted(parent_bodies.items()):
        target=stage/name
        for ancestor in reversed(target.parent.parents):
            if ancestor==stage or ancestor.is_relative_to(stage):
                if not ancestor.exists(): directory(ancestor,True)
        if not target.parent.exists(): directory(target.parent,True)
        publish(target,raw,meter)
    return stage


def launch_argv(stage,parent_bodies,grant,bundle,configuration):
    source=grant['source']; manifest=decode(parent_bodies['program/SOURCE_MANIFEST.json'])
    launcher=decode(parent_bodies['LAUNCHER.json']); clock=grant['clock']; bp=manifest['files']['bootstrap.py']
    need(launcher['schema']=='neural007_literal_launcher_v1' and launcher['python_flags']==['-I','-S','-B','-c'], 'Exact immutable parent literal launcher')
    argv=[sys.executable,*launcher['python_flags'],launcher['literal_python'],str(stage/'program/bootstrap.py'),
          str(bp['bytes']),bp['sha256'],str(clock['deadline']),
          '--source-root',str(stage/'program'),'--manifest-bytes',str(source['bytes']),
          '--manifest-sha256',source['sha256'],'--origin',str(clock['origin']),'--deadline',str(clock['deadline'])]
    for root in grant['qualified_dependency_roots']: argv+=['--dependency-root',root]
    configuration_path=bundle['configuration']['path']
    argv+=['campaign','--roster',str(stage/'design/ROSTER.json'),'--folds',str(stage/'design/FOLDS.json'),
           '--output',configuration['root'],'--profile',configuration['frozen_profile'],'--grant',bundle['grant']['path'],
           '--configuration',configuration_path,'--index',bundle['index']['path']]
    return argv


def execute(args,repo,doc,registry_raw,manifest_raw,freeze_raw,files,parent_bodies,dependencies,
            base,entry_started,bootstrap_reads,bootstrap_external_upper):
    # Only this point follows exact full-interface and runtime qualification.
    startup=Meter(256*1024*1024,1,entry_started+120)
    review_raw=capture(path(args.review),meter=startup,cap=1048576); review=decode(review_raw)
    required={'schema','authorized','action','condition','source','parent_source','registry','bundle','clock','closeout_deadline',
        'environment_qualification','resources','endpoints','campaign_request','work','semantic_intake',
        'qualified_dependency_roots','other_reserve_bytes','output','environment'}
    need(type(review) is dict and set(review)==required and review['schema']=='sleep_full153_central_review_v1'
         and review['authorized'] is True and review['action']=='collect','Explicit full collection review, no implicit score authority')
    source=pin(manifest_raw); parent_source=pin(parent_bodies['program/SOURCE_MANIFEST.json'])
    need(review['source']==source and review['parent_source']==parent_source and review['registry']==pin(registry_raw),'Exact central and unchanged parent sources')
    clock=review['clock']; need(type(clock) is dict and set(clock)=={'origin','deadline'}
         and all(number(x) for x in clock.values()) and 0<=clock['origin']<=entry_started<clock['deadline'], 'Previously sealed root clock')
    startup.end=min(entry_started+120,clock['origin']+120)
    startup.check(); signal.setitimer(signal.ITIMER_REAL,startup.end-time.monotonic())
    profile=review['resources']; need(number(review['closeout_deadline']) and review['closeout_deadline']>clock['deadline']+90, 'Separately selected complete closeout and emergency interval')
    meter=Meter(profile['read_bytes'],profile['write_bytes'],review['closeout_deadline'],
        profile['max_member_bytes'],profile['json_depth'],profile['json_nodes'])
    meter.read(bootstrap_reads+bootstrap_external_upper+startup.read_bytes)
    qualification(review,source,meter)
    need(type(args.other_reserve_bytes) is str and args.other_reserve_bytes.isdecimal()
         and int(args.other_reserve_bytes)==review['other_reserve_bytes'], 'Exact unrelated occupied/future reservation')
    integer(review['other_reserve_bytes'])
    output=path(args.output); need(len(str(output).encode())<=256 and str(output).isascii(),'Qualified bounded neutral operation-root prefix')
    need(str(output)==review['output'] and not output.exists(),'Exact fresh central parent')
    need(type(review['endpoints']) is list and 1<=len(review['endpoints'])<=2
         and len({x['path'] for x in review['endpoints']})==len(review['endpoints']), 'Every distinct native/model endpoint once')
    gate=helper(dependencies['tools/neurobench_campaign_gate.py'],'_sleep_central_gate',repo/'tools/neurobench_campaign_gate.py')
    first=repeat_authority(repo,review,doc,manifest_raw,freeze_raw,files['entry.py'],base,gate,meter)
    # Producer/operation bundle is opened only after runtime, environment and
    # campaign authority. The grant/configuration contain no implicit permission.
    need(path(args.program)==locator(review['bundle']),'Exact selected central bundle path')
    bundle=read_operand(review['bundle'],meter)
    grant=read_operand(bundle['grant'],meter); configuration=read_operand(bundle['configuration'],meter)
    index_body=capture(locator(bundle['index']),{k:bundle['index'][k] for k in ('bytes','sha256')},meter,1048576)
    native_policy=read_json(configuration['native']['mechanical_policy_path'],meter,configuration['native']['mechanical_policy_pin'])
    validate_operands(bundle,configuration,grant,review,parent_source,output)
    allocation=resources.admit(profile,configuration,grant,sum(map(len,parent_bodies.values())),review['endpoints'])
    need(review['closeout_deadline']>=clock['deadline']+90+profile['closeout_seconds'],'Unextended preselected readback endpoint')
    need(shutil.disk_usage(output.parent).free>=profile['free_floor_bytes']+review['other_reserve_bytes']+
         profile['retained_bytes']+profile['parent_retained_bytes'],'Complete parent+observer storage plus unrelated holds')
    # Only the independently selected current process is constrained here.
    # These source operations are never invoked during construction controls.
    resource.setrlimit(resource.RLIMIT_AS,(profile['memory_bytes'],profile['memory_bytes']))
    resource.setrlimit(resource.RLIMIT_CPU,(profile['cpu_seconds'],profile['cpu_seconds']))
    directory(output,True)
    for name in ('native-control','native-jobs','native-quarantine'): directory(output/name,True)
    stage=stage_parent(parent_bodies,output,meter)
    argv=launch_argv(stage,parent_bodies,grant,bundle,configuration)
    env=review['environment']; need(type(env) is dict and all(type(k) is str and type(v) is str for k,v in env.items()),'Exact qualified environment')
    need(all(k not in env for k in ('PYTHONPATH','PYTHONHOME','DOCKER_HOST','DOCKER_CONTEXT')),'No ambient source/daemon substitution')
    # Recheck the actual sealed operation bytes, WORK, registry and helpers
    # immediately before launching. sys.orig_argv is the actual central caller.
    need(capture(path(args.review),pin(review_raw),meter)==review_raw,'Review unchanged before dispatch')
    for d in (review['bundle'],bundle['grant'],bundle['configuration'],bundle['index']):
        capture(locator(d),{k:d[k] for k in ('bytes','sha256')},meter)
    second=repeat_authority(repo,review,doc,manifest_raw,freeze_raw,files['entry.py'],base,gate,meter)
    authority=gate.finish(first,second,list(sys.orig_argv),str(repo))
    startup.check(); need(meter.read_bytes<=256*1024*1024,'All prelaunch source/qualification/operation metadata stays within selected256MiB envelope')
    need(time.monotonic()<clock['deadline'],'Complete startup before original production clock')
    publish(output/'START.json',encode({'source':source,'parent_source':parent_source,'review':pin(review_raw),
        'root_clock':clock,'entry_observed_at':entry_started,'closeout_deadline':review['closeout_deadline'],
        'argv':argv,'actual_central_argv':list(sys.orig_argv),'authority':authority,'allocation':allocation,
        'collection_authenticates_held_target_bytes_operator_only':True,'protected_grade_selected':False}),meter)
    signal.setitimer(signal.ITIMER_REAL,clock['deadline']-time.monotonic())
    outcome=None; stage_name='parent_collection'; error=None
    try:
        outcome=caller_observer.run(argv,clock['deadline'],clock['deadline']+90,env,str(repo),output/'CHILD_BIRTH.json',meter)
        signal.setitimer(signal.ITIMER_REAL,review['closeout_deadline']-time.monotonic())
        publish(output/'stdout.bin',outcome['stdout'],meter); publish(output/'stderr.bin',outcome['stderr'],meter)
        publish(output/'CALLER.json',encode(outcome['record']),meter)
        stage_name='complete_metadata_and_daemon_observation'
        result=readback.collect(configuration,grant,parent_source,parent_bodies,index_body,outcome['stdout'],
            profile,review['endpoints'],meter,native_policy)
        result.update(closeout_deadline=review['closeout_deadline'],root_clock=clock,
            actual_central_external_exit_still_required=True,root_hold_release_authorized=False,
            source=source,parent_source=parent_source,authoritative_scope='collection_metadata_only',
            charged_read_bytes=meter.read_bytes,charged_write_bytes_before_final=meter.write_bytes,
            helper_read_upper_charges_included=bootstrap_external_upper+160*1024*1024,
            physical_io_bytes=None,peak_rss_bytes=None)
        publish(output/'CAPTURED_METADATA_INDEX.json',encode(meter.index),meter)
        publish(output/'RESULT.json',encode(result),meter)
        return result
    except BaseException as exc:
        if isinstance(exc,caller_observer.ChildFailure): outcome=exc.bundle
        error={'schema':'sleep_central_failed_v1','stage':stage_name,'error_type':type(exc).__name__,
            'root_clock':clock,'closeout_deadline':review['closeout_deadline'],'successful_collection':False,
            'automatic_retry':False,'mutating_central_cleanup_signals':False,'remaining_process_or_daemon_state':'unknown',
            'root_hold_release_authorized':False,'charged_reads':meter.read_bytes,'charged_writes':meter.write_bytes}
        try:
            signal.setitimer(signal.ITIMER_REAL,max(.000001,review['closeout_deadline']-time.monotonic()))
            if outcome is not None:
                error['caller']=outcome['record']
                for name,key in [('FAILED.stdout','stdout'),('FAILED.stderr','stderr')]:
                    publish(output/name,outcome[key],meter)
            publish(output/'FAILED.json',encode(error),meter)
        except BaseException:
            # Incomplete receipt is explicit uncertainty, never a success claim.
            pass
        raise
