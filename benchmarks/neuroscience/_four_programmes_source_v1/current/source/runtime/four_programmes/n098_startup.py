"""N098 fixed prelaunch and final-binding custody.

The bootstrap, issuer and parked channel are independent source prerequisites.
No dictionary or callback creates their private authority. The ordinary joins
below do not relax that boundary and never execute the scientific programme.
"""
import time
from .common import need,closed,encode,parse,pin,descriptor,failure,bounded_size,DependencyUnavailable,Store
from .n098_contract import (capture,validate,validate_selection_projection,original_interval,
                            rows_valid,resource_projection,selection_projection)

_BOOTSTRAP=object();_PRELAUNCH=object();_FINAL=object();_BOUND=object();_PERMIT=object();_FAILURE=object()
OPERATIONS=("prelaunch_recheck","request_join","final_attach","delegate_for_exec","bound_external",
            "final_chain_capture","host_final_binding","host_run_close","collection_report","host_failure_close","failure_report")
REQUIRED_ROWS=(("H","N098_STARTUP"),("ROOT_ISSUER","N098_FINAL_BINDING"),
               ("H","N098_RUN_AND_CLOSE"),("H","N098_COLLECTION_REPORT"))

class BootstrapCustody:
    """Transferred by reference from the independently selected root entry."""
    def __init__(self,token,*,share,host,store,selected,windows,source_context,channel):
        need(token is _BOOTSTRAP,"only separately selected fixed bootstrap source")
        self.share=share;self.host=host;self.store=store;self.selected=selected;self.windows=windows
        self.source_context=source_context;self.channel=channel
        self.operation_rows=None # Exact independent startup profile remains unselected.
        self.start_spec=None;self.pass_fds=None # Same profile must own actual bridge argv/FDs.
        self.attempted=False;self.transferred=False;self.owner=None
        self.primary=None;self.secondary=[];self.unknown=set();self.terminal_attempted=False
    def own(self,error,dimension):
        if self.primary is None:self.primary=error
        else:self.secondary.append(error)
        self.unknown.add(dimension);self.share.own_error(error,dimension)
    def consume(self):
        need(not self.attempted and not self.transferred,"one original bootstrap transfer attempt")
        self.attempted=True
    def healthy(self):
        need(self.primary is None and not self.unknown and self.share.first_error is None and
             not self.share.unknown and not self.share.cleanup_errors,"complete original bootstrap prefix")
        # Preserve the early Share and its completed interval. Later host work
        # uses only an already selected currently active H row; no extension.
        self.current_host_share().check()
    def current_host_share(self,operation="prelaunch_recheck"):
        if not self.transferred:return self.share
        return self.owner._current_host_share(operation)


def bootstrap_from_selected_root(*args,**kwargs):
    # No selected upstream constructor/qualification exists. Do not allocate a
    # replacement Share from caller JSON or pretend an ordinary source pin is
    # a runtime bootstrap. Source integration must select the real fixed entry.
    raise DependencyUnavailable("N098 original bootstrap source",
        "Exact independent bootstrap/physical observer/interval-profile constructor is not selected; "
        "existing costs and the original H:N098_STARTUP Share must be supplied by that source")

class PrelaunchAdmission:
    __slots__=("_token","bootstrap","prelaunch_selection_pin","selection_raw","selection","subject_pin", "subject_raw","subject",
               "resource_raw","resource","resource_pin","legacy_raw","legacy","legacy_pin","context","environment","catalog","repo")
    def __init__(self,token,**fields):
        need(token is _PRELAUNCH,"fixed source-owned prelaunch verifier only")
        self._token=token
        need(set(fields)==set(self.__slots__)-{"_token"},"complete private prelaunch inputs")
        for k,v in fields.items():setattr(self,k,v)
    def check_original(self,operation="prelaunch_recheck"):
        need(self._token is _PRELAUNCH and type(self.bootstrap) is BootstrapCustody,"actual original prelaunch context")
        self.bootstrap.current_host_share(operation).charge("work_units",sum(map(len,(self.selection_raw,self.subject_raw,self.resource_raw,self.legacy_raw)))*64+4096)
        for raw,value,expected in ((self.selection_raw,self.selection,self.prelaunch_selection_pin),
                                   (self.subject_raw,self.subject,self.subject_pin),
                                   (self.resource_raw,self.resource,self.resource_pin),
                                   (self.legacy_raw,self.legacy,self.legacy_pin)):
            need(raw==encode(value) and pin(raw)=={k:expected[k] for k in ("bytes","sha256")},"unchanged exact captured prelaunch bytes")
        self.bootstrap.healthy()


