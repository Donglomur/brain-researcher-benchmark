"""Complete frozen-program snapshot only under an actual registered native lease."""
from dataclasses import dataclass,asdict
import os
from ..core.custody import VerifiedAuthority,digest
from ..core.artifact_outcomes import (ArtifactValidationError,CandidateSnapshotContext,
                                      validate_candidate_entry)
from ..process_guard.barrier_v2 import SnapshotLease
from ..process_guard.contracts import PublicMount
from .filesystem import (ContextIOError,ContextIOFailure,IOLimits,IOCounter,TreeWriter,inventory,
                         open_absolute_dir,root_still_named,relative_path,absolute_path,token)


@dataclass(frozen=True)
class SnapshotReceipt:
    root: str
    members: tuple
    entry_relative_path: str
    entry_digest: str
    runtime_digest: str
    context_digest: str
    inventories_digest: str
    counters: tuple
    authority_digest: str
    io_binding_digest: str

    @property
    def program_manifest_digest(self):return digest([asdict(p) for p in self.members])

    def to_dict(self):
        return {'schema':'n073-frozen-program-snapshot-v1','root':self.root,
                'members':[asdict(p) for p in self.members],
                'program_manifest_digest':self.program_manifest_digest,
                'entry_relative_path':self.entry_relative_path,'entry_digest':self.entry_digest,
                'runtime_digest':self.runtime_digest,'context_digest':self.context_digest,
                'inventories_digest':self.inventories_digest,'counters':dict(self.counters),
                'authority_digest':self.authority_digest,'io_binding_digest':self.io_binding_digest,
                'backing_mount_qualified':False,
                'cost_scope':'all scoped work/tmp regular-file payload reads and writes; logical calls only, excludes physical OS I/O and filesystem allocation'}

    @property
    def receipt_digest(self):return digest(self.to_dict())

    def mount(self):
        result=PublicMount('frozen_program',self.root,'/program',self.members,
                           self.program_manifest_digest,self.receipt_digest)
        result.validate();return result


def snapshot_io_bindings(*,context_digest,runtime_digest,parent_path,name,entry_relative_path,limits):
    absolute_path(parent_path);token(name);relative_path(entry_relative_path);limits.validate()
    if not entry_relative_path.startswith('work/'):
        raise ContextIOError('entry must be explicit complete executable under work/')
    return {'context_digest':context_digest,'runtime_digest':runtime_digest,
            'snapshot_io_digest':digest({'parent':parent_path,'name':name,'entry':entry_relative_path,
                                        'limits':asdict(limits),'schema':'n073-snapshot-io-v1'})}


