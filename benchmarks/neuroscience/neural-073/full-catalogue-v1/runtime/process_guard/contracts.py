"""Pure assembly contracts; these objects neither grant authority nor touch files."""
from dataclasses import dataclass, asdict
import posixpath
import re
from ..core.custody import digest, require_digest
from ..core.resources import CandidateCaps


class GuardError(RuntimeError):
    pass


def absolute_path(value):
    if (not isinstance(value, str) or not value.startswith('/') or '\x00' in value
            or posixpath.normpath(value) != value or value == '/'):
        raise GuardError('canonical explicit absolute path required')
    return value


@dataclass(frozen=True)
class MemberPin:
    path: str
    bytes: int
    sha256: str
    mode: int

    def validate(self):
        if (not isinstance(self.path, str) or self.path.startswith('/') or not self.path
            or posixpath.normpath(self.path) != self.path or self.path in ('.','..')
            or self.path.startswith('../') or '\x00' in self.path):
            raise GuardError('canonical relative manifest path required')
        require_digest(self.sha256)
        if set(self.path.split('/')) & {'.git','.hg','.svn','.ssh','.aws','.codex'}:
            raise GuardError('private/repository control member forbidden in public/runtime export')
        if type(self.bytes) is not int or self.bytes < 0 or self.mode not in (0o444,0o555):
            raise GuardError('read-only regular file pin required')


@dataclass(frozen=True)
class PublicMount:
    role: str
    source: str
    destination: str
    members: tuple
    manifest_digest: str
    export_evidence_digest: str

    def validate(self):
        allowed = {'training':'/data/training','query':'/data/query','reference_tools':'/tools',
                   'knowledge':'/knowledge','frozen_program':'/program'}
        if self.role not in allowed or self.destination != allowed[self.role]:
            raise GuardError('only explicit public export mount roles are allowed')
        absolute_path(self.source)
        if self.source in ('/home','/Users','/root','/tmp','/var','/etc','/usr','/opt'):
            raise GuardError('broad host directory mount forbidden')
        if self.source.startswith(('/home/','/Users/','/root/')):
            raise GuardError('home-directory source mounts are forbidden')
        require_digest(self.manifest_digest); require_digest(self.export_evidence_digest)
        validate_members(self.members)
        if self.manifest_digest != digest([asdict(p) for p in self.members]):
            raise GuardError('public manifest digest mismatch')


def validate_members(members):
    if not isinstance(members, tuple) or not members:
        raise GuardError('explicit immutable complete member tuple required')
    for member in members:
        if not isinstance(member, MemberPin):
            raise GuardError('typed source pins required')
        member.validate()
    names = [p.path for p in members]
    if names != sorted(names) or len(set(names)) != len(names):
        raise GuardError('manifest must be sorted and unique')


@dataclass(frozen=True)
class GuardAdmission:
    context_id: str
    arm: str
    bwrap_path: str
    bwrap_bytes: int
    bwrap_sha256: str
    runtime_root: str
    runtime_members: tuple
    runtime_manifest_digest: str
    environment_evidence_digest: str
    control_source_digest: str
    export_allowlist_digest: str
    cgroup_parent: str
    cgroup_parent_mount_id: int
    scratch_mount: str
    scratch_mount_id: int
    scratch_device: str
    scratch_capacity_bytes: int
    scratch_exclusivity_evidence_digest: str
    cpus: tuple
    memory_nodes: tuple
    initial_phase_mounts: tuple

    def validate(self):
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', self.context_id) or self.arm not in ('F','I'):
            raise GuardError('opaque safe context token and arm required')
        for path in (self.bwrap_path,self.runtime_root,self.cgroup_parent,self.scratch_mount):
            absolute_path(path)
        if not self.cgroup_parent.startswith('/sys/fs/cgroup/'):
            raise GuardError('explicit delegated cgroup-v2 parent required')
        for value in (self.bwrap_sha256,self.runtime_manifest_digest,self.environment_evidence_digest,
                      self.control_source_digest,self.export_allowlist_digest,self.scratch_exclusivity_evidence_digest):
            require_digest(value)
        if type(self.bwrap_bytes) is not int or not 0 < self.bwrap_bytes <= 64*2**20:
            raise GuardError('bounded pinned bwrap executable required')
        validate_members(self.runtime_members)
        if self.runtime_manifest_digest != digest([asdict(p) for p in self.runtime_members]):
            raise GuardError('runtime manifest digest mismatch')
        for values, size in ((self.cpus,16),(self.memory_nodes,None)):
            if (not isinstance(values,tuple) or not values or values != tuple(sorted(set(values)))
                or any(type(v) is not int or v < 0 for v in values) or (size and len(values) != size)):
                raise GuardError('explicit unique sorted CPU16/NUMA bindings required')
        if (type(self.scratch_capacity_bytes) is not int or not 0 < self.scratch_capacity_bytes <= CandidateCaps().writable_bytes
            or any(type(v) is not int or v <= 0 for v in (self.scratch_mount_id,self.cgroup_parent_mount_id))
            or not re.fullmatch(r'\d+:\d+', self.scratch_device)):
            raise GuardError('dedicated hard-bounded scratch admission required')
        mounts = validate_mounts(self.initial_phase_mounts, phase='prequery', arm=self.arm)
        if digest([asdict(m) for m in mounts]) != self.export_allowlist_digest:
            raise GuardError('initial public allowlist binding mismatch')

    @property
    def binding_digest(self):
        return digest(asdict(self))