def admit_n098_prelaunch(bootstrap,*,catalog,adapter_manifest,repo,selected_context,selected_templates,environment):
    """Bounded producer for the exact original earlier PrelaunchSelection."""
    need(type(bootstrap) is BootstrapCustody and not bootstrap.attempted,"actual unconsumed bootstrap custody")
    b=bootstrap;m=b.share
    try:
        b.healthy()
        from . import dependencies
        dependencies.require("context_v6_source_admission",selected_context)
        dependencies.require("context_four_programme_source_templates",selected_templates)
        dependencies.require("root_issuer_source_and_qualification",b.selected["issuer"])
        dependencies.require("n098_same_process_startup_qualification",environment)
        from .context_boundary import admitted_context
        context=admitted_context("NEURAL-098",catalog,selected_context,selected_templates,environment)
        need(type(b.store) is Store and b.store.meter is m and b.host.meter is m,"same original bootstrap I/O and observer Share")
        sr,s=capture(b.store,b.selected["prelaunch_selection"],"PrelaunchSelection",131072)
        tr,t=capture(b.store,s["subject"],"PrelaunchSubject",131072)
        rr,r=capture(b.store,t["resource_subject"],"ResourceProjection",262144)
        lr=b.store.read(t["input_selection_subject"],1048576,metadata=True);l=parse(lr,1048576)
        need(lr==encode(l),"exact complete canonical selection projection")
        expected=catalog["programmes"]["NEURAL-098"]
        need(t["source_binding"]=={"accepted_manifest":expected["source_manifest"],
             "accepted_candidate":expected["accepted_candidate"],"adapter_manifest":adapter_manifest},"exact whole accepted source binding")
        for name in ("startup_source","startup_endpoint","root_bootstrap_source","original_clock","startup_window"):
            need(t[name]==b.selected[name],"same independently selected bootstrap "+name)
        for name in ("issuer","source_admission","environment_qualification"):
            need(s[name]==b.selected[name],"same independently selected earlier "+name)
        need(s["subject"]==b.selected["prelaunch_subject"] and t["resource_subject"]==b.selected["resource_subject"] and
             t["input_selection_subject"]==b.selected["selection_subject"],"exact immutable root prelaunch paths")
        need(t["campaign_id"]==r["campaign_id"]==b.selected["campaign_id"],"same original campaign")
        original_interval(r,t);rows=rows_valid(r)
        need(all(k in rows for k in REQUIRED_ROWS),"all four fixed startup/issuer/run-close/report reservations")
        validate_selection_projection(l,expected["source_manifest"]["sha256"],r,m)
        return PrelaunchAdmission(_PRELAUNCH,bootstrap=b,prelaunch_selection_pin=b.selected["prelaunch_selection"],
              selection_raw=sr,selection=s,subject_pin=s["subject"],subject_raw=tr,subject=t,resource_raw=rr,resource=r,
              resource_pin=t["resource_subject"],legacy_raw=lr,legacy=l,legacy_pin=t["input_selection_subject"],
              context=context,environment=environment,catalog=catalog,repo=repo)
    except BaseException as error:b.own(error,"prelaunch_admission");raise

