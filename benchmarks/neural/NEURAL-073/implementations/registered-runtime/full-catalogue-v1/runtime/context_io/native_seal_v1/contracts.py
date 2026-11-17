"""Explicit future native seal admission. No namespace or mount effects here."""
from dataclasses import dataclass,asdict
import posixpath
from ...core.custody import EvidencePin,digest,require_digest
from ...process_guard.contracts import PublicMount,validate_members
from ..capsules import CapsuleReceipt
from ..snapshot import SnapshotReceipt
from ..filesystem import ContextIOError,IOLimits,absolute_path,token


@dataclass(frozen=True)
class MountAPIContract:
    """External qualification contract, not a claimed installed util-linux version.

    No qualified mount implementation/source closure is currently held. A future
    root selection must authenticate these exact evidence bodies before native
    activation. An evidence hash alone is never a source/API qualification.
    """
    executable: str
    executable_bytes: int
    executable_sha256: str
    implementation_version: str
    source_api_closure: EvidencePin
    native_command_controls: EvidencePin

    def validate(self):
        absolute_path(self.executable);require_digest(self.executable_sha256)
        if self.executable.startswith(('/Users/','/home/','/root/')):raise ContextIOError('mount executable must be admitted immutable runtime, not a home file')
        if type(self.executable_bytes) is not int or not 0<self.executable_bytes<=67108864:
            raise ContextIOError('bounded explicit mount executable pin required')
        if not isinstance(self.implementation_version,str) or not self.implementation_version:
            raise ContextIOError('actual qualified implementation version required')
        for evidence,kind in ((self.source_api_closure,'mount_source_api_closure'),(self.native_command_controls,'mount_native_command_controls')):
            if type(evidence) is not EvidencePin or evidence.kind!=kind:raise ContextIOError('exact external mount evidence kind required')
        # These exact arguments must be supported by the qualified implementation.
        # This source neither discovers a version nor guesses qualification.

    @property
    def fingerprint(self):
        self.validate();return digest(asdict(self))


@dataclass(frozen=True)
class SealAdmission:
    namespace_device: int
    namespace_inode: int
    host_reference_pid: int
    host_namespace_device: int
    host_namespace_inode: int
    namespace_qualification: EvidencePin
    expected_euid: int
    target_parent: str
    target_parent_device: int
    target_parent_inode: int
    target_parent_mount_id: int
    target_name: str
    mount_api: MountAPIContract
    limits: IOLimits
    source_closure_digest: str
    timeout_seconds: int=20
    output_bytes_per_stream: int=8192
    mountinfo_byte_cap: int=4194304

    def validate(self):
        for value in (self.namespace_device,self.namespace_inode,self.host_reference_pid,
                      self.host_namespace_device,self.host_namespace_inode,
                      self.target_parent_device,self.target_parent_inode,self.target_parent_mount_id):
            if type(value) is not int or value<=0:raise ContextIOError('exact positive namespace/target identity required')
        if (self.namespace_device,self.namespace_inode)==(self.host_namespace_device,self.host_namespace_inode):
            raise ContextIOError('host/global namespace is never a sealing target')
        if type(self.expected_euid) is not int or self.expected_euid<0:raise ContextIOError('explicit uid required')
        if type(self.namespace_qualification) is not EvidencePin or self.namespace_qualification.kind!='private_mount_namespace_native_qualification':
            raise ContextIOError('external private namespace/native qualification required')
        absolute_path(self.target_parent);token(self.target_name)
        if self.target_parent.startswith(('/Users/','/home/','/root/')):raise ContextIOError('native target cannot be a home path')
        if type(self.mount_api) is not MountAPIContract or type(self.limits) is not IOLimits:
            raise ContextIOError('concrete mount and I/O contracts required')
        self.mount_api.validate();self.limits.validate();require_digest(self.source_closure_digest)
        if (self.timeout_seconds!=20 or self.output_bytes_per_stream!=8192 or self.mountinfo_byte_cap!=4194304):
            raise ContextIOError('changing native transport ceilings needs a reviewed successor')

    @property
    def fingerprint(self):
        self.validate();return digest(asdict(self))


