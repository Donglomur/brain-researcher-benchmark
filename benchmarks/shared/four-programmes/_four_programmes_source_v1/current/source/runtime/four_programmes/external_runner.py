"""Concrete whole external-programme controller; no scientific work on import.

Original source executes only after the independently selected Context/native
admission. Its source link is explicitly unavailable in the present candidate.
"""
import hashlib,json,time
from pathlib import Path
from . import dependencies
from .common import need,closed,integer,encode,parse,failure,bounded_size,Store
from .observer import HostObserver,OriginalProcessObservation
from .resources import RootResources
from .roots import BoundRoots
from .external_campaigns import n056_argv,n056_outputs,n098_argv,n098_outputs

_ADMITTED=object()
class ExternalAdmission:
    __slots__=('binding','catalog','repo','context','environment','prelaunch_view','_token')
    def __init__(self,token,*,binding,catalog,repo,context,environment,prelaunch_view=None):
        need(token is _ADMITTED,'original full external-source admission only')
        self.binding=binding;self.catalog=catalog;self.repo=Path(repo)
        self.context=context;self.environment=environment;self.prelaunch_view=prelaunch_view;self._token=token

def admit_external(*,binding,catalog,repo,selected_context,selected_templates,environment):
    """Source-owned missing Context integration cannot be supplied as a callback."""
    need(binding['programme']=='NEURAL-056','N098 must use the original staged prelaunch and bound-view path')
    dependencies.require('context_v6_source_admission',selected_context)
    dependencies.require('context_four_programme_source_templates',selected_templates)
    from .context_boundary import admitted_context
    context=admitted_context(binding['programme'],catalog,selected_context,selected_templates,environment)
    return ExternalAdmission(_ADMITTED,binding=binding,catalog=catalog,repo=repo,context=context,environment=environment)

def bind_n098_external(bound_view):
    from .n098_startup import BoundResourceView
    need(type(bound_view) is BoundResourceView,"actual original private N098 bound view")
    v=bound_view;o=v.owner;e=v.evidence;a=o.prelaunch_admission
    need(o.staged and o.phase=="BOUND" and v is o.bound_view and e is o.binding_evidence and
         v.plan is o.plan and v.pin==o.pin and o.running is e.running,
         "same original staged owner/view/final evidence")
    o._healthy_startup();o._current_host_share("bound_external").check();e.check_original(o,o.running)
    need(e.binding['root']['programme_bindings']['startup_authority_bridge']==a.prelaunch_selection_pin==o.original_selection_pin,
         "same earlier PrelaunchSelection bridge in bound external admission")
    return ExternalAdmission(_ADMITTED,binding=e.binding,catalog=a.catalog,repo=a.repo,context=a.context,
                             environment=a.environment,prelaunch_view=v)

def admit_n098_prelaunch(*args,**kwargs):
    from .n098_startup import admit_n098_prelaunch as admit
    return admit(*args,**kwargs)

def _roots(admission,stores,output_store,host,resources):
    need(type(admission) is ExternalAdmission and type(stores) is BoundRoots and
         type(output_store) is Store and type(host) is HostObserver and type(resources) is RootResources,
         'actual admitted source, original observer, root stores and single resources')
    binding=admission.binding
    if binding['programme']=='NEURAL-098':
        v=admission.prelaunch_view
        need(resources.staged and v is resources.bound_view and v.owner is resources and
             v.evidence is resources.binding_evidence and resources.phase in ('BOUND','DELEGATED') and
             host is resources.bootstrap.host and v.evidence.running is resources.running,
             'same original N098 bound owner and actual parked process; never a second constructor')
        need(binding['root']['programme_bindings']['startup_authority_bridge']==resources.original_selection_pin==
             resources.prelaunch_admission.prelaunch_selection_pin==resources.running.spec['parent_launch'],
             'exact earlier parent bridge on actual final external caller')
    else:need(admission.prelaunch_view is None and not resources.staged,'no N098 private view on other programme')
    need(resources.pin==binding['resource_pin'] and resources.plan==binding['resources'],
         'same original root resource selection')
    need(output_store.root in stores.roots.values(),'explicit output root already in original routing')
    need(host.outputs.root in stores.roots.values(),'actual host evidence root already selected')
    return binding

def _capture_absolute(store,name,cap):
    raw,d=store.capture_created(name,cap,metadata=True)
    return raw,{**d,'path':str(store.root/d['path'])}

