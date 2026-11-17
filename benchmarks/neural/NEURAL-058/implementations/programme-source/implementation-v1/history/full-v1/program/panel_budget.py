"""One persistent matched ceiling per complete13-animal workflow panel."""
from core import need, finite, integer, Budget


class PanelBudget:
    def __init__(self,parent,profile,identity,engine,provider_selection,record):
        self.parent=parent;self.profile=profile;self.identity=identity;self.engine=engine;self.emit=record
        self.origin=parent.origin;self.panel_start=parent.tick()
        self.deadline=min(parent.deadline,self.panel_start+finite(profile['wall_seconds']))
        self.read_cap=integer(profile['read_bytes'],1);self.write_cap=integer(profile['write_bytes'],1)
        self.read_bytes=self.write_bytes=0;self.closed=False
        from provider import Provider
        self.provider=Provider(provider_selection,self,record,profile)
        self.previous_engine_budget=engine.budget;engine.budget=self
        try:
            engine.begin_scope(identity,self.deadline,{'native_cpu_ns':profile['native_cpu_ns'],
                                                     'gpu_device_seconds':profile['gpu_device_seconds']})
        except BaseException:
            engine.budget=self.previous_engine_budget
            raise

    def tick(self,cutoff=None):
        need(not self.closed,'no work after panel close')
        return self.parent.tick(min(self.deadline,cutoff if cutoff is not None else self.deadline))

    def reserve_read(self,n):
        self.tick();n=integer(n);need(self.read_bytes+n<=self.read_cap,'whole-panel read cap')
        self.parent.reserve_read(n);self.read_bytes+=n

    def reserve_write(self,n):
        self.tick();n=integer(n);need(self.write_bytes+n<=self.write_cap,'whole-panel write cap')
        self.parent.reserve_write(n);self.write_bytes+=n

    def episode_cutoff(self,ordinal,count):
        # Deterministic equal allocation from the original panel origin. A late
        # preceding animal cannot reset the next deadline or gain extra budget.
        integer(ordinal,0,count-1);integer(count,1)
        return min(self.deadline,self.panel_start+(ordinal+1)*(self.deadline-self.panel_start)/count)

    def snapshot(self):
        return {'panel':self.identity,'origin':self.origin,'panel_start':self.panel_start,'deadline':self.deadline,
                'read_reserved_bytes':self.read_bytes,'write_reserved_bytes':self.write_bytes,
                'provider_calls':self.provider.calls,'provider_tokens_observed':self.provider.tokens,
                'provider_money_reserved':self.provider.money_reserved,'scope':self.engine.scope,
                'closed':self.closed}

    def record(self):
        return self.snapshot()

    def finish(self):
        self.tick();scope=self.engine.end_scope(self.identity);self.closed=True
        self.engine.budget=self.previous_engine_budget
        value=self.snapshot();value['native_scope']=scope;return value

    def fail(self):
        value=self.snapshot()
        try: value['native_scope']=self.engine.abort_scope()
        finally:
            self.closed=True;self.engine.budget=self.previous_engine_budget
        value['failed']=True;return value
