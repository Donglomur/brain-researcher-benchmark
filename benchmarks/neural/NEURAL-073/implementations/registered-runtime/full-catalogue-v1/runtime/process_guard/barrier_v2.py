"""Additive typed F snapshot lock; frozen original guard source stays unchanged.

Typed custody prevents accidental misuse inside the trusted host. It is not a
security boundary against arbitrary same-process Python or hostile host admins.
"""
from dataclasses import dataclass
import posixpath
import threading
import weakref
from ..core.custody import digest,require_digest
from .contracts import GuardError
from .linux import GuardContext,_read,_kv,_no_symlink_path

_SEAL=object()
_CAPS=weakref.WeakKeyDictionary()
_LEASES=weakref.WeakKeyDictionary()
_BINDINGS=weakref.WeakKeyDictionary()


def validate_snapshot_fields(*,snapshot_digest,program_manifest_digest,entry_digest,entry_relative_path,runtime_digest):
    for d in (snapshot_digest,program_manifest_digest,entry_digest,runtime_digest):require_digest(d)
    if (not isinstance(entry_relative_path,str) or not entry_relative_path or entry_relative_path.startswith('/')
        or posixpath.normpath(entry_relative_path)!=entry_relative_path or entry_relative_path in ('.','..')
        or entry_relative_path.startswith('../') or '\x00' in entry_relative_path):
        raise GuardError('canonical immutable program entry relative path required')
    return dict(snapshot_digest=snapshot_digest,program_manifest_digest=program_manifest_digest,
                entry_digest=entry_digest,entry_relative_path=entry_relative_path,runtime_digest=runtime_digest)


class SnapshotCapability:
    __slots__=('__weakref__',)
    def __init__(self,seal):
        if seal is not _SEAL:raise GuardError('only real owned guard freeze can issue snapshot capability')

    @property
    def context_id(self):
        if self not in _CAPS:raise GuardError('unregistered snapshot capability')
        return _CAPS[self]['guard'].a.context_id

    @property
    def barrier_receipt(self):
        if self not in _CAPS:raise GuardError('unregistered snapshot capability')
        # Canonical immutable-value copy, never expose the private registry record.
        import json
        return json.loads(json.dumps(_CAPS[self]['barrier']))


class SnapshotLease:
    __slots__=('__weakref__',)
    def __init__(self,seal):
        if seal is not _SEAL:raise GuardError('snapshot lease requires actual registered native barrier')

    def _record(self):
        record=_LEASES.get(self)
        if record is None:raise GuardError('unregistered or consumed snapshot lease')
        return record

    @property
    def opaque_context_id(self):return self._record()['guard'].a.context_id

    @property
    def context_digest(self):return digest(self.opaque_context_id)

    @property
    def runtime_manifest_digest(self):return self._record()['guard'].a.runtime_manifest_digest

    def require_drained(self):
        record=_LEASES.get(self)
        if record is None:raise GuardError('unregistered or consumed snapshot lease')
        guard=record['guard']
        with guard._snapshot_lock:
            if guard._snapshot_phase!='copying' or guard._snapshot_lease is not self:
                raise GuardError('snapshot lock is not active')
            guard._recheck_snapshot(record)
            return tuple(record['roots'])

    def complete(self,*,snapshot_digest,program_manifest_digest,entry_digest,entry_relative_path,runtime_digest):
        fields=validate_snapshot_fields(snapshot_digest=snapshot_digest,program_manifest_digest=program_manifest_digest,
            entry_digest=entry_digest,entry_relative_path=entry_relative_path,runtime_digest=runtime_digest)
        record=_LEASES.get(self)
        if record is None:raise GuardError('unregistered or consumed snapshot lease')
        guard=record['guard']
        with guard._snapshot_lock:
            self.require_drained()
            if runtime_digest!=guard.a.runtime_manifest_digest:raise GuardError('frozen runtime differs from actual guard admission')
            binding=FrozenSnapshotBinding(_SEAL)
            _BINDINGS[binding]={'guard':guard,'fields':fields,'barrier_digest':record['barrier']['receipt_digest']}
            guard._snapshot_binding=binding;guard._snapshot_phase='complete';del _LEASES[self]
            return binding

    def abort(self,reason):
        if not isinstance(reason,str) or not reason:raise GuardError('explicit snapshot incident required')
        record=_LEASES.get(self)
        if record is None:raise GuardError('unregistered or consumed snapshot lease')
        guard=record['guard']
        with guard._snapshot_lock:
            guard._snapshot_phase='failed';guard._snapshot_failure=reason;del _LEASES[self]


