"""Actual bounded HM native observations under one original resource owner.

Inactive source. Neither metadata nor these classes creates external isolation,
provisioning or scientific qualification. No effect occurs on import.
"""
import ctypes
import errno
import fcntl
import os
import stat
import struct
import sys
import time
from pathlib import Path
from .common import need, closed, integer, encode, parse, pin, failure
from .roots import BoundRoots
from .observer import HostObserver, StorageObservation, KernelGroup, HMOwnExitAccountingV1
from .identity import process_identity
from . import dependencies

FORMAT_CAP = 1048576
BLKGETSIZE64_LP64 = 0x80081272


def retain(owner, error, site):
    """Raw first survives a failing secondary retention path."""
    if owner.raw_first is None:owner.raw_first = error
    elif error is not owner.raw_first:owner.secondaries.append((error, site))
    parent = getattr(owner, 'campaign', None)
    if parent is not None and parent is not owner:
        try:parent.retain(error, site)
        except BaseException as later:
            if later is not owner.raw_first:owner.secondaries.append((later, site + ':retention'))


def exact_wrapper(value):
    closed(value, ('descriptor', 'body'))
    d = value['descriptor'];closed(d, ('path', 'bytes', 'sha256'))
    raw = encode(value['body'])
    need(len(raw) <= FORMAT_CAP and pin(raw) == {k:d[k] for k in ('bytes','sha256')},
         'exact complete canonical metadata wrapper')
    return raw


class HMNativeConfigurationV1:
    def __init__(self, campaign, roots):
        self.campaign = campaign;self.raw_first = None;self.secondaries = []
        self.raw = None;self.body = None;self.provisioning = None;self.complete = False
        campaign.configuration = self  # before source reads
        try:
            need(type(roots) is BoundRoots and roots.meter is campaign.reservations.host_share,
                 'actual original H source/configuration roots and Share')
            self.roots = roots;self.descriptor = campaign.plan.body['native_configuration']
            need('path' in self.descriptor and self.descriptor['bytes'] <= FORMAT_CAP,
                 'actual finite native configuration source descriptor')
            self.raw = roots.read(self.descriptor, self.descriptor['bytes'], metadata=True)
            self.body = parse(self.raw, FORMAT_CAP)
            need(encode(self.body) == self.raw, 'canonical native configuration')
            b = self.body
            closed(b, ('schema','source_manifest','observer_source','worker_source','environment',
                'launch_policy','group_parent','selected_host_qualification','storage_provisioning','worker_bootstrap'))
            need(b['schema'] == 'hm_whole_native_configuration_v1', 'distinct closed native source configuration')
            for k in ('source_manifest','observer_source','worker_source','environment','launch_policy'):
                need(b[k] == campaign.plan.body[k], 'same selected native ' + k)
            need(b['storage_provisioning'] == campaign.plan.body['storage'] and
                 'path' in b['storage_provisioning'], 'same original fixed-volume provisioning descriptor')
            qualification = b['selected_host_qualification']
            closed(qualification, ('environment','observer_source','source_manifest','fixed_volume_provisioning'))
            need(qualification == {'environment':b['environment'], 'observer_source':b['observer_source'],
                 'source_manifest':b['source_manifest'],'fixed_volume_provisioning':b['storage_provisioning']},
                 'independent host binding includes exact volume/custody selection')
            dependencies.require('root_observer_host_clock_environment', qualification)
            pd = b['storage_provisioning'];need(pd['bytes'] <= FORMAT_CAP, 'finite complete provisioning source')
            pr = roots.read(pd, pd['bytes'], metadata=True);self.provisioning_raw = pr
            self.provisioning = parse(pr, FORMAT_CAP)
            need(encode(self.provisioning) == pr, 'canonical exact provisioning source')
            p = self.provisioning
            closed(p, ('schema','environment','observer_source','mountpoint','filesystem_id',
                'filesystem_device','filesystem_inode','block_device','block_device_rdev',
                'backend_capacity_bytes','whole_group_identity','custody_authority','provisioning_authority',
                'writer_scope','resize_policy','accounting'))
            need(p['schema'] == 'hm_exclusive_fixed_block_volume_v1' and
                 p['environment'] == b['environment'] and p['observer_source'] == b['observer_source'] and
                 p['writer_scope'] == 'original_whole_campaign_only' and
                 p['resize_policy'] == 'immutable_provisioned_backend' and
                 p['accounting'] == 'allocated_physical_blocks_with_filesystem_metadata',
                 'selected concrete provisioned exclusive fixed-volume variant')
            for k in ('custody_authority','provisioning_authority'):
                closed(p[k], ('path','bytes','sha256'));integer(p[k]['bytes'],1)
                # Full bodies are required by the independent binding, and are
                # authenticated here as evidence. They do not grant themselves.
                roots.read(p[k], p[k]['bytes'], metadata=True)
            for k in ('filesystem_id','filesystem_device','filesystem_inode','block_device_rdev','backend_capacity_bytes'):
                integer(p[k],1)
            for key in ('mountpoint','block_device'):
                path=Path(p[key]);need(path.is_absolute() and '..' not in path.parts and
                    str(path)==p[key], 'exact preselected native absolute path')
            need(type(campaign.host) is HostObserver and type(campaign.host.whole_group) is KernelGroup and
                 type(campaign.host.storage) is StorageObservation,
                 'actual existing whole-group/storage observation owners')
            need(tuple(p['whole_group_identity']) == campaign.host.whole_group.identity and
                 Path(p['mountpoint']) == campaign.host.storage.path,
                 'actual original enclosing group and exclusive volume selection')
            parent=Path(b['group_parent']);whole=campaign.host.whole_group.path
            need(parent.is_absolute() and parent.is_relative_to(whole) and
                 '..' not in parent.parts, 'fresh W groups inside original whole domain')
            self.complete = True
        except BaseException as error:
            retain(self,error,'native_configuration');raise self.raw_first

    def require_original(self):
        need(self.campaign.configuration is self and self.complete and self.raw_first is None and
             encode(self.body) == self.raw and encode(self.provisioning) == self.provisioning_raw,
             'same original immutable native configuration and provisioning source')
        self.campaign.plan.require_original();return self


