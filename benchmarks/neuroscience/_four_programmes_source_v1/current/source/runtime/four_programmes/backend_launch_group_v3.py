"""Full original H launch PID/TID/raw-byte producer, never a count projection.

Four separately observed hierarchies and six actual raw reads for every TID.
No server-subtree record, reconstructed kernel bytes, or excluded worker shortcut.
"""
import os,stat
from .common import need,same,pin,bounded_size
from .backend_capture import CapturedRecord,CaptureAttempt
from .backend_linux_host_observation import HostNativeIOCustody
from .backend_linux_observations import parse_proc_stat,process_identity_from_observation
from .backend_linux_threads import parse_thread_status
from .observer import KernelGroup


class LaunchKernelTextReadV3:
    """One original read occurrence, with partial buffers before all checks."""
    def __init__(self,owner,role,ceiling,source):
        self.owner=owner;self.role=role;self.ceiling=ceiling;self.source=source
        self.slot=None;self.parts=[];self.known=0;self.raw=None;self.eof=False
        self.observed_ns=None;self.closed_ns=None;self.raw_first=None;self.secondaries=[]
        self.raw_attempt=None;self.raw_pin=None;self.body=None;self.complete=False
        self.ordinal=len(owner.raw_reads);owner.raw_reads.append(self)
    def retain(self,error):
        if self.raw_first is None:self.raw_first=error
        elif error is not self.raw_first:self.secondaries.append(error)
        self.owner.retain(error,'raw_text')
    def run(self,directory,name):
        o=self.owner;io=o.io;p=o.publisher;original=None
        try:
            need(self.ceiling<=p.maximum_bytes,'whole raw output ceiling fits original per-member limit before read')
            # All byte/readback/canonical copies are conservatively admitted
            # under the same original H partition before the physical read.
            p.meter.charge('retained_bytes',16*self.ceiling+8192)
            p.meter.charge('work_units',64*self.ceiling+8192)
            self.slot=io.slot('group' if name.startswith('cgroup.') else 'proc')
            self.slot.openat(directory,name,os.O_RDONLY|os.O_NONBLOCK)
            self.slot.set_nonblocking();io.work();observed=os.fstat(self.slot.fd)
            need(stat.S_ISREG(observed.st_mode),'actual fixed kernel text file')
            while not self.eof:
                maximum=min(4096,self.ceiling+1-self.known)
                need(maximum>0,'finite original raw read plus positive EOF reservation')
                raw=io.recv(self.slot,maximum,o.deadline)
                need(raw is not None,'kernel metadata EAGAIN refuses without hidden wait/retry')
                self.parts.append(raw)
                need(type(raw)is bytes and len(raw)<=maximum,'actual bounded raw kernel return')
                self.known+=len(raw)
                need(self.known<=self.ceiling,'no truncated/overflow raw kernel capture')
                if raw==b'':self.eof=True
            self.raw=b''.join(self.parts);self.observed_ns=io.now(o.deadline)
        except BaseException as error:original=error;self.retain(error);raise
        finally:
            if self.slot is not None:
                try:
                    closed=self.slot.close()
                    if self.slot.raw_first is not None:raise self.slot.raw_first
                    need(closed,'known once-only raw kernel descriptor closure')
                    self.closed_ns=io.now(o.deadline)
                except BaseException as error:
                    self.retain(error)
                    if original is None:raise
        # Exact raw occurrence is published, not synthesized from parsed IDs.
        name=o.prefix+'_RAW_'+str(self.ordinal)+'.txt'
        key=(str(p.outputs.root),name)
        need(name not in p.attempts and key not in p.parent.canonical_publications and
             len(p.parent.canonical_publications)<p.maximum_members,'whole-owner raw publication census')
        attempt=CaptureAttempt(name,'KernelTextBytesV3');self.raw_attempt=attempt
        p.attempts[name]=attempt;p.parent.canonical_publications[key]=attempt
        try:
            attempt.raw=self.raw;attempt.write_entered=True
            descriptor=p.outputs.write(name,self.raw);attempt.provisional=descriptor;self.raw_pin=descriptor
            attempt.readback_entered=True
            reread=p.outputs.read(descriptor,p.maximum_bytes,metadata=True)
            need(reread==self.raw and pin(reread)==pin(self.raw),'complete original kernel byte readback')
            self.body={'schema':'four_kernel_text_capture_v1','role':self.role,'raw_bytes':descriptor,
                'request_ceiling':self.ceiling,'eof_observed':True,'closed':True,
                'observed_ns':self.observed_ns,'closed_ns':self.closed_ns,
                'source':self.source,'cost_prefix':o.attempt.owner.cost_prefix()}
            self.complete=True;attempt.complete=self;return self
        except BaseException as error:attempt.retain(error);p.raw_first=error;self.retain(error);raise


