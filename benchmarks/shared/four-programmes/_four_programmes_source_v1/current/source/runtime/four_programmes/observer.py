"""Actual future original process/tree observation. No launch occurs on import.

Only an independently selected Linux environment may activate this source.
Per-job scientific methods remain original; these are enclosing observations.
"""
import os
import json
import selectors
import signal
import stat
import subprocess
import sys
import time
from pathlib import Path
from .common import need,closed,integer,failure,encode,pin,bounded_size
from .identity import process_identity, kernel_read
from . import dependencies

_ORIGINAL=object()

class OriginalProcessObservation:
    __slots__=("record","receipt","receipt_record","stdout","stderr","identity","_token")
    def __init__(self,token,record,receipt,receipt_record,stdout,stderr,identity):
        need(token is _ORIGINAL,"actual original host observer only")
        self.record=record;self.receipt=receipt;self.receipt_record=receipt_record;self.stdout=stdout;self.stderr=stderr
        self.identity=identity;self._token=token
    @property
    def success(self):
        r=self.record
        return (r["spawn_attempted"] is True and r["spawn_acknowledged"] is True and
                r["natural_exit"] is True and type(r["exit_code"]) is int and r["exit_code"]==0 and
                r["streams_eof"]=={"stdout":True,"stderr":True} and r["group_empty"] is True and
                r["group_removed"] is True and r["forced"] is False and r["timed_out"] is False and
                r["original_failure"] is None and r["cleanup_errors"]==[] and r["unknown_dimensions"]==[] and
                r["physical_final_known"] is True and r["publication_complete"] is True)