def run_n056(admission,*,stores,output_store,host,resources,launch):
    """One actual original outer invocation, then its complete original outputs.

    No direct caller.run shortcut, source relocation, reference-only route or
    substitute numerical method. Any failure retains original observation and
    full outstanding delegation; the original exception stays primary.
    """
    b=_roots(admission,stores,output_store,host,resources)
    need(b['programme']=='NEURAL-056','fixed N056 whole route')
    closed(launch,('nonce','group_parent','group_name','host_output_prefix','original_capture_name'))
    rb=b['root']['programme_bindings'];meter=host.meter
    profile=stores.document(rb['profile'],4194304)
    authority=stores.document(rb['legacy_authority'],4194304)
    manifest_pin=admission.catalog['programmes']['NEURAL-056']['source_manifest']
    manifest=stores.document(manifest_pin,4194304)
    # This is the exact original n056.core.canonical/digest encoding, distinct
    # from this adapter's LF-terminated metadata codec.
    meter.charge('work_units',bounded_size(manifest));meter.charge('retained_bytes',bounded_size(manifest))
    source_id=hashlib.sha256(json.dumps(manifest,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
    need(authority['source_id']==source_id,'actual complete original N056 source identity')
    programme=output_store.root/'programme';capture=output_store.root/launch['original_capture_name']
    from .common import relative
    relative(launch['original_capture_name'])
    need(not programme.exists() and not capture.exists() and programme!=capture,
         'fresh original whole output and outer capture destinations')
    argv=n056_argv(b,profile,authority,repo=admission.repo,catalog=admission.catalog,
                   programme_output=programme,evidence_output=capture)
    hard=b['resources']['hard_envelope'];outer=profile['outer']
    need(Path(launch['group_parent'])==host.whole_group.path,
         'original external aggregate below the selected whole root')
    aggregate=Path(launch['group_parent'])/launch['group_name']
    nested=Path(outer['cgroup'])
    need(nested.parent==aggregate and nested.name.startswith('n056-') and nested.name!='entry' and
         profile['runtime']['cgroup_parent']==str(nested/'jobs'),
         'original controller and every original job remain under actual observed aggregate')
    need(time.monotonic_ns()+integer(outer['wall_ns'],1)+integer(outer['cleanup_ns'],1)<=hard['run_deadline_ns'],
         'complete original nested interval must fit before the earlier root run cutoff')
    resources.delegate_programme(b['resources']['programme_budget'])
    spec={'mode':'n056_outer','argv':argv,'cwd':str(admission.repo),
          'env':{'PATH':'/usr/bin:/bin','PYTHONDONTWRITEBYTECODE':'1','OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1'},
          'source':admission.catalog['programmes']['NEURAL-056']['source_manifest'],
          'campaign':b['resources']['campaign_id'],'nonce':launch['nonce'],'parent_launch':b['launch_pin'],
          'group_parent':launch['group_parent'],'group_name':launch['group_name'],
          'limits':{'memory_bytes':hard['memory_bytes'],'pids':hard['pids'],'cpu_ns':hard['cpu_ns'],
                    'stream_bytes':integer(outer['stream_bytes'],1),'whole_cpu_ns':hard['cpu_ns'],
                    'whole_memory_bytes':hard['memory_bytes'],'whole_storage_bytes':hard['retained_storage_bytes']},
          'run_deadline_ns':hard['run_deadline_ns'],'evidence_deadline_ns':hard['evidence_deadline_ns'],
          'output_prefix':launch['host_output_prefix']}
    running=host.start(spec);observed=host.finish(running)
    need(type(observed) is OriginalProcessObservation,'actual host return')
    result=None;primary=running.primary
    try:
        need(observed.success,'original N056 enclosing process fully observed')
        # The source creates its capture directory only after launch. It is
        # opened as an explicitly named root after actual original closure.
        captures=Store(capture,meter)
        _,complete=_capture_absolute(captures,'ORIGINAL_COMPLETION.json',integer(outer['terminal_file_bytes'],1))
        _,join=_capture_absolute(captures,'TERMINAL_JOIN.json',integer(outer['terminal_file_bytes'],1))
        result=n056_outputs(observed,store=stores,completion_pin=complete,join_pin=join,expected_source_id=source_id,
                            stream_cap=outer['stream_bytes'],metadata_cap=outer['terminal_file_bytes'])
    except BaseException as error:
        if primary is None:primary=error;meter.own_error(error,'N056_original_output_admission')
        else:meter.cleanup_errors.append(failure(error))
    resources.close(observed.record)
    record={'schema':'four_complete_n056_campaign_adapter_v1','request':b['request_pin'],
            'root_selection':b['root_pin'],'original_launch':b['launch_pin'],'original_observation':observed.record,
            'original_receipt':observed.receipt,'original_programme':result,'resources':resources.record(),
            'failure':None if primary is None else failure(primary),'scientific_qualification':False}
    try:record_pin=output_store.publish('N056_ADAPTER_REPORT.json',record)
    except BaseException as error:
        if primary is None:primary=error;meter.own_error(error,'N056_adapter_report_publication')
        else:meter.cleanup_errors.append(failure(error))
        record_pin=None
    if primary is not None:
        try:BaseException.__setattr__(primary,'four_original_campaign',{'report':record_pin,'observation':observed.record})
        except BaseException as error:meter.cleanup_errors.append(failure(error))
        raise primary
    return record_pin

def run_n098(admission,*,stores,output_store,host,resources):
    """Complete same-process N098 invocation, full collection and original failure.

    No second HostObserver.start is present. Independent prelaunch/final issuer
    and grant prerequisites remain explicit; their missing producer is not
    replaced by an invented success-shaped result or another original process.
    """
    from .n098_startup import send_final_exec,observe_failed_owner
    b=_roots(admission,stores,output_store,host,resources)
    need(b['programme']=='NEURAL-098' and resources.phase=='BOUND','one complete original bound N098 campaign')
    e=resources.binding_evidence;running=resources.running;observed=None;finish_attempted=False
    result=None;record_pin=None;primary=None;delegation=None
    try:
        need(running.spec['parent_launch']==resources.original_selection_pin,'unchanged original parked parent')
        argv=n098_argv(b,e.legacy,repo=admission.repo,catalog=admission.catalog,analysis_python=e.argv[0])
        need(argv==e.argv,'exact originally selected interpreter and full original entry argv')
        resources.activate_host_share('host_run_close')
        delegation,permit=resources.delegate_for_exec_once(admission.prelaunch_view,b['resources']['programme_budget'],running)
        send_final_exec(permit)
        resources.activate_host_share('host_run_close')
        finish_attempted=True
        observed=host.finish(running)
        need(type(observed) is OriginalProcessObservation and observed.success,'same original N098 process and all descendants complete')
        need(observed.identity==running.identity and observed.identity['parent_launch']==resources.original_selection_pin,
             'same boot/PID/start/nonce and earlier parent after original entry exec')
        # All complete original products are admitted only after full original
        # exit. Collection uses its explicitly selected later Share, not a new
        # cap or the now-inactive startup allowance.
        m=resources._current_host_share('collection_report')
        source_roots={k:s.root for k,s in stores.stores.items()}
        forbidden=set().union(*(s.forbidden for s in stores.stores.values()))
        collection=BoundRoots(source_roots,relative_base=stores.relative_base,meter=m,forbidden=forbidden)
        work=Path(e.legacy['output_parent'])/e.legacy['output_name']
        probe={'path':str(work/'COMPLETE.json'),'bytes':0,'sha256':'0'*64}
        rooted,translated=collection.route(probe)
        raw,d=rooted.capture_created(translated['path'],16777216,metadata=True)
        complete_pin={**d,'path':str(rooted.root/d['path'])}
        result=n098_outputs(observed,store=collection,complete_pin=complete_pin,selection_pin=e.legacy_pin,
                            source_sha=admission.catalog['programmes']['NEURAL-098']['source_manifest']['sha256'])
        resources.close(observed.record)
        report_store=Store(output_store.root,m)
        report={'schema':'four_complete_n098_campaign_adapter_v1','request':b['request_pin'],'root_selection':b['root_pin'],
                'final_launch':b['launch_pin'],'original_parent_launch':resources.original_selection_pin,
                'prelaunch_selection':resources.original_selection_pin,'final_binding_join':e.join_pin,
                'whole_original_delegation':delegation,'original_observation':observed.record,
                'original_receipt':observed.receipt,'original_programme':result,'resources':resources.record(),
                'all33_people_four_conditions_49_parents_retained':True,'scientific_qualification':False}
        record_pin=report_store.publish('N098_ADAPTER_REPORT.json',report)
        m.check()
        return record_pin
    except BaseException as error:
        primary=resources.fail_once(error,'N098_complete_original_campaign')
        if not finish_attempted:
            # The actual failed handoff still owns the same parked process.
            observation=observe_failed_owner(resources)
            try:resources.terminalize_failure_once(observation)
            except BaseException as later:
                if later is not primary:resources.fail_once(later,'N098_failure_terminalization')
        else:
            # No repeated finish after ambiguous original wait/cleanup/capture.
            resources.unknown.add('N098_original_finish_or_later_collection')
        try:
            m=resources._current_host_share('failure_report')
            report_store=Store(output_store.root,m)
            record_pin=report_store.publish('N098_ADAPTER_FAILURE.json',{
                'schema':'four_n098_complete_campaign_failure_v1','original_parent_launch':resources.original_selection_pin,
                'final_binding_join':e.join_pin,'original_observation':None if observed is None else observed.record,
                'resources':resources.record(),'raw_first_error_retained_in_owner':True,'scientific_qualification':False})
        except BaseException as later:resources.fail_once(later,'N098_failure_publication')
        try:BaseException.__setattr__(primary,'four_original_campaign',{'report':record_pin,'owner':resources,
                               'observation':None if observed is None else observed.record})
        except BaseException as later:resources.fail_once(later,'N098_failure_attachment')
        raise primary
