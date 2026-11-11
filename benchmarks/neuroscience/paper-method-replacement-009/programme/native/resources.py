"""Pre-effect reservation and original cumulative/final resource admission."""
from .io import need, integer, number, exact

KEYS = ("wall_ms", "cpu_usec", "memory_bytes", "processes", "cumulative_write_bytes",
        "retained_bytes", "files", "member_bytes", "input_bytes", "output_bytes", "log_bytes")


def limits(value):
    exact(value, KEYS)
    need(all(integer(value[k], 1) for k in KEYS), "Every resource cap is an explicit positive integer")
    need(value["member_bytes"] <= value["retained_bytes"] and
         value["output_bytes"] <= value["retained_bytes"], "Consistent retained allowances")
    return value


class Budget:
    def __init__(self, total):
        self.total = dict(limits(total)); self.reservations = {}; self.observations = {}

    def reserve(self, key, cap, collection_bytes, terminal_bytes, terminal_files):
        limits(cap)
        need(key not in self.reservations and integer(collection_bytes, 1) and
             integer(terminal_bytes, 1) and integer(terminal_files, 1), "Fresh complete terminal reservation")
        need(collection_bytes >= cap["output_bytes"], "Reserve full copy before any producer")
        reservation = {"caps": dict(cap), "collection": collection_bytes,
                       "terminal": terminal_bytes, "terminal_files": terminal_files}
        proposed = list(self.reservations.values()) + [reservation]
        # Peak-memory/pids are bounded also per process; sequential union is
        # conservatively reserved here rather than claiming unmeasured overlap.
        for k in KEYS:
            cost = sum(x["caps"][k] for x in proposed)
            if k in ("cumulative_write_bytes", "retained_bytes"):
                cost += sum(x["collection"] + x["terminal"] for x in proposed)
            if k == "files": cost += sum(x["terminal_files"] for x in proposed)
            need(cost <= self.total[k], "Complete campaign reservation exceeds " + k)
        self.reservations[key] = reservation
        return reservation

    def commit(self, key, observed):
        need(key in self.reservations and key not in self.observations, "Original reserved operation once")
        exact(observed, KEYS)
        cap = self.reservations[key]["caps"]
        need(all(integer(observed[k]) for k in KEYS), "Original final resource counters")
        self.observations[key] = dict(observed)
        return [k for k in KEYS if observed[k] > cap[k]]


def eligible(record, cap):
    limits(cap)
    need(record["selected_limits"] == cap, "Original selected per-worker allowance")
    exact(record["resources"], KEYS)
    need(all(integer(record["resources"][k]) and record["resources"][k] <= cap[k]
             for k in KEYS), "Final individual worker resource ceiling")
    need(record["returncode"] == 0 and type(record["returncode"]) is int and
         record["natural_completion"] is True and record["all_descendants_absent"] is True,
         "Original natural completion and full descendant cleanup")
    need(record["quota_observer_complete"] is True and record["final_sample_after_exit"] is True,
         "Complete original accounting through terminal sample")
    need(record.get('failure')is None,'Original failure cannot be admitted as successful resource evidence')
    return record



# One controller clock spans the invocation. Only explicitly owned actor
# wall intervals are subtracted; supervisor CPU never pauses. Context exits never
# resets or pauses this clock.
from contextvars import ContextVar
from contextlib import contextmanager
from functools import wraps
import time
import math
_CURRENT_CONTROLLER=ContextVar('cogm_original_controller',default=None)


def checkpoint(stage):
    meter=_CURRENT_CONTROLLER.get()
    if meter is not None:meter.checkpoint(stage)


def controller_operation(fn):
    @wraps(fn)
    def guarded(*args,**kwargs):
        meter=_CURRENT_CONTROLLER.get()
        if meter is None:return fn(*args,**kwargs)
        return meter.call(fn.__module__+'.'+fn.__qualname__,lambda:fn(*args,**kwargs))
    return guarded


def controller_call(stage,fn,*args,**kwargs):
    meter=_CURRENT_CONTROLLER.get()
    return fn(*args,**kwargs)if meter is None else meter.call(stage,lambda:fn(*args,**kwargs))