class AuthenticatedFinalBinding:
    __slots__=("_token","owner","prelaunch_admission","running","binding","plan_raw","plan","plan_pin", "join","join_pin",
               "parked","parked_pin","legacy","legacy_pin","envelope","envelope_pin","live_identity","prefix_pin","argv","channel","schemas")
    def __init__(self,token,**fields):
        need(token is _FINAL,"fixed independent final chain verifier only")
        self._token=token;need(set(fields)==set(self.__slots__)-{"_token"},"complete final source evidence")
        for k,v in fields.items():setattr(self,k,v)
    def check_original(self,owner,running):
        need(self._token is _FINAL and self.owner is owner and self.running is running and
             self.prelaunch_admission is owner.prelaunch_admission,"same actual original final evidence owner")
        need(self.plan_raw==encode(self.plan) and pin(self.plan_raw)=={k:self.plan_pin[k] for k in ("bytes","sha256")},
             "same actual complete final plan bytes")
        need(self.binding["resources"] is self.plan and self.binding["resource_pin"]==self.plan_pin,"same final bound plan object")
        need(self.channel is owner.bootstrap.channel,"unchanged original private bridge channel")


def final_issuer_evidence(*args,**kwargs):
    raise DependencyUnavailable("N098 final issuer/channel producer",
        "No independently selected final issuer publication/parked-ready/grant record source and qualification exists; "
        "a generic HostEvent, descriptor, flag or structural bind_root return cannot mint final admission")

class BoundResourceView:
    __slots__=("_token","owner","plan","pin","evidence")
    def __init__(self,token,owner,evidence):
        need(token is _BOUND,"successful original bind_final_once only")
        self._token=token;self.owner=owner;self.plan=owner.plan;self.pin=owner.pin;self.evidence=evidence

class ExecPermit:
    __slots__=("_token","owner","view","running","channel","argv","evidence","attempted")
    def __init__(self,token,owner,view,running):
        need(token is _PERMIT,"original once-only complete delegation only")
        self._token=token;self.owner=owner;self.view=view;self.running=running
        self.evidence=view.evidence;self.channel=view.evidence.channel;self.argv=view.evidence.argv;self.attempted=False
    def consume(self,owner,running,channel):
        need(self._token is _PERMIT and not self.attempted and self.owner is owner and self.running is running and
             self.channel is channel,"same original unused private exec permit")
        self.attempted=True # Burn before checks or any ambiguous write.
        try:owner._healthy_startup();need(owner.phase=="DELEGATED","complete original delegation before grant")
        except BaseException as error:owner.fail_once(error,"exec_permit_attempt");raise
        return self.evidence

class FailureObservation:
    __slots__=("_token","owner","observer","running","observed","known","spawn_disposition","publication_prefixes")
    def __init__(self,token,*,owner,observer,running,observed,known,spawn_disposition,publication_prefixes):
        need(token is _FAILURE,"same original failure observation producer only")
        self._token=token;self.owner=owner;self.observer=observer;self.running=running;self.observed=observed
        self.known=known;self.spawn_disposition=spawn_disposition;self.publication_prefixes=publication_prefixes

def observe_failed_owner(owner):
    """Own actual original H finish once; never retry an uncertain terminal path."""
    from .resources import RootResources
    from .observer import OriginalProcessObservation
    need(type(owner) is RootResources and owner.staged and owner.primary is not None,
         "original failed staged resource owner")
    need(not getattr(owner,"failure_observation_attempted",False),"one failure observation attempt")
    owner.failure_observation_attempted=True
    host=owner.bootstrap.host;r=owner.running;observed=None;known=False
    spawn="not_attempted" if not owner.host_start_attempted else "attempted_unacknowledged"
    publications=[]
    try:
        if r is None:
            # The selected independent parent bootstrap/physical finalizer is
            # absent; no child PID is not a substitute for that observation.
            raise DependencyUnavailable("N098 original pre-child parent closure",
                "The fixed original root bootstrap finalizer and publication are not selected; physical closure remains unknown")
        spawn="acknowledged" if r.record["spawn_acknowledged"] else ("attempted_unacknowledged" if r.record["spawn_attempted"] else "not_attempted")
        need(host.active.get(r.spec["nonce"]) is r,"same unconsumed actual H lifecycle")
        owner.activate_host_share("host_failure_close")
        observed=host.finish(r)
        need(type(observed) is OriginalProcessObservation,"actual original H failure observation")
        rec=observed.record
        # A known failed exit is distinct from a successful scientific result.
        known=(rec["streams_eof"]=={"stdout":True,"stderr":True} and rec["group_empty"] is True and
               rec["group_removed"] is True and rec["physical_final_known"] is True and rec["publication_complete"] is True and
               not rec["cleanup_errors"] and not rec["unknown_dimensions"])
        publications=list(rec["original_output_prefixes"])
        if r.primary is not None and r.primary is not owner.primary:owner.fail_once(r.primary,"original_H_failure")
        if not known:owner.unknown.add("original_final_physical_cleanup_or_publication")
    except BaseException as error:
        owner.fail_once(error,"original_failure_observation")
    return FailureObservation(_FAILURE,owner=owner,observer=host,running=r,observed=observed,known=known,
                              spawn_disposition=spawn,publication_prefixes=publications)

