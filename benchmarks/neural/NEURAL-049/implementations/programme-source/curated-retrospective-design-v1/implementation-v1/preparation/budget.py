"""Inherited clock and cumulative I/O plus explicit live reservations."""
from contextlib import contextmanager
from . import contracts as c
from .storage import Meter

class Budget(Meter):
    def __init__(self, inherited_context):
        c.need(type(inherited_context) is dict and set(inherited_context)=={'origin','deadline','limits'}, 'inherited budget fields')
        caps=inherited_context['limits']
        c.need(type(caps) is dict and set(caps)==c.BASE_LIMITS|c.EXTRA_LIMITS
               and all(c.integer(v,1) for v in caps.values()), 'complete selected positive limits')
        c.need(caps['files']==caps['output_files'], 'output file cap alias')
        super().__init__({**inherited_context,'limits':{k:caps[k] for k in c.BASE_LIMITS}})
        self.limits=dict(caps)
        self.live=self.peak_live=self.reserved_array_elements=0
        self.rows_seen=self.sources_seen=0
        self.reservations=0

    def reserve(self, amount, label):
        self.tick();c.need(c.integer(amount) and self.live+amount<=self.limits['live_bytes'], 'live allocation reservation: '+label)
        self.live+=amount;self.peak_live=max(self.peak_live,self.live);self.reservations+=1
        return amount

    def release(self, amount):
        c.need(c.integer(amount) and amount<=self.live,'balanced live reservation')
        self.live-=amount

    @contextmanager
    def hold(self, amount, label):
        n=self.reserve(amount,label)
        try: yield
        finally: self.release(n)

    def elements(self, n):
        self.tick();c.need(c.integer(n) and n<=self.limits['array_elements'],'array element cap')
        self.reserved_array_elements+=n

    def add_rows(self,n):
        self.tick();c.need(c.integer(n) and self.rows_seen+n<=self.limits['rows'],'complete row count cap')
        self.rows_seen+=n

    def source(self):
        self.tick();c.need(self.sources_seen+1<=self.limits['source_files'],'source file cap')
        self.sources_seen+=1

    def record(self):
        result=super().record()
        result.update({'planned_live_bytes':getattr(self,'live',0),'peak_planned_live_bytes':getattr(self,'peak_live',0),
                       'cumulative_declared_array_elements':getattr(self,'reserved_array_elements',0),
                       'rows_seen':getattr(self,'rows_seen',0),'sources_seen':getattr(self,'sources_seen',0),
                       'actual_allocator_native_workspace_peak':'unqualified; independent profile required',
                       'source_dispositions':getattr(self,'progress',[]),
                       'current_row':getattr(self,'progress_current',None)})
        return result
