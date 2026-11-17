"""Original total envelopes with prospective closeout capacity, never a reset.

Attempted counters include refused allocations. Admitted reservations separately
bound actual selected logical work. Neither set measures physical I/O or RSS.
A scientific failure permanently closes science; only reserved metadata closeout
may continue under the original closeout clock and total ceilings.
"""
from contextlib import contextmanager
from ach_util import need,integer,Refusal,finish_owned

class OperationLedger:
    def __init__(self,base,closeout_reserve):
        need(not any(base.used.values()),'wrap fresh original ledger before any work')
        need(type(closeout_reserve) is dict and set(closeout_reserve)=={'read_bytes','write_bytes','retained_bytes','live_bytes','requests'},
             'complete prospective metadata-only closeout reserve')
        for k,v in closeout_reserve.items():integer(v,1);need(v<base.limits[k],'closeout reserve inside original total')
        self.base=base;self.reserve_for_closeout=dict(closeout_reserve)
        self.admitted={k:0 for k in base.limits};self.stopped=False
    def __getattr__(self,name):return getattr(self.base,name)
    def tick(self,phase='scientific'):
        if phase=='scientific':need(not self.stopped,'scientific work stopped permanently after failure')
        return self.base.tick(phase)
    def reserve(self,charges,phase,*,cutoff='scientific'):
        self.tick(cutoff);need(type(charges) is dict and set(charges)<=set(self.used) and 'live_bytes' not in charges,'known cumulative charge')
        for v in charges.values():integer(v)
        if cutoff!='scientific':need(set(charges)<=set(self.reserve_for_closeout)-{'live_bytes'},'metadata-only closeout after science')
        for k,v in charges.items():self.used[k]+=v
        caps={k:self.limits[k]-(self.reserve_for_closeout.get(k,0) if cutoff=='scientific' else 0) for k in charges}
        exceeded=[k for k,v in charges.items() if self.admitted[k]+v>caps[k]]
        if exceeded:
            self.base.failures.append({'phase':phase,'charges':dict(charges),'exceeded':exceeded,
                'allocation_admitted':False,'original_cutoff':cutoff});self.stopped=True
            raise Refusal('attempted allocation exceeds selected original scope; retained attempted counters')
        for k,v in charges.items():self.admitted[k]+=v
    def acquire_live(self,amount,phase,*,cutoff='scientific'):
        self.tick(cutoff);integer(amount)
        cap=self.limits['live_bytes']-(self.reserve_for_closeout['live_bytes'] if cutoff=='scientific' else 0)
        if self.base.live_current+amount>cap:
            self.base.used['live_bytes']=max(self.base.used['live_bytes'],self.base.live_current+amount)
            self.base.failures.append({'phase':phase,'live_attempted':amount,'allocation_admitted':False});self.stopped=True
            raise Refusal('attempted live reservation exceeds original scope')
        result=self.base.acquire_live(amount,phase,cutoff=cutoff)
        self.admitted['live_bytes']=max(self.admitted['live_bytes'],self.base.live_current)
        return result
    def release_live(self,token):return self.base.release_live(token)
    def observe(self,charges,phase):
        """Past independently measured work: accounting, not new allocation.

        Preserve the actual overrun before refusing, while still permitting the
        prospectively reserved metadata closeout. Job peaks are named maxima;
        they do not become a synchronized whole-operation live measurement.
        """
        self.base.tick('closeout')
        need(set(charges)<=set(self.used) and all(k.startswith(('observed_job_','native_observed_')) for k in charges),
             'separate independently observed resource dimensions')
        for k,v in charges.items():
            integer(v)
            self.used[k]=max(self.used[k],v) if k.endswith('live_peak_bytes') else self.used[k]+v
        exceeded=[k for k in charges if self.used[k]>self.limits[k]]
        if exceeded:
            self.stopped=True;self.base.failures.append({'phase':phase,'observed_overrun':exceeded,'charges':charges})
            raise Refusal('independently observed resource overrun retained')
    @contextmanager
    def live(self,amount,phase,*,cutoff='scientific'):
        token=self.acquire_live(amount,phase,cutoff=cutoff)
        primary=None
        try:yield
        except BaseException as error:primary=error;raise
        finally:finish_owned([('logical live reservation release',lambda:self.release_live(token))],primary)
    def fail(self,phase,error):self.stopped=True;self.base.fail(phase,error)
    def report(self):
        return {**self.base.report(),'admitted_logical_reservations':dict(self.admitted),
            'prospective_closeout_reserve':dict(self.reserve_for_closeout),'science_permanently_stopped':self.stopped,
            'attempted_counts_are_not_consumed_allocations':True}
