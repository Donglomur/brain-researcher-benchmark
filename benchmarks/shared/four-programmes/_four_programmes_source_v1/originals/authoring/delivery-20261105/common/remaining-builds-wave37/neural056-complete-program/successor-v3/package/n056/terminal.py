"""Prospectively reserved terminal custody, separate from ordinary work budget.

Only bounded private evidence is accepted. This is not an execution retry or an
extension of a work deadline. Unpersisted/late evidence prevents completion.
"""
import os,time
from pathlib import Path
from .core import need,absolute,canonical,byte_pin

def resource_verdict(resources,limits):
    failures=[];observed={}
    try:
        def fields(key):
            rows=[line.split() for line in resources[key].splitlines()]
            need(all(len(x)==2 for x in rows),'resource pairs')
            need(len({x[0] for x in rows})==len(rows),'unique resource fields')
            result={k:int(v) for k,v in rows};need(all(v>=0 for v in result.values()),'nonnegative resources')
            return result
        observed['cpu_ns']=fields('cpu.stat')['usage_usec']*1000
        observed['memory_peak_bytes']=int(resources['memory.peak'])
        need(observed['memory_peak_bytes']>=0,'nonnegative memory peak')
        observed['memory_events']=fields('memory.events');observed['pids_events']=fields('pids.events')
        for key in ('oom','oom_kill','max'):need(key in observed['memory_events'],'complete memory event counters')
        need('max' in observed['pids_events'],'complete PID limit counter')
        if observed['cpu_ns']>limits['cpu_ns']:failures.append('final leaf CPU exceeded')
        if observed['memory_peak_bytes']>limits['memory_bytes']:failures.append('final leaf memory exceeded')
        if any(observed['memory_events'][k] for k in ('oom','oom_kill','max')):failures.append('memory limit event')
        if observed['pids_events']['max']:failures.append('PID limit event')
    except Exception as exc:failures.append('resource observation incomplete:'+type(exc).__name__)
    return {'complete':not failures,'failures':failures,'observed':observed,
            'cpu_limit_ns':limits['cpu_ns'],'memory_limit_bytes':limits['memory_bytes'],
            'pids_limit':limits['pids'],'pids_peak_not_measured':True,
            'basis':'final leaf measurements and kernel limit counters; no aggregate slack'}

class TerminalCustody:
    def __init__(self,root,slots,budget,deadline_ns,clock=time.monotonic_ns):
        self.root=absolute(str(Path(root).absolute()));self.slots=dict(slots);self.budget=budget
        self.deadline=deadline_ns;self.clock=clock;self.used=set();self.observations=[]
        need(slots and all(type(k)is str and '/' not in k and k not in ('.','..')
              and type(v)is int and v>=1024 for k,v in slots.items()),'finite terminal slots')
        need(clock()<deadline_ns,'terminal interval already exhausted')
        if budget:budget.reserve(written=sum(slots.values()))
        self.fd=os.open(self.root,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
        self.identity=os.fstat(self.fd)
    def emit(self,name,value,extra_ledger=None,deadline_ns=None):
        need(name in self.slots and name not in self.used,'one reserved terminal slot')
        self.used.add(name);n=0;fd=None;raw=None;error=None;flushed=False
        cutoff=min(self.deadline,deadline_ns) if deadline_ns is not None else self.deadline
        try:
            need(self.clock()<cutoff,'terminal evidence cutoff')
            raw=canonical(value)+b'\n';need(len(raw)<=self.slots[name],'terminal slot cap')
            # dir_fd retains original private directory identity under path swaps.
            fd=os.open(name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=self.fd)
            while n<len(raw):
                need(self.clock()<cutoff,'terminal write cutoff')
                done=os.write(fd,raw[n:]);need(done>0,'terminal short write');n+=done
                if self.budget:self.budget.record_known(written=done)
                if extra_ledger:extra_ledger.record_known(written=done)
            os.fsync(fd);flushed=True
            need(self.clock()<cutoff,'terminal flush cutoff')
            now=os.stat(self.root,follow_symlinks=False)
            need((now.st_dev,now.st_ino)==(self.identity.st_dev,self.identity.st_ino),'terminal directory custody changed')
            return {'path':str(self.root/name),**byte_pin(raw)}
        except Exception as exc:
            error=type(exc).__name__+': '+str(exc);raise
        finally:
            if fd is not None:os.close(fd)
            self.observations.append({'name':name,'known_written':n,'flushed':flushed,
              'deadline_ns':cutoff,'observed_ns':self.clock(),'error':error})
    def close(self):
        if self.fd is not None:os.close(self.fd);self.fd=None

def finalize_attempt(custody,budget,failure,completed_blocks):
    """Independent slots: failure-write errors never suppress the known cost."""
    errors=[];pins={}
    if failure is not None:
        try:pins['failure']=custody.emit('PROGRAMME_FAILURE.json',failure)
        except Exception as exc:errors.append('failure:'+type(exc).__name__+': '+str(exc))
    snapshot={'schema':'neural056_terminal_cost_v2','cost':budget.compact(),
              'completed_final_blocks':completed_blocks,'failure_evidence_errors':list(errors),
              'terminal_cost_rule':'known counts before this cost-file write; its final bytes are added by external observer',
              'terminal_attempts':list(custody.observations),'complete_outputs':failure is None}
    try:pins['cost']=custody.emit('WHOLE_COST.json',snapshot)
    except Exception as exc:errors.append('cost:'+type(exc).__name__+': '+str(exc))
    return {'pins':pins,'errors':errors,'known_final_cost':budget.compact(),
            'terminal_attempts':list(custody.observations)}
