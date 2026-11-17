"""Original whole opportunity and one-time nested adapter reservations."""
import time
from .common import Meter,need,integer,closed,failure
from .n098_resources import StagedN098Resources

class Share(Meter):
    def __init__(self,row,*,origin_ns,deadline_ns):
        limits={k:row[k] for k in ("read_bytes","write_bytes","work_units","retained_bytes")}
        super().__init__(limits,origin_ns=origin_ns,deadline_ns=deadline_ns,
                         owner=row["owner_role"],reservation_id=row["reservation_id"])
        self.row=dict(row);self.process_starts=0;self.cpu_ns=0;self.wall_ns=0;self._active=None
        self._raw_first_error=None;self._raw_error_history=[];self._early_parent_custody=None
        self._end_attempted=False;self._end_observation=None;self._end_primary=None;self._end_secondary=[]
    def own_error(self,error,dimension=None):
        # The original exception is owned before metadata projection, including
        # early plan reads that precede nested EarlyResources construction.
        if self._raw_first_error is None:self._raw_first_error=error
        self._raw_error_history.append((error,dimension))
        parent=self._early_parent_custody
        if parent is not None:
            from .early_resources import ParentCustody
            need(type(parent)is ParentCustody and parent.share is self,'same actual early raw-error owner')
            mapped=None
            if dimension is not None:
                if 'read'in dimension:mapped='read_bytes'
                elif 'write'in dimension:mapped='write_bytes'
                elif 'cpu'in dimension:mapped='cpu_ns'
                elif 'clock'in dimension or 'wall'in dimension:mapped='wall_ns'
            parent.retain(error,'source_capture','unknown_failure','Share.own_error',mapped)
        super().own_error(error,dimension)
    def charge(self,kind,amount):
        try:
            custodian=getattr(self,'bootstrap_custodian',None)
            protected=None if custodian is None else custodian.logical_counters.protected_owner
            if protected is not None:
                # Repeated original source checks remain attributable to H.
                # Only its separate terminal view may spend the terminal pool.
                return protected.charge('host',kind,amount)
            return super().charge(kind,amount)
        except BaseException as error:
            parent=self._early_parent_custody
            if parent is not None:
                from .early_resources import retain_source_failure
                raise retain_source_failure(parent,error,'Share.charge')
            if self._raw_first_error is None:self._raw_first_error=error
            self._raw_error_history.append((error,None))
            raise
    def _bootstrap_terminal_hold(self,dimension):
        custodian=getattr(self,'bootstrap_custodian',None)
        if custodian is None:return 0
        return 0 if custodian.logical_counters.terminal_entered() else custodian.terminal[dimension]
    def check(self):
        super().check()
        custodian=getattr(self,'bootstrap_custodian',None)
        if custodian is not None and custodian.transferred and custodian.logical_counters.protected_owner is None:
            # Actual elapsed observations keep the original span/native slack;
            # a failed observation remains owned, never rolled back or retried.
            try:custodian.observe_clock()
            except BaseException as error:
                parent=self._early_parent_custody
                if parent is not None:
                    from .early_resources import retain_source_failure
                    raise retain_source_failure(parent,error,'Share.check.bootstrap_clock')
                raise
        window=getattr(self,"_selected_window",None)
        if window is not None:
            need(window["start_ns"]<=time.monotonic_ns()<window["stop_ns"],"original selected share operation interval")
    def spawn_attempt(self):
        custodian=getattr(self,'bootstrap_custodian',None)
        protected=None if custodian is None else custodian.logical_counters.protected_owner
        if protected is not None:return protected.charge('host','process_starts',1)
        self.check();need(self.process_starts+getattr(self,'bootstrap_native_slack',{}).get('process_starts',0)<self.row["process_starts"]-self._bootstrap_terminal_hold("process_starts"),"earlier complete source process reservation")
        self.process_starts+=1
    def begin(self):
        self.check();need(self._active is None,"one accounting span for this selected share")
        self._active=(time.monotonic_ns(),time.process_time_ns())
        self._end_attempted=False;self._end_observation=None;self._end_primary=None;self._end_secondary=[]
    def end(self):
        need(self._active is not None,"original accounting span")
        need(not self._end_attempted,"one end observation attempt; failed span cannot retry")
        # Keep the original start until every actual end check is admitted.
        # Latch before any fallible observation; never repeat or double-charge.
        self._end_attempted=True;start=self._active
        observed={"wall_end_ns":None,"cpu_end_ns":None,"wall_delta_ns":None,"cpu_delta_ns":None,
                  "admitted":False}
        self._end_observation=observed
        def own(error,dimension):
            if self._end_primary is None:self._end_primary=error
            else:self._end_secondary.append(error);self.cleanup_errors.append(failure(error))
            self.own_error(error,dimension)
        # Independent observations preserve either known dimension even when
        # the other clock fails. Unknown never becomes zero consumption.
        for label,read_clock,index,counter in (("wall",time.monotonic_ns,0,"wall_ns"),
                                               ("cpu",time.process_time_ns,1,"cpu_ns")):
            try:
                end=read_clock();integer(end)
                observed[label+"_end_ns"]=end
                need(end>=start[index],"nondecreasing original observed "+label+" clock")
                delta=end-start[index];observed[label+"_delta_ns"]=delta
                setattr(self,counter,getattr(self,counter)+delta)
            except BaseException as error:own(error,"share_"+label+"_end")
        for label,counter in (("wall","wall_ns"),("cpu","cpu_ns")):
            try:need(getattr(self,counter)+getattr(self,'bootstrap_native_slack',{}).get(counter,0)<=self.row[counter]-self._bootstrap_terminal_hold(counter),"same selected common-work "+label+" share with original terminal hold")
            except BaseException as error:own(error,"share_"+label+"_limit")
        try:self.check()
        except BaseException as error:own(error,"share_final_cutoff")
        if self._end_primary is not None:raise self._end_primary
        observed["admitted"]=True;self._active=None
    def record(self):
        return {**super().record(),"process_starts":self.process_starts,"observed_own_process_cpu_ns":self.cpu_ns,
                "observed_active_span_wall_ns":self.wall_ns,"active_unclosed_span":self._active is not None,
                "original_unclosed_start":None if self._active is None else list(self._active),
                "end_observation_attempted":self._end_attempted,"end_observation":self._end_observation,
                "whole_descendant_CPU_measured_here":False,"nested_overlapping_observations_not_added":True,
                "original_bootstrap_native_reserved":dict(getattr(self,'bootstrap_native_reserved',{})),
                "original_bootstrap_native_completed":dict(getattr(self,'bootstrap_native_completed',{})),
                "retained_native_allocation_slack":dict(getattr(self,'bootstrap_native_slack',{}))}