def send_final_exec(permit):
    """The exact grant/channel producer is a still-unselected fixed source seam."""
    need(type(permit) is ExecPermit,"actual original private exec permit")
    permit.consume(permit.owner,permit.running,permit.channel)
    raise DependencyUnavailable("N098 exact private final exec grant",
        "The source-qualified final grant encoding, inherited-channel bridge and same-PID exec producer "
        "are not selected; the original one-use permit has been consumed and cannot be replayed")

class _OriginalQualificationIO:
    """Original read_pin API charged to the existing selected H Share."""
    def __init__(self,meter):
        self.meter=meter;self.read_reserved=0;self.read_completed=0
        self.write_reserved=0;self.write_completed=0
    def check(self):self.meter.check()
    def charge_read(self,n):
        self.meter.charge('read_bytes',n);self.read_reserved+=n
        self.meter.charge('retained_bytes',n);self.meter.charge('work_units',n*64+4096)
    def charge_write(self,n):
        # Qualification is read-only. No original Budget or fresh output quota.
        need(False,'no qualification-side output producer selected')


def verify_final_chain(owner,join_pin,*,schemas,session,request_catalog,adapter_manifest):
    """Fixed actual-source producer for AuthenticatedFinalBinding.

    The independent issuer/parked-ready provenance seam deliberately refuses
    until separately selected. Every later structural relation is nevertheless
    concrete here, including original selection and qualification APIs.
    """
    from .resources import RootResources
    from .source_session import SourceSession
    from .request import source_check,bind_root
    from .identity import process_identity
    from .external_campaigns import n098_argv
    need(type(owner) is RootResources and owner.staged and owner.phase=='PRELAUNCH',
         'same original unbound N098 owner')
    try:
        owner._healthy_startup();a=owner.prelaunch_admission;r=owner.running
        need(type(session) is SourceSession and session.programme=='NEURAL-098',
             'actual fixed original N098 source session, never callbacks')
        # This call currently raises. Its actual source-owned issuer/ready/frame
        # producer has not been selected; JSON checks below cannot supply it.
        final_issuer_evidence(owner,join_pin)
        owner.activate_host_share('host_final_binding')
        m=owner._current_host_share('final_chain_capture')
        need(session.store.meter is m,'same earlier H row owns original qualification source and API work')
        store=Store(owner.bootstrap.store.root,m,forbidden=owner.bootstrap.store.forbidden)
        jr,j=capture(store,join_pin,'FinalBindingJoin',131072)
        need(j['prelaunch_selection']==owner.original_selection_pin and r is not None,
             'same actual original earlier selection and parked process')
        expected_parked=getattr(owner,'parked_identity_pin',None)
        expected_prefix=getattr(owner,'startup_cost_prefix_pin',None)
        need(expected_parked is not None and expected_prefix is not None and
             j['parked_identity']==expected_parked and j['original_startup_cost_prefix']==expected_prefix,
             'actual earlier H-produced parked identity and startup prefix; never issuer-supplied substitutes')
        kr,k=capture(store,j['parked_identity'],'ParkedIdentity',131072)
        pr=store.read(j['resource_plan'],262144,metadata=True);plan=parse(pr,262144)
        need(pr==encode(plan),'canonical final original resource bytes')
        lr=store.read(j['legacy_selection'],1048576,metadata=True);legacy=parse(lr,1048576)
        need(lr==encode(legacy),'canonical final original legacy selection bytes')
        root_raw=store.read(j['root_selection'],262144,metadata=True);root=parse(root_raw,262144)
        launch_raw=store.read(j['launch_binding'],262144,metadata=True);launch=parse(launch_raw,262144)
        request_raw=store.read(j['request'],131072,metadata=True)
        checked=source_check(request_raw,schemas,request_catalog,adapter_manifest,m)
        binding=bind_root(checked,j['request'],j['root_selection'],root,j['launch_binding'],launch,
                          j['resource_plan'],plan,schemas,m,n098_prelaunch_context=a)
        need(encode(resource_projection(plan))==a.resource_raw and encode(selection_projection(legacy))==a.legacy_raw,
             'both entire unchanged original projections, no omitted fields')
        need(legacy['qualifications']['controller-envelope']==j['controller_envelope'] and
             binding['request']['campaign_inputs']['legacy_selection']==j['legacy_selection'] and
             plan['programme_budget']['legacy_selection']==j['legacy_selection'],
             'same complete original final legacy/envelope/resource chain')
        source=request_catalog['programmes']['NEURAL-098']['source_manifest']
        m.charge('work_units',bounded_size(legacy)*64+4096)
        session.api('n098_selection')(legacy,'campaign',source['sha256'])
        qbudget=_OriginalQualificationIO(m)
        envelope=session.api('n098_qualification')(a.repo,legacy,'controller-envelope',source['sha256'],qbudget)
        need(type(envelope) is dict and envelope['properties']['controller_pid']==r.identity['pid'] and
             envelope['properties']['selection_id']==legacy['execution_authority']['selection_id'] and
             envelope['properties']['whole_budget']==legacy['budget'] and
             all(envelope['properties'].get(key) is True for key in ('independent_original_supervisor',
                 'controller_and_descendants_in_aggregate_envelope','hard_wall_cpu_memory_storage_limits',
                 'startup_and_cleanup_within_original_deadline')),'all original controller lifetime requirements')
        # Re-capture exact selected envelope bytes: the original API also reads
        # its independently qualified source files. Both actual costs are kept.
        envelope_raw=store.read(j['controller_envelope'],1048576,metadata=True)
        need(parse(envelope_raw,1048576)==envelope,'same exact original envelope object')
        need(r.owner is owner.bootstrap.host and r.owner.active.get(r.spec['nonce']) is r and r.child.poll() is None,
             'same actual still-live original parked handle')
        live=process_identity(r.child.pid,launch_nonce=r.spec['nonce'],source=r.spec['source'],
                              parent_launch=r.spec['parent_launch'],mapping=r.owner.mapping,meter=m)
        need(live==r.identity==k['process'] and k['prelaunch_selection']==owner.original_selection_pin and
             k['source']==a.subject['startup_source'] and k['original_clock']==a.subject['original_clock'] and
             a.subject['startup_window']['start_ns']<=k['actual_capture_ns']<a.subject['startup_window']['stop_ns'],
             'actual original boot PID start nonce source ready and clock')
        # The interpreter is fixed by the original analysis qualification. The
        # independently selected bridge profile must name exactly that argv.
        argv=getattr(owner.bootstrap,'final_argv',None)
        if argv is None:
            raise DependencyUnavailable('N098 exact final interpreter/argv profile','Independent startup profile has not selected the actual same-PID exec argv')
        need(argv==n098_argv(binding,legacy,repo=a.repo,catalog=request_catalog,analysis_python=argv[0]),
             'full exact original interpreter/entry selection argv')
        owner._healthy_startup()
        return AuthenticatedFinalBinding(_FINAL,owner=owner,prelaunch_admission=a,running=r,binding=binding,
              plan_raw=pr,plan=plan,plan_pin=j['resource_plan'],join=j,join_pin=join_pin,parked=k,parked_pin=j['parked_identity'],
              legacy=legacy,legacy_pin=j['legacy_selection'],envelope=envelope,envelope_pin=j['controller_envelope'],
              live_identity=live,prefix_pin=j['original_startup_cost_prefix'],argv=argv,channel=owner.bootstrap.channel,schemas=schemas)
    except BaseException as error:owner.fail_once(error,'final_original_chain_verification');raise
