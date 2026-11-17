"""Strong original observations, owned before serialization or cleanup.

These objects are controller-private, never participant receipts. An exception
carries the SAME object, including handles, consumed bytes and first exception.
Snapshots are fallible projections, not the source of dispatch/outcome truth.
"""
import time
import math
from dataclasses import dataclass, asdict


@dataclass(frozen=True)
class WorkerTerminal:
    programme: str
    job: str
    result_core: str
    started: float
    deadline: float
    completed: float
    wall_limit_ms: int
    costs: tuple
    phase: str = "actor_owned_work_complete"
    clock: str = "original_controller_monotonic"

    def body(self):
        value=asdict(self);value["costs"]=dict(self.costs);return value


class WorkerDeadlineExceeded(TimeoutError):
    pass


class ObservationError(RuntimeError):
    def __init__(self, observation):
        self.observation = observation
        self.original_exception = observation.first_error
        # Never format the original exception while establishing ownership.
        super().__init__('Original execution custody failure; inspect observation')


def error_record(exc):
    try: reason = str(exc)[:2048]
    except BaseException: reason = '<exception formatting unavailable>'
    return {'type': type(exc).__name__, 'reason': reason}


class Observation:
    def __init__(self, kind, *, started=None, sample_clock=True):
        self.kind = kind; self.started = time.monotonic() if sample_clock else started
        self.record = {}; self.handles = {}; self.streams = {}
        self.children = {}; self.publications = {}; self.failures = []
        self.first_error = None; self.first_stage = None; self.failure_observations = []
        self.completed = None; self.result = None; self.campaign = None
        self.deadline = None; self.wall_limit_ms = None; self.clock_observations = []
        self.terminal = None; self.original_result = None; self.sealed_state = None; self.sealed_build = None

    def bind_deadline(self, wall_ms, parent=None):
        from .io import need
        need(self.deadline is None, 'Original worker deadline binds once')
        need(type(wall_ms)is int and wall_ms>0, 'Exact original wall allowance')
        if parent is not None:
            need(parent.deadline is not None and parent.wall_limit_ms==wall_ms, 'Same original actor clock')
            self.started=parent.started;self.deadline=parent.deadline
        else:self.deadline=self.started+wall_ms/1000
        self.wall_limit_ms=wall_ms

    def check_deadline(self, stage):
        try:
            now=time.monotonic()
            if not math.isfinite(now) or self.deadline is None or now<self.started:
                raise RuntimeError('Original elapsed clock unavailable')
            self.clock_observations.append({'stage':stage,'observed':now,'elapsed_ms':(now-self.started)*1000})
            if now>self.deadline:raise WorkerDeadlineExceeded('Original per-worker deadline exceeded at '+stage)
            return now
        except BaseException as exc:
            self.fail(exc,stage);raise

    def complete_worker(self, programme, job, result):
        from .io import digest,need
        need(self.terminal is None and self.first_error is None, 'No unresolved actor work at completion')
        # All source/state/product work and terminal event writes have finished.
        # Freeze their identity before the last original-clock observation.
        core=digest({k:result[k]for k in ('job','status','closure','reason')})
        costs=dict(result['costs']);now=self.check_deadline('actor_final_outward_success')
        costs['wall_ms']=math.ceil((now-self.started)*1000)
        result['costs']=costs
        self.terminal=WorkerTerminal(programme['identity'],job['id'],core,self.started,self.deadline,
                                     now,self.wall_limit_ms,tuple(sorted(costs.items())))
        self.completed=result
        return self.terminal

    def fail(self, exc, stage):
        child = exc.observation if isinstance(exc, ObservationError) else None
        if child is self: return
        if child is not None:
            if not any(o is child for o in self.failure_observations):
                self.failure_observations.append(child)
            if child.first_error is not None:
                exc = child.first_error; stage = child.first_stage
        # Own the original raw object before any clock or fallible projection.
        if self.first_error is None:
            self.first_error = exc; self.first_stage = stage
        if not any(e is exc for _, e in self.failures): self.failures.append((stage, exc))
        if child is not None:
            # Unwrapping a carrier must not discard its secondary clock errors
            # or its strong unavailable-accounting observations.
            for secondary_stage, secondary in child.failures:
                if not any(e is secondary for _, e in self.failures):
                    self.failures.append((secondary_stage, secondary))

    def attempt(self, stage, call):
        try: return call()
        except BaseException as exc:
            self.fail(exc, stage); return None

    def failure(self):
        if self.first_error is None:return None
        try:reason=str(self.first_error)[:2048]
        except BaseException as exc:
            self.fail(exc,'exception_formatting');reason='<exception formatting unavailable>'
        return {'type':type(self.first_error).__name__,'reason':reason}

    def secondary(self):
        return [{'stage': s, **error_record(e)} for s, e in self.failures if e is not self.first_error]

    def publish(self, name, body, call):
        # Original logical body precedes serialization/write. State is never
        # promoted to durable on a partial write, flush, fsync or close failure.
        slot = {'body': body, 'state': 'attempted', 'pin': None}
        self.publications[name] = slot
        try:
            slot['pin'] = call(); slot['state'] = 'durable'; return slot['pin']
        except BaseException as exc:
            slot['state'] = 'failed_unknown_prefix'; slot['error'] = exc
            self.fail(exc, 'publication:' + name); return None

    def publication_summary(self):
        return {k: {'state': v['state'], 'pin': v['pin'],
                    'error': error_record(v['error']) if 'error' in v else None}
                for k, v in self.publications.items()}

    def raise_failure(self):
        raise ObservationError(self) from self.first_error


def snapshot(observation):
    """Bounded data-only projection. Actual bytes/handles remain strongly owned."""
    from .io import identity
    return {'schema': 'cogm-original-observation-v1', 'kind': observation.kind,
            'record': observation.record, 'failure': observation.failure(),
            'lifetime': {'started':observation.started,'deadline':observation.deadline,
                         'wall_limit_ms':observation.wall_limit_ms,'observations':observation.clock_observations},
            'terminal':None if observation.terminal is None else observation.terminal.body(),
            'first_failure_stage': observation.first_stage,
            'secondary_failures': observation.secondary(),
            'failure_observation_links': [{'kind': child.kind, 'record': child.record,
                'failure': child.failure(), 'secondary_failures': child.secondary()}
                for child in observation.failure_observations],
            'publications': observation.publication_summary(),
            'consumed_streams': {k: identity(v) for k, v in observation.streams.items()},
            'children': {k: snapshot(v) for k, v in observation.children.items()},
            'custody': 'original_controller_observation; unavailable publication is not no-dispatch'}