class KernelGroup:
    """Retains the actual created directory FD and rejects renamed/reused owners."""
    def __init__(self,parent,name,meter):
        need(sys.platform=="linux","separately qualified Linux cgroup-v2 only")
        p=Path(parent)
        need(p.is_absolute() and str(p).startswith('/sys/fs/cgroup/') and
             all(not x.is_symlink() for x in (p,*p.parents)),"exact qualified delegated cgroup parent")
        need(type(name) is str and name and len(name)<=200 and all(c in 'abcdefghijklmnopqrstuvwxyz0123456789-_' for c in name),
             "one source-owned unique group name")
        self.path=p/name;self.meter=meter;self.fd=None;self.created=False;self.removed=False;self.identity=None
        self.entry_fd=None;self.entry_identity=None;self.entry_created=False;self.entry_removed=False
    def prepare(self,limits):
        need(not self.created,"one original group creation attempt")
        self.path.mkdir(mode=0o700);self.created=True
        try:
            self.fd=os.open(self.path,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
            s=os.fstat(self.fd);self.identity=(s.st_dev,s.st_ino)
            # The aggregate remains empty of direct processes. Original nested
            # scientific groups and this entry leaf share its actual limits.
            available=set(self.read('cgroup.controllers',4096).decode('ascii').split())
            need({'cpu','memory','pids'}<=available,'actual delegated aggregate controllers')
            self.write('cgroup.subtree_control',b'+cpu +memory +pids')
            for key,value in (("memory.max",limits["memory_bytes"]),("memory.swap.max",0),("pids.max",limits["pids"])):
                self.write(key,str(value).encode('ascii'))
            os.mkdir('entry',mode=0o700,dir_fd=self.fd);self.entry_created=True
            self.entry_fd=os.open('entry',os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=self.fd)
            entry=os.fstat(self.entry_fd);self.entry_identity=(entry.st_dev,entry.st_ino)
            self.read('cgroup.events',4096);self.read('cpu.stat',4096)
            probe=os.stat('cgroup.kill',dir_fd=self.fd,follow_symlinks=False)
            need(stat.S_ISREG(probe.st_mode),"actual aggregate kill interface")
        except BaseException as error:
            self.meter.own_error(error,"group_setup");raise
    def own(self):
        need(self.fd is not None and not self.removed,"owned live group handle")
        a=os.fstat(self.fd);b=self.path.lstat()
        need((a.st_dev,a.st_ino)==(b.st_dev,b.st_ino)==self.identity and stat.S_ISDIR(b.st_mode),"original group still owns this path")
    def _io(self,name,cap,data=None):
        need(name in ("memory.max","memory.swap.max","pids.max","cgroup.procs","cgroup.kill","cpu.stat","memory.peak","cgroup.events",
                      "cgroup.controllers","cgroup.subtree_control"),
             "fixed kernel interface")
        self.meter.check();self.own();fd=None;primary=None;raw=b''
        self.meter.charge("read_bytes" if data is None else "write_bytes",cap+1 if data is None else len(data))
        try:
            fd=os.open(name,(os.O_RDONLY if data is None else os.O_WRONLY)|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=self.fd)
            if data is None:
                while len(raw)<=cap:
                    block=os.read(fd,min(4096,cap+1-len(raw)))
                    if not block:break
                    raw+=block
                need(len(raw)<=cap,"complete bounded kernel observation")
            else:
                offset=0
                while offset<len(data):
                    self.meter.check();n=os.write(fd,data[offset:]);need(n>0,"kernel write progress");offset+=n
        except BaseException as error:
            primary=error;self.meter.own_error(error,"kernel_"+("read" if data is None else "write"))
        if fd is not None:
            closing,fd=fd,None
            try:os.close(closing)
            except BaseException as error:
                self.meter.cleanup_errors.append(failure(error))
                if primary is None:primary=error;self.meter.own_error(error,"kernel_fd_close")
        if primary is not None:raise primary
        self.own();return raw
    def read(self,name,cap):return self._io(name,cap)
    def write(self,name,data):return self._io(name,0,data)
    def sample(self):
        cpu=dict(line.split() for line in self.read('cpu.stat',4096).decode('ascii').splitlines())
        events=dict(line.split() for line in self.read('cgroup.events',4096).decode('ascii').splitlines())
        memory=int(self.read('memory.peak',256));usage=int(cpu['usage_usec'])*1000
        integer(memory);integer(usage)
        need(events['populated'] in ('0','1'),"actual kernel populated flag")
        return {"cpu_ns":usage,"memory_peak":memory,"empty":events['populated']=='0'}
    def kill(self):self.write('cgroup.kill',b'1')
    def remove(self):
        self.own();need(self.sample()['empty'],"whole original group empty before removal")
        # Workers must remove their own nested job groups. Unknown extra groups
        # cause rmdir to fail; this observer never discovers/deletes foreign paths.
        if self.entry_created and not self.entry_removed:
            need(self.entry_fd is not None and self.entry_identity is not None,'retained actual entry leaf owner')
            a=os.fstat(self.entry_fd);b=os.stat('entry',dir_fd=self.fd,follow_symlinks=False)
            need((a.st_dev,a.st_ino)==(b.st_dev,b.st_ino)==self.entry_identity and stat.S_ISDIR(b.st_mode),
                 'same actual entry leaf before removal')
            os.rmdir('entry',dir_fd=self.fd);self.entry_removed=True
        self.path.rmdir();self.removed=True
    def close(self):
        primary=None
        for field in ('entry_fd','fd'):
            fd=getattr(self,field);setattr(self,field,None)
            if fd is None:continue
            try:os.close(fd)
            except BaseException as error:
                self.meter.own_error(error,"group_fd_close")
                if primary is None:primary=error
                else:self.meter.cleanup_errors.append(failure(error))
        if primary is not None:raise primary

class RunningProcess:
    """Handle produced by actual start; no caller-created success representation."""
    def __init__(self,token,observer,spec):
        need(token is _ORIGINAL,"actual host-owned process handle")
        self.owner=observer;self.spec=spec;self.child=None;self.group=None;self.selector=None;self.identity=None;self.finish_attempted=False
        self.chunks={"stdout":[],"stderr":[]};self.counts={"stdout":0,"stderr":0};self.primary=None
        self.record={"schema":"four_original_process_observation_v1","mode":spec["mode"],"argv":spec["argv"],
                     "source":spec["source"],"campaign":spec["campaign"],"spawn_attempted":False,"spawn_acknowledged":False,
                     "natural_exit":False,"exit_code":None,"streams_eof":{"stdout":False,"stderr":False},
                     "group_empty":False,"group_removed":False,"forced":False,"timed_out":False,
                     "original_failure":None,"cleanup_errors":[],"unknown_dimensions":[],"physical_final_known":False,
                     "physical_final":None,"physical_prefix":{},"publication_complete":False,"original_run_deadline_ns":spec["run_deadline_ns"],
                     "original_evidence_deadline_ns":spec["evidence_deadline_ns"],"original_output_prefixes":[]}
    def own_failure(self,error,dimension):
        if self.primary is None:self.primary=error;self.record["original_failure"]=failure(error)
        if dimension not in self.record["unknown_dimensions"]:self.record["unknown_dimensions"].append(dimension)
        self.owner.meter.own_error(error,dimension)

class HostObserver:
    def __init__(self,*,selected_environment,meter,output_store,clock_mapping,whole_group,storage):
        dependencies.require("root_observer_host_clock_environment",selected_environment)
        need(type(whole_group) is KernelGroup and type(storage) is StorageObservation,
             "fixed actual kernel and storage owners, not supplied observer callbacks")
        self.meter=meter;self.outputs=output_store;self.mapping=clock_mapping
        self.whole_group=whole_group;self.storage=storage;self.active={};self.consumed=set()
    def start(self,spec,*,pass_fds=()):
        closed(spec,("mode","argv","cwd","env","source","campaign","nonce","parent_launch","group_parent","group_name",
                     "limits","run_deadline_ns","evidence_deadline_ns","output_prefix"))
        need(spec["mode"] in ("n056_outer","n098_bridge","ci_stage","hm_stage","coordinator","hm_whole_host"),"fixed selected original source caller")
        closed(spec["limits"],("memory_bytes","pids","cpu_ns","stream_bytes","whole_cpu_ns","whole_memory_bytes","whole_storage_bytes"))
        for value in spec["limits"].values():integer(value,1)
        need(type(pass_fds) is tuple and len(set(pass_fds))==len(pass_fds) and
             all(type(fd) is int and fd>=0 for fd in pass_fds),"source-owned unique descriptor set")
        need(type(spec["argv"]) is list and spec["argv"] and all(type(x) is str and '\0' not in x for x in spec["argv"]),"literal original argv")
        need(spec["nonce"] not in self.consumed and spec["evidence_deadline_ns"]<=self.meter.deadline_ns and
             time.monotonic_ns()<spec["run_deadline_ns"]<=spec["evidence_deadline_ns"],"one original nonrenewed invocation")
        self.consumed.add(spec["nonce"]);r=RunningProcess(_ORIGINAL,self,spec)
        self.active[spec["nonce"]]=r
        try:
            r.group=KernelGroup(spec["group_parent"],spec["group_name"],self.meter)
            r.group.prepare(spec["limits"])
            self.meter.spawn_attempt();r.record["spawn_attempted"]=True
            groupfd=r.group.entry_fd
            def setup():
                # Fixed source-owned pre-exec join, before any selected executable.
                fd=os.open('cgroup.procs',os.O_WRONLY|os.O_NOFOLLOW,dir_fd=groupfd)
                try:
                    data=str(os.getpid()).encode('ascii');off=0
                    while off<len(data):
                        n=os.write(fd,data[off:]);need(n>0,"child group join progress");off+=n
                finally:os.close(fd)
                os.set_inheritable(groupfd,False)
            r.child=subprocess.Popen(spec["argv"],cwd=spec["cwd"],env=spec["env"],stdin=subprocess.DEVNULL,
                                     stdout=subprocess.PIPE,stderr=subprocess.PIPE,close_fds=True,pass_fds=tuple(pass_fds)+(groupfd,),
                                     start_new_session=True,preexec_fn=setup)
            r.record["spawn_acknowledged"]=True
            r.identity=process_identity(r.child.pid,launch_nonce=spec["nonce"],source=spec["source"],
                                         parent_launch=spec["parent_launch"],mapping=self.mapping,meter=self.meter)
            r.selector=selectors.DefaultSelector()
            for name in ("stdout","stderr"):
                stream=getattr(r.child,name);os.set_blocking(stream.fileno(),False)
                r.selector.register(stream,selectors.EVENT_READ,name)
            return r
        except BaseException as error:
            r.own_failure(error,"original_spawn_or_start");return r
    def _physical(self,r):
        own=r.group.sample();r.record["physical_prefix"]["worker"]=own
        whole=self.whole_group.sample();r.record["physical_prefix"]["whole"]=whole
        storage=self.storage.observe()
        r.record["physical_prefix"]["storage_bytes"]=storage
        need(own["cpu_ns"]<=r.spec["limits"]["cpu_ns"] and own["memory_peak"]<=r.spec["limits"]["memory_bytes"] and
             whole["cpu_ns"]<=r.spec["limits"]["whole_cpu_ns"] and
             whole["memory_peak"]<=r.spec["limits"]["whole_memory_bytes"] and
             storage<=r.spec["limits"]["whole_storage_bytes"],"original whole physical bounds")
        return {"worker":own,"whole":whole,"storage_bytes":storage}
    def pump(self,r,*,poll_interval_ns=None):
        need(type(r) is RunningProcess and r.owner is self,"actual owned running process")
        if r.primary is not None:return False
        if poll_interval_ns is not None:integer(poll_interval_ns,1)
        period=.05 if poll_interval_ns is None else min(.05,poll_interval_ns/1e9)
        try:
            now=time.monotonic_ns();self.meter.check()
            if now>=r.spec["run_deadline_ns"]:
                r.record["timed_out"]=True;raise TimeoutError("original enclosing run cutoff")
            self._physical(r)
            for key,_ in r.selector.select(min(period,max(0,(r.spec["run_deadline_ns"]-now)/1e9))):
                name=key.data;remaining=r.spec["limits"]["stream_bytes"]-r.counts[name]
                need(remaining>0,"no EOF probe or data read after selected stream allowance is exhausted")
                n=min(65536,remaining)
                self.meter.charge("read_bytes",n);self.meter.charge("retained_bytes",n)
                try:part=os.read(key.fileobj.fileno(),n)
                except BlockingIOError:continue
                if not part:r.record["streams_eof"][name]=True;r.selector.unregister(key.fileobj)
                else:r.chunks[name].append(part);r.counts[name]+=len(part)
            exit_owner=getattr(r,'_hm_exit_accounting_v1',None)
            code=(exit_owner.poll_and_reap_once() if exit_owner is not None else r.child.poll())
            if code is not None:
                r.record["exit_code"]=code;r.record["natural_exit"]=True
                if not r.selector.get_map():
                    need(type(code) is int and code==0,"actual original natural integer zero")
                    need(r.group.sample()["empty"],"all original descendants exited")
                    return False
            return True
        except BaseException as error:r.own_failure(error,"original_observation");return False
    def finish(self,r,*,pump=True):
        need(type(r) is RunningProcess and r.owner is self,"actual original running process")
        need(self.active.get(r.spec["nonce"]) is r,"one original lifecycle completion")
        need(not r.finish_attempted,"one original finish attempt; unknown retained handle cannot retry")
        need(type(pump)is bool,"explicit original pump disposition")
        if not pump:
            from .hm_whole_job_native_v1 import HMNativeStageAttemptV1
            stage=getattr(r,"_hm_native_stage_v1",None)
            stage_owned=(type(stage)is HMNativeStageAttemptV1 and stage.running is r and
                 stage.campaign.host is self and stage.campaign.stages.get(stage.sequence)is stage and
                 stage.loop_finished and stage.finish_entered)
            exit_owner=getattr(r,'_hm_exit_accounting_v1',None)
            exit_owned=(type(exit_owner)is HMOwnExitAccountingV1 and exit_owner.observer is self and
                        exit_owner.running is r and self._hm_exit_owners_v1.get(id(r))is exit_owner)
            need(stage_owned or exit_owned,
                 "skip only the actual retained HM source-owned completed pump loop")
            need(r.primary is not None or (r.record["natural_exit"] is True and
                 r.record["exit_code"]==0 and r.record["streams_eof"]=={"stdout":True,"stderr":True}),
                 "actual failed or fully observed exited worker before skip")
        r.finish_attempted=True
        if pump:
            while self.pump(r):pass
        if r.primary is not None and r.group is not None:
            try:r.group.kill();r.record["forced"]=True
            except BaseException as error:r.record["cleanup_errors"].append(failure(error));r.own_failure(error,"owned_group_kill")
        if r.child is not None:
            try:
                remaining=(r.spec["evidence_deadline_ns"]-time.monotonic_ns())/1e9
                need(remaining>0,"original evidence interval still open")
                exit_owner=getattr(r,'_hm_exit_accounting_v1',None)
                if exit_owner is not None:
                    # Keep real whole physical observation active during a
                    # selected C/H cleanup wait. A capture failure is retained;
                    # cleanup may still reap the child, never issue known CPU.
                    while r.child.returncode is None:
                        self.meter.check()
                        need(time.monotonic_ns()<r.spec['evidence_deadline_ns'],'original selected terminal cutoff')
                        try:self._physical(r)
                        except BaseException as error:r.own_failure(error,'terminal_physical')
                        # A known physical failure cannot suppress the one
                        # owned child exit capture/disposal attempt.
                        try:exit_owner.poll_and_reap_once()
                        except BaseException as error:
                            r.own_failure(error,'own_exit_cpu_unknown')
                            if exit_owner.raw_first is not None:
                                r.child.poll()  # disposal after failed capture, explicitly ineligible
                        if r.child.returncode is None:
                            time.sleep(min(exit_owner.poll_interval_ns/1e9,
                                max(0,(r.spec['evidence_deadline_ns']-time.monotonic_ns())/1e9)))
                    code=r.child.returncode
                else:code=r.child.wait(timeout=remaining)
                r.record["exit_code"]=code
            except BaseException as error:r.record["cleanup_errors"].append(failure(error));r.own_failure(error,"original_wait")
            for name in ("stdout","stderr"):
                try:getattr(r.child,name).close()
                except BaseException as error:r.record["cleanup_errors"].append(failure(error));r.own_failure(error,"original_stream_close")
        if r.selector is not None:
            try:r.selector.close()
            except BaseException as error:r.record["cleanup_errors"].append(failure(error));r.own_failure(error,"original_selector_close")
        if r.group is not None:
            try:
                r.record["physical_final"]=self._physical(r)
                if getattr(r,'_hm_exit_accounting_v1',None)is not None:
                    r.record['physical_final']['worker_pids_peak']=read_owned_pid_peak_v1(r.group,self.meter)
                    r.record['physical_final']['whole_pids_peak']=read_owned_pid_peak_v1(self.whole_group,self.meter)
                    need(r.record['physical_final']['worker_pids_peak']<=r.spec['limits']['pids'],
                         'actual selected process lifetime concurrency within its original limit')
                r.record["physical_final_known"]=True
                r.record["group_empty"]=r.record["physical_final"]["worker"]["empty"]
                r.group.remove();r.record["group_removed"]=True
            except BaseException as error:r.record["cleanup_errors"].append(failure(error));r.own_failure(error,"final_physical_or_cleanup")
            try:r.group.close()
            except BaseException as error:r.record["cleanup_errors"].append(failure(error));r.own_failure(error,"group_fd_close")
        exit_owner=getattr(r,'_hm_exit_accounting_v1',None)
        if exit_owner is not None:
            try:
                exit_owner.require_final()
                r.record['own_exit_cpu']=exit_owner.record()
            except BaseException as error:r.own_failure(error,'own_exit_cpu_unknown')
            try:exit_owner.close_once()
            except BaseException as error:r.own_failure(error,'own_exit_pidfd_close')
            if exit_owner.raw_first is None:
                try:r.record['own_exit_cpu']=exit_owner.record()
                except BaseException as error:r.own_failure(error,'own_exit_cpu_projection')
        # Joining retained chunks creates another complete byte string. Admit
        # that extent before allocation; unknown materialization is not empty
        # output, and a quota/MemoryError must not displace an earlier failure.
        materialized={};r.record["stream_materialization"]={}
        for name in ("stdout","stderr"):
            r.record[name+"_bytes"]=r.counts[name]
            try:
                self.meter.charge("retained_bytes",r.counts[name])
                raw=b''.join(r.chunks[name])
                need(len(raw)==r.counts[name],"exact actual retained stream byte count")
                materialized[name]=raw;r.record["stream_materialization"][name]=True
            except BaseException as error:
                materialized[name]=None;r.record[name]=None;r.record["stream_materialization"][name]=False
                r.own_failure(error,"original_"+name+"_materialization")
        stdout=materialized['stdout'];stderr=materialized['stderr'];receipt=None;receipt_record=None
        try:
            self.meter.check();need(time.monotonic_ns()<r.spec["evidence_deadline_ns"],"original publication cutoff")
            for name,raw in (("stdout",stdout),("stderr",stderr)):
                if raw is None:continue
                d=self.outputs.write(r.spec["output_prefix"]+"_"+name+".txt",raw)
                r.record["original_output_prefixes"].append(d);r.record[name]=d;r.record[name+"_bytes"]=len(raw)
            r.record["identity"]=r.identity;r.record["closed_ns"]=time.monotonic_ns();r.record["costs"]=self.meter.record()
            # A file cannot assert successful completion of its own publication.
            # Keep that exact earlier record separately from the actual H return.
            bound=bounded_size(r.record)
            self.meter.charge("work_units",bound);self.meter.charge("retained_bytes",bound)
            receipt_record=json.loads(encode(r.record))
            receipt=self.outputs.publish(r.spec["output_prefix"]+"_PROCESS.json",receipt_record)
            self.meter.check();need(time.monotonic_ns()<r.spec["evidence_deadline_ns"],"original final cutoff")
            r.record["publication_complete"]=True
        except BaseException as error:
            r.record["publication_complete"]=False;r.own_failure(error,"original_terminal_publication")
        # A failed observation must not discard the actual unresolved process
        # or group owner. Keep its original handle and full reservation. This
        # retained handle is diagnostic only: finish_attempted forbids retry.
        closed_child=(r.child is None and not r.record["spawn_attempted"]) or (
            r.child is not None and type(r.record["exit_code"]) is int)
        if r.record["group_empty"] and r.record["group_removed"] and closed_child:
            self.active.pop(r.spec["nonce"],None)
        return OriginalProcessObservation(_ORIGINAL,r.record,receipt,receipt_record,stdout,stderr,r.identity)

class StorageObservation:
    """Observe the exact independently qualified exclusive output filesystem.

    Mount/quota setup is an external native prerequisite. This class neither
    installs a quota nor treats statvfs as proof that one was configured.
    """
    def __init__(self,root,*,selected_environment,filesystem_id,meter):
        dependencies.require("root_observer_host_clock_environment",selected_environment)
        p=Path(root)
        need(p.is_absolute() and all(not x.is_symlink() for x in (p,*p.parents)),"selected original private output volume")
        self.path=p;self.meter=meter;self.fd=None;self.identity=None;self.filesystem_id=filesystem_id
        self.fd=os.open(p,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
        try:
            s=os.fstat(self.fd);self.identity=(s.st_dev,s.st_ino)
            self.baseline=self._raw()
        except BaseException as error:
            self.meter.own_error(error,"storage_bootstrap");closing,self.fd=self.fd,None
            try:os.close(closing)
            except BaseException as cleanup:self.meter.cleanup_errors.append(failure(cleanup))
            raise
    def _raw(self):
        self.meter.check();self.meter.charge("work_units",4096)
        try:
            need(self.fd is not None,"original live storage observer")
            a=os.fstat(self.fd);b=self.path.lstat()
            need((a.st_dev,a.st_ino)==(b.st_dev,b.st_ino)==self.identity,"original exclusive volume identity")
            v=os.fstatvfs(self.fd)
            need(v.f_fsid==self.filesystem_id,"independently selected filesystem")
            used=(v.f_blocks-v.f_bfree)*v.f_frsize;integer(used)
            return used
        except BaseException as error:self.meter.own_error(error,"storage_observation");raise
    def observe(self):
        now=self._raw();need(now>=self.baseline,"unexpected external volume deletion or reuse")
        return now-self.baseline
    def close(self):
        if self.fd is not None:
            closing,self.fd=self.fd,None
            try:os.close(closing)
            except BaseException as error:self.meter.own_error(error,"storage_close");raise


_HM_EXIT=object()


def read_owned_pid_peak_v1(group,meter):
    """Actual lifetime concurrency before removal; never process creations."""
    need(type(group)is KernelGroup,'actual retained original cgroup')
    group.own();fd=None;first=None;raw=None
    try:
        meter.charge('read_bytes',257)
        fd=os.open('pids.peak',os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=group.fd)
        raw=os.read(fd,257)
        need(len(raw)<=256 and raw.strip().isdigit() and not os.read(fd,1),'complete lifetime PID/TID peak')
    except BaseException as error:first=error
    finally:
        if fd is not None:
            try:os.close(fd)
            except BaseException as error:
                if first is None:first=error
                else:
                    try:meter.cleanup_errors.append(failure(error))
                    except BaseException:pass
    if first is not None:raise first
    group.own();return int(raw)


class HMOwnExitAccountingV1:
    """One actual parent's nonreaping exit capture for its source-owned C/H.

    /proc/PID/stat fields14/15 are process-thread-group CPU, excluding waited
    child fields16/17. A selected tick domain dividing1e9 has two separately
    truncated counters: lower=(u+s)*tick, exclusive upper=(u+s+2)*tick.
    Only this owner's actual kernel observation can produce a final value.
    """
    def __init__(self,token,observer,running,*,role,expected_identity,clock_mapping,poll_interval_ns):
        need(token is _HM_EXIT and type(observer)is HostObserver and type(running)is RunningProcess and
             running.owner is observer and observer.active.get(running.spec['nonce'])is running,
             'actual retained parent and its original child')
        need(role in ('C','H') and running.spec['mode']=={'C':'coordinator','H':'hm_whole_host'}[role],
             'distinct selected controller/host process mode')
        need(running.identity==expected_identity and running.child is not None and
             running.primary is None and running.child.returncode is None and not running.finish_attempted and
             getattr(running,'_hm_exit_accounting_v1',None)is None,
             'bind exact original identity before any reaping or terminal attempt')
        integer(poll_interval_ns,1)
        self.observer=observer;self.running=running;self.role=role;self.identity=dict(expected_identity)
        self.mapping=clock_mapping;self.poll_interval_ns=poll_interval_ns
        self.raw_first=None;self.secondaries=[];self.pidfd=None;self.capture_entered=False
        self.captured=False;self.reaped=False;self.close_entered=False;self.closed=False
        self.raw_stat=None;self.exit_body=None;self.exit_body_raw=None;self.wait_info=None
        self.poll_attempts=0;self.actual_reap_code=None
        running._hm_exit_accounting_v1=self
        if not hasattr(observer,'_hm_exit_owners_v1'):observer._hm_exit_owners_v1={}
        observer._hm_exit_owners_v1[id(running)]=self
        try:
            need(sys.platform=='linux',
                 'selected Linux original-parent wait mechanism')
            need(clock_mapping is observer.mapping,'same independently selected actual clock mapping')
            need(process_identity(running.child.pid,launch_nonce=self.identity['launch_nonce'],
                 source=self.identity['source'],parent_launch=self.identity['parent_launch'],
                 mapping=self.mapping,meter=observer.meter)==self.identity,'exact unreaped child at binding')
            observer.meter.check();self.pidfd=os.pidfd_open(running.child.pid,0)
        except BaseException as error:
            self.retain(error,'exit_owner_bind');self.close_once();raise self.raw_first

    def retain(self,error,site):
        if self.raw_first is None:self.raw_first=error
        elif error is not self.raw_first:self.secondaries.append((site,error))
        try:self.running.own_failure(error,'own_exit_cpu:'+site)
        except BaseException as later:
            if later is not self.raw_first:self.secondaries.append((site+':retention',later))

    def require_original(self):
        need(self.running._hm_exit_accounting_v1 is self and self.running.owner is self.observer and
             self.observer._hm_exit_owners_v1.get(id(self.running))is self and
             self.running.identity==self.identity and self.mapping is self.observer.mapping,
             'same retained source-owned exit observer and child')
        if self.raw_first is not None:raise self.raw_first
        return self

    def capture_if_exited(self):
        self.require_original()
        if self.captured:return self
        need(not self.capture_entered and not self.close_entered and self.pidfd is not None and
             self.running.child.returncode is None,'no retry/reaping before original exit capture')
        try:
            self.observer.meter.check();self.poll_attempts+=1
            info=os.waitid(os.P_PIDFD,self.pidfd,os.WEXITED|os.WNOHANG|os.WNOWAIT)
            if info is None or info.si_pid==0:return None
            self.capture_entered=True;self.wait_info=info
            need(info.si_pid==self.identity['pid'] and
                 info.si_code in (os.CLD_EXITED,os.CLD_KILLED,os.CLD_DUMPED),
                 'actual terminal event for the exact retained child pidfd')
            raw=kernel_read('/proc/'+str(self.identity['pid'])+'/stat',8192,self.observer.meter)
            self.raw_stat=raw;begin=raw.find(b'(');end=raw.rfind(b')')
            need(begin>0 and end>begin and int(raw[:begin].strip())==self.identity['pid'],'exact original terminal stat PID')
            fields=raw[end+2:].split();need(len(fields)>=20 and fields[0]==b'Z','complete unreaped original zombie stat')
            user=int(fields[11]);system=int(fields[12]);start=int(fields[19])
            for value in (user,system,start):integer(value)
            hz=self.mapping['clock_ticks'];integer(hz,1)
            need(os.sysconf('SC_CLK_TCK')==hz and 1000000000%hz==0,'selected exact-divisor kernel tick domain')
            need(start*1000000000//hz+self.mapping['tick_to_monotonic_offset_ns']==self.identity['start_monotonic_ns'],
                 'same original start tick; no reused PID admission')
            actual=process_identity(self.identity['pid'],launch_nonce=self.identity['launch_nonce'],
                source=self.identity['source'],parent_launch=self.identity['parent_launch'],
                mapping=self.mapping,meter=self.observer.meter)
            need(actual==self.identity,'same terminal boot/PID/start/source identity before reap')
            tick=1000000000//hz
            body={'schema':'hm_owned_process_exit_cpu_v1','role':self.role,'identity':self.identity,
                'waitid':{'si_pid':info.si_pid,'si_code':info.si_code,'si_status':info.si_status},
                'stat':pin(raw),'clock_ticks':hz,'utime_ticks':user,'stime_ticks':system,
                'cpu_lower_ns':(user+system)*tick,'cpu_upper_exclusive_ns':(user+system+2)*tick,
                'observation_monotonic_ns':time.monotonic_ns(),'scope':'complete own process thread group, excludes child CPU',
                'kernel_and_clock_qualification_still_required':True}
            self.exit_body=body;self.exit_body_raw=encode(body);self.captured=True;return self
        except BaseException as error:self.retain(error,'terminal_capture');raise self.raw_first

    def poll_and_reap_once(self):
        self.require_original()
        if self.reaped:return self.actual_reap_code
        if self.capture_if_exited()is None:return None
        try:
            code=self.running.child.poll()
            expected=(self.wait_info.si_status if self.wait_info.si_code==os.CLD_EXITED else -self.wait_info.si_status)
            need(type(code)is int and code==expected,'same actual status reaped only after complete exit capture')
            self.actual_reap_code=code;self.reaped=True;return code
        except BaseException as error:self.retain(error,'actual_reap');raise self.raw_first

    def require_final(self,minimum_cpu_ns=0):
        self.require_original();integer(minimum_cpu_ns)
        need(self.captured and self.exit_body_raw==encode(self.exit_body) and
             self.exit_body['cpu_upper_exclusive_ns']>minimum_cpu_ns,
             'actual immutable final process bound contains every earlier live sample')
        return self.exit_body['cpu_upper_exclusive_ns']

    def record(self):
        self.require_final()
        return {'schema':'hm_owned_exit_accounting_record_v1','body':json.loads(self.exit_body_raw),
                'complete':self.captured and self.reaped and self.closed and self.raw_first is None,
                'identity':dict(self.identity),'cpu_upper_ns':self.exit_body['cpu_upper_exclusive_ns'],
                'cpu_upper_exclusive_ns':self.exit_body['cpu_upper_exclusive_ns'],
                'reaped':self.reaped,'actual_reap_code':self.actual_reap_code,
                'pidfd_closed':self.closed,'poll_attempts':self.poll_attempts,'scientific_qualification':False}

    def close_once(self):
        if self.close_entered:return self.closed
        self.close_entered=True;fd,self.pidfd=self.pidfd,None
        try:
            if fd is not None:os.close(fd)
            self.closed=True;return True
        except BaseException as error:self.retain(error,'pidfd_close');raise self.raw_first


def bind_hm_exit_accounting_v1(observer,running,*,role,expected_identity,clock_mapping,poll_interval_ns):
    return HMOwnExitAccountingV1(_HM_EXIT,observer,running,role=role,expected_identity=expected_identity,
                               clock_mapping=clock_mapping,poll_interval_ns=poll_interval_ns)
