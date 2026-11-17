"""Fixed Linux inherited carrier observations before worker protocol activation.

No caller supplies a descriptor, FD, H object, OS provider or authority token.
This physical owner never mints WorkerPreHelloAdmissionV3: the fixed installed
entry must additionally prove its actual source/native inheritance provenance.
Its successful return is retained evidence for that issuer, not permission to
run participant code. There are no native operations at module import.
"""
import os
import fcntl
import stat
import socket
import struct
import select
import time
import hashlib
from .common import need, same, integer
from .backend_json import canonical, parse
from .backend_native_v3_codec import validate_native_type

_ENTRY=object()
_original_import=None
# Full independently installed expectation verification and one repeated live
# check before endpoint handoff. These are required original debits, not grants.
from .worker_installed_expectation_data import MAXIMUM_EXPECTATION_BYTES
INSTALLED_EXPECTATION_WORK_BOUND=3*(MAXIMUM_EXPECTATION_BYTES*128+4096)
INSTALLED_EXPECTATION_RETAINED_BOUND=3*(MAXIMUM_EXPECTATION_BYTES*16+4096)
_NAMESPACES=('mnt','pid','net','user','ipc','uts','cgroup')
# A fixed preparse schedule, NOT a grant. The actual H launcher must reserve
# this whole prefix from its existing original control share before exec.
# Body extents cannot increase it. A smaller original share refuses launch.
INITIAL_READ_BOUND=65537+129+2*8193+7*256+12
INITIAL_RETAINED_BOUND=10*65536+2*8192+32768
INITIAL_WORK_BOUND=64*INITIAL_RETAINED_BOUND
INITIAL_MAXIMUM_FDS=12
INITIAL_WORK_BOUND += INSTALLED_EXPECTATION_WORK_BOUND
INITIAL_RETAINED_BOUND += INSTALLED_EXPECTATION_RETAINED_BOUND


def _parse_parent_stat_v3(raw,expected_pid):
    """Exact pure parse_proc_stat projection from the selected Linux observer.

    Kept local so the pre-Hello import does not load backend/server owners.
    The original source/body pin is preserved by the handoff's derivation map.
    """
    need(type(raw)is bytes and len(raw)<=8192,'bounded original proc stat bytes')
    start=raw.find(b'(');end=raw.rfind(b')')
    need(start>0 and end>start and int(raw[:start].strip())==expected_pid,'actual proc PID owner')
    fields=raw[end+2:].split();need(len(fields)>=20,'complete process start/parent/group fields')
    parent=int(fields[1]);group=int(fields[2]);session=int(fields[3]);ticks=int(fields[19])
    for n in (expected_pid,parent,group,session,ticks):integer(n)
    return {'pid':expected_pid,'parent_pid':parent,'process_group':group,'session':session,
            'start_ticks':ticks,'state':fields[0].decode('ascii')}


class WorkerInheritedSlotV3:
    def __init__(self,owner,role,fd=None):
        self.owner=owner;self.role=role;self.fd=fd;self.socket=None
        self.entered=fd is not None;self.close_entered=False;self.closed=False
        self.raw_first=None;self.unknown=False
        owner.slots.append(self)
    def close_once(self):
        if self.close_entered:return self.closed
        self.close_entered=True;fd,sock=self.fd,self.socket;self.fd=None;self.socket=None
        try:
            if sock is not None:sock.close()
            elif fd is not None:os.close(fd)
            elif self.entered:self.unknown=True;return False
            self.closed=True;return True
        except BaseException as error:
            self.raw_first=error;self.unknown=True;self.owner.retain(error,'close_'+self.role);return False


