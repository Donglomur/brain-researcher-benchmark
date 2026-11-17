"""Concrete sealed readonly bootstrap carrier IO, behind the V3 issuer gate.

This class owns physical descriptors and exact byte prefixes only. It cannot
create WorkerPreHelloAdmission, RootBootstrapAdmission or descriptor authority.
The fixed V3 producer must first validate its full earlier descriptor/limits.
"""
import os,fcntl,stat,hashlib
from .common import need
from .backend_linux_io import NativeIOCustody,DescriptorSlot


class HBootstrapMemfdPhysical(NativeIOCustody):
    def __init__(self,channel):
        from .backend_linux_channel import HNativeChannelOwner
        from .backend_native_reservations import NativeReservationLedger,NativeReservedMeter
        need(type(channel)is HNativeChannelOwner and channel.attempt.native_channel is channel and
             type(channel.reservation_ledger)is NativeReservationLedger and
             type(channel.meter)is NativeReservedMeter and channel.meter.slot is channel.reservation_ledger.control_arm,
             'actual original H channel and earlier prepaid arm control reservation')
        channel.attempt.require_live_original()
        need(getattr(channel,'bootstrap_carrier_physical',None)is None and not channel.poisoned,
             'one retained physical carrier, no retry or external issuer')
        self.channel=channel;self.handle=channel.attempt;self.meter=channel.meter
        self.slots=[];self.raw_first=None;self.raw_secondaries=[];self.last_time=None
        self.known_read=0;self.known_written=0;self.unknown_read=False;self.unknown_write=False
        self.raw_descriptor=None;self.digest=None;self.read_parts=[];self.raw_write_results=[]
        self.raw_seek=None;self.readback=None;self.eof=None;self.required_seals=None;self.seals_observed=[]
        self.memfd_slot=None;self.readonly_slot=None;self.alias199_slot=None;self.proc_slots=[]
        self.before_stat=None;self.readonly_stat=None;self.alias_stat=None;self.observed_parent_pid=None
        self.raw_stats=[];self.access_flags=[];self.fd_flags=[]
        self.entered=False;self.complete=False;self.close_entered=False;self.closed=False
        channel.bootstrap_carrier_physical=self

    def retain(self,error,site):
        if self.raw_first is None:self.raw_first=error
        elif error is not self.raw_first:self.raw_secondaries.append(error)
        self.channel.retain(error,'bootstrap_carrier_'+site)
    def now(self,deadline):return self.channel._now(deadline)
    def mark_unknown(self):self.handle.owner.parent.unknown.update(('read_bytes','write_bytes','work_units','retained_bytes'))
    def _slot(self,role):
        self.work();self.meter.charge('retained_bytes',512);return DescriptorSlot(self,role)
    def _close(self,slot):
        closed=slot.close()
        if slot.raw_first is not None:raise slot.raw_first
        need(closed,'known complete original carrier close; never retry uncertain occurrence')
    def _stat(self,slot):
        self.work();value=os.fstat(slot.fd);self.raw_stats.append((slot,value))
        need(stat.S_ISREG(value.st_mode)and value.st_nlink==0 and value.st_size==len(self.raw_descriptor),
             'actual anonymous exact-length memfd, not path-selected artifact')
        return value
    def _seals(self,slot):
        self.work();value=fcntl.fcntl(slot.fd,fcntl.F_GET_SEALS);self.seals_observed.append((slot,value))
        need(type(value)is int and value==self.required_seals,'exact immutable required seal set')
    def _readonly(self,slot,before):
        observed=self._stat(slot);self._seals(slot);self.work()
        flags=fcntl.fcntl(slot.fd,fcntl.F_GETFL);self.access_flags.append((slot,flags))
        need(flags&os.O_ACCMODE==os.O_RDONLY and
             (observed.st_dev,observed.st_ino,observed.st_size)==(before.st_dev,before.st_ino,before.st_size),
             'same original sealed inode through a distinct readonly file description')
        self.work();fd_flags=fcntl.fcntl(slot.fd,fcntl.F_GETFD);self.fd_flags.append((slot,fd_flags))
        need(fd_flags&fcntl.FD_CLOEXEC,'parent carrier occurrence stays close-on-exec until exact selected keep-set')
        return observed

    def prepare_bytes(self,raw,deadline):
        """Internal physical primitive; exact V3 descriptor validation is upstream.

        A successful return is not an admission handle or permission to Popen.
        The fixed source producer must impose all stricter profile/input/record
        bounds before calling; this structural ceiling adds no allowance.
        """
        need(not self.entered and not self.channel.poisoned,'one original physical carrier preparation')
        self.entered=True
        try:
            need(type(raw)is bytes and 0<len(raw)<=65536,'finite original canonical byte extent')
            self.now(deadline);self.meter.charge('retained_bytes',len(raw)*3+4096)
            self.work(len(raw)*64+4096);self.raw_descriptor=raw;self.digest=hashlib.sha256(raw).hexdigest()
            self.required_seals=fcntl.F_SEAL_WRITE|fcntl.F_SEAL_GROW|fcntl.F_SEAL_SHRINK|fcntl.F_SEAL_SEAL
            self.memfd_slot=self._slot('carrier_rw');s=self.memfd_slot;s.acquire_entered=True;self.work()
            try:s.fd=os.memfd_create('four-bootstrap-v3',os.MFD_CLOEXEC|os.MFD_ALLOW_SEALING)
            except BaseException as error:s.retain(error);raise
            offset=0
            while offset<len(raw):
                n=min(4096,len(raw)-offset);self.now(deadline);self.work();self.meter.charge('write_bytes',n)
                try:result=os.write(s.fd,raw[offset:offset+n])
                except BaseException:self.unknown_write=True;raise
                self.raw_write_results.append(result)
                if type(result)is int and result>=0:self.known_written+=result
                need(type(result)is int and result==n,'short/ambiguous carrier write cannot continue or replay')
                offset+=result
            self.work();self.raw_seek=os.lseek(s.fd,0,os.SEEK_SET);need(self.raw_seek==0,'actual original readback rewind')
            remaining=len(raw)
            while remaining:
                n=min(4096,remaining);self.now(deadline);self.work();self.meter.charge('read_bytes',n)
                try:part=os.read(s.fd,n)
                except BaseException:self.unknown_read=True;raise
                self.read_parts.append(part)
                if type(part)is bytes:self.known_read+=len(part)
                need(type(part)is bytes and len(part)==n,'complete bounded original carrier readback')
                remaining-=len(part)
            self.now(deadline);self.work();self.meter.charge('read_bytes',1)
            try:self.eof=os.read(s.fd,1)
            except BaseException:self.unknown_read=True;raise
            if type(self.eof)is bytes:self.known_read+=len(self.eof)
            need(self.eof==b'','separately admitted positive EOF probe, no hidden extra bytes')
            self.readback=b''.join(self.read_parts)
            need(self.readback==raw,'exact original complete carrier bytes before sealing')
            self.work();fcntl.fcntl(s.fd,fcntl.F_ADD_SEALS,self.required_seals)
            self._seals(s);self.before_stat=self._stat(s)
            # Only this exact owned occurrence may be reopened through own
            # proc-fd. No supplied Pin.path or general alias traversal exists.
            root=self._slot('proc');self.proc_slots.append(root);root.fixed_proc_root()
            self.work();self.observed_parent_pid=os.getpid()
            need(type(self.observed_parent_pid)is int and self.observed_parent_pid>0,'actual current original H PID')
            proc=self._slot('proc');self.proc_slots.append(proc)
            proc.openat(root.fd,str(self.observed_parent_pid),os.O_RDONLY|os.O_DIRECTORY|os.O_NONBLOCK)
            fds=self._slot('proc');self.proc_slots.append(fds)
            fds.openat(proc.fd,'fd',os.O_RDONLY|os.O_DIRECTORY|os.O_NONBLOCK)
            ro=self._slot('carrier_ro');self.readonly_slot=ro;ro.acquire_entered=True;self.work()
            try:ro.fd=os.open(str(s.fd),os.O_RDONLY|os.O_CLOEXEC,dir_fd=fds.fd)
            except BaseException as error:ro.retain(error);raise
            self.readonly_stat=self._readonly(ro,self.before_stat)
            self._close(s)  # No RW occurrence survives acquisition of alias199.
            for slot in reversed(self.proc_slots):self._close(slot)
            alias=self._slot('carrier_alias199');self.alias199_slot=alias;alias.acquire_entered=True;self.work()
            try:alias.fd=fcntl.fcntl(ro.fd,fcntl.F_DUPFD_CLOEXEC,199)
            except BaseException as error:alias.retain(error);raise
            need(type(alias.fd)is int and alias.fd==199 and alias.fd!=ro.fd,
                 'distinct exact199 alias; occupied199 is never closed or overwritten')
            self.alias_stat=self._readonly(alias,self.before_stat)
            self._close(ro);self.now(deadline);self.complete=True;return self
        except BaseException as error:self.retain(error,'prepare');raise

    def require_physical_complete(self):
        need(self.channel.bootstrap_carrier_physical is self and self.complete and self.raw_first is None and
             not self.close_entered and self.alias199_slot.fd==199 and not self.alias199_slot.close_entered,
             'actual live completed physical carrier only, not V3 source/native admission')
        return self
    def close_once(self):
        if self.close_entered:return self.closed
        self.close_entered=True;complete=True
        for slot in reversed(self.slots):
            try:complete=slot.close()and complete
            except BaseException as error:complete=False;self.retain(error,'close')
        self.closed=complete;return complete