def snapshot_program(lease,*,authority,parent_path,name,entry_relative_path,limits,counter=None):
    """Returns (SnapshotReceipt, registered FrozenSnapshotBinding).

    All metadata enumeration is confined to the two roots actually issued by the
    drained guard; no neural/source/package search is performed. Both complete
    writable roots, including empty directories, are captured without filtering.
    Runtime packages remain exact immutable admitted runtime, bound by its digest.
    Symlink/hardlink/special/cross-device/private-control entries fail the entire
    snapshot. Any failure after lease acceptance aborts query permanently.
    """
    if type(lease) is not SnapshotLease:raise ContextIOError('actual registered native SnapshotLease required')
    if type(authority) is not VerifiedAuthority:raise ContextIOError('verified author authority required')
    bindings=snapshot_io_bindings(context_digest=lease.context_digest,
        runtime_digest=lease.runtime_manifest_digest,parent_path=parent_path,name=name,
        entry_relative_path=entry_relative_path,limits=limits)
    authority_digest=authority.require(role='candidate_author',domain='authentic',bindings=bindings)
    work=IOCounter() if counter is None else counter
    if type(work) is not IOCounter:raise ContextIOError('concrete logical counter required')
    writer=None;fds=[];completed=False;candidate_context=None;result=None;original=None;cleanup_errors=[]
    try:
        candidate_context=CandidateSnapshotContext.from_registered_lease(lease,authority=authority,bindings=bindings)
        roots=candidate_context.require_active()
        if type(roots) is not tuple or len(roots)!=2 or roots[0]==roots[1]:raise ContextIOError('exact work/tmp roots required')
        if any(parent_path==r or parent_path.startswith(r+'/') or r.startswith(parent_path+'/'+name+'/') for r in roots):
            raise ContextIOError('snapshot destination overlaps writable source roots')
        for root in roots:fds.append(open_absolute_dir(root))
        inventories=tuple(inventory(fd,limits,work,candidate_context=candidate_context) for fd in fds)
        if (sum(len(x.files) for x in inventories)>limits.max_files
            or 1+sum(len(x.directories) for x in inventories)>limits.max_directories
            or sum(x.bytes for x in inventories)>limits.max_total_bytes):
            raise ContextIOError('complete two-root snapshot exceeds capacity')
        candidates={prefix+'/'+f.path:f for prefix,inv in zip(('work','tmp'),inventories) for f in inv.files}
        validate_candidate_entry({path:item.output_mode for path,item in candidates.items()},entry_relative_path)
        writer=TreeWriter(parent_path,name,limits,work)
        for prefix,root,fd,inv in zip(('work','tmp'),roots,fds,inventories):
            if lease.require_drained()!=roots:raise ContextIOError('lease roots changed')
            root_still_named(root,fd);writer.mkdir(prefix)
            for directory in inv.directories:
                if directory[0]:writer.mkdir(prefix+'/'+directory[0])
            for item in inv.files:
                lease.require_drained()
                writer.copy_file(fd,item,prefix+'/'+item.path)
            if inventory(fd,limits,work)!=inv:raise ContextIOError('complete source inventory changed during capture')
        pins=writer.finish();entry=next(p for p in pins if p.path==entry_relative_path)
        # Root identity and complete metadata inventories are rechecked together,
        # closing mutations between the two sequential source-root copies.
        for root,fd,inv in zip(roots,fds,inventories):
            root_still_named(root,fd)
            if inventory(fd,limits,work)!=inv:raise ContextIOError('source changed before final binding')
        if lease.require_drained()!=roots:raise ContextIOError('lease roots changed at completion')
        receipt=SnapshotReceipt(writer.path,pins,entry_relative_path,entry.sha256,
            lease.runtime_manifest_digest,lease.context_digest,digest([asdict(x) for x in inventories]),
            tuple(sorted(work.to_dict().items())),authority_digest,bindings['snapshot_io_digest'])
        binding=lease.complete(snapshot_digest=receipt.receipt_digest,
            program_manifest_digest=receipt.program_manifest_digest,entry_digest=entry.sha256,
            entry_relative_path=entry_relative_path,runtime_digest=receipt.runtime_digest)
        completed=True
        result=(receipt,binding)
    except Exception as exc:
        original=exc
    finally:
        # Descriptor cleanup is part of infrastructure, never ordinary candidate
        # invalidity. Preserve each original close error before classification.
        if writer is not None:
            try:writer.close()
            except Exception as close_exc:
                cleanup_errors.append({'resource':'snapshot_writer','type':type(close_exc).__name__,'message':str(close_exc)})
                if original is None:original=close_exc
        for index,fd in enumerate(fds):
            try:os.close(fd)
            except Exception as close_exc:
                cleanup_errors.append({'resource':'candidate_root_fd_'+str(index),'type':type(close_exc).__name__,'message':str(close_exc)})
                if original is None:original=close_exc
    if original is None:
        return result
    classification_error=None
    if (type(original) is ArtifactValidationError and candidate_context is not None
        and not cleanup_errors and not completed):
        try:
            failure=candidate_context.reject(original,counters=work.to_dict(),
                partial_root=parent_path+'/'+name,staging_created=writer is not None)
        except Exception as rejection_error:
            classification_error={'type':type(rejection_error).__name__,'message':str(rejection_error)}
        else:
            raise failure from original
    abort_failure=None
    if not completed:
        try:lease.abort('snapshot infrastructure failure; original causes and counters preserved')
        except Exception as abort_exc:
            abort_failure={'type':type(abort_exc).__name__,'message':str(abort_exc)}
    infrastructure_details={'abort_failure':abort_failure,'classification_error':classification_error,
        'cleanup_errors':cleanup_errors,'snapshot_binding_already_issued':completed}
    if type(original) is ArtifactValidationError:
        infrastructure_details['unqualified_artifact_finding']=original.to_dict()
    raise ContextIOFailure(original,counter=work,partial_root=parent_path+'/'+name,
                           abort_failure=infrastructure_details) from original
