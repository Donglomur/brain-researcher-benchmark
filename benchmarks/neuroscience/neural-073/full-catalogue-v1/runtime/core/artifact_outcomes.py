"""Candidate artifact taxonomy; only a real drained snapshot can qualify failure.

Pure validation errors are NOT scoreable outcomes or native custody evidence.
Trusted-host typed custody is not a boundary against arbitrary same-process code.
"""
import json
import os
import posixpath
import stat
import weakref
from .custody import CustodyError,VerifiedAuthority,canonical,digest

ARTIFACT_REASONS=frozenset({'missing_entry','entry_not_executable',
    'forbidden_candidate_path','forbidden_candidate_file_type',
    'hardlinked_candidate_file','privileged_candidate_mode'})
_CONTEXT_SEAL=object();_FAILURE_SEAL=object();_CONTEXTS=weakref.WeakKeyDictionary()


class ArtifactValidationError(RuntimeError):
    """A pure validation finding. Never catch this as a countable context failure."""
    def __init__(self,reason,*,relative_path,details):
        if reason not in ARTIFACT_REASONS or not isinstance(relative_path,str) or not isinstance(details,dict):
            raise CustodyError('fixed typed artifact finding required')
        self.reason=reason
        self._finding=canonical({'reason':reason,'relative_path':relative_path,'details':details})
        super().__init__(reason+': '+relative_path)

    def to_dict(self):return json.loads(self._finding)


class CandidateArtifactFailure(RuntimeError):
    """Issued only after actual context custody/drain recheck and successful abort.

    Owner still must qualify complete native/usage closure. This exception does
    not itself certify that closure; it preserves the failed-case denominator.
    """
    def __init__(self,evidence,seal):
        if seal is not _FAILURE_SEAL:raise CustodyError('actual registered snapshot rejection required')
        self._evidence=canonical(evidence)
        super().__init__('candidate F artifact rejected: '+evidence['artifact']['reason'])

    @property
    def evidence(self):return json.loads(self._evidence)


def validate_candidate_path(path):
    """Pure validation of one candidate-created relative member name."""
    if (not isinstance(path,str) or not path or path.startswith('/')
        or posixpath.normpath(path)!=path or path in ('.','..') or path.startswith('../')
        or '\x00' in path or '\\' in path
        or any(ord(c)<32 or ord(c)==127 for c in path)
        or set(path.split('/'))&{'.git','.hg','.svn','.ssh','.aws','.codex'}):
        raise ArtifactValidationError('forbidden_candidate_path',relative_path=str(path),
                                      details={'rule':'canonical public artifact member, no private control names'})


def validate_candidate_stat(path,observed,*,expected_device):
    """Pure metadata check; cross-device/custody uncertainty is infrastructure."""
    validate_candidate_path(path)
    if type(observed) is not os.stat_result or type(expected_device) is not int:
        raise CustodyError('actual or explicitly invented stat metadata required')
    if observed.st_dev!=expected_device:raise CustodyError('candidate root crossed device; custody invalid')
    mode=observed.st_mode
    if not (stat.S_ISREG(mode) or stat.S_ISDIR(mode)):
        kind=('symlink' if stat.S_ISLNK(mode) else 'fifo' if stat.S_ISFIFO(mode)
              else 'socket' if stat.S_ISSOCK(mode) else 'device_or_special')
        raise ArtifactValidationError('forbidden_candidate_file_type',relative_path=path,
                                      details={'observed_kind':kind,'mode':mode})
    if mode&(stat.S_ISUID|stat.S_ISGID):
        raise ArtifactValidationError('privileged_candidate_mode',relative_path=path,
                                      details={'mode':mode})
    if stat.S_ISREG(mode) and observed.st_nlink!=1:
        raise ArtifactValidationError('hardlinked_candidate_file',relative_path=path,
                                      details={'link_count':observed.st_nlink})


