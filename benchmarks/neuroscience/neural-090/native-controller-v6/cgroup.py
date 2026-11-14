"""Task-specific cgroup-v2 controls adapted from the reviewed TMS owner."""
import os,stat,time
from pathlib import Path
from .common import need,Ledger
class Cgroup:
    def __init__(self,root,name,budget,limits):
        self.path=Path(root)/name;self.budget=budget;self.limits=limits;self.events=[];self.errors=Ledger();self.identity=None;self.closed=False
    def io(self,name,value=None):
        need(name in {'cgroup.procs','cgroup.events','cpu.stat','memory.peak','memory.events','pids.events','memory.max','memory.swap.max','pids.max','cpu.max','cgroup.kill','cgroup.subtree_control'},'closed kernel operand')
        self.budget.tick();fd=None;first=len(self.errors.events);event={'name':name,'write':value,'body':None};self.events.append(event)
        try:
            s=self.path.stat();need(self.identity==(s.st_dev,s.st_ino),'same owned cgroup')
            if value is None:self.budget.read(8193)
            else:self.budget.write(len(value.encode('ascii')))
            fd=os.open(self.path/name,(os.O_RDONLY if value is None else os.O_WRONLY)|os.O_NOFOLLOW)
            if value is None:
                raw=os.read(fd,8193);event['body']=raw.hex();need(len(raw)<=8192,'bounded kernel counter');return raw.decode('ascii').strip()
            raw=value.encode('ascii');need(os.write(fd,raw)==len(raw),'whole kernel control')
        except BaseException as e:self.errors.record('cgroup:'+name,e)
        finally:
            if fd is not None:self.errors.attempt('cgroup-close:'+name,lambda:os.close(fd))
            if len(self.errors.events)>first:self.errors.raise_first(self.events)
    def create(self,branch=True):
        need(os.uname().sysname=='Linux'and str(self.path).startswith('/sys/fs/cgroup/') and not self.path.exists(),'fresh local Linux cgroup-v2')
        self.path.mkdir();s=self.path.stat();self.identity=(s.st_dev,s.st_ino)
        need(self.io('cgroup.procs')=='','fresh empty cgroup')
        self.io('memory.max',str(self.limits['rss_bytes']));self.io('memory.swap.max','0')
        self.io('pids.max',str(min(self.limits['pids'],self.limits['threads'])))
        self.io('cpu.max','100000 100000')
        if branch:self.io('cgroup.subtree_control','+cpu +memory +pids')
        need(self.cpu()==0,'fresh cumulative CPU counter');return self
    def values(self,name):
        rows={}
        for line in self.io(name).splitlines():
            k,v=line.split();need(k not in rows and v.isdecimal(),'exact nonnegative kernel counter');rows[k]=int(v)
        return rows
    def cpu(self):return self.values('cpu.stat')['usage_usec']/1e6
    def monitor(self):
        need(self.cpu()<=self.limits['cpu_seconds'],'actual cumulative cgroup CPU ceiling')
        need(int(self.io('memory.peak'))<=self.limits['rss_bytes'],'actual memory peak ceiling')
        need(all(v==0 for k,v in self.values('memory.events').items()if k in {'oom','oom_kill','max'}),'no cgroup memory enforcement event')
        need(self.values('pids.events').get('max',0)==0,'no task-count enforcement event')
    def kill(self):
        if self.identity is not None and not self.closed:self.io('cgroup.kill','1')
    def finish(self):
        while self.values('cgroup.events')['populated']!=0:
            self.budget.tick();time.sleep(min(.01,max(0,self.budget.end-time.monotonic())))
        need(self.io('cgroup.procs')=='','complete descendant cgroup emptiness')
        local=Ledger();local.attempt('final-limit-admission',self.monitor)
        cpu=local.attempt('final-cpu',self.cpu)
        peak=local.attempt('final-memory',lambda:int(self.io('memory.peak')))
        result={'cpu_seconds':cpu,'memory_peak_bytes':peak,'task_count_max':min(self.limits['pids'],self.limits['threads']),'events':self.events}
        def remove():
            s=self.path.stat();need((s.st_dev,s.st_ino)==self.identity,'same empty cgroup before removal');self.path.rmdir();self.closed=True
        local.attempt('empty-cgroup-remove',remove)
        for where,error in self.errors.events:local.record(where,error)
        local.raise_first(result);return result
