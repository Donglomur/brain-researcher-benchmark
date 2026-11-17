"""Typed scientific and resource boundaries."""
import math
from .custody import need, Budget as IOBudget, encode, pin

class RequiredUnscorable(RuntimeError):
    def __init__(self, gate, detail, evidence=None):
        super().__init__(detail)
        self.gate, self.detail, self.evidence = gate, detail, evidence
    def record(self):
        return {'status':'required_unscorable','gate':self.gate,'reason':self.detail,'evidence':self.evidence}

def integer(x, low=0, high=None):
    need(type(x) is int and x >= low and (high is None or x <= high), 'typed bounded integer')
    return x

def real(x, low=None, high=None):
    need(type(x) in (int,float) and math.isfinite(x), 'finite real excluding bool')
    need((low is None or x>=low) and (high is None or x<=high), 'real range')
    return x

def keys(d,names):
    need(type(d) is dict and set(d)==set(names),'exact contract keys')

def distinct(values):
    need(type(values) is list and all(type(x)is str and x for x in values) and len(values)==len(set(values)), 'unique ordered identifiers')
    return values

class Budget(IOBudget):
    def __init__(self, *, seconds,read_bytes,write_bytes,array_bytes,origin=None):
        super().__init__(seconds=seconds,read_bytes=read_bytes,write_bytes=write_bytes,origin=origin)
        self.array_cap=integer(array_bytes,1)
        self.array_live=0
        self.array_peak=0
        self.array_cumulative=0
        self.cpu_usec=0
    def reserve_array(self,n):
        self.check();integer(n)
        need(self.array_live+n<=self.array_cap,'selected simultaneous logical array reservation')
        self.array_live+=n;self.array_peak=max(self.array_peak,self.array_live);self.array_cumulative+=n
    def release_array(self,n):
        integer(n);need(n<=self.array_live,'owned reservation release');self.array_live-=n
        self.check()
    def record(self):
        return dict(super().record(),array_live=self.array_live,array_peak=self.array_peak,
                    array_cumulative=self.array_cumulative,cpu_usec=self.cpu_usec,
                    physical_RSS_measured_by_controller=False)
    def adopt(self,record):
        # A continuation cannot reset earlier peaks, charges, CPU or the original clock.
        need(record['origin']==self.origin and record['deadline']==self.deadline,'same whole-lifetime clock')
        for name in ('read_reserved','write_reserved','read_completed','write_completed','array_live','array_peak','array_cumulative','cpu_usec'):
            integer(record[name]);setattr(self,name,max(getattr(self,name),record[name]))
        need(self.read_reserved<=self.read_cap and self.write_reserved<=self.write_cap and self.array_peak<=self.array_cap,'entire historical allowance fits')
        self.check()

def result_variant(variant):
    need(variant in ('held_author_source','paper_independent','corrected_scientific','prospective'),'declared scientific variant')
    return variant

