"""V3 source-owned native artifact observation under an actual earlier grant.

No native work occurs at import. These are concrete syscall consumers, not a
native authority issuer or per-operation CPU/RSS qualification. The original H
must already enforce the selected physical envelope and approve the full grant.
"""
import os
import stat
import hashlib
from pathlib import PurePosixPath
from .common import need
from .worker_meter_v3 import WorkerEffectAttempt
from .worker_channel_v3 import require_capture

_ROLES=('server_executable','model_gguf','template','tokenizer_source','renderer_source')
_FIELDS=('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns','st_mode','st_nlink','st_uid')

def artifact_requirements_v3(size,descriptors,extent):
    """Exact conservative requested-size schedule; logical units, not CPU/RSS.

    A short read may return one byte after requesting min(65536, remaining).
    Both requested allocation and requested-size work must cover every such
    attempt. No native qualifier or authority is issued by this arithmetic.
    """
    need(type(size)is int and size>=0 and type(descriptors)is int and descriptors>=1 and
         type(extent)is int and extent>=0,'finite exact source extents')
    requested=(size*(size+1)//2 if size<=65536 else
               65536*(size-65536)+65536*65537//2)
    return {'read_bytes':size,'write_bytes':0,'process_starts':0,
            'work_units':128*extent+8192+4097*size+4096*(8*descriptors+64)+requested,
            'retained_bytes':32*extent+8192+32*size+requested+8192*descriptors+131072+65536}

class WorkerDescriptorSlotV3:
    """Registered before acquisition; one relinquishment even after failure."""
    def __init__(self,io,attempt,role):
        self.io=io;self.attempt=attempt;self.role=role;self.ordinal=len(io.slots)
        self.fd=None;self.entered=False;self.close_entered=False;self.closed=False
        self.raw_first=None;self.secondaries=[];self.unknown=False;self.identity=None
        io.slots.append(self);attempt.slots.append(self)
    def retain(self,error):
        if self.raw_first is None:self.raw_first=error
        elif error is not self.raw_first:self.secondaries.append(error)
        self.unknown=True;self.attempt.retain(error,'descriptor_'+self.role)
    def close_once(self):
        if self.close_entered:return self.closed
        self.close_entered=True;fd=self.fd;self.fd=None
        try:
            if fd is not None:os.close(fd)
            elif self.entered:self.unknown=True;return False
            self.closed=True;return True
        except BaseException as error:self.retain(error);return False

class ArtifactReadV3:
    def __init__(self,io,role,effect,prior):
        self.io=io;self.role=role;self.effect=effect;self.prior=prior;self.slots=[]
        self.selected=None;self.relative_components=None;self.absolute_components=None
        self.root=None;self.file=None;self.file_stat=None;self.parent_ordinal=None
        self.count=0;self.digest=None;self.last_read=None;self.observed_ns=None
        self.raw_first=None;self.secondaries=[];self.unknown_read=False
        self.work_used=0;self.retained_used=0;self.requirements=None
        self.close_entered=False;self.closed=False;self.complete=False
        io.attempts.append(self);io.owner.artifact_attempts[role]=self
    def retain(self,error,site):
        if self.raw_first is None:self.raw_first=error
        elif error is not self.raw_first:self.secondaries.append((site,error))
        self.io.retain(error,site)
    def debit(self,work=0,retained=0):
        need(type(work)is int and work>=0 and type(retained)is int and retained>=0,
             'fixed nonnegative logical operation accounting')
        self.work_used+=work;self.retained_used+=retained
        need(self.work_used<=self.effect.maximum['work_units'] and
             self.retained_used<=self.effect.maximum['retained_bytes'],
             'original full granted work/copy accounting, no fresh allowance')
    def close_once(self):
        if self.close_entered:return self.closed
        self.close_entered=True;ok=True
        for slot in reversed(self.slots):ok=slot.close_once() and ok
        self.closed=ok
        return ok

class WorkerNativeIOV3:
    """Distinct V3 owner; never an EarlyResources or .charge compatibility shim."""
    def __init__(self,owner):
        from .worker_backend_v3 import WorkerBackendOwnerV3
        need(type(owner)is WorkerBackendOwnerV3 and owner.context.backend is owner and
             owner.base is not None and owner.io is None,'same actual prepared V3 owner')
        self.owner=owner;self.context=owner.context;self.meter=owner.meter
        self.slots=[];self.attempts=[];self.raw_first=None;self.secondaries=[]
        self.close_entered=False;self.closed=False
    def retain(self,error,site):
        if self.raw_first is None:self.raw_first=error
        elif error is not self.raw_first:self.secondaries.append((site,error))
        self.owner.retain(error,'native_'+site)
    def _now(self,attempt):
        attempt.debit(work=1,retained=32)
        return self.context.channel.endpoint.now(attempt.effect.deadline)
    def _open(self,attempt,parent,name,directory):
        slot=WorkerDescriptorSlotV3(self,attempt,'directory' if directory else 'artifact')
        attempt.debit(work=4096,retained=8192);slot.entered=True
        try:
            flags=os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC|os.O_NONBLOCK
            if directory:flags|=os.O_DIRECTORY
            if parent is None:
                need(name=='/','only fixed initial root anchor')
                slot.fd=os.open('/',flags)
            else:
                need(type(parent)is WorkerDescriptorSlotV3 and parent.io is self and
                     parent.fd is not None and not parent.close_entered and
                     type(name)is str and name not in ('','.','..') and '/'not in name and '\0'not in name,
                     'actual retained parent and selected one-component child')
                slot.fd=os.open(name,flags,dir_fd=parent.fd)
            # Retain the returned fd before any fstat/name or deadline check.
            slot.identity=os.fstat(slot.fd)
            need(stat.S_ISDIR(slot.identity.st_mode) if directory else stat.S_ISREG(slot.identity.st_mode),
                 'actual expected opened type; no FIFO or symlink body read')
            if parent is not None:
                named=os.stat(name,dir_fd=parent.fd,follow_symlinks=False)
                need(all(getattr(named,k)==getattr(slot.identity,k) for k in _FIELDS),
                     'same actual named/opened inode before any read')
            self._now(attempt);return slot
        except BaseException as error:slot.retain(error);raise
    def _read(self,attempt,n):
        need(type(n)is int and 0<n<=65536 and attempt.count+n<=attempt.selected['bytes'],
             'positive bounded complete selected extent; no extra EOF probe')
        attempt.debit(work=4096+n,retained=n)
        try:raw=os.read(attempt.file.fd,n)
        except BaseException as error:
            attempt.unknown_read=True;attempt.retain(error,'read_unknown');raise
        attempt.last_read=raw
        if type(raw)is bytes:attempt.count+=len(raw)
        attempt.effect.acknowledge_read(raw)
        need(type(raw)is bytes and 0<len(raw)<=n,'actual positive original regular-file prefix')
        return raw
    def read_selected_artifact_v3(self,role,effect,prior):
        need(role in _ROLES and type(effect)is WorkerEffectAttempt and effect.meter is self.meter and
             self.meter.current_effect is effect and not self.close_entered,
             'fixed actual artifact consumer with current original grant')
        attempt=ArtifactReadV3(self,role,effect,prior);primary=None
        try:
            need(effect.site=='artifact_read' and effect.stage=='initialization' and
                 not effect.entered and effect.grant is not None and
                 len(prior)==len(effect.prior_captures)==3 and all(x is y for x,y in zip(effect.prior_captures,prior)),
                 'exact complete original artifact effect operands')
            extent=sum(len(c.raw) for c in prior)
            metadata_work=extent*128+8192;metadata_retained=extent*32+8192
            need(effect.maximum['work_units']>=metadata_work and effect.maximum['retained_bytes']>=metadata_retained and
                 effect.maximum['write_bytes']==0 and effect.maximum['process_starts']==0 and
                 effect.maximum['cpu_ns']>0 and effect.maximum['wall_ns']>0,
                 'complete initial metadata allocation and original physical grant before decode')
            effect.enter();attempt.debit(work=metadata_work,retained=metadata_retained)
            require_capture(prior[0],self.context,'BackendAttemptBase')
            require_capture(prior[1],self.context,'NativeArtifactRootSelectionV1')
            require_capture(prior[2],self.context,'NativeRootObservationV1')
            need(prior[0] is self.owner.base and prior[1] is self.context.bootstrap('NativeArtifactRootSelectionV1') and
                 any(prior[2] is r for r in self.owner.admission.roots),'same real earlier original owners')
            selection=prior[1].body;root=prior[2].body
            rows=[r for r in selection['roles'] if r['role']==role]
            need(len(rows)==1 and rows[0]['root_id']==root['root_id'] and root['readonly'] is True and
                 root['source_admission']==self.context.context_identity['source_admission'] and
                 root['root_policy']==selection['root_policy'],'exact original selected readonly root/role/source')
            row=rows[0];attempt.selected=dict(row['selected']);attempt.relative_components=tuple(row['relative_components'])
            absolute=root['absolute_mount'];path=PurePosixPath(absolute)
            need(type(absolute)is str and absolute.startswith('/') and str(path)==absolute and
                 all(c not in ('','.','..') for c in path.parts[1:]) and len(absolute)<=4096,
                 'literal original canonical absolute mount, no caller path or alias')
            attempt.absolute_components=tuple(path.parts[1:]);components=attempt.relative_components
            need(1<=len(components)<=64 and all(type(c)is str and 0<len(c)<=255 and c not in ('.','..') and
                 '/'not in c and '\0'not in c for c in components),'entire original safe relative component route')
            size=attempt.selected['bytes'];need(type(size)is int and size>=0,'complete selected ordinary artifact extent')
            # One-byte short reads are the worst-case progress schedule. Full
            # source bounds cover every such read plus anchored metadata/FDs.
            # Work/copy figures are logical source units, not observed CPU/RSS.
            descriptors=1+len(attempt.absolute_components)+len(components)
            required=artifact_requirements_v3(size,descriptors,extent)
            attempt.requirements=required
            need(all(effect.maximum[k]>=v for k,v in required.items()),
                 'whole read/short-read work/copy/descriptor requirements before first syscall')
            parent=self._open(attempt,None,'/',True)
            for component in attempt.absolute_components:parent=self._open(attempt,parent,component,True)
            attempt.root=parent;s=parent.identity;expected=root['identity']
            need(stat.S_ISDIR(s.st_mode) and (s.st_dev,s.st_ino,s.st_mode,s.st_uid)==
                 (expected['device'],expected['inode'],expected['mode'],expected['uid']),
                 'actual opened root equals earlier admitted literal root OS identity')
            attempt.debit(work=4096);v=os.fstatvfs(parent.fd)
            need(v.f_flag&os.ST_RDONLY,'actual root filesystem readonly observation')
            for component in components[:-1]:
                parent=self._open(attempt,parent,component,True)
                need(parent.identity.st_dev==s.st_dev,'no unselected mount crossing within artifact root')
            attempt.parent_ordinal=parent.ordinal
            attempt.file=self._open(attempt,parent,components[-1],False);before=attempt.file.identity
            need(before.st_dev==s.st_dev and before.st_size==size and before.st_nlink==1 and
                 stat.S_IMODE(before.st_mode)&0o222==0,'whole exact immutable regular artifact before body read')
            digest=hashlib.sha256()
            while attempt.count<size:
                raw=self._read(attempt,min(65536,size-attempt.count));digest.update(raw);self._now(attempt)
            attempt.debit(work=8192,retained=1024)
            after=os.fstat(attempt.file.fd);named=os.stat(components[-1],dir_fd=parent.fd,follow_symlinks=False)
            need(all(getattr(before,k)==getattr(after,k)==getattr(named,k) for k in _FIELDS),
                 'same complete opened and named immutable artifact after full read')
            root_after=os.fstat(attempt.root.fd)
            need((root_after.st_dev,root_after.st_ino,root_after.st_mode,root_after.st_uid)==
                 (s.st_dev,s.st_ino,s.st_mode,s.st_uid) and os.fstatvfs(attempt.root.fd).f_flag&os.ST_RDONLY,
                 'same actual readonly selected root after full original byte observation')
            attempt.digest=digest.hexdigest();attempt.file_stat=after
            need(attempt.count==size and attempt.digest==attempt.selected['sha256'],
                 'full original byte extent and hash, no prefix success')
            attempt.observed_ns=self._now(attempt)
        except BaseException as error:primary=error;attempt.retain(error,'artifact_read')
        finally:
            if not attempt.close_once():
                # close_once already retains an actual first close exception.
                # Preserve its identity at both effect.fail and raise; invent a
                # fallback only when closure is unknown without a raw error.
                error=attempt.raw_first
                if error is None:error=RuntimeError('original artifact descriptor closure unknown')
                if primary is None:primary=error
                attempt.retain(error,'close_unknown')
            if self.meter.current_effect is effect and effect.grant is not None and not effect.reported:
                try:
                    if primary is not None:
                        unknown=[]
                        if attempt.unknown_read:unknown.append('read_bytes')
                        if not attempt.closed:unknown.append('retained_bytes')
                        effect.fail(primary,tuple(unknown))
                    else:effect.finish()
                    self.meter.observe_effect(effect)
                except BaseException as error:
                    if primary is None:primary=error
                    attempt.retain(error,'effect_observation')
        if primary is not None:raise primary
        need(effect.reported and attempt.closed,'actual final acknowledged effect and all descriptor closes')
        attempt.complete=True;return attempt
    def close_all_once_v3(self):
        # Cleanup ownership is unconditional; no new clock, grant or context
        # check may suppress closure of an actual returned descriptor.
        if self.close_entered:return self.closed
        self.close_entered=True;ok=True
        for slot in reversed(self.slots):ok=slot.close_once() and ok
        self.closed=ok;return ok
