"""Persistent logical reservation owner; external physical enforcement remains a gate."""
import time
from .contracts import need

class Budget:
    def __init__(self, original_start_ns, deadline_ns, limits, clock=time.monotonic_ns):
        need(type(original_start_ns) is int and type(deadline_ns) is int and deadline_ns>original_start_ns,'original launcher clock')
        need(set(limits)=={'read_bytes','write_bytes','calls','tokens','cpu_ns','gpu_ns','money_microunits'},'closed complete cost axes')
        need(all(type(v) is int and v>=0 for v in limits.values()),'prospective nonnegative ceilings')
        self.start=original_start_ns;self.deadline=deadline_ns;self.limits=dict(limits)
        self.used={k:0 for k in limits};self.clock=clock;self.closed=False;self.first=None;self.events=[]
        self.tick()
    def tick(self):
        if self.first is not None:raise self.first
        try:
            need(not self.closed,'live original owner')
            need(self.start<=self.clock()<=self.deadline,'original interval not extended')
        except BaseException as error:self.fail(error);raise
    def reserve(self,kind,n):
        self.tick()
        try:
            need(kind in self.used and type(n) is int and n>=0,'closed reservation')
            self.used[kind]+=n;self.events.append((kind,n))
            need(self.used[kind]<=self.limits[kind],'whole-study ceiling; attempted excess retained')
        except BaseException as error:self.fail(error);raise
    def fail(self,error):
        if self.first is None:self.first=error
    def snapshot(self):
        return {'start':self.start,'deadline':self.deadline,'used':dict(self.used),'limits':dict(self.limits),'closed':self.closed,'failed':self.first is not None,'physical_aggregate':'UNQUALIFIED'}
    def close(self):
        self.tick();self.closed=True
        return self.snapshot()

def finish_preserving(primary,actions):
    """Every cleanup is attempted; no diagnostic hook can mask the original."""
    failures=[]
    for action in actions:
        try:action()
        except BaseException as error:failures.append(error)
    if primary is not None:
        if failures:raise BaseExceptionGroup('original operation and cleanup failures',[primary,*failures])
        raise primary
    if failures:raise BaseExceptionGroup('independent cleanup failures',failures)
