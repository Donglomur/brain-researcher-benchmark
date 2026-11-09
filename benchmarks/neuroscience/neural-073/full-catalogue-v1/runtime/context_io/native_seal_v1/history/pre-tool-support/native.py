"""Concrete future private-namespace bind/remount, never activated on import."""
from dataclasses import dataclass,asdict
import base64
import hashlib
import os
import posixpath
import selectors
import signal
import stat
import subprocess
import sys
import time
from ...core.custody import VerifiedAuthority,digest
from ...process_guard.contracts import PublicMount
from ..capsules import CapsuleReceipt
from ..filesystem import (ContextIOError,IOCounter,TreeWriter,inventory,open_absolute_dir,
                          open_relative_dir,root_still_named,identity,revision,require_regular)
from .contracts import (SealAdmission,sources_for,seal_bindings,mount_commands,
                        parse_private_mountinfo,covering_mount,verify_bound_mount)


class NativeSealFailure(ContextIOError):
    """Original one-attempt command and partial-mount evidence; never success."""
    def __init__(self,original,evidence):
        self.evidence=evidence
        super().__init__('native sealing failed: '+type(original).__name__+': '+str(original))


@dataclass(frozen=True)
class SealedPublicExports:
    mounts: tuple
    evidence_bytes: bytes

    @property
    def evidence_digest(self):return hashlib.sha256(self.evidence_bytes).hexdigest()

    def to_dict(self):
        import json
        return {'evidence':json.loads(self.evidence_bytes),
                'evidence_digest':self.evidence_digest,'mounts':[asdict(m) for m in self.mounts]}