def controller_fatal_call(stage,fn,*args,**kwargs):
    """Custody/infrastructure does not inherit a local validation boundary."""
    meter=_CURRENT_CONTROLLER.get()
    return fn(*args,**kwargs)if meter is None else meter.call(stage,lambda:fn(*args,**kwargs),force_fatal=True)


def controller_local_call(stage,fn,*args,**kwargs):
    """Explicit product/metric domain, still charged to the original clock."""
    meter=_CURRENT_CONTROLLER.get()
    return fn(*args,**kwargs)if meter is None else meter.call(stage,lambda:fn(*args,**kwargs),local_errors=True)


def controller_local_operation(fn):
    @wraps(fn)
    def guarded(*args,**kwargs):
        return controller_local_call(fn.__module__+'.'+fn.__qualname__,fn,*args,**kwargs)
    return guarded


def require_local_outcome(exc,stage):
    """Only an explicitly owned local outcome may enter a local classifier."""
    meter=_CURRENT_CONTROLLER.get()
    if meter is not None and not meter._known_local(exc):
        meter.observation.fail(exc,stage+':undeclared_failure')
        meter.checkpoint(stage+':fatal')


class ControllerBudgetExceeded(TimeoutError):
    pass


class ControllerMeter:
    """One original residual clock; strong errors precede all clock/projection work."""
    def __init__(self,programme):
        from .observation import Observation
        # Establish a carrier without sampling a clock while constructing it.
        self.observation=Observation('original_controller',started=None,sample_clock=False)
        self.observation.controller=self
        self.started=None;self.cpu_started=None;self.last_clock=(None,None)
        self.cap=programme['body']['resource_plan']['controller_caps']
        need(set(self.cap)=={'wall_ms','cpu_usec'}and
             all(type(v)is int and v>0 for v in self.cap.values()),'Original positive controller residual envelope')
        expected={k:programme['body']['resource_plan']['total'][k]-
                  sum(j['resource_reservation']['caps'][k]for j in programme['body']['jobs'])
                  for k in self.cap}
        need(self.cap==expected,'Controller allowance is the original unallocated whole-programme remainder')
        self.used={k:0.0 for k in self.cap};self.excluded={k:0.0 for k in self.cap}
        self.observations=[];self.actor_intervals=[];self.paused=False
        self.local_outcomes=[];self._local_scope=None
        self.checkpoint_count=0;self.last_sample=None;self.failed_clock_samples=[]
        self.clock_accounting_complete=True;self.actor_wall_exclusion_complete=True
        self.observation.record={'phase':'controller_invocation','caps':dict(self.cap),
            'other_host_counters':'unqualified; wall/CPU evidence does not certify host I/O'}
        sample=self._sample('controller_origin')
        self.started=sample['wall']['value'];self.cpu_started=sample['cpu']['value']
        self.observation.started=self.started
        self.observation.record.update(original_started=self.started,original_cpu_started_ns=self.cpu_started)
        self._project('controller_origin')
        if self.observation.first_error is not None:self.observation.raise_failure()

    @property
    def active(self):
        return _CURRENT_CONTROLLER.get()is self and not self.paused

    def snapshot(self):
        return {'schema':'cogm-controller-cost-v3','caps':dict(self.cap),'used':dict(self.used),
                'excluded_actor_intervals':list(self.actor_intervals),'excluded':dict(self.excluded),
                'original_started':self.started,'original_cpu_started_ns':self.cpu_started,
                'checkpoints':self.checkpoint_count,'last_clock':self.last_clock,
                'last_clock_attempt':self.last_sample,'failed_clock_samples':list(self.failed_clock_samples),
                'clock_accounting_complete':self.clock_accounting_complete,
                'actor_wall_exclusion_complete':self.actor_wall_exclusion_complete,
                'used_meaning':'latest valid observed cumulative values; incomplete observations never certify current costs',
                'clock_reset':False,'accounting':'original wall minus known actor wall; full supervisor process CPU, excluding no host work; worker cgroup CPU is separate',
                'final_outward_admitted':getattr(self,'final_outward_admitted',False),
                'first_failure_present':self.observation.first_error is not None}

    def _known_local(self,exc):
        return any(any(error is exc for _,error in o.failures)for o in self.local_outcomes)

    def _local_type(self,exc):
        from .io import Refusal
        from .scientific import Unsupported
        from .observation import ObservationError
        return not isinstance(exc,ObservationError)and isinstance(exc,(Refusal,Unsupported,ValueError,TypeError,KeyError,IndexError))

    def _own_local(self,exc,stage):
        if self._known_local(exc):return
        from .observation import Observation
        o=self._local_scope
        if o is None:
            o=Observation('declared_local_outcome',started=self.started,sample_clock=False)
            o.record={'scope':'declared_product_or_metric','stage':stage,'original_clock_shared':True}
        o.fail(exc,stage)
        if not any(x is o for x in self.local_outcomes):
            self.local_outcomes.append(o)
            self.observation.children['local_outcome_'+str(len(self.local_outcomes))]=o

    def _sample(self,stage):
        """Attempt both clocks independently and retain missing/invalid evidence."""
        sample={'stage':stage,'wall':{'available':False,'value':None},
                'cpu':{'available':False,'value':None}}
        last=list(self.last_clock)
        for i,(name,reader) in enumerate((('wall',time.monotonic),('cpu',time.process_time_ns))):
            try:
                value=reader()
                valid=(type(value)in(int,float)and math.isfinite(value))if name=='wall' else(type(value)is int and value>=0)
                need(valid and(last[i]is None or value>=last[i]),'Original '+name+' clock evidence unavailable')
                sample[name]={'available':True,'value':value};last[i]=value
            except BaseException as exc:
                # No rendering, snapshot or second clock call precedes ownership.
                self.observation.fail(exc,stage+':'+name+'_clock')
                sample[name]['failure_type']=type(exc).__name__
                self.clock_accounting_complete=False
        self.last_clock=tuple(last);self.last_sample=sample
        self.checkpoint_count+=1
        if not all(sample[k]['available']for k in('wall','cpu')):self.failed_clock_samples.append(sample)
        return sample

    def _account(self,sample):
        if sample['wall']['available']and self.started is not None and self.actor_wall_exclusion_complete:
            self.used['wall_ms']=max(self.used['wall_ms'],max(0.,(sample['wall']['value']-self.started)*1000-self.excluded['wall_ms']))
        if sample['cpu']['available']and self.cpu_started is not None:
            self.used['cpu_usec']=max(self.used['cpu_usec'],max(0.,(sample['cpu']['value']-self.cpu_started)/1000))

    def _project(self,stage):
        self.observation.record['last_stage']=stage
        try:
            value=self.snapshot()
            self.observation.record['costs']=value
            self.observation.record['cost_projection']='available'
        except BaseException as exc:
            self.observation.fail(exc,stage+':cost_projection')
            self.observation.record['cost_projection']='unavailable; prior projection is not current evidence'

    def _finish_checkpoint(self,stage,sample):
        self._account(sample)
        if any(self.used[k]>self.cap[k]for k in self.cap):
            self.observation.fail(ControllerBudgetExceeded('Original cumulative controller allowance exceeded at '+stage),stage)
        self._project(stage)
        if self.observation.first_error is not None:self.observation.raise_failure()
        return dict(self.used)

    def checkpoint(self,stage,original_error=None):
        # This is deliberately outside every clock/projection call.
        if original_error is not None:self.observation.fail(original_error,stage+':original_operation')
        try:
            need(not self.paused,'Controller work cannot run inside actor ownership')
            need(not getattr(self,'final_outward_admitted',False),'Completed controller invocation cannot reopen')
        except BaseException as exc:self.observation.fail(exc,stage)
        return self._finish_checkpoint(stage,self._sample(stage))

    @contextmanager
    def activate(self,stage):
        current=_CURRENT_CONTROLLER.get()
        need(current is None or current is self,'One original controller per composed invocation')
        self.checkpoint(stage+':enter')
        token=_CURRENT_CONTROLLER.set(self)
        try:
            try:yield self
            except BaseException as exc:
                if not self._known_local(exc):self.observation.fail(exc,stage+':original_operation')
                self.checkpoint(stage+':failed')
                raise
            else:self.checkpoint(stage+':leave')
        finally:_CURRENT_CONTROLLER.reset(token)

    def call(self,stage,call,*,local_errors=False,force_fatal=False):
        self.checkpoint(stage+':before')
        previous=self._local_scope
        if force_fatal:self._local_scope=None
        elif local_errors and previous is None:
            from .observation import Observation
            self._local_scope=Observation('declared_local_outcome',started=self.started,sample_clock=False)
            self._local_scope.record={'scope':'declared_product_or_metric','stage':stage,'original_clock_shared':True}
        try:
            try:value=call()
            except BaseException as exc:
                local=(not force_fatal and self._local_type(exc)and
                       (self._local_scope is not None or self._known_local(exc)))
                if local:self._own_local(exc,stage+':local_outcome')
                else:self.observation.fail(exc,stage+':original_operation')
                try:self.checkpoint(stage+':after_failure')
                except BaseException:
                    # The first fatal controller cause remains first. Retain
                    # the earlier local outcome as explicit contextual evidence.
                    if local:self.observation.fail(exc,stage+':local_outcome_context')
                    raise
                raise
        finally:self._local_scope=previous
        self.checkpoint(stage+':after')
        return value

    def run(self,stage,call):
        from .observation import Observation
        # A phase borrows the original origin; allocating its carrier cannot
        # sample a replacement clock while an earlier error is unwinding.
        o=Observation('controller_phase',started=self.started,sample_clock=False);self.observations.append(o)
        o.record={'stage':stage,'shared_original_clock':True,'before':dict(self.used)}
        try:
            with self.activate(stage):value=self.call(stage,call)
            o.completed=value;o.record['after']=dict(self.used)
            return value
        except BaseException as exc:
            o.fail(exc,stage);o.record['after']=dict(self.used);o.raise_failure()

    @contextmanager
    def actor(self,stage):
        """Restore ownership before sampling, even while an actor error unwinds."""
        self.checkpoint(stage+':controller_before_actor')
        need(not self.paused,'Actor ownership is nonoverlapping')
        a,c=self.last_clock
        token=_CURRENT_CONTROLLER.set(None);self.paused=True
        try:
            try:yield
            except BaseException as exc:
                self.observation.fail(exc,stage+':original_actor_operation')
                raise
        finally:
            # Neither clock nor a data projection is allowed ahead of these.
            self.paused=False
            try:_CURRENT_CONTROLLER.reset(token)
            except BaseException as exc:self.observation.fail(exc,stage+':context_restoration')
            sample=self._sample(stage+':actor_completed')
            b=sample['wall']['value'];d=sample['cpu']['value']
            interval={'stage':stage,'started':a,'completed':b,'cpu_started_ns':c,'cpu_completed_ns':d,
                      'wall_ms':None if b is None else(b-a)*1000,
                      'cpu_usec':None if d is None else(d-c)/1000,
                      'clock_complete':all(sample[k]['available']for k in('wall','cpu')),
                      'supervisor_cpu_included_in_controller':True,
                      'context_restored_before_clock_sampling':True}
            self.actor_intervals.append(interval)
            if b is None:self.actor_wall_exclusion_complete=False
            else:self.excluded['wall_ms']+=interval['wall_ms']
            # CPU is the supervisor's counter, already excluding worker CPU.
            self.excluded['cpu_usec']=0.0
            self._finish_checkpoint(stage+':controller_after_actor',sample)

    def final(self,stage):
        self.checkpoint(stage)
        try:
            costs=self.snapshot();costs['final_outward_admitted']=True
        except BaseException as exc:
            self.observation.fail(exc,stage+':final_cost_projection')
            self.observation.record['cost_projection']='unavailable; no final admission'
            self.observation.raise_failure()
        self.final_outward_admitted=True
        self.observation.record['costs']=costs
        self.observation.completed=costs
        return costs


def controller_iter(iterable,stage):
    """Admit iterator advancement, including directory enumeration, before next."""
    iterator=iter(iterable)
    while True:
        checkpoint(stage+':before_next')
        try:value=next(iterator)
        except StopIteration:
            checkpoint(stage+':exhausted');return
        checkpoint(stage+':after_next')
        yield value


def controller_method(fn):
    @wraps(fn)
    def guarded(self,*args,**kwargs):
        if self.controller.paused:return fn(self,*args,**kwargs)
        return self.controller.run(fn.__qualname__,lambda:fn(self,*args,**kwargs))
    return guarded