class RootResources(StagedN098Resources):
    def __init__(self,plan,plan_pin,schemas,bootstrap_meter):
        self.staged=False
        need(plan.get("programme")!="NEURAL-098","N098 requires original staged prelaunch owner")
        schemas.validate("resources","root_resource_plan_schema",plan,bootstrap_meter)
        self.plan=plan;self.pin=plan_pin;self.shares={};self.delegated=False;self.terminal=None
        hard=plan["hard_envelope"]
        need(hard["origin_monotonic_ns"]<hard["run_deadline_ns"]<=hard["evidence_deadline_ns"],"original complete root interval")
        rows=plan["adapter_reservations"]
        need(len({r["reservation_id"] for r in rows})==len(rows),"one immutable identity per earlier adapter share")
        need(len({(r["owner_role"],r["stage"]) for r in rows})==len(rows),"one exact owner/stage share")
        need(sum(r["cpu_ns"] for r in rows)<=hard["cpu_ns"] and
             sum(r["retained_bytes"] for r in rows)<=hard["retained_storage_bytes"],"adapter shares inside original whole opportunity")
        self.rows={(r["owner_role"],r["stage"]):r for r in rows}
    def share(self,owner,stage):
        if self.staged:return self._staged_share(owner,stage)
        key=(owner,stage);need(key in self.rows,"no unselected adapter owner or stage")
        if key not in self.shares:
            h=self.plan["hard_envelope"]
            self.shares[key]=Share(self.rows[key],origin_ns=h["origin_monotonic_ns"],deadline_ns=h["evidence_deadline_ns"])
        return self.shares[key]
    def delegate_programme(self,programme_budget):
        need(not self.staged or (self.phase=="BOUND" and self._delegating),"N098 original private once-only delegation path")
        need(not self.delegated and programme_budget==self.plan["programme_budget"],"one full exact programme delegation")
        self.delegated=True
        return {"schema":"four_original_programme_delegation_v1","resource_plan":self.pin,
                "programme":self.plan["programme"],"budget":programme_budget,
                "full_reservation_retained_on_failure":True,"new_allowance":False}
    def close(self,original_observation):
        need(self.delegated and self.terminal is None,"original one-time campaign close")
        self.terminal=original_observation
        return self.record()
    def record(self):
        if self.staged:return self._staged_record()
        return {"schema":"four_original_resource_custody_v1","selection":self.pin,
                "programme_delegated":self.delegated,"programme_reserved":self.plan["programme_budget"] if self.delegated else None,
                "adapter_shares":[self.shares[k].record() for k in sorted(self.shares)],
                "original_final_observation":self.terminal,"no_nested_reservation_double_sum":True,
                "unknown_whole_completion":self.terminal is None,"capacity_scientifically_qualified_here":False}