class WorkerBootstrapPhysicalV3:
    """One entry-local original physical occurrence, not a decoded capability."""
    def __init__(self,token):
        need(token is _ENTRY,'fixed private entry-local physical constructor')
        self.slots=[];self.raw_first=None;self.secondaries=[];self.unknowns=set()
        self.entered=False;self.complete=False;self.closed=False;self.close_entered=False
        self.carrier=WorkerInheritedSlotV3(self,'inherited199',199)
        self.channel=WorkerInheritedSlotV3(self,'inherited198',198)
        self.pidfd=None;self.proc=None;self.parent_proc=None;self.proc_children=[]
        self.raw_results=[];self.raw_parts=[];self.raw_descriptor=None;self.descriptor=None
        self.eof=None;self.raw_clock=None;self.last_time=None;self.clock_observations=[]
        self.stat_before=None;self.stat_after=None
        self.digest=None;self.observed_parent_pid=None;self.observed_worker_pid=None
        self.parent_stats=[];self.parent_namespace=None;self.peer_credentials=None
        self.original_clock_ticks=None;self.raw_boot=None;self.boot=None;self.parent_identity=None
        self.read_reserved=0;self.read_observed=0;self.work_used=0;self.retained_used=0
        self.protocol=None;self.source_qualified=False;self.prehello_admission=None

    def retain(self,error,site):
        if self.raw_first is None:self.raw_first=error
        elif error is not self.raw_first:self.secondaries.append(error)
        self.unknowns.add(site)

    def _work(self,n=4096):
        need(type(n)is int and n>=0 and self.work_used+n<=INITIAL_WORK_BOUND,
             'whole fixed initial work schedule, no parse-selected allowance')
        self.work_used+=n

    def _retain_bound(self,n):
        need(type(n)is int and n>=0 and self.retained_used+n<=INITIAL_RETAINED_BOUND,
             'whole retained original bootstrap prefix bound')
        self.retained_used+=n

    def _read_bound(self,n):
        need(type(n)is int and n>0 and self.read_reserved+n<=INITIAL_READ_BOUND,
             'positive initial read admitted before syscall')
        self.read_reserved+=n;self._retain_bound(n);self._work()

    def _slot(self,role):
        need(len(self.slots)<INITIAL_MAXIMUM_FDS,'finite original initial descriptor occurrence census')
        self._work();self._retain_bound(512);return WorkerInheritedSlotV3(self,role)

    def _clock(self):
        self._work();self.raw_clock=time.monotonic_ns();self.clock_observations.append(self.raw_clock)
        now=self.raw_clock
        need(type(now)is int and now>=0 and (self.last_time is None or now>=self.last_time),
             'actual nondecreasing initial clock, never renewed')
        self.last_time=now
        if self.descriptor is not None:
            d=self.descriptor;s=d['start_body']
            need(s['original_S_ns']<=now<=d['prehello_deadline_ns'],
                 'carrier/import consumes original S/J, never evidence deadline extension')
        return now

    def _observe(self,kind,value):
        # Caller assigns each actual syscall result here before validation.
        self.raw_results.append((kind,value));return value

    def _read_exact(self,slot,n):
        out=[];remaining=n
        while remaining:
            size=min(4096,remaining);self._read_bound(size)
            try:raw=os.read(slot.fd,size)
            except BaseException:self.unknowns.add('read_prefix');raise
            self._observe('read_'+slot.role,raw);out.append(raw)
            if type(raw)is bytes:self.read_observed+=len(raw)
            need(type(raw)is bytes and len(raw)==size,'exact sealed byte extent, no short-read continuation')
            remaining-=len(raw)
        self._read_bound(1)
        try:eof=os.read(slot.fd,1)
        except BaseException:self.unknowns.add('read_eof');raise
        self._observe('eof_'+slot.role,eof)
        if type(eof)is bytes:self.read_observed+=len(eof)
        need(eof==b'','separately admitted positive EOF; no hidden suffix')
        self.eof=eof;return b''.join(out)

    def _read_kernel(self,parent,name,maximum):
        slot=self._slot('proc_'+name);first=None
        try:
            slot.entered=True
            slot.fd=os.open(name,os.O_RDONLY|os.O_CLOEXEC|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=parent.fd)
            observed=self._observe('stat_'+slot.role,os.fstat(slot.fd))
            need(stat.S_ISREG(observed.st_mode),'actual fixed kernel metadata file')
            # One bounded read and an independently prepaid positive EOF.
            # A kernel short prefix with more data refuses; no new reservation
            # or unbounded retry turns it into an apparently complete census.
            self._read_bound(maximum)
            try:raw=os.read(slot.fd,maximum)
            except BaseException:self.unknowns.add('read_'+name);raise
            self._observe('read_'+slot.role,raw)
            if type(raw)is bytes:self.read_observed+=len(raw)
            need(type(raw)is bytes and len(raw)<=maximum,'actual bounded kernel read prefix')
            self._read_bound(1)
            try:eof=os.read(slot.fd,1)
            except BaseException:self.unknowns.add('eof_'+name);raise
            self._observe('eof_'+slot.role,eof)
            if type(eof)is bytes:self.read_observed+=len(eof)
            need(eof==b'','positive kernel EOF, no truncated or hidden suffix')
            return raw
        except BaseException as error:first=error;self.retain(error,'kernel_'+name);raise
        finally:
            closed=slot.close_once()
            if first is None:
                if slot.raw_first is not None:raise slot.raw_first
                need(closed,'known complete original kernel metadata close')

    def _open_directory(self,parent,name,role):
        slot=self._slot(role);slot.entered=True
        if parent is None:
            need(name=='/proc','only fixed original proc root')
            slot.fd=os.open(name,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
        else:
            need(type(name)is str and name not in ('','.','..') and '/'not in name,'fixed one-component proc path')
            slot.fd=os.open(name,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=parent.fd)
        observed=self._observe('stat_'+role,os.fstat(slot.fd))
        need(stat.S_ISDIR(observed.st_mode),'actual opened kernel directory');return slot

    def _descriptor_joins(self):
        d=self.descriptor;s=d['start_body'];r=d['reservation_body'];c=d['context']
        for kind,body,ref in [('WorkerStartObservationV1',s,d['start_observation']),
                              ('ChannelBudgetReservationV1',r,d['reservation'])]:
            raw=canonical(body,65536)
            need(len(raw)==ref['bytes'] and hashlib.sha256(raw).hexdigest()==ref['sha256'],
                 'delivered earlier actual body must match its completed original Pin')
        need(c['original_attempt']==s['original_attempt'] and c['condition']==s['condition']==r['condition'] and
             d['host']==s['host'] and d['boot_id']==d['host']['boot_id'] and
             d['context_policy']==r['context_policy'] and
             d['clock_mapping_source']==s['clock_mapping']==r['original_clock_mapping'] and
             s['owner_binding']==r['original_owner_binding'] and s['schedule']==r['schedule'] and
             s['E_ns']==r['original_evidence_deadline_ns'],
             'same original context/start/owner/reservation/clock/schedule')
        need(s['original_S_ns']<s['J_ns']<=s['G_ns']<s['R_ns']<=s['E_ns'] and
             s['R_ns']==s['original_S_ns']+s['schedule']['duration_ns'] and
             d['prehello_deadline_ns']==min(s['J_ns'],s['R_ns']) and
             s['schedule']['earliest_launch_ns']<=s['original_S_ns']<=s['schedule']['latest_launch_ns'] and
             s['R_ns']<=s['schedule']['common_cutoff_ns'],
             'exact earlier original time domain, not a new import deadline')
        need(self.clock_observations and all(s['original_S_ns']<=t<=d['prehello_deadline_ns']
                                             for t in self.clock_observations),
             'already observed preparse work also belongs to the actual earlier S/J interval')
        a=r['arm_reserved']
        need(a['read_bytes']>=INITIAL_READ_BOUND and a['retained_bytes']>=INITIAL_RETAINED_BOUND and
             a['work_units']>=INITIAL_WORK_BOUND and 0<r['packet_limit']<=65536 and
             0<r['maximum_sequences']<=4096 and 0<len(self.raw_descriptor)<=r['logical_record_limit'],
             'original H must already have reserved the complete fixed initial prefix')

    def _parent_poll(self):
        self._work();value=self._observe('parent_pidfd_poll',select.select([self.pidfd.fd],[],[self.pidfd.fd],0))
        need(value==([],[],[]),'actual original parent is live, not PID reuse')

    def _parent_start(self):
        self._parent_poll();raw=self._read_kernel(self.parent_proc,'stat',8192)
        fields=_parse_parent_stat_v3(raw,self.observed_parent_pid);self.parent_stats.append(fields)
        d=self.descriptor
        start=fields['start_ticks']*1000000000//d['clock_ticks']+d['tick_to_monotonic_offset_ns']
        need(fields['state']not in ('Z','X','x') and start==d['host']['start_monotonic_ns'],
             'actual original live parent start/boot under same qualified tick mapping')
        self._parent_poll()

    def observe_inherited_v3(self):
        need(not self.entered,'one original fixed worker import, including failed attempts');self.entered=True
        try:
            self._clock();self._work()
            self.stat_before=self._observe('carrier_stat_before',os.fstat(199))
            a=self.stat_before
            need(stat.S_ISREG(a.st_mode) and a.st_nlink==0 and 0<a.st_size<=65536,
                 'actual anonymous bounded inherited carrier inode')
            seals=fcntl.F_SEAL_WRITE|fcntl.F_SEAL_GROW|fcntl.F_SEAL_SHRINK|fcntl.F_SEAL_SEAL
            need(self._observe('carrier_seals',fcntl.fcntl(199,fcntl.F_GET_SEALS))==seals,
                 'exact immutable Linux seal set')
            access=self._observe('carrier_access',fcntl.fcntl(199,fcntl.F_GETFL))
            need(access&os.O_ACCMODE==os.O_RDONLY,'actual readonly inherited file description')
            offset=self._observe('carrier_offset',os.lseek(199,0,os.SEEK_CUR))
            need(offset==0,'original readonly reopen starts at zero; never rewind supplied carrier')
            self.raw_descriptor=self._read_exact(self.carrier,a.st_size)
            self.raw_parts=[self.raw_descriptor];self._retain_bound(len(self.raw_descriptor)*8)
            self._work(len(self.raw_descriptor)*64)
            self.digest=hashlib.sha256(self.raw_descriptor).hexdigest()
            self.descriptor=parse(self.raw_descriptor,65536,maximum_depth=64,
                                  maximum_members=65536,maximum_string_bytes=65536)
            validate_native_type('WorkerPreHelloDescriptorV3',self.descriptor)
            need(canonical(self.descriptor,65536)==self.raw_descriptor,'exact complete canonical inherited bytes')
            self._descriptor_joins();self._clock()
            self.stat_after=self._observe('carrier_stat_after',os.fstat(199))
            need(all(getattr(a,k)==getattr(self.stat_after,k)for k in
                     ('st_dev','st_ino','st_mode','st_size','st_nlink')),'same original sealed carrier throughout')
            self.observed_parent_pid=self._observe('getppid',os.getppid())
            self.observed_worker_pid=self._observe('getpid',os.getpid())
            d=self.descriptor
            need(self.observed_parent_pid==d['host']['pid'] and
                 type(self.observed_worker_pid)is int and self.observed_worker_pid>0 and
                 self.observed_worker_pid!=self.observed_parent_pid,'actual parent and distinct worker observations')
            self.pidfd=self._slot('parent_pidfd');self.pidfd.entered=True
            self.pidfd.fd=os.pidfd_open(self.observed_parent_pid,0);self._parent_poll()
            self.proc=self._open_directory(None,'/proc','proc_root')
            self.parent_proc=self._open_directory(self.proc,str(self.observed_parent_pid),'parent_proc')
            parent=self.proc
            for name in ('sys','kernel','random'):
                parent=self._open_directory(parent,name,'proc_'+name);self.proc_children.append(parent)
            self.raw_boot=self._read_kernel(parent,'boot_id',128);self.boot=self.raw_boot.decode('ascii').strip()
            self.original_clock_ticks=self._observe('clock_ticks',os.sysconf('SC_CLK_TCK'))
            need(self.boot==d['boot_id'] and self.original_clock_ticks==d['clock_ticks'],
                 'actual Linux boot and original tick domain')
            self._parent_start();namespace={'schema':'four_namespace_identity_v1'}
            for name in _NAMESPACES:
                self._read_bound(256);raw=self._observe('parent_ns_'+name,os.readlink('ns/'+name,dir_fd=self.parent_proc.fd))
                need(type(raw)is str and len(raw)<=255 and raw.startswith(name+':[') and raw.endswith(']'),
                     'fixed actual original parent namespace link')
                namespace[name]=raw
            self.parent_namespace=namespace
            need(same(namespace,d['host_namespace']),'actual original parent namespaces, not worker assertion')
            observed=self._observe('channel_stat',os.fstat(198));need(stat.S_ISSOCK(observed.st_mode),'actual inherited channel socket')
            # Ownership of FD198 already exists even if wrapping it raises.
            self.channel.socket=socket.socket(fileno=198)
            sock=self.channel.socket
            need(sock.family==socket.AF_UNIX and sock.getsockopt(socket.SOL_SOCKET,socket.SO_TYPE)==socket.SOCK_SEQPACKET,
                 'exact inherited private Unix seqpacket endpoint')
            self._read_bound(12);raw=self._observe('channel_peer',sock.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,12))
            need(type(raw)is bytes and len(raw)==12,'actual complete original peer credential')
            self.peer_credentials=struct.unpack('3i',raw)
            parent_stat=self._observe('parent_proc_user',os.fstat(self.parent_proc.fd))
            need(self.peer_credentials[0]==self.observed_parent_pid and self.peer_credentials[1]==parent_stat.st_uid and
                 self.peer_credentials[2]>=0,'same actual original parent peer and user')
            sock.setblocking(False);sock.setsockopt(socket.SOL_SOCKET,socket.SO_PASSCRED,1)
            self._work();flags=self._observe('channel_fd_flags',fcntl.fcntl(198,fcntl.F_GETFD))
            fcntl.fcntl(198,fcntl.F_SETFD,flags|fcntl.FD_CLOEXEC)
            verified=self._observe('channel_fd_flags_verified',fcntl.fcntl(198,fcntl.F_GETFD))
            need(verified&fcntl.FD_CLOEXEC,'worker endpoint cannot leak into descendants')
            self._parent_start()
            # Close199 once before the final fallible clock. No later code may
            # retry its integer, even if close released it and then raised.
            closed=self.carrier.close_once()
            if self.carrier.raw_first is not None:raise self.carrier.raw_first
            need(closed,'known original inherited199 closure')
            self._clock();self.complete=True;return self
        except BaseException as error:self.retain(error,'import');raise

    def require_physical_complete_v3(self):
        need(_original_import is self and self.complete and self.raw_first is None and
             self.carrier.closed and not self.close_entered and self.channel.fd==198,
             'same original completed physical import; not source/native admission')
        return self

    def close_all_once(self):
        if self.close_entered:return self.closed
        self.close_entered=True;complete=True
        for slot in reversed(self.slots):complete=slot.close_once()and complete
        self.closed=complete;return complete


def observe_fixed_worker_bootstrap_v3():
    """Fixed entry physical observation only. No admitted proxy is returned."""
    global _original_import
    need(_original_import is None,'one entry-local singleton, no original import retry')
    _original_import=WorkerBootstrapPhysicalV3(_ENTRY)
    try:return _original_import.observe_inherited_v3()
    except BaseException:
        _original_import.close_all_once()
        raise
