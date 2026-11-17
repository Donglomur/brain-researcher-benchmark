"""One irreversible authority event, independent of userspace acknowledgement.

A qualified, same-FD-authenticated, single-link kernel commit at or before the
signed deadline establishes the terminal fact. Delivery delay/error cannot
revoke it. Missing/partial/late/unknown publication has no DONE authority.
All actual Linux filesystem/clock semantics remain independent runtime gates.
"""
from __future__ import annotations
import hashlib,os,sys,time
from pathlib import Path
from .io import Artifact,ContractError,ordinary,identity,decode
from .evidence import issue
from .deadline import check

RULE='qualified_single_link_kernel_commit_v4'


def final_path(root,stage):return Path(root)/'journal'/(stage+'.final.json')


def _read_commit(ref,root,stage,*,meter=None,archival=False):
    expected=final_path(root,stage)
    role='signed_terminal_failure' if archival else 'signed_stage_completion'
    if ref.path!=str(expected) or ref.role!=role or ref.producer!=stage:
        raise ContractError('exact fixed terminal authority path/role/producer required')
    p=ordinary(expected);fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        before=os.fstat(fd)
        if before.st_nlink!=1 or before.st_size!=ref.bytes or ref.bytes>4_000_000:
            raise ContractError('publication is partial, multiply linked or malformed')
        parts=[];n=0
        while True:
            chunk=os.read(fd,min(65536,ref.bytes-n+1))
            if not chunk:break
            n+=len(chunk)
            if meter:meter.read(len(chunk))
            if n>ref.bytes:raise ContractError('publication grew')
            parts.append(chunk)
        after=os.fstat(fd);body=b''.join(parts)
        if identity(before)!=identity(after) or len(body)!=ref.bytes or hashlib.sha256(body).hexdigest()!=ref.sha256:
            raise ContractError('publication identity or exact body changed')
        envelope=decode(body);payload=envelope.get('payload',{});content=payload.get('content',{})
        if content.get('authority_rule')!=RULE:raise ContractError('wrong terminal authority rule')
        issued=payload.get('issued_at');bound=content.get('publication_deadline_ns')
        if type(issued) is not int or type(bound) is not int:raise ContractError('exact signed publication interval required')
        if not archival and not issued*1_000_000_000<=after.st_ctime_ns<=bound:
            raise ContractError('single-link kernel commit was not within the admitted deadline')
        return envelope,{'kernel_ctime_ns':after.st_ctime_ns,'publication_deadline_ns':bound,
                         'device':after.st_dev,'inode':after.st_ino,'links':after.st_nlink}
    finally:os.close(fd)


def read_authoritative(ref,root,stage,*,meter=None):
    # Neither acknowledgement/observation presence nor a later marker can
    # create, revoke or replace a committed fact. Signature/current-attempt
    # verification is still mandatory in the actual prerequisite caller.
    return _read_commit(ref,root,stage,meter=meter)[0]


def _reconcile(root,stage,expected,meter):
    path=final_path(root,stage)
    try:os.lstat(path)
    except FileNotFoundError:return None,None,{'status':'not_published','reason':'fixed terminal path absent'}
    except BaseException as exc:return None,None,{'status':'unresolved','reason':type(exc).__name__+': '+str(exc)[:2048]}
    errors=[]
    for payload,pending in expected:
        archival=payload['kind']=='terminal_failure'
        ref=Artifact(str(path),pending.bytes,pending.sha256,
            'signed_terminal_failure' if archival else 'signed_stage_completion','operator',stage)
        try:
            envelope,commit=_read_commit(ref,root,stage,meter=meter,archival=archival)
            if envelope['payload']!=payload:raise ContractError('committed payload differs from the exact decision signed by this invocation')
            return ref,payload,{'status':'committed','commit':commit}
        except BaseException as exc:errors.append({'type':type(exc).__name__,'message':str(exc)[:2048]})
    return None,None,{'status':'unresolved','reason':'no exact independently readable timely terminal decision','errors':errors}


def publish(store,stage,plan,decision,key):
    """Preserve effects/errors, then reconcile the sole kernel authority event.

    No post-commit deadline check can reinterpret a timely committed fact. All
    pre-commit work retains its original monotonic/epoch deadline. A late
    syscall acknowledgement is controller overhead and reported separately.
    Any error after attempted publication is reconciled against the same exact
    file rule used by DONE. If reconciliation is unavailable, return unresolved
    without writing a contradictory authoritative success/failure marker.
    """
    expected=[];errors=[];started=time.monotonic()
    try:
        if sys.platform!='linux':raise ContractError('qualified Linux publication required')
        payload=decision()
        pending=store.json('journal/'+stage+'.terminal.pending.json',issue(payload,key),
            role='signed_terminal_pending',visibility='operator',producer=stage)
        expected.append((payload,pending))
        if payload['kind']=='completion':
            try:check(plan,phase='terminal')
            except ContractError:
                payload=decision()
                pending=store.json('journal/'+stage+'.failed.pending.json',issue(payload,key),
                    role='signed_terminal_pending',visibility='operator',producer=stage)
                expected.append((payload,pending))
        final=final_path(store.root,stage)
        directory=os.open(final.parent,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
        try:os.fsync(directory)
        finally:os.close(directory)
        if payload['kind']=='completion':check(plan,phase='terminal')
        os.link(pending.path,final,follow_symlinks=False)
        os.unlink(pending.path)
    except BaseException as exc:
        errors.append({'type':type(exc).__name__,'message':str(exc)[:2048],
                       'scope':'publication_or_acknowledgement; authority determined only by reconciliation'})
    ref,payload,observation=_reconcile(store.root,stage,expected,store.meter)
    wall=time.time();mono=time.monotonic()
    observation.update(schema='neural063_publication_observation_v4',authority_rule=RULE,
        attempt_expires_at=plan['attempt_expires_at'],acknowledged_wall_time=wall,
        acknowledged_monotonic_time=mono,publication_call_wall_seconds=mono-started,
        stage_elapsed_through_acknowledgement=mono-plan['admitted_monotonic'],
        acknowledgement_seconds_after_terminal_deadline=max(0.0,mono-plan['terminal_deadline']),
        attempt_lifetime_at_acknowledgement='expired' if wall>=plan['attempt_expires_at'] else 'not_expired',
        publication_errors=errors,physical_cpu_seconds=None,physical_io_bytes=None,
        physical_peak_ram_bytes=None,
        cost_policy='Publication and acknowledgement overhead is common controller cost; observed wall tail is retained, physical counters unknown unless independently measured. A late acknowledgement never grants additional scientific/candidate work or erases cost/overrun evidence.',
        observation_write_and_delivery_tail='not yet observed; never zero-imputed')
    return ref,payload,observation
