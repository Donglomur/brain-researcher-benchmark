"""Future qualified local cgroup-v2 source; original samples survive every error.

Construction uses only invented ordinary counter files, never a native cgroup.
"""
import os,stat
from pathlib import Path
from .common import require,relative,FailureCarrier,diagnostic_type

class Cgroup:
    def __init__(self,root,name,budget,deadline):
        self.root=Path(root);self.name=str(relative(name));require('/'not in self.name,'one owned cgroup component');self.path=self.root/self.name
        self.budget=budget;self.deadline=deadline;self.events=[];self.created=False;self.closed=False;self.initial_cpu=None;self.max_cpu=None;self.final=None;self.identity=None;self.errors=FailureCarrier()
    def read(self,name):
        require(name in('cgroup.procs','cpu.stat','cgroup.events','memory.peak'),'closed original kernel read names');self.budget.check('before cgroup read',self.deadline)
        fd=None;body=b'';first=None;event={'kind':'read','name':name,'body':None,'returned_bytes':0,'closed':False,'error':None};self.events.append(event)
        try:
            self.budget.admit_read(16385);fd=os.open(self.path/name,os.O_RDONLY|os.O_NOFOLLOW);body=os.read(fd,16385);event['returned_bytes']=len(body);event['body_hex']=body.hex();self.budget.read(len(body));require(len(body)<=16384,'bounded kernel counter');event['body']=body.decode('ascii')
        except BaseException as exc:first=exc;self.errors.fail(exc,'read:'+name);event['error']=diagnostic_type(exc)
        finally:
            if fd is not None:
                try:os.close(fd);event['closed']=True
                except BaseException as exc:
                    first=exc if first is None else first;self.errors.fail(exc,'read-close:'+name)
                    self.budget.uncertain('cgroup-read:'+name,'managed_descriptor_closure',exc,descriptor=fd)
                    event['close_error']=diagnostic_type(exc)
        if first is not None:raise first
        self.budget.check('after cgroup read and close',self.deadline);return body.decode('ascii').strip()
    def write(self,name,value,emergency=False):
        require(name in('memory.max','memory.swap.max','pids.max','cpu.max','cgroup.subtree_control','cgroup.kill'),'closed original kernel write names')
        if not emergency:self.budget.check('before cgroup control',self.deadline)
        raw=value.encode('ascii');reserved_bytes,_=self.budget.reserved();require(len(raw)<=256 and self.budget.write_bytes+reserved_bytes+len(raw)<=self.budget.limits['write_bytes'],'same original kernel write allowance preserves receipt reservation');fd=None;count=0;first=None;event={'kind':'write','name':name,'bytes':0,'expected_bytes':len(raw),'closed':False,'emergency':emergency};self.events.append(event)
        try:
            fd=os.open(self.path/name,os.O_WRONLY|os.O_NOFOLLOW)
            while count<len(raw):
                try:n=os.write(fd,raw[count:])
                except BaseException as exc:
                    n=self.budget.failed_write('cgroup-write:'+name,exc,len(raw)-count)
                    if type(n)is int and 0<n<=len(raw)-count:count+=n;self.budget.write_bytes+=n;event['bytes']=count
                    elif n is None:event['unknown_write_tail']=True
                    raise
                n=self.budget.write_count('cgroup-write:'+name,n,len(raw)-count)
                if n is None:event['unknown_write_tail']=True
                require(n is not None and n>0,'kernel write progress');count+=n;self.budget.write_bytes+=n;event['bytes']=count
        except BaseException as exc:first=exc;self.errors.fail(exc,'write:'+name);event['error']=diagnostic_type(exc)
        finally:
            if fd is not None:
                try:os.close(fd);event['closed']=True
                except BaseException as exc:
                    first=exc if first is None else first;self.errors.fail(exc,'write-close:'+name)
                    self.budget.uncertain('cgroup-write:'+name,'managed_descriptor_closure',exc,descriptor=fd)
                    event['close_error']=diagnostic_type(exc)
        if first is not None:raise first
        if not emergency:self.budget.check('after cgroup control and close',self.deadline)
    def create(self,memory,pids):
        require(os.uname().sysname=='Linux'and Path('/sys/fs/cgroup/cgroup.controllers').is_file(),'qualified local unified Linux cgroup')
        require(self.root.is_absolute()and self.root.is_relative_to('/sys/fs/cgroup')and self.root.is_dir()and not self.path.exists(),'fresh exact delegated cgroup')
        require(not any(p.is_symlink()for p in(self.root,*self.root.parents)),'literal original cgroup path')
        self.budget.check('before original cgroup mkdir',self.deadline);self.path.mkdir();self.created=True;s=self.path.lstat();self.identity=(s.st_dev,s.st_ino)
        require(self.read('cgroup.procs')=='','new parent empty');self.write('memory.max',str(memory));self.write('memory.swap.max','0');self.write('pids.max',str(pids));self.write('cpu.max','100000 100000');self.write('cgroup.subtree_control','+cpu +memory +pids');self.initial_cpu=self.cpu();require(self.initial_cpu==0,'fresh cgroup zero CPU');return self
    def cpu(self):
        rows={}
        for line in self.read('cpu.stat').splitlines():
            key,value=line.split();require(key not in rows,'unique original CPU counter');rows[key]=value
        require('usage_usec'in rows and rows['usage_usec'].isdigit(),'actual nonnegative cgroup CPU');value=int(rows['usage_usec'])/1e6
        previous=self.max_cpu;self.max_cpu=value if previous is None else max(previous,value);require(previous is None or value>=previous,'nondecreasing original subtree CPU');return value
    def sample(self):
        value=self.cpu();require(self.initial_cpu is not None and value>=self.initial_cpu,'known original initial counter');return value-self.initial_cpu
    def finish(self):
        self.final={'cpu_seconds':None,'known_cpu_lower_bound':None if self.max_cpu is None or self.initial_cpu is None else self.max_cpu-self.initial_cpu,'cpu_complete':False,'memory_peak_bytes':None,'populated':None,'complete':False,'original_events':self.events}
        require(self.read('cgroup.procs')=='','owned direct processes absent');rows=dict(line.split()for line in self.read('cgroup.events').splitlines());require(rows.get('populated')in('0','1'),'known original population');self.final['populated']=rows['populated']=='1';require(not self.final['populated'],'all original descendant cgroups empty')
        self.final['cpu_seconds']=self.sample();self.final['cpu_complete']=True;peak=self.read('memory.peak');require(peak.isdigit(),'known original memory peak');self.final['memory_peak_bytes']=int(peak)
        self.budget.check('after original subtree counters',self.deadline);s=self.path.lstat();require((s.st_dev,s.st_ino)==self.identity,'same owned cgroup before removal');self.path.rmdir();self.closed=True;self.final['complete']=True;return self.final
    def emergency_kill(self):
        if self.created and not self.closed:
            s=self.path.lstat();require((s.st_dev,s.st_ino)==self.identity,'only original owned cgroup emergency control');self.write('cgroup.kill','1',emergency=True)
            # This is never evidence of wait, counter completeness or absence.
            event={'kind':'emergency-kill-not-closure','time':None};self.events.append(event)
            event['time']=self.budget.clock()