class HLaunchGroupOwnerV3:
    def __init__(self,observation):
        from .development_native_observations import DevelopmentNativeObservation
        from .backend_launch_start_v3 import HWorkerStartOwnerV3
        need(type(observation)is DevelopmentNativeObservation,'fixed actual H native observer')
        a=observation.attempt;a.require_live_original()
        need(a.native_observations is observation and observation.identity_complete and
             type(observation.io)is HostNativeIOCustody and observation.io.original_observation is observation and
             type(a.start_observation)is HWorkerStartOwnerV3,
             'same actual original worker identity and earlier H start')
        a.start_observation.require_original_capture_v3()
        need(a.launch_group_owner is None and a.launch_ack is None,'one complete group producer before Ack')
        self.observation=observation;self.attempt=a;self.io=observation.io;self.publisher=observation.publisher
        self.deadline=a.run_deadline_ns;self.prefix=observation._prefix()+'_LAUNCH_GROUP'
        self.group=a.process.group;self.worker=observation.identity
        self.raw_reads=[];self.passes=[];self.thread_rows=[];self.directory_slots=[];self.iterators=[]
        self.raw_first=None;self.secondaries=[];self.entered=False;self.closed=False;self.capture=None
        self.root=None;self.group_anchor=None;self.entry_anchor=None
        a.launch_group_owner=self
    def retain(self,error,site):
        if self.raw_first is None:self.raw_first=error
        elif error is not self.raw_first:self.secondaries.append(error)
        self.observation.retain(error,'launch_group_'+site,'launch_group')
    def _anchor(self,fd,expected=None):
        self.io.work();s=os.fstat(fd)
        need(stat.S_ISDIR(s.st_mode),'actual original cgroup directory')
        pair=(s.st_dev,s.st_ino)
        if expected is not None:need(pair==expected,'same retained original group anchor')
        return {'schema':'four_kernel_group_anchor_v1','device':s.st_dev,'inode':s.st_ino}
    def _read(self,fd,name,role,cap,source):
        return LaunchKernelTextReadV3(self,role,cap,source).run(fd,name)
    def _ids(self,read):
        words=read.raw.split();need(len(words)<=4096 and all(x.isdigit()for x in words),'full bounded decimal ID census')
        values=sorted(int(x)for x in words)
        need(all(x>0 for x in values) and len(values)==len(set(values)),'unique positive observed identities')
        return values
    def _slot(self,role):
        s=self.io.slot(role);self.directory_slots.append(s);return s
    def _close(self,s):
        ok=s.close()
        if s.raw_first is not None:raise s.raw_first
        need(ok,'actual original once-only directory closure')
    def _walk(self,fd,path,rows):
        need(len(path)<=64 and len(rows)<4096,'complete bounded hierarchy without truncation')
        self.io.now(self.deadline);anchor=self._anchor(fd)
        source=self.attempt.pair.contract.profile['group_source']
        procs=self._read(fd,'cgroup.procs','cgroup.procs',65536,source)
        threads=self._read(fd,'cgroup.threads','cgroup.threads',65536,source)
        row={'schema':'four_launch_group_row_v1','relative_components':list(path),'anchor':anchor,
             'pids':self._ids(procs),'tids':self._ids(threads),'procs':procs.body,'threads':threads.body}
        rows.append(row);self.io.work();self.io.meter.charge('retained_bytes',65536)
        iterator=None;original=None;item=None
        try:
            iterator=os.scandir(fd);item=[iterator,False];self.iterators.append(item)
            names=[];seen=0
            while True:
                self.io.now(self.deadline);self.io.work();self.io.meter.charge('read_bytes',4096)
                try:entry=next(iterator)
                except StopIteration:break
                seen+=1;need(seen<=4096,'bounded complete directory metadata')
                name=entry.name
                need(type(name)is str and name not in ('','.','..') and '/'not in name and '\0'not in name and
                     len(name)<=255 and not entry.is_symlink(),'nofollow exact kernel child component')
                if entry.is_dir(follow_symlinks=False):names.append(name)
            need(len(names)==len(set(names)),'no duplicate kernel directory names')
            for name in sorted(names):
                slot=self._slot('group');first=None
                try:
                    slot.openat(fd,name,os.O_RDONLY|os.O_DIRECTORY|os.O_NONBLOCK)
                    self.io.work();s=os.stat(name,dir_fd=fd,follow_symlinks=False)
                    need((s.st_dev,s.st_ino)==slot.identity[:2] and stat.S_ISDIR(s.st_mode),'same named and opened nested group')
                    self._walk(slot.fd,path+(name,),rows)
                except BaseException as error:first=error;self.retain(error,'walk');raise
                finally:
                    try:self._close(slot)
                    except BaseException as error:
                        self.retain(error,'directory_close')
                        if first is None:raise
        except BaseException as error:original=error;self.retain(error,'enumerate');raise
        finally:
            if item is not None and not item[1]:
                item[1]=True
                try:iterator.close()
                except BaseException as error:
                    self.retain(error,'iterator_close')
                    if original is None:raise
    def _pass(self,phase):
        rows=[];record={'schema':'four_launch_census_pass_v1','phase':phase,'root':self.group_anchor,
                       'rows':rows,'enumeration_complete':False,'observed_ns':None}
        self.passes.append(record);self._walk(self.group.fd,(),rows)
        pids=[p for row in rows for p in row['pids']];tids=[t for row in rows for t in row['tids']]
        need(len(pids)<=4096 and len(tids)<=4096 and len(set(pids))==len(pids) and len(set(tids))==len(tids) and
             set(pids)<=set(tids) and set(pids)=={self.worker['pid']},'complete worker-only original PID/TID census')
        record['observed_ns']=self.io.now(self.deadline);record['enumeration_complete']=True
        return record
    @staticmethod
    def _projection(record):
        return [(r['relative_components'],r['anchor'],r['pids'],r['tids'])for r in record['rows']]
    def _threads(self):
        self.root=self._slot('proc');self.root.fixed_proc_root()
        source=self.attempt.pair.contract.profile['identity_source']
        expected=[tid for row in self.passes[0]['rows']for tid in row['tids']]
        for ordinal,tid in enumerate(expected):
            first_slot=len(self.directory_slots);first=None
            try:
                directory=self._slot('proc');directory.openat(self.root.fd,str(tid),os.O_RDONLY|os.O_DIRECTORY|os.O_NONBLOCK)
                reads={}
                reads['stat_before']=self._read(directory.fd,'stat','stat_before',8192,source)
                reads['status_before']=self._read(directory.fd,'status','status_before',65536,source)
                before=parse_proc_stat(reads['stat_before'].raw,tid);tgid=parse_thread_status(reads['status_before'].raw,tid)
                need(tgid==self.worker['pid'],'every actual thread belongs to original worker')
                leader=self._slot('proc');leader.openat(self.root.fd,str(tgid),os.O_RDONLY|os.O_DIRECTORY|os.O_NONBLOCK)
                reads['leader_before']=self._read(leader.fd,'stat','leader_before',8192,source)
                reads['leader_after']=self._read(leader.fd,'stat','leader_after',8192,source)
                reads['stat_after']=self._read(directory.fd,'stat','stat_after',8192,source)
                reads['status_after']=self._read(directory.fd,'status','status_after',65536,source)
                after=parse_proc_stat(reads['stat_after'].raw,tid)
                leader_before=parse_proc_stat(reads['leader_before'].raw,tgid)
                leader_after=parse_proc_stat(reads['leader_after'].raw,tgid)
                need(before['start_ticks']==after['start_ticks'] and before['parent_pid']==after['parent_pid'] and
                     parse_thread_status(reads['status_after'].raw,tid)==tgid and
                     leader_before['start_ticks']==leader_after['start_ticks'] and
                     leader_before['parent_pid']==leader_after['parent_pid']==self.attempt.owner.parent.identity['pid'] and
                     leader_before['state']not in ('Z','X') and leader_after['state']not in ('Z','X') and
                     before['state']not in ('Z','X') and after['state']not in ('Z','X'),
                     'actual stable live TID/TGID/start/parent and original leader')
                identity,_=process_identity_from_observation(reads['leader_after'].raw,tgid,self.worker['boot_id'],
                    self.attempt.host.mapping,self.worker['launch_nonce'],self.worker['source'],self.worker['parent_launch'])
                need(same(identity,self.worker),'exact original process identity; no TID nonce fabrication')
                self.thread_rows.append({'schema':'four_launch_thread_identity_v1','ordinal':ordinal,'tid':tid,'tgid':tgid,
                    'start_ticks':before['start_ticks'],'leader_start_ticks':leader_before['start_ticks'],
                    'parent_pid':before['parent_pid'],'observed_ns':self.io.now(self.deadline),
                    **{k:r.body for k,r in reads.items()}})
            except BaseException as error:first=error;self.retain(error,'thread');raise
            finally:
                for slot in reversed(self.directory_slots[first_slot:]):
                    try:self._close(slot)
                    except BaseException as error:
                        self.retain(error,'thread_close')
                        if first is None:first=error
                if first is not None and self.raw_first is first:raise first
        self._close(self.root)
    def run_v3(self):
        need(not self.entered,'one original launch-group attempt');self.entered=True
        try:
            a=self.attempt;g=self.group;p=self.publisher;p.require_native_source_v3()
            need(type(g)is KernelGroup and g is a.worker_kernel.group and g is a.process.group,
                 'same actual H kernel group and distinct entry owner')
            self.io.mark_unknown() # A finite census is not measured physical qualification.
            g.own();self.group_anchor=self._anchor(g.fd,g.identity);self.entry_anchor=self._anchor(g.entry_fd,g.entry_identity)
            need(g.fd!=g.entry_fd and self.group_anchor!=self.entry_anchor,'distinct actual aggregate and original entry anchors')
            self._pass('initial_before');self._pass('initial_after')
            need(self._projection(self.passes[0])==self._projection(self.passes[1]),'initial full hierarchy equality')
            self._threads();self._pass('recheck_before');self._pass('recheck_after')
            need(all(self._projection(x)==self._projection(self.passes[0])for x in self.passes),
                 'all four exact paths/inodes/PID/TID projections agree')
            need(all(x.complete and x.eof and x.slot.closed for x in self.raw_reads) and
                 all(x[1]for x in self.iterators) and all(s.closed for s in self.directory_slots),
                 'full original raw/EOF/close census, no unobserved completion')
            self.closed=True;g.own();o=self.observation;profile=a.pair.contract.profile
            process={'schema':'ci_process_observation_v1','attempt':a.prefix_capture.pin,'condition':a.condition,
                'cost_prefix':a.owner.cost_prefix(),'group_identity':self.worker,'identity':self.worker,
                'observed_ns':self.io.now(self.deadline),'parent_identity':a.owner.parent.identity,'producer':'host','subject':'worker'}
            a.process_capture=p.capture(o._prefix()+'_WORKER_PROCESS.json','ProcessObservation',process)
            body={'schema':'four_worker_launch_group_observation_v1','original_attempt':a.prefix_capture.pin,
                'condition':a.condition,'launch_request':a.arm.launch.pin,'owner_binding':a.owner.parent.binding_pin,
                'start_observation':a.start_observation.require_original_capture_v3().pin,'worker':self.worker,
                'worker_process_observation':a.process_capture.pin,'group_anchor':self.group_anchor,'entry_anchor':self.entry_anchor,
                **{r['phase']:r for r in self.passes},'thread_identities':self.thread_rows,
                'only_original_worker_threads':True,'unresolved_count':0,'group_source':profile['group_source'],
                'identity_source':profile['identity_source'],'observer_source':profile['observer_source'],
                'observed_ns':self.io.now(self.deadline),'cost_prefix':a.owner.cost_prefix()}
            self.capture=p.capture(o._prefix()+'_WORKER_GROUP.json','WorkerLaunchGroupObservationV1',body)
            a.group_capture=self.capture;return self.capture
        except BaseException as error:self.retain(error,'run');raise
        finally:
            for slot in reversed(self.directory_slots):
                if not slot.close_entered:
                    try:self._close(slot)
                    except BaseException as error:self.retain(error,'final_close')