def validate_candidate_entry(entry_modes,entry_relative_path):
    """Pure full-inventory entry check using exact relative-path/output-mode values.

    Production supplies the exact inventoried work/tmp records. Missing entry
    and ordinary nonexecutable files are distinct fixed reasons. This function
    does not grant native context validity or authorize filesystem reads.
    """
    if type(entry_modes) is not dict or any(type(k) is not str or type(v) is not int or v not in (0o444,0o555) for k,v in entry_modes.items()):
        raise CustodyError('concrete complete inventory mode mapping required')
    validate_candidate_path(entry_relative_path)
    if not entry_relative_path.startswith('work/'):
        raise ArtifactValidationError('forbidden_candidate_path',relative_path=entry_relative_path,
                                      details={'rule':'F entry must be under work/'})
    if entry_relative_path not in entry_modes:
        raise ArtifactValidationError('missing_entry',relative_path=entry_relative_path,
                                      details={'inventory_has_entry':False})
    if entry_modes[entry_relative_path]!=0o555:
        raise ArtifactValidationError('entry_not_executable',relative_path=entry_relative_path,
                                      details={'output_mode':entry_modes[entry_relative_path]})


class CandidateSnapshotContext:
    """Registered real lease boundary; there is no invented/native-success mode."""
    __slots__=('__weakref__',)
    def __init__(self,seal):
        if seal is not _CONTEXT_SEAL:raise CustodyError('real snapshot context issuance required')

    @classmethod
    def from_registered_lease(cls,lease,*,authority,bindings):
        from ..process_guard.barrier_v2 import SnapshotLease
        if type(lease) is not SnapshotLease or type(authority) is not VerifiedAuthority:
            raise CustodyError('actual registered lease and verified author authority required')
        authority.require(role='candidate_author',domain='authentic',bindings=bindings)
        roots=lease.require_drained()
        if type(roots) is not tuple or len(roots)!=2 or roots[0]==roots[1]:
            raise CustodyError('actual complete work/tmp roots required')
        ctx=cls(_CONTEXT_SEAL)
        _CONTEXTS[ctx]={'lease':lease,'roots':roots,'context_digest':lease.context_digest,
            'context_id':lease.opaque_context_id,'runtime_digest':lease.runtime_manifest_digest,
            'authority_digest':authority.authority_digest,'bindings_digest':digest(dict(bindings))}
        return ctx

    def require_active(self,root_fd=None):
        record=_CONTEXTS.get(self)
        if record is None:raise CustodyError('unregistered or consumed candidate snapshot context')
        lease=record['lease'];roots=lease.require_drained()
        if roots!=record['roots'] or lease.context_digest!=record['context_digest'] or lease.runtime_manifest_digest!=record['runtime_digest']:
            raise CustodyError('candidate snapshot custody changed')
        if root_fd is not None:
            if type(root_fd) is not int:raise CustodyError('explicit actual root fd required')
            opened=os.fstat(root_fd)
            if not stat.S_ISDIR(opened.st_mode):raise CustodyError('candidate snapshot root is not directory')
            root_stats=tuple(os.stat(root,follow_symlinks=False) for root in roots)
            actual={(st.st_dev,st.st_ino) for st in root_stats}
            if (opened.st_dev,opened.st_ino) not in actual:raise CustodyError('inventory fd is outside actual candidate roots')
        return roots

    def reject(self,original,*,counters,partial_root,staging_created):
        if type(original) is not ArtifactValidationError:
            raise CustodyError('only pure typed artifact validation can be a candidate failure')
        if type(counters) is not dict or any(type(v) is not int or v<0 for v in counters.values()):
            raise CustodyError('complete concrete I/O counters required')
        if type(staging_created) is not bool:raise CustodyError('explicit staging state required')
        self.require_active();record=_CONTEXTS[self]
        # Native/root/drain failures here propagate as infrastructure; no typed
        # countable outcome is issued until abort actually succeeds.
        record['lease'].abort('ordinary invalid candidate F artifact: '+original.reason)
        del _CONTEXTS[self]
        evidence={'schema':'n073-candidate-artifact-failure-v1','classification':'candidate_failure',
            'artifact':original.to_dict(),'original_type':type(original).__name__,'original_message':str(original),
            'context_id':record['context_id'],'context_digest':record['context_digest'],
            'runtime_digest':record['runtime_digest'],'authority_digest':record['authority_digest'],
            'snapshot_bindings_digest':record['bindings_digest'],'counters':dict(counters),
            'partial_root':partial_root,'staging_created':staging_created,
            'actual_snapshot_abort':'completed','failed_case_policy':'retain_all_expected_query_ids',
            'launchable':False,'complete_native_closure_still_required':True}
        return CandidateArtifactFailure(evidence,_FAILURE_SEAL)
