"""Bounded actual nested cgroup census, separate from no-escape qualification.

Every directory and metadata FD is anchored and retained before observation.
Two equal full traversals detect observed changes; they are not a claim that
unqualified Linux isolation or a racing live subtree is a global atomic view.
"""
import os
import stat
from .common import need
from .backend_linux_io import NativeIOCustody
from .backend_linux_host_observation import HostNativeIOCustody
from .backend_linux_observations import read_kernel_fd


class GroupCensus:
    def __init__(self,io,aggregate_fd,aggregate_identity,worker_pid,server_pid,deadline,*,stopped_whole_arm=False):
        need(type(io) in (NativeIOCustody,HostNativeIOCustody),'same closed original worker or H census owner')
        need((type(server_pid) is int and server_pid>0) or (server_pid is None and type(io) is HostNativeIOCustody),
             'exact server identity when scoped; H raw whole aggregate has no invented server identity')
        self.io=io;self.fd=aggregate_fd;self.identity=aggregate_identity
        self.worker_pid=worker_pid;self.server_pid=server_pid;self.deadline=deadline
        need(type(stopped_whole_arm) is bool and
             (not stopped_whole_arm or (type(io) is HostNativeIOCustody and server_pid is None and
              io.original_observation is not None and io.original_observation.kernel.wait_consumed and
              not io.original_observation.kernel.reap_unknown)),
             'stopped whole-arm scope only from actual original H consumed wait')
        self.stopped_whole_arm=stopped_whole_arm
        self.entered=False;self.passes=[];self.iterators=[];self.raw_first=None;self.secondaries=[]
        self.observed_ns=None;self.stable=False;self.closed=False
        self.thread_passes=[];self.residual_pids=None;self.residual_thread_ids=None
        self.unresolved_thread_ids=None

    def retain(self,error):
        if self.raw_first is None:self.raw_first=error
        elif error is not self.raw_first:self.secondaries.append(error)
        self.io.retain(error,'subtree')

    def _members(self,fd,name):
        need(name in ('cgroup.procs','cgroup.threads'),'fixed complete kernel membership roles')
        slot=self.io.slot('group');original=None
        try:
            slot.openat(fd,name,os.O_RDONLY|os.O_NONBLOCK)
            raw=read_kernel_fd(slot,65536,self.deadline)
            words=raw.split();need(len(words)<=4096 and all(x.isdigit() for x in words),'bounded complete PID census')
            pids=tuple(sorted(int(x) for x in words))
            need(all(x>0 for x in pids) and len(pids)==len(set(pids)),'unique positive process identities')
            return pids
        except BaseException as error:original=error;self.retain(error);raise
        finally:
            if not slot.close() and slot.raw_first is not None:
                self.retain(slot.raw_first)
                for secondary in slot.raw_secondaries:self.retain(secondary)
                if original is None:raise slot.raw_first

    def _walk(self,fd,path,rows,threads,depth):
        need(depth<=64 and len(rows)<4096,'finite refused-overflow group traversal')
        self.io.now(self.deadline);self.io.work();a=os.fstat(fd)
        need(stat.S_ISDIR(a.st_mode),'actual cgroup directory')
        pids=self._members(fd,'cgroup.procs');rows.append((path,a.st_dev,a.st_ino,pids))
        tids=self._members(fd,'cgroup.threads');threads.append((path,a.st_dev,a.st_ino,tids))
        self.io.meter.charge('retained_bytes',65536)
        # Own the iterator immediately. next/scandir may do physical metadata
        # IO; its admission is conservative and its unmeasured effects stay in
        # the original owner's unknown dimensions, never measured zero.
        iterator=None;original=None
        try:
            self.io.work();iterator=os.scandir(fd);self.iterators.append([iterator,False])
            children=[];entries=0
            while True:
                self.io.now(self.deadline);self.io.work();self.io.meter.charge('read_bytes',4096)
                try:entry=next(iterator)
                except StopIteration:break
                entries+=1;need(entries<=4096,'bounded physical directory entries')
                name=entry.name
                need(type(name) is str and name not in ('','.', '..') and '/' not in name and len(name)<=255,
                     'bounded anchored cgroup entry')
                if entry.is_symlink():raise RuntimeError('unexpected cgroup symlink')
                if entry.is_dir(follow_symlinks=False):children.append(name)
            for name in sorted(children):
                slot=self.io.slot('group');child_error=None
                try:
                    slot.openat(fd,name,os.O_RDONLY|os.O_DIRECTORY|os.O_NONBLOCK)
                    b=os.stat(name,dir_fd=fd,follow_symlinks=False)
                    need((b.st_dev,b.st_ino)==slot.identity[:2] and stat.S_ISDIR(b.st_mode),
                         'same named/opened nested group, no replacement')
                    self._walk(slot.fd,path+(name,),rows,threads,depth+1)
                except BaseException as error:child_error=error;self.retain(error);raise
                finally:
                    if not slot.close() and slot.raw_first is not None:
                        self.retain(slot.raw_first)
                        for secondary in slot.raw_secondaries:self.retain(secondary)
                        if child_error is None:raise slot.raw_first
        except BaseException as error:original=error;self.retain(error);raise
        finally:
            if iterator is not None:
                item=self.iterators[-1] if self.iterators[-1][0] is iterator else next(x for x in self.iterators if x[0] is iterator)
                if not item[1]:
                    item[1]=True
                    try:iterator.close()
                    except BaseException as error:
                        self.retain(error)
                        if original is None:raise

    def run(self):
        need(not self.entered,'one complete original server-subtree observation');self.entered=True
        try:
            self.io.mark_unknown() # physical metadata cost is not asserted measured.
            root=os.fstat(self.fd)
            need(stat.S_ISDIR(root.st_mode) and (root.st_dev,root.st_ino)==
                 (self.identity['device'],self.identity['inode']),'actual original aggregate anchor')
            for _ in range(2):
                rows=[];threads=[];self.passes.append(rows);self.thread_passes.append(threads)
                self._walk(self.fd,(),rows,threads,0)
                all_pids=[p for r in rows for p in r[3]]
                all_tids=[p for r in threads for p in r[3]]
                need(len(all_pids)<=4096 and len(all_pids)==len(set(all_pids)),
                     'whole aggregate unique bounded membership, including nested groups')
                if self.stopped_whole_arm:
                    need(not all_pids and not all_tids,'actual whole arm empty, including every thread')
                else:need(self.worker_pid in all_pids,'actual live original worker retained')
                need(len(all_tids)<=4096 and len(all_tids)==len(set(all_tids)) and set(all_pids)<=set(all_tids),
                     'bounded unique full thread census including every process leader')
            need(self.passes[0]==self.passes[1] and self.thread_passes[0]==self.thread_passes[1],
                 'stable fully observed hierarchy and complete PID/TID membership')
            self.stable=True;self.observed_ns=self.io.now(self.deadline)
            self.closed=all(x[1] for x in self.iterators)
            self.residual_pids=tuple(p for p in all_pids if p!=self.worker_pid)
            self.residual_thread_ids=tuple(t for t in all_tids if t!=self.worker_pid)
            # Nonleader TIDs are not silently relabeled as the excluded worker.
            # A later actual /proc identity/TGID resolver must account for each;
            # without it, a typed empty/complete subtree is unavailable.
            self.unresolved_thread_ids=tuple(t for t in all_tids if t not in all_pids)
            return self
        except BaseException as error:self.retain(error);raise
