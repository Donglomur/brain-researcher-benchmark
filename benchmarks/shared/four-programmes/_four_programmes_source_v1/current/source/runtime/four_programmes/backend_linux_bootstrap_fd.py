"""Inactive fixed parent-owned FD198 producer for the complete context V2 ABI.

No child is launched here. The actual H Popen owner must use this exact keep
set and its fixed group-join-before-exec path after full bootstrap admission.
"""
import os
import fcntl
import stat
from .common import need
from .backend_linux_channel import HNativeChannelOwner
from .observer import RunningProcess,KernelGroup

WORKER_FD=198


class HWorkerEndpointAlias:
    def __init__(self,channel):
        need(type(channel) is HNativeChannelOwner and channel.attempt.native_channel is channel and
             channel.worker_alias is None,'one original source-owned bootstrap descriptor slot')
        self.channel=channel;self.attempt=channel.attempt;self.meter=channel.meter
        self.fd=None;self.raw_result=None;self.group=None;self.original_worker_fd=None
        self.entered=False;self.returned=False;self.ready=False
        self.close_entered=False;self.closed=False;self.unknown=False
        self.identity=None;self.raw_first=None;self.secondaries=[]
        channel.worker_alias=self # Before any descriptor observation/effect.

    def retain(self,error,site):
        if self.raw_first is None:self.raw_first=error
        elif error is not self.raw_first:self.secondaries.append(error)
        self.unknown=True;self.ready=False;self.channel.retain(error,'bootstrap_fd_'+site)

    def acquire(self,deadline):
        need(not self.entered,'one original fixed inherited descriptor attempt');self.entered=True
        try:
            c=self.channel;a=self.attempt;a.require_live_original()
            need(c.setup_complete and not c.poisoned and c.worker is not None and c.host is not None,
                 'both original source-owned channel endpoints before alias preparation')
            r=a.process
            need(type(r) is RunningProcess and r.owner is a.host and r.child is None and
                 type(r.group) is KernelGroup and r.group.entry_fd is not None,
                 'actual retained original group prepared before sole child launch')
            self.group=r.group;c._now(deadline);c._work()
            worker=c.worker.fileno();host=c.host.fileno();entry=self.group.entry_fd
            need(all(type(x) is int and x>2 for x in (worker,host,entry)) and len({worker,host,entry})==3,
                 'distinct actual worker/host/group descriptors, never stdio or supplied integer authority')
            self.original_worker_fd=worker
            self.meter.charge('retained_bytes',1024);c._work()
            # Always a distinct alias occurrence, including when the original
            # worker endpoint already occupies198. Never overwrite that slot.
            self.raw_result=fcntl.fcntl(worker,fcntl.F_DUPFD_CLOEXEC,WORKER_FD)
            if type(self.raw_result) is int and self.raw_result>=WORKER_FD:self.fd=self.raw_result
            self.returned=True
            need(self.fd==WORKER_FD,'FD198 occupied; retain/close only the actually returned higher alias')
            self.meter.charge('read_bytes',8192);c._work()
            original=os.fstat(worker);alias=os.fstat(self.fd)
            need(stat.S_ISSOCK(original.st_mode) and stat.S_ISSOCK(alias.st_mode) and
                 (original.st_dev,original.st_ino)==(alias.st_dev,alias.st_ino),
                 'actual alias of the same original private worker socket')
            self.identity=(alias.st_dev,alias.st_ino);c._now(deadline);self.ready=True;return self
        except BaseException as error:
            self.retain(error,'acquire')
            # Any successfully returned alias belongs to this failed attempt.
            # Unknown acquisition without a returned fd is retained, not guessed.
            self.close_once();raise self.raw_first

    def pass_fds(self):
        need(self.ready and self.raw_first is None and not self.channel.poisoned and not self.close_entered and self.fd==WORKER_FD and
             self.attempt.native_channel is self.channel and self.channel.worker_alias is self and
             self.attempt.process.group is self.group and self.group.entry_fd!=WORKER_FD,
             'same original prepared alias and actual group before fixed Popen')
        return (WORKER_FD,self.group.entry_fd)

    def close_once(self):
        if self.close_entered:return self.closed
        self.close_entered=True;self.ready=False;fd=self.fd;self.fd=None
        try:
            if fd is not None:os.close(fd)
            elif self.entered:
                self.unknown=True;return False
            self.closed=True;return True
        except BaseException as error:self.retain(error,'close');return False
