"""Concrete H-owned Linux private seqpacket endpoints and bounded physical IO.

This source is inactive until the complete context ABI is adopted/integrated.
It creates no RootBootstrapAdmission, worker capability or nominal wire reply.
Fixed protocol consumers must validate the actual packet and original sequence.
"""
import socket
import os
import select
import struct
import time
from .common import need
from .early_resources import EarlyResources
from .development_handles import DevelopmentAttemptHandle
from .observer import RunningProcess


class HNativeChannelOwner:
    """Immediate ownership of both endpoint objects, including partial setup."""
    def __init__(self,attempt):
        need(type(attempt) is DevelopmentAttemptHandle,'actual source-owned H attempt')
        attempt.require_live_original()
        need(type(attempt.owner) is EarlyResources and attempt.native_channel is None,
             'one actual original owner, never a decoded H clone')
        self.attempt=attempt;self.owner=attempt.owner;self.meter=self.owner.arms[attempt.condition]
        self.raw_pair=None;self.host=None;self.worker=None;self.setup_entered=False;self.setup_complete=False
        self.close_entered=set();self.close_completed=set();self.raw_first=None;self.secondaries=[]
        self.worker_process=None;self.pid=None;self.uid=None;self.nonblocking=False
        self.raw_receives=[];self.raw_sends=[];self.send_attempts=0;self.receive_attempts=0
        self.known_read=0;self.known_written=0;self.unknown_read=False;self.unknown_write=False
        self.poisoned=False;self.last_time=None
        self.native_observer=None
        self.worker_alias=None
        self.reservation_ledger=None;self.receiver_activation=None;self.protocol=None
        self.current_receive_result=None;self.unexpected_fd_slots=[]
        self.worker_anchor=None
        self.bootstrap_carrier_physical=None
        self.setup_observations=[]
        attempt.native_channel=self # Retained before acquisition/clock/cost effects.

    def use_control_reservation(self,ledger):
        from .backend_native_reservations import NativeReservationLedger
        need(type(ledger)is NativeReservationLedger and ledger.channel is self and
             self.reservation_ledger is ledger and not self.setup_entered and self.protocol is None,
             'same prior original control reservation before endpoint acquisition')
        self.meter=ledger.arm_meter()
        return self

    def retain(self,error,site):
        if self.raw_first is None:self.raw_first=error
        elif error is not self.raw_first:self.secondaries.append(error)
        self.poisoned=True;self.attempt.retain(error,'native_channel_'+site)

    def _now(self,deadline):
        self.meter.check();now=time.monotonic_ns()
        need(type(deadline) is int and deadline<=self.attempt.evidence_deadline_ns<=self.owner.parent.original_deadline and
             self.owner.parent.original_origin<=now<=deadline and
             (self.last_time is None or now>=self.last_time),'actual unchanged H clock and original evidence cutoff')
        self.last_time=now;return now

    def _work(self):self.meter.charge('work_units',4096)

    def acquire(self,deadline):
        need(not self.setup_entered and not self.poisoned,'one original endpoint acquisition')
        self.setup_entered=True
        try:
            self._now(deadline);self._work();self.meter.charge('retained_bytes',4096)
            # Store the entire original tuple immediately; close_all can still
            # find BOTH returned sockets if later assignment/setup fails.
            self.raw_pair=socket.socketpair(socket.AF_UNIX,socket.SOCK_SEQPACKET|socket.SOCK_CLOEXEC,0)
            need(type(self.raw_pair) is tuple and len(self.raw_pair)==2,'actual two-endpoint socketpair')
            self.host,self.worker=self.raw_pair
            for endpoint in self.raw_pair:
                endpoint.setsockopt(socket.SOL_SOCKET,socket.SO_PASSCRED,1)
                endpoint.setblocking(False)
                self._work();self.meter.charge('read_bytes',8)
                observed_type=endpoint.getsockopt(socket.SOL_SOCKET,socket.SO_TYPE)
                self.setup_observations.append((endpoint,'SO_TYPE',observed_type))
                self._work();self.meter.charge('read_bytes',8)
                observed_credentials=endpoint.getsockopt(socket.SOL_SOCKET,socket.SO_PASSCRED)
                self.setup_observations.append((endpoint,'SO_PASSCRED',observed_credentials))
                self._work();observed_blocking=endpoint.getblocking()
                self.setup_observations.append((endpoint,'blocking',observed_blocking))
                need(observed_type==socket.SOCK_SEQPACKET and observed_credentials==1 and observed_blocking is False,
                     'actual original endpoint type/credential/nonblocking readback')
            self.nonblocking=True;self.setup_complete=True;self._now(deadline)
            return self
        except BaseException as error:self.retain(error,'acquire');raise

    def bind_returned_worker(self):
        """Select credentials from the exact retained actual H launch result."""
        need(self.setup_complete and not self.poisoned and self.worker_process is None,'one original worker binding')
        self.attempt.require_live_original();r=self.attempt.process
        need(type(r) is RunningProcess and r.owner is self.attempt.host and r.child is not None and
             r.record['spawn_acknowledged'] and r.identity is not None and r.identity['pid']==r.child.pid,
             'actual returned H process/start identity; packet assertion is not a producer')
        need(self.attempt.arm.workspace.identity is not None,'actual original workspace user observation')
        self.worker_process=r;self.pid=r.child.pid;self.uid=self.attempt.arm.workspace.identity['uid']
        try:
            from .backend_host_worker_anchor import HWorkerIdentityAnchor
            anchor=HWorkerIdentityAnchor(self)
            anchor.open_original(self.attempt.evidence_deadline_ns)
            return self
        except BaseException as error:self.retain(error,'bind_worker');raise

    def _worker_live(self,deadline):
        from .backend_host_worker_anchor import HWorkerIdentityAnchor
        need(type(self.worker_anchor)is HWorkerIdentityAnchor and self.worker_anchor.channel is self and
             self.worker_anchor.complete,'actual original worker pidfd/start owner before packet effects')
        self.worker_anchor.check_live(deadline)

    def _ready(self,deadline,write=False):
        need(self.setup_complete and self.nonblocking and self.host is not None and not self.poisoned and
             'host' not in self.close_entered,'original known nonblocking endpoint')
        while True:
            now=self._now(deadline);need(now<deadline,'no readiness operation after original cutoff');self._work()
            try:r,w,x=select.select([] if write else [self.host],[self.host] if write else [],[self.host],min(.05,(deadline-now)/1000000000))
            except InterruptedError:continue
            need(not x,'original endpoint exceptional condition')
            if (w if write else r):return

    def _nonblocking_ready_owner(self):
        need(self.setup_complete and self.nonblocking and self.host is not None and not self.poisoned and
             'host' not in self.close_entered,'actual original live nonblocking endpoint')

    def try_receive_v3(self,maximum,deadline):
        """At most one nonblocking recvmsg; None means observed EAGAIN only.

        The original reservation/attempt remains consumed on EAGAIN. No wait,
        renewed deadline or decoded replacement owner is introduced.
        """
        self._nonblocking_ready_owner()
        need(type(maximum) is int and 0<maximum<=65536 and self.worker_process is not None,
             'positive selected packet bound and actual worker binding')
        need(self.receive_attempts<4096,'finite original physical receive attempts')
        self.receive_attempts+=1
        try:
            self._worker_live(deadline);self._now(deadline)
            self.meter.charge('read_bytes',maximum+64)
            self.meter.charge('retained_bytes',maximum+64);self._work()
            try:result=self.host.recvmsg(maximum,socket.CMSG_SPACE(12),socket.MSG_DONTWAIT)
            except BlockingIOError:return None
            except BaseException:self.unknown_read=True;raise
            self.current_receive_result=result # Entire returned prefix before any list allocation/check.
            self.raw_receives.append(result) # Before shape/credential/clock checks.
            raw,ancillary,flags,address=result
            if type(raw) is bytes:self.known_read+=len(raw)
            # Linux SCM_RIGHTS installs new descriptors even when the
            # protocol rejects the message. Retain every returned integer
            # occurrence before refusal; never let validation skip close.
            for level,kind,data in ancillary:
                if level==socket.SOL_SOCKET and kind==socket.SCM_RIGHTS:
                    need(type(data)is bytes,'actual returned descriptor bytes')
                    for index in range(0,len(data)-len(data)%4,4):
                        fd=struct.unpack('i',data[index:index+4])[0]
                        self.unexpected_fd_slots.append({'fd':fd,'close_entered':False,'closed':False,'raw_first':None})
                    need(len(data)%4==0,'complete bounded received rights extent')
            if flags&socket.MSG_TRUNC:self.unknown_read=True
            need(type(raw) is bytes and 0<len(raw)<=maximum,'original complete nonempty bounded packet')
            need(not flags&(socket.MSG_TRUNC|socket.MSG_CTRUNC),'no truncated payload or credential census')
            need(len(ancillary)==1 and ancillary[0][0:2]==(socket.SOL_SOCKET,socket.SCM_CREDENTIALS),
                 'one actual per-message credential; no SCM_RIGHTS or other ancillary capability')
            credentials=ancillary[0][2];need(type(credentials) is bytes and len(credentials)==12,'exact Linux ucred extent')
            pid,uid,gid=struct.unpack('3i',credentials)
            need(pid==self.pid and uid==self.uid and gid>=0,'same actual returned worker process and user')
            self._worker_live(deadline);self._now(deadline);return raw
        except BaseException as error:
            self.retain(error,'receive');self.close_unexpected_rights();raise

    def receive(self,maximum,deadline):
        """Legacy blocking wrapper, not used by the original two-arm driver."""
        while True:
            self._ready(deadline)
            raw=self.try_receive_v3(maximum,deadline)
            if raw is not None:return raw

    def close_unexpected_rights(self):
        complete=True
        for slot in self.unexpected_fd_slots:
            if slot['close_entered']:
                complete=complete and slot['closed'];continue
            slot['close_entered']=True;fd=slot['fd'];slot['fd']=None
            try:
                need(type(fd)is int and fd>=0,'actual received descriptor integer')
                os.close(fd);slot['closed']=True
            except BaseException as error:
                complete=False;slot['raw_first']=error;self.retain(error,'unexpected_fd_close')
        return complete

    def try_send_v3(self,wire,maximum,deadline):
        """One atomic nonblocking send; None means known no transfer only."""
        self._nonblocking_ready_owner()
        need(type(wire) is bytes and type(maximum) is int and 0<len(wire)<=maximum<=65536,
             'exact source-encoded bounded reply bytes')
        need(self.send_attempts<4096,'finite original physical send attempts');self.send_attempts+=1
        try:
            self._worker_live(deadline);self._now(deadline)
            self.meter.charge('write_bytes',len(wire));self._work()
            try:sent=self.host.sendmsg([wire],[],socket.MSG_DONTWAIT|socket.MSG_NOSIGNAL)
            except BlockingIOError:return None
            except BaseException:self.unknown_write=True;raise
            self.raw_sends.append(sent)
            if type(sent) is int and sent>=0:self.known_written+=sent
            need(type(sent) is int and sent==len(wire),'one complete atomic seqpacket send; partial is never replayed')
            self._worker_live(deadline);self._now(deadline);return sent
        except BaseException as error:self.retain(error,'send');raise

    def send(self,wire,maximum,deadline):
        """Legacy blocking wrapper, not used by the original two-arm driver."""
        while True:
            self._ready(deadline,True)
            sent=self.try_send_v3(wire,maximum,deadline)
            if sent is not None:return sent

    def close_endpoint(self,side):
        need(side in ('host','worker'),'fixed original endpoint role')
        if side in self.close_entered:return side in self.close_completed
        self.close_entered.add(side) # Clear/latch before ambiguous object close.
        endpoint=getattr(self,side);setattr(self,side,None)
        if endpoint is None and self.raw_pair is not None:endpoint=self.raw_pair[0 if side=='host' else 1]
        try:
            if endpoint is not None:endpoint.close()
            elif self.setup_entered:raise RuntimeError('unknown endpoint acquisition prefix')
            self.close_completed.add(side);return True
        except BaseException as error:self.retain(error,'close_'+side);return False

    def close_all(self):
        # No read/drain/wait or clock gate can block independent close attempts.
        carrier_closed=True
        if self.bootstrap_carrier_physical is not None:
            try:
                from .backend_linux_bootstrap_memfd import HBootstrapMemfdPhysical
                need(type(self.bootstrap_carrier_physical)is HBootstrapMemfdPhysical and
                     self.bootstrap_carrier_physical.channel is self,'fixed original physical carrier cleanup')
                carrier_closed=self.bootstrap_carrier_physical.close_once()
            except BaseException as error:carrier_closed=False;self.retain(error,'carrier_close')
        alias_closed=True
        if self.worker_alias is not None:
            try:
                from .backend_linux_bootstrap_fd import HWorkerEndpointAlias
                need(type(self.worker_alias) is HWorkerEndpointAlias and self.worker_alias.channel is self,
                     'fixed source-owned original alias cleanup, no supplied callback')
                alias_closed=self.worker_alias.close_once()
            except BaseException as error:alias_closed=False;self.retain(error,'alias_close')
        rights_closed=self.close_unexpected_rights()
        anchor_closed=True
        if self.worker_anchor is not None:
            try:
                from .backend_host_worker_anchor import HWorkerIdentityAnchor
                need(type(self.worker_anchor)is HWorkerIdentityAnchor and self.worker_anchor.channel is self,
                     'fixed original worker identity owner cleanup')
                anchor_closed=self.worker_anchor.close_once()
            except BaseException as error:anchor_closed=False;self.retain(error,'worker_anchor_close')
        a=self.close_endpoint('host');b=self.close_endpoint('worker');return carrier_closed and alias_closed and rights_closed and anchor_closed and a and b