@dataclass(frozen=True)
class SealSource:
    role: str
    source: str
    destination: str
    members: tuple
    manifest_digest: str
    receipt_digest: str



@dataclass(frozen=True)
class ToolTreeReceipt:
    """Private trusted receipt for the concrete projected reference-tool tree.

    This does not certify fit validity by itself; exact fit/tool/source projection
    evidence must be authenticated and joined by the owner before signing.
    """
    mount: PublicMount
    context_digest: str
    fit_evidence_digest: str
    tool_projection_evidence_digest: str
    source_projection_evidence_digest: str
    domain: str = 'authentic'

    def validate(self):
        if type(self.mount) is not PublicMount or self.mount.role!='reference_tools' or self.mount.destination!='/tools':
            raise ContextIOError('only the concrete full reference_tools mount is accepted')
        self.mount.validate()
        if self.domain!='authentic':raise ContextIOError('invented tool tree cannot enter native sealing')
        for value in (self.context_digest,self.fit_evidence_digest,
                      self.tool_projection_evidence_digest,self.source_projection_evidence_digest):
            require_digest(value)

    def to_dict(self):
        self.validate()
        return {'schema':'n073-reference-tool-tree-receipt-v1',**asdict(self)}

    @property
    def receipt_digest(self):return digest(self.to_dict())


def sources_for(receipt):
    if type(receipt) is CapsuleReceipt:
        if receipt.domain!='authentic':raise ContextIOError('invented capsule cannot enter native sealing')
        folders={'knowledge':'common','training':'training','query':'query'}
        if tuple(r for r,unused in receipt.role_members)!=('knowledge','training','query'):
            raise ContextIOError('exact full capsule role order required')
        result=tuple(SealSource(role,receipt.root+'/'+folders[role],
            {'knowledge':'/knowledge','training':'/data/training','query':'/data/query'}[role],
            members,digest([asdict(m) for m in members]),receipt.receipt_digest)
            for role,members in receipt.role_members)
    elif type(receipt) is ToolTreeReceipt:
        receipt.validate();mount=receipt.mount
        result=(SealSource('reference_tools',mount.source,'/tools',mount.members,
                          mount.manifest_digest,receipt.receipt_digest),)
    elif type(receipt) is SnapshotReceipt:
        result=(SealSource('frozen_program',receipt.root,'/program',receipt.members,
                          receipt.program_manifest_digest,receipt.receipt_digest),)
        entries=[m for m in receipt.members if m.path==receipt.entry_relative_path]
        if len(entries)!=1 or entries[0].sha256!=receipt.entry_digest or entries[0].mode!=0o555:
            raise ContextIOError('snapshot entry/manifest identity mismatch')
    else:raise ContextIOError('actual typed capsule, snapshot or reference-tool receipt required')
    for source in result:
        absolute_path(source.source);validate_members(source.members)
        # Validate source role/path/member contract without asserting read-only
        # backing-mount readiness. Real home paths correctly fail here.
        PublicMount(source.role,source.source,source.destination,source.members,
                    source.manifest_digest,source.receipt_digest).validate()
    return result


def seal_bindings(receipt,admission):
    if type(admission) is not SealAdmission:raise ContextIOError('typed native seal admission required')
    admission.validate();sources=sources_for(receipt)
    target=admission.target_parent+'/'+admission.target_name
    for source in sources:
        if (source.source==target or source.source.startswith(target+'/') or target.startswith(source.source+'/')):
            raise ContextIOError('native seal source/target overlap')
    return {'source_receipt_digest':receipt.receipt_digest,
            'seal_admission_digest':admission.fingerprint,
            'seal_sources_digest':digest([asdict(s) for s in sources]),
            'native_seal_source_digest':admission.source_closure_digest,
            'namespace_qualification_digest':admission.namespace_qualification.sha256,
            'mount_api_closure_digest':admission.mount_api.source_api_closure.sha256,
            'mount_native_controls_digest':admission.mount_api.native_command_controls.sha256}


