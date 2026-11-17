"""Per-context attempted logical work, inherited clocks and measured-cost joins."""
from .common import Ledger,need,integer,pin,fields

LOGICAL_CAPS={'read_bytes':'cumulative_read_bytes','write_bytes':'cumulative_write_bytes','retained_bytes':'retained_bytes',
    'processes':'processes','provider_calls':'provider_calls','provider_input_tokens':'provider_input_tokens',
    'provider_output_tokens':'provider_output_tokens','provider_cost_microunits':'provider_cost_microunits',
    'generated_source_bytes':'source_bytes'}
PHYSICAL_CAPS={'read_bytes':'cumulative_read_bytes','write_bytes':'cumulative_write_bytes','retained_bytes':'retained_bytes',
    'peak_live_bytes':'live_bytes','cpu_ns':'cpu_ns','wall_ns':'wall_ns','provider_calls':'provider_calls',
    'input_tokens':'provider_input_tokens','output_tokens':'provider_output_tokens','cost_microunits':'provider_cost_microunits',
    'processes':'processes','generated_source_bytes':'source_bytes','tools':'tools'}

def bounded_resources(resources,limits):
    fields(resources,PHYSICAL_CAPS)
    for dimension,limit in PHYSICAL_CAPS.items():
        value=integer(resources[dimension]);need(value<=integer(limits[limit],1),'independent context cap exceeded: '+dimension)
    return resources

class ScopedLedger(Ledger):
    def __init__(self,*a,**kw):self.scope=None;self.scope_history={};super().__init__(*a,**kw)
    def begin_context(self,context,limits):
        need(self.scope is None and context not in self.scope_history,'one fresh active resource context')
        self.tick();self.scope={'context':context,'limits':dict(limits),'origin_ns':self.clock(),'used':{k:0 for k in LOGICAL_CAPS},
            'live_current':0,'live_peak':0,'live_tokens':{},'failures':[],'closed':False}
        self.scope_history[context]=self.scope
    def _check(self,cutoff='scientific'):
        s=self.scope
        if s is None:return
        # Closeout can retain failure evidence but does not grant further science.
        if cutoff=='scientific':need(self.clock()-s['origin_ns']<s['limits']['wall_ns'],'original context wall cutoff')
        over=[k for k,v in s['used'].items() if v>s['limits'][LOGICAL_CAPS[k]]]
        if over:
            if over not in s['failures']:s['failures'].append(over)
            need(cutoff!='scientific','context attempted-work cap exceeded: '+','.join(over))
    def tick(self,phase='scientific'):
        now=super().tick(phase);self._check(phase);return now
    def reserve(self,charges,phase,*,cutoff='scientific'):
        # Global attempted counters and per-context counters both preserve an
        # over-limit request. No caller allocation occurs before this returns.
        primary=None
        try:super().reserve(charges,phase,cutoff=cutoff)
        except BaseException as error:primary=error
        if self.scope is not None:
            for k,v in charges.items():
                if k in self.scope['used']:self.scope['used'][k]+=v
        if primary is not None:raise primary
        self._check(cutoff)
    def acquire_live(self,amount,phase,*,cutoff='scientific'):
        if self.scope is not None:
            proposed=self.scope['live_current']+integer(amount)
            self.scope['live_peak']=max(self.scope['live_peak'],proposed)
            need(proposed<=self.scope['limits']['live_bytes'],'context preventive live cap')
        token=super().acquire_live(amount,phase,cutoff=cutoff)
        if self.scope is not None:
            self.scope['live_tokens'][token]=amount;self.scope['live_current']+=amount
        return token
    def release_live(self,token):
        if self.scope is not None and token in self.scope['live_tokens']:
            self.scope['live_current']-=self.scope['live_tokens'].pop(token)
        return super().release_live(token)
    def end_context(self,*,failed=False):
        need(self.scope is not None,'active context closure');s=self.scope
        try:
            self.tick('closeout' if failed else 'scientific')
            need(not s['live_tokens'],'all context logical live tokens released')
            s['closed']=True;s['failed']=failed;s['finished_ns']=self.clock()
            return {k:v for k,v in s.items() if k!='live_tokens'}
        finally:self.scope=None
    def report(self):
        result=super().report();result['context_logical_records']={k:{n:v for n,v in s.items() if n!='live_tokens'} for k,s in self.scope_history.items()}
        return result
