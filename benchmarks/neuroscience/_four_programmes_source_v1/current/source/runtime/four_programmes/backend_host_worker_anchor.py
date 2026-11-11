"""Actual original-worker pidfd/start anchor for each private H packet.

This is source construction, not a bootstrap/native qualification issuer.
Only the retained original H RunningProcess selects the PID and identity.
"""
import os
import select
import stat
from .common import need, same
from .backend_json import canonical
from .observer import RunningProcess, HostObserver
from .precommit_records import validate_type
from .backend_linux_io import NativeIOCustody, DescriptorSlot
from .backend_linux_observations import read_kernel_fd, process_identity_from_observation


class HWorkerIdentityAnchor(NativeIOCustody):
    def __init__(self, channel):
        from .backend_linux_channel import HNativeChannelOwner
        need(type(channel)is HNativeChannelOwner and channel.attempt.native_channel is channel and
             channel.worker_anchor is None,'one fixed original H worker identity owner')
        self.channel=channel;self.handle=channel.attempt;self.meter=channel.meter
        self.running=channel.worker_process;self.host=self.handle.host
        self.slots=[];self.raw_first=None;self.raw_secondaries=[];self.last_time=None
        self.known_read=0;self.known_written=0;self.unknown_read=False;self.unknown_write=False
        self.pidfd=None;self.root=None;self.directory=None;self.boot=None
        self.expected_identity=None;self.expected_mapping=None;self.identity_object=None;self.mapping_object=None
        self.current_poll=None;self.polls=[];self.current_observation=None;self.observations=[]
        self.entered=False;self.complete=False;self.close_entered=False;self.closed=False
        channel.worker_anchor=self  # Before clock, allocation or syscall effects.

    def retain(self,error,site):
        if self.raw_first is None:self.raw_first=error
        elif error is not self.raw_first:self.raw_secondaries.append(error)
        self.channel.retain(error,'worker_identity_'+site)

    def now(self,deadline):return self.channel._now(deadline)

    def mark_unknown(self):
        self.handle.owner.parent.unknown.update(('read_bytes','work_units','retained_bytes'))

    def slot(self,role):
        need(role in ('proc','pidfd'),'fixed original worker identity descriptor roles')
        self.work();self.meter.charge('retained_bytes',512)
        return DescriptorSlot(self,role)

    def _original(self):
        c=self.channel;a=self.handle;r=self.running
        a.require_live_original()
        need(c.worker_anchor is self and c.worker_process is r and a.process is r and
             type(r)is RunningProcess and type(self.host)is HostObserver and r.owner is self.host and
             self.host.active.get(r.spec['nonce'])is r and r.child is not None and
             r.record['spawn_acknowledged'] and r.identity is not None and r.child.pid==c.pid==r.identity['pid'],
             'same actual registered original H process, never packet-selected identity')
        need(r.identity['launch_nonce']==r.spec['nonce'] and same(r.identity['source'],r.spec['source']) and
             same(r.identity['parent_launch'],r.spec['parent_launch']),
             'original source/nonce/parent identity from original spawn spec')
        if self.expected_identity is not None:
            self.meter.charge('retained_bytes',32768);self.work(32768)
            need(r.identity is self.identity_object and self.host.mapping is self.mapping_object and
                 canonical(r.identity,16384)==self.expected_identity and canonical(self.host.mapping,16384)==self.expected_mapping,
                 'same original immutable identity and qualified clock-map value, no replaced or mutated dict')
        return r

    def _poll(self,deadline):
        self.now(deadline);self.work();self.meter.charge('retained_bytes',512)
        need(self.pidfd is not None and self.pidfd.fd is not None and not self.pidfd.close_entered,
             'retained original pidfd before every native packet')
        self.current_poll=select.select([self.pidfd.fd],[],[self.pidfd.fd],0)
        self.polls.append(self.current_poll)  # Retain actual result before validation.
        ready,writable,exceptional=self.current_poll
        need(not ready and not writable and not exceptional,'original worker still live, no PID reuse authority')

    def _read(self,parent,name,cap,deadline):
        slot=self.slot('proc');primary=None;raw=None
        try:
            slot.openat(parent.fd,name,os.O_RDONLY|os.O_NONBLOCK)
            raw=read_kernel_fd(slot,cap,deadline)
            self.current_observation={'name':name,'raw':raw,'slot':slot,'identity':None}
            self.observations.append(self.current_observation)
        except BaseException as error:
            primary=error;self.retain(error,'read')
        closed=slot.close()  # Independent from later clock/parse and never retried.
        if primary is not None:raise primary
        if slot.raw_first is not None:raise slot.raw_first
        need(closed,'actual original worker metadata close; uncertain close is not success')
        return raw

    def open_original(self,deadline):
        need(not self.entered,'one original worker identity acquisition');self.entered=True
        try:
            r=self._original();validate_type('OriginalProcessIdentity',r.identity)
            self.now(deadline);self.meter.charge('retained_bytes',32768);self.work(32768)
            self.identity_object=r.identity;self.mapping_object=self.host.mapping
            self.expected_identity=canonical(r.identity,16384);self.expected_mapping=canonical(self.host.mapping,16384)
            need(len(self.expected_identity)<=16384 and len(self.expected_mapping)<=16384,
                 'bounded actual original identity/clock metadata')
            self.pidfd=self.slot('pidfd');self.pidfd.acquire_entered=True;self.work()
            try:self.pidfd.fd=os.pidfd_open(r.child.pid,0)
            except BaseException as error:self.pidfd.retain(error);raise
            self._poll(deadline)
            self.root=self.slot('proc');self.root.fixed_proc_root()
            self.directory=self.slot('proc')
            self.directory.openat(self.root.fd,str(r.child.pid),os.O_RDONLY|os.O_DIRECTORY|os.O_NONBLOCK)
            parent=self.root
            for name in ('sys','kernel','random'):
                child=self.slot('proc');child.openat(parent.fd,name,os.O_RDONLY|os.O_DIRECTORY|os.O_NONBLOCK);parent=child
            raw_boot=self._read(parent,'boot_id',128,deadline)
            self.boot=raw_boot.decode('ascii').strip()
            need(self.boot==r.identity['boot_id']==self.host.mapping['boot_id'],'actual anchored Linux boot matches original owner')
            self.check_live(deadline);self.complete=True;return self
        except BaseException as error:self.retain(error,'open');raise

    def check_live(self,deadline):
        try:
            r=self._original();need(self.entered and not self.close_entered and self.raw_first is None,
                                   'same original live worker identity owner')
            self._poll(deadline);self.work();observed=os.fstat(self.directory.fd)
            need(stat.S_ISDIR(observed.st_mode) and observed.st_uid==self.channel.uid and
                 (observed.st_dev,observed.st_ino,observed.st_mode)==self.directory.identity,
                 'same opened worker proc directory/user, never a new PID path')
            raw=self._read(self.directory,'stat',8192,deadline)
            identity,fields=process_identity_from_observation(raw,r.child.pid,self.boot,self.host.mapping,
                r.spec['nonce'],r.spec['source'],r.spec['parent_launch'])
            self.current_observation['identity']=identity
            need(same(identity,r.identity) and fields['state']not in ('Z','X','x'),
                 'actual original worker start/boot/source remains live before and after every packet')
            self._poll(deadline);self.now(deadline)
            return self
        except BaseException as error:self.retain(error,'check');raise

    def close_once(self):
        if self.close_entered:return self.closed
        self.close_entered=True;complete=True
        for slot in reversed(self.slots):
            try:complete=slot.close()and complete
            except BaseException as error:complete=False;self.retain(error,'close')
        self.closed=complete;return complete