def mount_commands(admission,source,target):
    admission.validate();absolute_path(source);absolute_path(target)
    # --internal-only prohibits helper execution; --no-mtab prohibits incidental
    # mtab writes; --no-canonicalize keeps the already verified literal paths.
    base=(admission.mount_api.executable,'--internal-only','--no-mtab','--no-canonicalize')
    return (base+('--bind','--',source,target),
            base+('-o','remount,bind,ro,nosuid,nodev','--',source,target))


def parse_private_mountinfo(text):
    """Strict bounded kernel-format parser with propagation fields preserved."""
    if not isinstance(text,str) or len(text.encode('utf-8'))>4194304:
        raise ContextIOError('bounded kernel mountinfo text required')
    entries=[];ids=set()
    def unescape(v):
        for a,b in (('\\040',' '),('\\011','\t'),('\\012','\n'),('\\134','\\')):v=v.replace(a,b)
        return v
    for line in text.splitlines():
        f=line.split()
        if f.count('-')!=1:raise ContextIOError('invalid kernel mount separator')
        k=f.index('-')
        if k<6 or len(f)!=k+4 or len(entries)>=50000:raise ContextIOError('invalid bounded kernel mount record')
        try:mid,parent=int(f[0]),int(f[1]);major,minor=(int(x) for x in f[2].split(':'))
        except (ValueError,TypeError):raise ContextIOError('invalid kernel mount identity') from None
        if mid<=0 or parent<0 or major<0 or minor<0 or mid in ids:raise ContextIOError('duplicate/invalid mount ID')
        optional=f[6:k]
        if any(x.startswith(('shared:','master:','propagate_from:')) for x in optional):
            raise ContextIOError('namespace has shared/slave propagation; sealing forbidden')
        if any(x!='unbindable' for x in optional):raise ContextIOError('unqualified mount propagation field')
        root,path=unescape(f[3]),unescape(f[4])
        if not root.startswith('/') or not path.startswith('/') or posixpath.normpath(root)!=root or posixpath.normpath(path)!=path:
            raise ContextIOError('noncanonical kernel mount root/path')
        opts=f[5].split(',')
        if ('ro' in opts)==('rw' in opts):raise ContextIOError('ambiguous kernel mount read-only state')
        entries.append({'id':mid,'parent':parent,'device':f[2],'root':root,'path':path,
            'options':tuple(opts),'optional':tuple(optional),'fstype':f[k+1],
            'source':unescape(f[k+2]),'super_options':tuple(f[k+3].split(','))})
        ids.add(mid)
    if not entries:raise ContextIOError('empty mount table')
    return tuple(entries)


def covering_mount(entries,path):
    absolute_path(path)
    choices=[m for m in entries if path==m['path'] or path.startswith(m['path'].rstrip('/')+'/')]
    if not choices:raise ContextIOError('no covering mount')
    depth=max(len(m['path']) for m in choices);best=[m for m in choices if len(m['path'])==depth]
    if len(best)!=1:raise ContextIOError('stacked/ambiguous covering mounts')
    return best[0]


def verify_bound_mount(entries,*,source_before,source_path,target,previous_ids,require_ro):
    actual=[m for m in entries if m['path']==target]
    if len(actual)!=1:raise ContextIOError('expected exactly one exclusive bind mount')
    bound=actual[0];suffix=posixpath.relpath(source_path,source_before['path'])
    expected_root=posixpath.normpath(posixpath.join(source_before['root'],suffix))
    if (bound['id'] in previous_ids or bound['device']!=source_before['device']
        or bound['root']!=expected_root or bound['fstype']!=source_before['fstype']):
        raise ContextIOError('bind mount source/device/root lineage mismatch')
    if any(m['path'].startswith(target+'/') for m in entries):raise ContextIOError('nested target mounts forbidden')
    if require_ro and (not {'ro','nosuid','nodev'}<=set(bound['options']) or 'rw' in bound['options']):
        raise ContextIOError('kernel did not report exact readonly/nosuid/nodev seal')
    return bound