def validate_mounts(mounts, *, phase, arm):
    if phase not in ('prequery','query') or arm not in ('F','I') or not isinstance(mounts,tuple):
        raise GuardError('explicit phase/arm/mount tuple required')
    for mount in mounts:
        if not isinstance(mount,PublicMount):
            raise GuardError('typed public mount contract required')
        mount.validate()
    roles = [m.role for m in mounts]
    if len(set(roles)) != len(roles) or 'training' not in roles:
        raise GuardError('unique public roles and training export required')
    if phase == 'prequery' and ('query' in roles or 'frozen_program' in roles):
        raise GuardError('prequery cannot see query or a future frozen program')
    if phase == 'query' and 'query' not in roles:
        raise GuardError('complete query export required')
    if phase == 'query' and arm == 'F' and 'frozen_program' not in roles:
        raise GuardError('F query needs immutable frozen program export')
    return mounts


def assemble_argv(admission, mounts, *, phase, candidate_argv, work_directory):
    """Pure argv assembly only; callers must authenticate before any use/effects."""
    admission.validate(); validate_mounts(mounts,phase=phase,arm=admission.arm)
    absolute_path(work_directory)
    if (not isinstance(candidate_argv,(tuple,list)) or not candidate_argv
        or any(not isinstance(x,str) or '\x00' in x for x in candidate_argv)
        or not candidate_argv[0].startswith('/')):
        raise GuardError('explicit absolute in-sandbox argv, without host shell interpolation, required')
    if phase == 'query' and admission.arm == 'F' and not candidate_argv[0].startswith('/program/'):
        raise GuardError('F query executable must be the immutable frozen program')
    args=[admission.bwrap_path,'--unshare-all','--die-with-parent','--new-session',
          '--cap-drop','ALL','--disable-userns','--assert-userns-disabled','--clearenv',
          '--ro-bind',admission.runtime_root,'/','--proc','/proc','--remount-ro','/proc',
          '--bind',work_directory,'/work','--bind',posixpath.dirname(work_directory)+'/tmp','/tmp','--chdir','/work',
          '--setenv','PATH','/usr/bin:/bin','--setenv','HOME','/work',
          '--setenv','TMPDIR','/tmp','--setenv','LANG','C.UTF-8']
    # The authenticated launcher additionally restores oom_score_adj=0, drops
    # inheritable/permitted/effective/ambient capabilities and reads no_new_privs
    # before exec. These argv flags independently constrain the candidate runtime.
    # Only standard character devices; no host /dev tree, GPU, sockets or cgroupfs.
    for device in ('null','zero','random','urandom'):
        args += ['--ro-bind','/dev/'+device,'/dev/'+device]
    for mount in mounts:
        args += ['--ro-bind',mount.source,mount.destination]
    return args+['--']+list(candidate_argv)


def cgroup_limits(admission):
    admission.validate(); caps=CandidateCaps()
    return {'cpuset.mems':','.join(map(str,admission.memory_nodes)),
            'cpuset.cpus':','.join(map(str,admission.cpus)),
            'cpu.max':f'{caps.simultaneous_cores*100000} 100000',
            'memory.max':str(caps.private_rss_bytes),'memory.swap.max':'0','memory.oom.group':'1'}