class FrozenSnapshotBinding:
    __slots__=('__weakref__',)
    def __init__(self,seal):
        if seal is not _SEAL:raise GuardError('only registered completed snapshot issues binding')

    def to_dict(self):
        record=_BINDINGS.get(self)
        if record is None:raise GuardError('unregistered frozen snapshot binding')
        return {'context_id':record['guard'].a.context_id,**record['fields'],
                'barrier_digest':record['barrier_digest']}


class GuardContextV2(GuardContext):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self._snapshot_lock=threading.RLock();self._snapshot_phase='none'
        self._snapshot_cap=None;self._snapshot_lease=None;self._snapshot_binding=None;self._snapshot_failure=None

    def freeze_barrier(self,*,authority):
        with self._snapshot_lock:
            if self._snapshot_phase!='none':raise GuardError('snapshot barrier is single-use')
            barrier=super().freeze_barrier(authority=authority)
            if self.a.arm!='F':return barrier
            # Only a successful real base barrier (authentic authority/native
            # owned cgroup drain) reaches this issuance path.
            roots=(str(self.root/'work'),str(self.root/'tmp'))
            root_identities=[]
            for path in roots:
                st=_no_symlink_path(path).stat();root_identities.append((st.st_dev,st.st_ino))
            capability=SnapshotCapability(_SEAL)
            _CAPS[capability]={'guard':self,'barrier':barrier,'cgroup_identity':self.identity,
                'roots':roots,'root_identities':tuple(root_identities)}
            self._snapshot_cap=capability;self._snapshot_phase='ready'
            return capability

    def _recheck_snapshot(self,record):
        self._authorize(self.authority,'candidate_author')
        self._owned()
        if record['guard'] is not self or self.identity!=record['cgroup_identity']:
            raise GuardError('snapshot guard/cgroup binding mismatch')
        if _kv(_read(self.cg/'cgroup.events'))['populated']!=0:
            raise GuardError('owned prequery tree is no longer drained')
        for path,identity in zip(record['roots'],record['root_identities']):
            st=_no_symlink_path(path).stat()
            if (st.st_dev,st.st_ino)!=identity:raise GuardError('snapshot root identity changed')

    def begin_snapshot(self,capability):
        with self._snapshot_lock:
            if not isinstance(capability,SnapshotCapability) or capability not in _CAPS:
                raise GuardError('actual registered snapshot capability required')
            record=_CAPS[capability]
            if record['guard'] is not self or self._snapshot_cap is not capability or self._snapshot_phase!='ready':
                raise GuardError('snapshot capability context/order mismatch')
            self._recheck_snapshot(record)
            lease=SnapshotLease(_SEAL);_LEASES[lease]=record
            self._snapshot_lease=lease;self._snapshot_phase='copying'
            return lease

    def run(self,*,authority,phase,mounts,argv,request_id):
        with self._snapshot_lock:
            if self.a.arm=='F' and self._snapshot_phase!='none':
                if self._snapshot_phase!='complete' or phase!='query':raise GuardError('all process launches locked until immutable snapshot completion')
                record=_BINDINGS.get(self._snapshot_binding)
                if record is None or record['guard'] is not self:raise GuardError('actual frozen snapshot binding missing')
                fields=record['fields']
                self._authorize(authority,'candidate_query',{k:v for k,v in fields.items() if k!='entry_relative_path'})
                programs=[m for m in mounts if m.role=='frozen_program']
                if len(programs)!=1 or programs[0].manifest_digest!=fields['program_manifest_digest']:
                    raise GuardError('query program differs from immutable snapshot manifest')
                entries=[p for p in programs[0].members if p.path==fields['entry_relative_path']]
                if len(entries)!=1 or entries[0].sha256!=fields['entry_digest'] or not argv or argv[0]!='/program/'+fields['entry_relative_path']:
                    raise GuardError('query entry differs from frozen executable')
            return super().run(authority=authority,phase=phase,mounts=mounts,argv=argv,request_id=request_id)
