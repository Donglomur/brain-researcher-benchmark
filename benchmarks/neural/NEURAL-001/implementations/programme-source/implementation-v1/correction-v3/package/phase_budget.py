"""Per-operation accounting bridge; missing observations refuse scientific admission."""
import time
from .protocol import require, Refusal
from .resources import ADDITIVE, PEAK, quantities


class PhaseBudget:
    def __init__(self, request, *, monitor, journal, clock=time.monotonic):
        self.origin=request['original_origin'];self.deadline=request['original_deadline']
        self.caps=request['caps'];self.clock=clock;self.monitor=monitor;self.journal=journal
        self.started=self.last=self.clock();self.used={k:0 for k in ADDITIVE}
        self.reserved={k:0 for k in ADDITIVE};self.pending={};self.unknown=[]
        self.cutoff=min(self.deadline,self.started+self.caps['additive']['wall_seconds'])
        require(self.origin<=self.started<self.cutoff<=self.deadline,'original phase clocks required')
        monitor.start(request,self.started,self.cutoff)

    def tick(self,cutoff=None):
        now=self.clock();end=self.cutoff if cutoff is None else min(cutoff,self.cutoff)
        require(self.origin<=self.last<=now<end<=self.deadline,'original monotonic phase deadline')
        self.last=now
        return now

    def _charge(self, key, amount):
        require(type(amount)in (int,float) and amount>=0,'nonnegative observed consumption')
        self.used[key]+=amount
        require(self.used[key]<=self.caps['additive'][key],'operation resource overrun:'+key)

    def charge_io(self,*,read_bytes=0,write_bytes=0):
        # Logical bytes only. Physical OS/cache I/O remains separately identified.
        self._charge('read_bytes',read_bytes);self._charge('write_bytes',write_bytes)

    def reserve_provider(self,prompt,output):
        self.tick();token=object()
        self.reserved['input_tokens']+=prompt;self.reserved['output_tokens']+=output
        self.reserved['reasoning_tokens']+=output
        for key in ('input_tokens','output_tokens','reasoning_tokens'):
            require(self.reserved[key]<=self.caps['additive'][key],'provider reservation ceiling:'+key)
        self._charge('provider_requests',1)
        self.pending[token]=('provider',prompt,output)
        return token

    def finish_provider(self,token,prompt,output,reasoning):
        require(token in self.pending and self.pending[token][0]=='provider','exact provider reservation')
        _,p,o=self.pending.pop(token)
        # Retain observed charges before ceiling checks; reasoning is a subset of
        # completion, not an additional billable total (separate budget field).
        self.used['input_tokens']+=prompt;self.used['output_tokens']+=output
        self.used['reasoning_tokens']+=reasoning
        require(prompt<=p and output<=o and reasoning<=output,'provider usage exceeds reservation/semantics')
        for key in ('input_tokens','output_tokens','reasoning_tokens'):
            require(self.used[key]<=self.caps['additive'][key],'provider observed ceiling:'+key)

    def abandon_provider(self,token,reason):
        self.pending.pop(token,None);self.unknown.append(('provider',reason))

    def reserve_tool(self,normal_end,cleanup_end):
        self.tick(normal_end);require(normal_end<cleanup_end<=self.deadline,'original tool deadlines')
        token=object();self._charge('tool_calls',1);self.pending[token]=('tool',normal_end,cleanup_end)
        return token

    def finish_tool(self,token,usage,peaks):
        require(token in self.pending and self.pending[token][0]=='tool','exact tool reservation')
        quantities(usage,ADDITIVE);quantities(peaks,PEAK);self.pending.pop(token)
        # Independent monitor owns combined parent/container CPU and peaks;
        # record all child facts rather than double-counting parent wall time.
        self.monitor.child_usage(usage,peaks)

    def abandon_tool(self,token,reason):
        self.pending.pop(token,None);self.unknown.append(('tool',reason))

    def reference_progress(self,event):
        self.tick();self.monitor.reference_progress(event);self.journal({'kind':'reference_progress','event':event})

    def finish(self):
        self.tick();require(not self.pending and not self.unknown,'pending/unknown usage prevents success')
        observed=self.monitor.finish(self.used,self.started,self.last)
        require(type(observed)is dict and set(observed)=={'usage','peaks','observation','admission'},
                'independent complete operation measurement required')
        quantities(observed['usage'],ADDITIVE);quantities(observed['peaks'],PEAK)
        require(observed['usage']['wall_seconds']>=self.last-self.started,'wall duration lower bound')
        for key in ADDITIVE:
            require(observed['usage'][key]>=self.used[key],'independent telemetry cannot erase known cost:'+key)
        return observed