class HMFixedVolumeCustodyV1:
    """Actual selected backing-device capacity; statvfs is usage/cross-check only."""
    def __init__(self,campaign):
        self.campaign=campaign;self.fd=None;self.open_entered=False;self.close_entered=False
        self.closed=False;self.raw_first=None;self.secondaries=[];self.samples=[];self.identity=None
        campaign.volume=self

    def open_once(self):
        need(not self.open_entered,'one original volume-open attempt');self.open_entered=True
        try:
            c=self.campaign.configuration.require_original();p=c.provisioning
            need(sys.platform=='linux' and ctypes.sizeof(ctypes.c_void_p)==8,
                 'selected Linux LP64 block ioctl ABI')
            self.campaign.meter.check();self.campaign.meter.charge('read_bytes',4096)
            self.fd=os.open(p['block_device'],os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC)
            s=os.fstat(self.fd);self.identity=(s.st_dev,s.st_ino,s.st_rdev)
            need(stat.S_ISBLK(s.st_mode) and s.st_rdev==p['block_device_rdev'],
                 'actual exact selected filesystem backing block device, not its parent device')
            return self.sample()
        except BaseException as error:retain(self,error,'volume_open');raise self.raw_first

    def sample(self):
        row={'capacity_bytes':None,'allocated_bytes':None,'retained_delta_bytes':None,'observed_ns':None}
        self.samples.append(row)
        try:
            p=self.campaign.configuration.require_original().provisioning;storage=self.campaign.host.storage
            need(self.fd is not None and not self.close_entered,'actual retained volume descriptor')
            self.campaign.meter.check();self.campaign.meter.charge('read_bytes',4096)
            s=os.fstat(self.fd);named=os.stat(p['block_device'],follow_symlinks=False)
            need((s.st_dev,s.st_ino,s.st_rdev)==self.identity==
                 (named.st_dev,named.st_ino,named.st_rdev),'same original native capacity owner')
            fs=os.fstat(storage.fd)
            need((fs.st_dev,fs.st_ino)==(p['filesystem_device'],p['filesystem_inode'])==storage.identity and
                 fs.st_dev==s.st_rdev,'actual mounted filesystem is on this exact selected block device')
            raw=fcntl.ioctl(self.fd,BLKGETSIZE64_LP64,b'\0'*8)
            need(type(raw)is bytes and len(raw)==8,'complete actual block capacity return')
            row['capacity_bytes']=struct.unpack('=Q',raw)[0]
            need(row['capacity_bytes']==p['backend_capacity_bytes'],
                 'actual provisioned backend capacity remains unchanged')
            v=os.fstatvfs(storage.fd)
            need(v.f_fsid==p['filesystem_id']==storage.filesystem_id and
                 v.f_blocks*v.f_frsize<=row['capacity_bytes'],'same volume, finite filesystem allocation domain')
            row['allocated_bytes']=(v.f_blocks-v.f_bfree)*v.f_frsize
            row['retained_delta_bytes']=storage.observe()
            need(row['allocated_bytes']>=storage.baseline and
                 row['capacity_bytes']-storage.baseline<=
                 self.campaign.plan.resource_plan['hard_envelope']['retained_storage_bytes'],
                 'fixed actual backend contains unchanged whole retained-storage opportunity')
            row['observed_ns']=time.monotonic_ns();return row
        except BaseException as error:retain(self,error,'volume_sample');raise self.raw_first

    def close_once(self):
        if self.close_entered:return self.closed
        self.close_entered=True;fd,self.fd=self.fd,None
        try:
            if fd is not None:os.close(fd)
            self.closed=True;return True
        except BaseException as error:retain(self,error,'volume_close');return False


