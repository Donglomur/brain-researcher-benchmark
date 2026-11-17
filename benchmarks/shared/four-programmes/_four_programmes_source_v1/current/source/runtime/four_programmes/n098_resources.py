"""Methods of the same RootResources object during the approved N098 lifecycle."""
import time
from .common import need,encode,parse,pin,failure,DependencyUnavailable,bounded_size
from .n098_contract import validate,original_interval,rows_valid,resource_projection,selection_projection
from .n098_startup import (BootstrapCustody,PrelaunchAdmission,AuthenticatedFinalBinding,BoundResourceView,
                           ExecPermit,FailureObservation,REQUIRED_ROWS,OPERATIONS,_BOUND,_PERMIT,_FAILURE)

class StagedN098Resources:
    @classmethod
    def for_prelaunch(cls,resource_subject,prelaunch_selection,source_admission,bootstrap_meter):
        from .resources import RootResources,Share
        need(cls is RootResources and type(bootstrap_meter) is BootstrapCustody,"one exact root owner and bootstrap custody")
        b=bootstrap_meter;owner=None
        # A duplicate call is a refusal, never a replacement owner.
        b.consume()
        try:
            need(type(source_admission) is PrelaunchAdmission and source_admission.bootstrap is b,
                 "actual original source-owned prelaunch admission")
            a=source_admission;a.check_original()
            need(resource_subject==a.resource_pin and prelaunch_selection==a.prelaunch_selection_pin,
                 "same exact originally captured prelaunch resource and selection paths")
            validate("ResourceProjection",a.resource,b.share);original_interval(a.resource,a.subject)
            rows=rows_valid(a.resource);need(all(k in rows for k in REQUIRED_ROWS),"complete four fixed adapter reservations")
            if b.operation_rows is None:
                raise DependencyUnavailable("N098 exact operation/row startup profile",
                    "Independent profile must bind final capture/attach and other host effects to earlier shares; no interval inference")
            need(type(b.operation_rows) is dict and set(b.operation_rows)==set(OPERATIONS) and
                 all(type(v) is tuple and v and all(k in rows and k[0]=="H" for k in v) for v in b.operation_rows.values()),
                 "independent profile covers every fixed original host operation, including failure")
            h=a.resource["hard_envelope"];window=a.subject["startup_window"]
            need(type(b.share) is Share and b.share.row==rows[REQUIRED_ROWS[0]] and
                 b.share.origin_ns==h["origin_monotonic_ns"] and b.share.deadline_ns==h["evidence_deadline_ns"],
                 "same previously allocated bootstrap Share and exact original limits/clock")
            need(b.selected["hard_envelope"]==h and b.host.meter is b.share,"same original physical bootstrap observer")
            need(set(b.windows)==set(rows),"exact selected operation interval for every original share")
            prior=None
            for key in REQUIRED_ROWS:
                w=b.windows[key];validate("Window",w,b.share)
                need(h["origin_monotonic_ns"]<=w["start_ns"]<w["stop_ns"]<=h["evidence_deadline_ns"],
                     "original complete selected absolute row interval")
                if prior is not None:need(prior<=w["start_ns"],"original disjoint fixed startup/issuer/run/report intervals")
                prior=w["stop_ns"]
            need(window["start_ns"]<=b.windows[REQUIRED_ROWS[0]]["start_ns"] and
                 b.windows[REQUIRED_ROWS[1]]["stop_ns"]<window["stop_ns"] and
                 b.windows[REQUIRED_ROWS[2]]["start_ns"]<window["stop_ns"],
                 "original startup lifecycle encompasses issuer and fixed post-issuer handoff")
            need(getattr(b.share,"_selected_window",None)==b.windows[REQUIRED_ROWS[0]],
                 "original bootstrap Share already owns its exact earlier operation interval")
            # Preserve the actual Share/cache/state; never reconstruct its prefix.
            owner=cls.__new__(cls);b.owner=owner
            owner.staged=True;owner.bootstrap=b;owner.prelaunch_admission=a;owner.original_selection_pin=a.prelaunch_selection_pin
            owner.resource_raw=a.resource_raw;owner.resource_subject=a.resource_pin;owner.selection_raw=a.legacy_raw
            owner.selection_subject=a.legacy_pin;owner.projected=a.resource;owner.rows=rows
            owner.shares={REQUIRED_ROWS[0]:b.share};owner.hard=h;owner.windows=b.windows
            owner.plan=None;owner.pin=None;owner.phase="PRELAUNCH";owner.delegated=False;owner.terminal=None
            owner.running=None;owner.running_attempted=False;owner.host_start_attempted=False;owner.binding_attempted=False;owner.binding_evidence=None
            owner.bound_view=None;owner.exec_permit=None;owner._delegating=False
            owner.primary=None;owner.secondary=[];owner.unknown=set();owner.terminal_attempted=False
            owner.failure_record=None;owner.failure_observation=None;owner.publication_prefixes=[]
            owner.host_share_handoffs=[]
            owner._healthy_startup();b.transferred=True
            return owner
        except BaseException as error:
            b.own(error,"prelaunch_owner_construction")
            if owner is not None:
                owner.phase="FAILED"
                try:BaseException.__setattr__(error,"four_incomplete_resource_owner",owner)
                except BaseException as secondary:b.own(secondary,"failed_owner_attachment")
            raise

    def _healthy_startup(self):
        need(self.staged and self.phase in ("PRELAUNCH","BOUND","DELEGATED") and self.primary is None and not self.unknown,
             "same live staged owner without failed or unknown prefix")
        self.prelaunch_admission.check_original()
        need(encode(self.projected)==self.resource_raw and encode(self.prelaunch_admission.legacy)==self.selection_raw,
             "unchanged complete original projections")
        for share in self.shares.values():
            need(share.first_error is None and not share.unknown and not share.cleanup_errors,
                 "no failed original adapter prefix")
        now=time.monotonic_ns();w=self.prelaunch_admission.subject["startup_window"]
        need(w["start_ns"]<=now<w["stop_ns"] and now<self.hard["run_deadline_ns"],"same original startup deadline")

    def _current_host_share(self,operation="prelaunch_recheck"):
        mapping=self.bootstrap.operation_rows
        if mapping is None or operation not in mapping:
            raise DependencyUnavailable("N098 exact operation/row startup profile",
                "No independently selected row owner for this actual source operation; inactive shares cannot pay")
        allowed=mapping[operation]
        need(type(allowed) is tuple and allowed and all(k in self.rows and k[0]=="H" for k in allowed),
             "fixed independently selected H operation owners")
        now=time.monotonic_ns()
        selected=[k for k in allowed if self.windows[k]["start_ns"]<=now<self.windows[k]["stop_ns"]]
        need(len(selected)==1,"one independently selected currently active H operation share")
        return self._staged_share(*selected[0])

    def _staged_share(self,owner,stage):
        from .resources import Share
        key=(owner,stage)
        need(self.phase in ("PRELAUNCH","BOUND","DELEGATED","FAILED") and key in self.rows and key in self.windows,
             "only originally selected same-owner share")
        w=self.windows[key];now=time.monotonic_ns()
        need(w["start_ns"]<=now<w["stop_ns"],"selected original operation interval, no inferred timeout")
        if key not in self.shares:
            self.shares[key]=Share(self.rows[key],origin_ns=self.hard["origin_monotonic_ns"],deadline_ns=self.hard["evidence_deadline_ns"])
            self.shares[key]._selected_window=w
        return self.shares[key]

    def activate_host_share(self,operation):
        """Same physical handles, explicitly selected current H accounting row.

        Never transfer consumption, merge counters or reset an origin. Every
        physical I/O component must still own the exact earlier H Share; a
        foreign observer/owner is a refusal, not silently reassigned work.
        """
        from .observer import HostObserver,KernelGroup,StorageObservation
        from .common import Store
        need(self.staged and self.phase in ("PRELAUNCH","BOUND","DELEGATED","FAILED"),"same active source owner")
        host=self.bootstrap.host;new=self._current_host_share(operation);old=host.meter
        need(type(host) is HostObserver and any(old is s for s in self.shares.values()) and any(new is s for s in self.shares.values()),
             "both actual accounting shares remain in the same original cache")
        pieces=[host,host.outputs,host.whole_group,host.storage]
        need(type(host.outputs) is Store and type(host.whole_group) is KernelGroup and
             type(host.storage) is StorageObservation,"actual original physical and output owners")
        if self.running is not None:
            need(self.running.owner is host and (host.active.get(self.running.spec["nonce"]) is self.running or
                 self.running.spec["nonce"] not in host.active),"same actual running or completed original handle")
            if self.running.group is not None:
                need(type(self.running.group) is KernelGroup,"same original child aggregate")
                pieces.append(self.running.group)
        need(all(component.meter is old for component in pieces),"no foreign meter or partially reassigned physical component")
        if new is old:return new
        # Both references and the full transition prefix are retained even if
        # a subsequent assignment/clock observation fails.
        row={"operation":operation,"from_share":old,"to_share":new,"applied_components":[],"complete":False}
        self.host_share_handoffs.append(row)
        try:
            for component in pieces:
                component.meter=new;row["applied_components"].append(type(component).__name__)
            new.check();row["complete"]=True
            return new
        except BaseException as error:self.fail_once(error,"original_host_share_handoff");raise

    def resource_projection_view(self):
        need(self.staged and self.phase in ("PRELAUNCH","BOUND","DELEGATED"),"actual live staged projection view")
        need(encode(self.projected)==self.resource_raw,"unchanged original projection")
        # A detached ordinary view is not a plan, owner or source authority.
        return parse(self.resource_raw,len(self.resource_raw))

    def start_parked_once(self):
        from .observer import HostObserver,RunningProcess
        need(self.staged and self.phase=="PRELAUNCH" and not self.host_start_attempted and not self.running_attempted,
             "one actual original parked process start")
        self._healthy_startup();b=self.bootstrap
        if b.start_spec is None or b.pass_fds is None:
            raise DependencyUnavailable("N098 selected parked bridge launch profile",
                "Exact startup source argv/inherited-FD producer is not selected; no child may start")
        need(type(b.host) is HostObserver and b.host.meter is b.share,"same actual bootstrap observer")
        spec=b.start_spec
        need(spec["parent_launch"]==self.original_selection_pin and spec["source"]==self.prelaunch_admission.subject["startup_source"] and
             spec["run_deadline_ns"]==self.hard["run_deadline_ns"] and spec["evidence_deadline_ns"]==self.hard["evidence_deadline_ns"],
             "exact original selected parked source/parent and nonrenewed cutoffs")
        self.host_start_attempted=True
        try:
            running=b.host.start(spec,pass_fds=b.pass_fds)
            self.attach_running_once(b.host,running)
            return running
        except BaseException as error:
            # HostObserver allocates its actual handle before dependent effects.
            # Recover only that exact original nonce slot; never enumerate or
            # restart processes, nor interpret an absent PID as no effect.
            known=b.host.active.get(spec["nonce"])
            if self.running is None and type(known) is RunningProcess and known.owner is b.host:
                self.running=known
            self.fail_once(error,"original_parked_start")
            raise

    def attach_running_once(self,host,running):
        from .observer import HostObserver,RunningProcess
        need(self.staged and self.phase=="PRELAUNCH" and not self.running_attempted,"one original start attachment")
        self.running_attempted=True
        try:
            need(type(host) is HostObserver and host is self.bootstrap.host and type(running) is RunningProcess and
                 running.owner is host and host.active.get(running.spec["nonce"]) is running,"actual original H-owned running handle")
            self.running=running;self.host_start_attempted=True # Custody before further fallible validation.
            spec=running.spec;a=self.prelaunch_admission
            need(spec["parent_launch"]==self.original_selection_pin and spec["source"]==a.subject["startup_source"] and
                 spec["campaign"]==a.subject["campaign_id"] and spec["mode"]=="n098_bridge" and
                 spec["run_deadline_ns"]==self.hard["run_deadline_ns"] and
                 spec["evidence_deadline_ns"]==self.hard["evidence_deadline_ns"],"original source/parent/campaign and hard cutoffs")
            need(running.group is not None and running.group.path.parent==host.whole_group.path,"same actual original aggregate")
            if running.identity is not None:
                need(running.identity["parent_launch"]==self.original_selection_pin and
                     running.identity["source"]==spec["source"] and running.identity["launch_nonce"]==spec["nonce"],
                     "unchanged actual initial process ancestry")
            if running.primary is not None:raise running.primary
            need(running.identity is not None and running.child is not None,"acknowledged actual parked process")
            self._healthy_startup()
        except BaseException as error:self.fail_once(error,"original_start_attachment");raise

    def bind_final_once(self,final_plan,final_plan_pin,final_binding_join,actual_parked_handle):
        need(self.staged and self.phase=="PRELAUNCH" and not self.binding_attempted,"one original final attach attempt")
        self.binding_attempted=True
        try:
            self._healthy_startup();e=final_binding_join;a=self.prelaunch_admission;r=self.running
            need(type(e) is AuthenticatedFinalBinding and r is actual_parked_handle and r is not None,
                 "same actual private final binding and original handle")
            e.check_original(self,r)
            need(final_plan is e.plan and final_plan_pin==e.plan_pin,"captured actual final plan, no caller replacement")
            # Full final schemas were checked by producer; repeat at actual owner.
            e.schemas.validate("resources","root_resource_plan_schema",final_plan,self._current_host_share("final_attach"))
            need(encode(resource_projection(final_plan))==self.resource_raw and
                 encode(selection_projection(e.legacy))==self.selection_raw,"full exact unchanged resource and original selection projections")
            original=self.original_selection_pin
            need(e.binding["root"]["programme_bindings"]["startup_authority_bridge"]==a.prelaunch_selection_pin==original==
                 r.spec["parent_launch"]==r.identity["parent_launch"]==e.parked["prelaunch_selection"]==e.join["prelaunch_selection"],
                 "all exact earlier PrelaunchSelection descriptor and parent joins")
            need(e.parked["process"]==r.identity==e.live_identity and e.parked["source"]==a.subject["startup_source"] and
                 e.parked["original_clock"]==a.subject["original_clock"],"same actual parked/live boot PID start nonce and source")
            need(e.join["resource_plan"]==e.plan_pin and e.join["legacy_selection"]==e.legacy_pin==
                 final_plan["programme_budget"]["legacy_selection"] and e.join["controller_envelope"]==e.envelope_pin==
                 e.legacy["qualifications"]["controller-envelope"],"whole final original legacy/envelope joins")
            need(e.envelope["properties"]["controller_pid"]==r.identity["pid"] and
                 e.envelope["properties"]["selection_id"]==e.legacy["execution_authority"]["selection_id"] and
                 e.envelope["properties"]["whole_budget"]==e.legacy["budget"],"actual original controller envelope")
            self._healthy_startup()
            self.plan=e.plan;self.pin=e.plan_pin;self.binding_evidence=e;self.phase="BOUND"
            view=BoundResourceView(_BOUND,self,e);self.bound_view=view
            return view
        except BaseException as error:self.fail_once(error,"final_binding_attach");raise

    def delegate_for_exec_once(self,bound_view,programme_budget,actual_parked_handle):
        need(self.staged and self.phase=="BOUND","only original fully bound owner may delegate")
        try:
            self._healthy_startup();self._current_host_share("delegate_for_exec").check();v=bound_view
            need(type(v) is BoundResourceView and v is self.bound_view and v.owner is self and
                 v.plan is self.plan and v.evidence is self.binding_evidence and actual_parked_handle is self.running,
                 "same actual bound view, owner, final evidence and original running handle")
            self.binding_evidence.check_original(self,self.running)
            need(self.binding_evidence.binding["root"]["programme_bindings"]["startup_authority_bridge"]==self.original_selection_pin,
                 "same earlier bridge before original delegation")
            need(programme_budget is self.plan["programme_budget"],"same complete original final programme reservation")
            self._delegating=True
            try:record=self.delegate_programme(programme_budget)
            finally:self._delegating=False
            self.phase="DELEGATED";permit=ExecPermit(_PERMIT,self,v,self.running);self.exec_permit=permit
            return record,permit
        except BaseException as error:self.fail_once(error,"original_programme_delegation");raise

    def fail_once(self,raw_error,dimension):
        need(isinstance(raw_error,BaseException),"actual original raw exception")
        if self.primary is None:self.primary=raw_error
        elif raw_error is not self.primary:self.secondary.append(raw_error)
        self.unknown.add(dimension)
        self.phase="TERMINAL_UNKNOWN" if self.terminal_attempted else "FAILED"
        # Owning an error is not a new metered effect or a reason to extend an
        # inactive early row. Keep the raw source owner independently of timing.
        self.bootstrap.share.own_error(raw_error,dimension)
        try:BaseException.__setattr__(self.primary,"four_original_resource_owner",self)
        except BaseException as error:self.secondary.append(error)
        return self.primary

    def terminalize_failure_once(self,observation):
        need(self.staged and self.primary is not None and not self.terminal_attempted,"one original failure terminalization")
        self.terminal_attempted=True
        try:
            m=self._current_host_share("failure_report")
            need(len(self.secondary)<=256 and len(self.unknown)<=256 and
                 all(len(s.cleanup_errors)<=256 and len(s.unknown)<=256 for s in self.shares.values()),
                 "complete failure metadata remains in original fixed domain")
            bound=16*bounded_size(self.projected)+65536+4096*(len(self.secondary)+len(self.unknown))
            m.charge("work_units",bound*64);m.charge("retained_bytes",bound)
            o=observation
            need(type(o) is FailureObservation and o._token is _FAILURE and o.owner is self and
                 o.observer is self.bootstrap.host and o.running is self.running,"same actual original failure observation")
            self.failure_observation=o;self.publication_prefixes.extend(o.publication_prefixes)
            self.phase="TERMINAL_KNOWN" if o.known else "TERMINAL_UNKNOWN"
            prefixes=[]
            for i,row in enumerate(self.projected["adapter_reservations"]):
                s=self.shares.get((row["owner_role"],row["stage"]))
                if s is None:continue # Unspent, full outstanding reservation remains in original projection.
                prefixes.append({"owner_role":row["owner_role"],"stage":row["stage"],"reservation_id":row["reservation_id"],
                    "resource_row_index":i,"limits":dict(s.limits),"spent":dict(s.spent),"process_starts":s.process_starts,
                    "observed_own_process_cpu_ns":s.cpu_ns,"observed_active_span_wall_ns":s.wall_ns,
                    "active_span_start":None if s._active is None else {"monotonic_ns":s._active[0],"process_cpu_ns":s._active[1]},
                    "original_error_present":s.first_error is not None,"first_error_diagnostic":None,
                    "secondary_error_diagnostics":[None for _ in s.cleanup_errors],"unknown_dimensions":sorted(s.unknown)})
            e=self.binding_evidence
            record={"schema":"four_n098_staged_failure_custody_v2","programme":"NEURAL-098","phase":self.phase,
                "prelaunch_selection":self.original_selection_pin,"resource_subject":self.resource_subject,"selection_subject":self.selection_subject,
                "final_resource_plan":self.pin,"final_binding_join":None if e is None else e.join_pin,
                "original_parent_launch":self.original_selection_pin,"final_launch":None if e is None else e.binding["launch_pin"],
                "original_clock":self.prelaunch_admission.subject["original_clock"],"startup_window":self.prelaunch_admission.subject["startup_window"],
                "delegated":self.delegated,"programme_reserved":self.plan["programme_budget"] if self.delegated else None,
                "adapter_prefixes":prefixes,"spawn_disposition":o.spawn_disposition,
                "original_process_identity":None if self.running is None else self.running.identity,
                "original_observation":None if o.observed is None else o.observed.receipt,
                "original_error_present":True,"first_error_diagnostic":None,"secondary_error_diagnostics":[None for _ in self.secondary],
                "unknown_dimensions":sorted(self.unknown),"publication_attempt_prefixes":list(self.publication_prefixes),
                "reservation_disposition":"FULL_RETAINED_NO_REUSE","successful_science":False,"self_authorizes_completion":False}
            # Diagnostic nulls mean no successfully published error record, not
            # a missing original exception; raw errors remain on the same owner.
            from .schema import check
            from .n098_tables import RECORD_DEFINITIONS
            check(record,RECORD_DEFINITIONS["FailureCustodyRecord"],root={"$defs":RECORD_DEFINITIONS})
            self.failure_record=record
            return record
        except BaseException as error:
            self.secondary.append(error);self.unknown.add("failure_terminalization");self.phase="TERMINAL_UNKNOWN"
            raise self.primary

    def _staged_record(self):
        return {"schema":"four_n098_same_owner_resource_state_v1","phase":self.phase,"prelaunch_selection":self.original_selection_pin,
                "resource_subject":self.resource_subject,"final_resource_plan":self.pin,"programme_delegated":self.delegated,
                "programme_reserved":self.plan["programme_budget"] if self.delegated else None,
                "adapter_shares":[self.shares[k].record() for k in sorted(self.shares)],"first_error":None if self.primary is None else failure(self.primary),
                "secondary_errors":[failure(e) for e in self.secondary],"unknown_dimensions":sorted(self.unknown),
                "original_final_observation":self.terminal,"failure_record":self.failure_record,
                "full_reservations_retained":True,"source_runtime_scientific_acceptance":False}