class NativeSealSession:
    """One invocation, authenticated before inspection or filesystem effects.

    Constructor/pure contracts do not certify a native environment. activate()
    requires concrete observed namespace/capability/private mount state and all
    externally qualified evidence selected by the root authentic authority.
    """
    def __init__(self,receipt,admission,*,authority):
        if type(admission) is not SealAdmission or type(authority) is not VerifiedAuthority:
            raise ContextIOError('typed admission and verified authentic sealing authority required')
        self.bindings=seal_bindings(receipt,admission)
        role='export' if type(receipt) is CapsuleReceipt else 'candidate_author'
        self.authority_digest=authority.require(role=role,domain='authentic',bindings=self.bindings)
        self.a=admission;self.receipt=receipt;self.sources=sources_for(receipt)
        if (sum(len(s.members) for s in self.sources)>admission.limits.max_files
            or sum(m.bytes for s in self.sources for m in s.members)>admission.limits.max_total_bytes):
            raise ContextIOError('complete native source closure exceeds explicit seal capacity')
        self.state='authorized';self.work=IOCounter();self.commands=[];self.observations=[]
        self.control_bytes_read=0;self.executable_bytes_read=0;self.nsfd=None;self.mountfd=None
        self.parentfd=None;self.targetfd=None;self.target=admission.target_parent+'/'+admission.target_name
        self.initial_namespace=None

    def _read_control(self,path,limit):
        # Only literal proc control paths are passed by this implementation.
        fd=os.open(path,os.O_RDONLY|os.O_CLOEXEC|os.O_NOFOLLOW)
        try:
            parts=[];n=0
            while True:
                b=os.read(fd,min(65536,limit+1-n));self.control_bytes_read+=len(b)
                if not b:break
                n+=len(b)
                if n>limit:raise ContextIOError('bounded native control read overflow')
                parts.append(b)
            return b''.join(parts).decode('utf-8')
        finally:os.close(fd)

    def _mounts(self):
        return parse_private_mountinfo(self._read_control('/proc/self/mountinfo',self.a.mountinfo_byte_cap))

    def _namespace(self):
        if sys.platform!='linux':raise ContextIOError('native sealing requires separately qualified Linux')
        if os.geteuid()!=self.a.expected_euid:raise ContextIOError('native uid changed')
        # Namespace handles are the intentional kernel namespace symlinks, not
        # arbitrary file paths. Their opened inode identities are authoritative.
        fd=os.open('/proc/self/ns/mnt',os.O_RDONLY|os.O_CLOEXEC)
        host=os.open('/proc/'+str(self.a.host_reference_pid)+'/ns/mnt',os.O_RDONLY|os.O_CLOEXEC)
        try:
            current=identity(os.fstat(fd));reference=identity(os.fstat(host))
            if current!=(self.a.namespace_device,self.a.namespace_inode) or reference!=(self.a.host_namespace_device,self.a.host_namespace_inode) or current==reference:
                raise ContextIOError('actual private/host namespace identity mismatch')
            if self.nsfd is not None and current!=identity(os.fstat(self.nsfd)):
                raise ContextIOError('namespace changed since activation')
            self.initial_namespace=current
        finally:os.close(fd);os.close(host)
        # A dedicated single-thread trusted worker prevents another local thread
        # from mutating this namespace between checks. External exclusivity and
        # source-writer quiescence remain signed native-qualification obligations.
        threads=[]
        with os.scandir('/proc/self/task') as scan:
            for ent in scan:
                threads.append(ent.name)
                if len(threads)>1:raise ContextIOError('native sealing requires dedicated single-thread worker')
        if len(threads)!=1:raise ContextIOError('native task identity missing')
        status=self._read_control('/proc/self/status',16384)
        fields=[line.split(':',1)[1].strip() for line in status.splitlines() if line.startswith('CapEff:')]
        if len(fields)!=1 or not (int(fields[0],16)&(1<<21)):
            raise ContextIOError('actual CAP_SYS_ADMIN missing in admitted private namespace')

    def _pin_executable(self,mounts):
        api=self.a.mount_api
        backing=covering_mount(mounts,api.executable)
        if 'ro' not in backing['options']:raise ContextIOError('mount executable requires immutable admitted runtime backing')
        pfd=open_absolute_dir(posixpath.dirname(api.executable));fd=None
        try:
            fd=os.open(posixpath.basename(api.executable),os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=pfd)
            before=os.fstat(fd);require_regular(before)
            if before.st_size!=api.executable_bytes or before.st_mode&0o222 or not before.st_mode&0o111:
                raise ContextIOError('mount executable pin/readonly/executable mode mismatch')
            h=hashlib.sha256();n=0
            while True:
                b=os.read(fd,min(65536,api.executable_bytes+1-n));self.executable_bytes_read+=len(b)
                if not b:break
                n+=len(b)
                if n>api.executable_bytes:raise ContextIOError('mount executable grew')
                h.update(b)
            if n!=api.executable_bytes or h.hexdigest()!=api.executable_sha256 or revision(os.fstat(fd))!=revision(before):
                raise ContextIOError('mount executable exact bytes changed')
            self.mountfd=fd;fd=None
        finally:
            if fd is not None:os.close(fd)
            os.close(pfd)

    def _verify_tree(self,path,members,*,mounts,readonly):
        if any(m['path'].startswith(path+'/') for m in mounts):raise ContextIOError('nested source/target mounts forbidden')
        backing=covering_mount(mounts,path)
        if readonly and 'ro' not in backing['options']:raise ContextIOError('actual tree backing is not readonly')
        fd=open_absolute_dir(path)
        try:
            before=inventory(fd,self.a.limits,self.work)
            expected={m.path:m for m in members}
            if set(expected)!={f.path for f in before.files}:raise ContextIOError('full public tree membership differs')
            if any(stat.S_IMODE(d[3])!=0o555 for d in before.directories):raise ContextIOError('public directories must already have fixed readonly metadata')
            for item in before.files:
                pin=expected[item.path]
                if item.size!=pin.bytes or stat.S_IMODE(item.revision[2])!=pin.mode:
                    raise ContextIOError('public extent/mode differs from exact pin')
                pfd=open_relative_dir(fd,posixpath.dirname(item.path));bodyfd=None
                try:
                    bodyfd=os.open(posixpath.basename(item.path),os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=pfd)
                    if revision(os.fstat(bodyfd))!=item.revision:raise ContextIOError('public member changed before read')
                    h=hashlib.sha256();n=0
                    while True:
                        b=os.read(bodyfd,min(self.a.limits.block_bytes,pin.bytes+1-n))
                        self.work.source_read_calls+=1;self.work.source_bytes_read+=len(b)
                        if not b:break
                        n+=len(b)
                        if n>pin.bytes:raise ContextIOError('public member grew')
                        h.update(b)
                    named=os.stat(posixpath.basename(item.path),dir_fd=pfd,follow_symlinks=False)
                    if n!=pin.bytes or h.hexdigest()!=pin.sha256 or revision(os.fstat(bodyfd))!=item.revision or revision(named)!=item.revision:
                        raise ContextIOError('public actual body differs from source pin')
                finally:
                    if bodyfd is not None:os.close(bodyfd)
                    os.close(pfd)
            root_still_named(path,fd)
            if inventory(fd,self.a.limits,self.work)!=before:raise ContextIOError('tree changed during full verification')
            return {'root_identity':identity(os.fstat(fd)),'inventory_digest':digest(asdict(before)),
                    'manifest_digest':digest([asdict(m) for m in members]),'backing_mount_id':backing['id']}
        finally:os.close(fd)

    def _command(self,argv):
        """One pinned internal mount command; bounded output, no shell/retry."""
        if self.mountfd is None:raise ContextIOError('exact mount executable not held')
        self._namespace();start=time.monotonic_ns()
        record={'argv':list(argv),'started':False,'exit':None,'failure':None,'stdout_bytes_received':0,'stderr_bytes_received':0}
        self.commands.append(record);proc=None;selector=selectors.DefaultSelector();out={'stdout':bytearray(),'stderr':bytearray()}
        try:
            proc=subprocess.Popen(argv,executable='/proc/self/fd/'+str(self.mountfd),
                pass_fds=(self.mountfd,),stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                env={'PATH':'/nonexistent','LANG':'C','LC_ALL':'C'},shell=False,start_new_session=True,close_fds=True)
            record['started']=True;record['pid']=proc.pid
            for name,stream in (('stdout',proc.stdout),('stderr',proc.stderr)):
                os.set_blocking(stream.fileno(),False);selector.register(stream,selectors.EVENT_READ,name)
            deadline=time.monotonic()+self.a.timeout_seconds
            while selector.get_map():
                if time.monotonic()>=deadline:raise ContextIOError('native mount command timeout')
                for key,unused in selector.select(min(.2,max(0,deadline-time.monotonic()))):
                    b=os.read(key.fileobj.fileno(),4096)
                    if not b:selector.unregister(key.fileobj);continue
                    name=key.data;record[name+'_bytes_received']+=len(b)
                    remaining=self.a.output_bytes_per_stream-len(out[name]);out[name].extend(b[:remaining])
                    if len(b)>remaining:raise ContextIOError('native mount command output cap exceeded')
            remaining=max(0,deadline-time.monotonic())
            record['exit']=proc.wait(timeout=remaining)
            if record['exit']!=0:raise ContextIOError('native mount command returned nonzero')
        except BaseException as exc:
            record['failure']={'type':type(exc).__name__,'message':str(exc)}
            if proc is not None and proc.poll() is None:
                # This exact child is started in its own session, before any
                # other job can join it under the qualified worker contract.
                os.killpg(proc.pid,signal.SIGKILL)
                record['exit']=proc.wait(timeout=5)
            raise
        finally:
            selector.close()
            if proc is not None:
                for stream in (proc.stdout,proc.stderr):
                    if stream is not None:stream.close()
            record['elapsed_ns']=time.monotonic_ns()-start
            for name,body in out.items():
                record[name+'_retained_bytes']=len(body);record[name+'_base64']=base64.b64encode(body).decode('ascii')
                record[name+'_retained_sha256']=hashlib.sha256(body).hexdigest()

    def _evidence(self):
        return {'schema':'n073-native-private-seal-v1','state':self.state,'admission_digest':self.a.fingerprint,
                'source_receipt_digest':self.receipt.receipt_digest,'authority_digest':self.authority_digest,
                'namespace_identity':self.initial_namespace,'target':self.target,
                'sources':[asdict(s) for s in self.sources],'commands':self.commands,'observations':self.observations,
                'counters':self.work.to_dict(),'control_bytes_read':self.control_bytes_read,
                'executable_bytes_read':self.executable_bytes_read,
                'no_automatic_retry_or_unmount':True,
                'cost_scope':'actual bounded control/payload bytes and command outcomes; physical OS allocation/cache I/O and complete native resource feasibility remain external'}

    def activate(self):
        if self.state!='authorized':raise ContextIOError('native sealing session is single-use')
        self.state='preflight'
        try:
            self._namespace();self.nsfd=os.open('/proc/self/ns/mnt',os.O_RDONLY|os.O_CLOEXEC)
            mounts=self._mounts();self._pin_executable(mounts)
            parent=covering_mount(mounts,self.a.target_parent)
            if (parent['id']!=self.a.target_parent_mount_id or parent['path']!=self.a.target_parent
                or parent['root']!='/' or parent['fstype']!='tmpfs' or 'rw' not in parent['options']):
                raise ContextIOError('exact separately admitted private tmpfs target parent required')
            self.parentfd=open_absolute_dir(self.a.target_parent)
            if identity(os.fstat(self.parentfd))!=(self.a.target_parent_device,self.a.target_parent_inode):
                raise ContextIOError('native target parent identity changed')
            # Verify every full source before creating any target or invoking a command.
            source_observations={}
            for source in self.sources:
                source_observations[source.role]=self._verify_tree(source.source,source.members,mounts=mounts,readonly=False)
            writer=TreeWriter(self.a.target_parent,self.a.target_name,self.a.limits,self.work)
            try:
                for source in self.sources:writer.mkdir(source.role)
                self.targetfd=os.dup(writer.fd)
                for role in writer.directories:
                    fd=open_relative_dir(writer.fd,role)
                    try:os.fchmod(fd,0o555);os.utime(fd,ns=(0,0))
                    finally:os.close(fd)
            finally:writer.close()
            self.state='binding'
            for source in self.sources:
                self._namespace();root_still_named(self.a.target_parent,self.parentfd);root_still_named(self.target,self.targetfd)
                before=self._mounts();target=self.target+'/'+source.role
                if any(m['path']==target or m['path'].startswith(target+'/') for m in before):raise ContextIOError('exclusive target already has a mount')
                # Authenticate again immediately before binding to close the gap
                # since all-source preflight. No source-writer lease is fabricated.
                current=self._verify_tree(source.source,source.members,mounts=before,readonly=False)
                if current!=source_observations[source.role]:raise ContextIOError('source changed since complete preflight')
                cover=covering_mount(before,source.source);previous_ids={m['id'] for m in before}
                bind,remount=mount_commands(self.a,source.source,target)
                self._command(bind);self._namespace();after_bind=self._mounts()
                bound=verify_bound_mount(after_bind,source_before=cover,source_path=source.source,target=target,previous_ids=previous_ids,require_ro=False)
                self.observations.append({'role':source.role,'stage':'bound','mount':bound})
                self._command(remount);self._namespace();after_ro=self._mounts()
                sealed=verify_bound_mount(after_ro,source_before=cover,source_path=source.source,target=target,previous_ids=previous_ids,require_ro=True)
                if sealed['id']!=bound['id']:raise ContextIOError('remount replaced the expected bind identity')
                if source.role=='frozen_program' and 'noexec' in sealed['options']:raise ContextIOError('program source is not executable under sealed backing mount')
                target_obs=self._verify_tree(target,source.members,mounts=after_ro,readonly=True)
                if target_obs['root_identity']!=current['root_identity']:
                    raise ContextIOError('actual bound root differs from original source identity')
                self.observations.append({'role':source.role,'stage':'readonly_verified','mount':sealed,'tree':target_obs})
            # Whole-set final checks prevent an earlier role changing while a
            # later role is being sealed; actual guard rechecks all on launch.
            self._namespace();final_mounts=self._mounts()
            for source in self.sources:
                target=self.target+'/'+source.role
                self._verify_tree(target,source.members,mounts=final_mounts,readonly=True)
            root_still_named(self.target,self.targetfd);self.state='sealed'
            from ...core.custody import canonical
            evidence=canonical(self._evidence());evidence_digest=hashlib.sha256(evidence).hexdigest()
            result=tuple(PublicMount(source.role,self.target+'/'+source.role,source.destination,
                    source.members,source.manifest_digest,evidence_digest) for source in self.sources)
            for m in result:m.validate()
            return SealedPublicExports(result,evidence)
        except Exception as exc:
            self.state='failed'
            partial_observation=None
            try:
                self._namespace()
                partial_observation={'target_mounts':[m for m in self._mounts()
                    if m['path']==self.target or m['path'].startswith(self.target+'/')]}
            except Exception as inspection_error:
                partial_observation={'inspection_error':{'type':type(inspection_error).__name__,
                    'message':str(inspection_error)}}
            evidence=self._evidence();evidence['original_error']={'type':type(exc).__name__,'message':str(exc)}
            evidence['partial_namespace_observation']=partial_observation
            evidence['launchable']=False
            # Do not attempt automatic unmount/remount/retry. Partial bindings are
            # private-namespace incidents, retained for its explicit owner close.
            raise NativeSealFailure(exc,evidence) from exc
        finally:
            for name in ('mountfd','nsfd','parentfd','targetfd'):
                fd=getattr(self,name)
                if fd is not None:os.close(fd);setattr(self,name,None)


def seal_public_trees(receipt,admission,*,authority):
    return NativeSealSession(receipt,admission,authority=authority).activate()