class HMContinuousProcessClocksV1:
    """Real H/C process clocks; child-tree and whole observations stay distinct."""
    def __init__(self,campaign):
        self.campaign=campaign;self.raw_first=None;self.secondaries=[];self.pidfds={}
        self.open_attempts=[];self.samples=[];self.clockids={};self.close_entered=False;self.closed=False
        self.begin=None;self.final=None;self.last_C_live_cpu_ns=0;campaign.clocks=self

    def start_once(self):
        need(self.begin is None and not self.open_attempts,'one original continuous-clock start')
        try:
            identities={'H':self.campaign.controller.host_identity,'C':self.campaign.controller.controller_identity}
            need(identities['H']['pid']==os.getpid() and identities['H']!=identities['C'],
                 'actual distinct original H/C processes')
            self.identities=identities
            libc=ctypes.CDLL(None,use_errno=True);getclock=libc.clock_getcpuclockid
            getclock.argtypes=(ctypes.c_int,ctypes.POINTER(ctypes.c_int));getclock.restype=ctypes.c_int
            self.libc=libc;self.getclock=getclock
            for name,identity in identities.items():
                self.open_attempts.append(name)
                if name=='C':
                    owner=self._controller_exit_owner()
                    if owner.capture_if_exited()is not None:
                        self.clockids[name]=None;continue
                else:self.pidfds[name]=os.pidfd_open(identity['pid'],0)
                out=ctypes.c_int();code=getclock(identity['pid'],ctypes.byref(out))
                if code:
                    original=OSError(code,'actual process CPU clock lookup')
                    if name=='C' and code==errno.ESRCH:
                        try:
                            if owner.capture_if_exited()is not None:
                                self.clockids[name]=None;continue
                        except BaseException as later:self.secondaries.append((later,'C_initial_exit_race_resolution'))
                    raise original
                self.clockids[name]=out.value
            self.begin=self.sample();return self.begin
        except BaseException as error:retain(self,error,'process_clock_start');raise self.raw_first

    def _controller_exit_owner(self):
        owner=getattr(self.campaign,'controller_exit_owner',None)
        need(type(owner)is HMOwnExitAccountingV1 and owner.role=='C' and
             owner.running is self.campaign.controller.controller_process and
             owner.observer is self.campaign.host and owner.identity==self.identities['C'],
             'actual retained original C process exit observer, never a supplied CPU receipt')
        owner.require_original();return owner

    def _controller_cpu(self,row):
        owner=self._controller_exit_owner();identity=self.identities['C']
        if owner.capture_if_exited()is not None:
            row['C_cpu_source']='observer_owned_exit_upper_bound'
            return owner.require_final(self.last_C_live_cpu_ns)
        try:
            value=time.clock_gettime_ns(self.clockids['C']);integer(value)
            actual=process_identity(identity['pid'],launch_nonce=identity['launch_nonce'],source=identity['source'],
                parent_launch=identity['parent_launch'],mapping=self.campaign.host.mapping,meter=self.campaign.meter)
            need(actual==identity,'same actual live C identity at its CPU sample')
        except OSError as original:
            if original.errno not in (errno.ESRCH,errno.ENOENT,errno.EINVAL):raise
            # An actual exit can occur between the nonreaping poll and clock or
            # /proc read. Only the same retained producer may establish it.
            try:
                final=owner.capture_if_exited()
                if final is not None:
                    row['C_cpu_source']='observer_owned_exit_upper_bound'
                    return owner.require_final(self.last_C_live_cpu_ns)
            except BaseException as later:self.secondaries.append((later,'C_exit_race_resolution'))
            raise original
        self.last_C_live_cpu_ns=max(self.last_C_live_cpu_ns,value)
        row['C_cpu_source']='live_process_clock';return value

    def sample(self):
        row={'monotonic_before_ns':None,'H_cpu_ns':None,'C_cpu_ns':None,'monotonic_after_ns':None,
             'C_cpu_source':None}
        self.samples.append(row);first=None
        for name,call in (('monotonic_before_ns',time.monotonic_ns),
            ('H_cpu_ns',lambda:time.clock_gettime_ns(self.clockids['H'])),
            ('C_cpu_ns',lambda:self._controller_cpu(row)),
            ('monotonic_after_ns',time.monotonic_ns)):
            try:row[name]=call();integer(row[name])
            except BaseException as error:
                if first is None:first=error
                retain(self,error,'process_clock_sample:'+name)
        if first is not None:raise self.raw_first
        for name,identity in self.identities.items():
            if name=='C':continue  # validated live or by its actual retained terminal producer above
            actual=process_identity(identity['pid'],launch_nonce=identity['launch_nonce'],source=identity['source'],
                parent_launch=identity['parent_launch'],mapping=self.campaign.host.mapping,meter=self.campaign.meter)
            need(actual==identity,'same actual live process identity for continuous '+name+' clock')
        if self.begin is not None:
            need(all(row[k]>=self.begin[k] for k in ('monotonic_before_ns','H_cpu_ns','C_cpu_ns','monotonic_after_ns')),
                 'nondecreasing complete process-clock prefix')
        return row

    def deltas(self,row):
        need(self.begin is not None,'actual continuous start')
        # Process clocks include earlier native configuration/bootstrap work.
        # Subtracting the first late sample would silently erase it.
        # The independent whole cgroup remains a separate overlapping counter.
        return {'H_own_cpu_ns':row['H_cpu_ns'],
                'C_own_cpu_ns':row['C_cpu_ns'],
                'C_cpu_source':row['C_cpu_source'],
                'wall_ns':row['monotonic_after_ns']-self.campaign.plan.origin_ns,
                'CPU_scope':'complete observed H/C process lifetimes through this sample',
                'before_first_sample_CPU_removed':False,
                'worker_subgroup_cpu_added':False,'whole_group_cpu_added':False}

    def close_once(self):
        if self.close_entered:return self.closed
        self.close_entered=True;all_closed=True
        for name in ('H','C'):
            fd=self.pidfds.pop(name,None)
            try:
                if fd is not None:os.close(fd)
            except BaseException as error:all_closed=False;retain(self,error,'process_pidfd_close:'+name)
        self.closed=all_closed;return all_closed


class HMStageChannelMeterV1:
    """Actual H endpoint costs charged once to the original H Share."""
    def __init__(self,stage):
        self.stage=stage;self.parent=stage.campaign.meter;self.deadline_ns=stage.allocation.deadline_ns
        self.cleanup_errors=[];self.raw_first=None
    def check(self):
        self.parent.check();need(time.monotonic_ns()<self.deadline_ns,'original complete stage channel cutoff')
        self.stage.poll_once()
    def charge(self,kind,n):self.check();return self.parent.charge(kind,n)
    def own_error(self,error,dimension=None):
        if self.raw_first is None:self.raw_first=error
        self.stage.retain(error,dimension or 'channel');self.parent.own_error(error,dimension)
