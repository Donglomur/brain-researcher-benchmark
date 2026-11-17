"""Finite trusted numerical job worker; no job starts at import.

Each actual fit is a separate Linux process with its original 4h/8-core/64GiB
ceiling and a retained result/failure receipt. This source performs no fits.
"""
from __future__ import annotations
import multiprocessing
import os
import signal
import sys
import threading
import time
from owner.io import ContractError, canonical, decode
from owner.process import creation_parent, bind_parent_death

MAX_WALL = 4 * 3600
MAX_CPU = 32 * 3600
MAX_RAM = 64 * (1024 ** 3)
CLEANUP_SECONDS = 6
READER_CLOSE_SECONDS = 1


def validate_allocation(allocation, *, rows, dimension, independent=False):
    required = {"rows", "dimension", "wall_seconds", "cpu_seconds", "ram_bytes", "cpu_ids", "result_bytes", "workspace_bytes", "input_object_bytes"}
    if not isinstance(allocation, dict) or set(allocation) != required:
        raise ContractError("exact per-fit concrete numerical allocation required")
    if allocation["rows"] != rows or allocation["dimension"] != dimension:
        raise ContractError("numerical allocation dimensions differ from full FIT scope")
    for key in required - {"cpu_ids"}:
        if type(allocation[key]) is not int or allocation[key] < 0:
            raise ContractError("finite integer allocation required")
    if not CLEANUP_SECONDS < allocation["wall_seconds"] <= MAX_WALL or not 0 < allocation["cpu_seconds"] <= MAX_CPU or not 0 < allocation["ram_bytes"] <= MAX_RAM:
        raise ContractError("per-fit allocation exceeds frozen envelope")
    if not isinstance(allocation["cpu_ids"], list) or not 0 < len(set(allocation["cpu_ids"])) <= 8 or any(type(v) is not int or v < 0 for v in allocation["cpu_ids"]):
        raise ContractError("one to eight explicitly assigned CPU IDs required")
    if allocation["result_bytes"] <= 0:
        raise ContractError("result transport bound required")
    # Lower-bound feasibility, with externally admitted native workspace and
    # retained parsed-input allocation. OS enforcement remains mandatory.
    arrays = (8 * rows * dimension * 6 + 8 * dimension * dimension * 2) if independent else (8 * dimension * dimension * 6 + 8 * dimension * 32)
    needed = arrays + allocation["workspace_bytes"] + allocation["input_object_bytes"] + allocation["result_bytes"]
    if needed > allocation["ram_bytes"]:
        raise ContractError("complete numerical job cannot fit admitted memory; no pruning")
    return {"array_lower_bound": arrays, "admitted_total_bytes": needed, **allocation}


def _child(connection, kind, arguments, allocation, expected_parent):
    bind_parent_death(expected_parent)
    import resource
    os.setsid()
    resource.setrlimit(resource.RLIMIT_AS, (allocation["ram_bytes"], allocation["ram_bytes"]))
    resource.setrlimit(resource.RLIMIT_CPU, (allocation["cpu_seconds"], allocation["cpu_seconds"]))
    os.sched_setaffinity(0, allocation["cpu_ids"])
    for name in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
        os.environ[name] = str(len(set(allocation["cpu_ids"])))
    start = time.monotonic()
    try:
        if kind == "primary":
            from .primary import fit
        elif kind == "independent":
            from .independent import fit
        else:
            raise ContractError("unknown closed numerical job kind")
        model = fit(*arguments)
        body = {"status": "complete", "model": model, "error": None}
    except BaseException as exc:
        body = {"status": "failed", "model": None, "error": {"type": type(exc).__name__, "message": str(exc)[:2048]}}
    usage = resource.getrusage(resource.RUSAGE_SELF)
    body["usage"] = {"wall_seconds": time.monotonic() - start, "cpu_seconds": usage.ru_utime + usage.ru_stime,
                     "peak_rss_bytes": usage.ru_maxrss * 1024, "pid": os.getpid()}
    encoded = canonical(body)
    if len(encoded) > allocation["result_bytes"]:
        body = {"status": "failed", "model": None, "error": {"type": "ResultBound", "message": "complete fit output exceeds admitted transport bound"}, "usage": body["usage"]}
        encoded = canonical(body)
    connection.send_bytes(encoded)
    connection.close()


def error_record(exc, where):
    return {"where":where,"type":type(exc).__name__,"message":str(exc)[:2048]}


def close_bounded(process, reader, receiver, pidfd, deadline, *, clock=time.monotonic,
                  signal_child=signal.pidfd_send_signal if hasattr(signal,'pidfd_send_signal') else None):
    """Every cleanup error becomes unresolved owned-stage escalation evidence.

    The prejoin pidfd is the only permitted signal identity. No exception from
    signaling, state inspection, join or reader closure escapes this protocol.
    """
    errors=[];signaled=False;child_unresolved=None;reader_unresolved=None
    def alive(obj, where):
        if obj is None:return False
        try:return obj.is_alive()
        except BaseException as exc:errors.append(error_record(exc,where));return None
    try:
        child_unresolved=alive(process,'child_state_before_signal')
        if child_unresolved is not False:
            if pidfd is None or signal_child is None:
                errors.append({'where':'signal','type':'PinnedIdentityUnavailable','message':'no numeric fallback permitted'})
            else:
                try:signal_child(pidfd,signal.SIGKILL);signaled=True
                except ProcessLookupError:pass
                except BaseException as exc:errors.append(error_record(exc,'signal'))
            try:process.join(timeout=max(0.0,deadline-clock()-READER_CLOSE_SECONDS))
            except BaseException as exc:errors.append(error_record(exc,'child_join'))
        try:receiver.close()
        except BaseException as exc:errors.append(error_record(exc,'reader_connection_close'))
        if reader is not None:
            try:reader.join(timeout=max(0.0,min(READER_CLOSE_SECONDS,deadline-clock())))
            except BaseException as exc:errors.append(error_record(exc,'reader_join'))
        child_unresolved=alive(process,'child_state_after_join')
        reader_unresolved=alive(reader,'reader_state_after_join')
    except BaseException as exc:
        errors.append(error_record(exc,'cleanup_protocol'));child_unresolved=reader_unresolved=None
    return {'signal_identity':'prejoin_owned_pidfd' if pidfd is not None else None,
            'kill_requested':signaled,'child_unresolved':child_unresolved,
            'reader_unresolved':reader_unresolved,'errors':errors,
            'owned_stage_escalation_required':bool(errors) or child_unresolved is not False or reader_unresolved is not False,
            'cleanup_deadline_monotonic':deadline}


def run(kind, arguments, allocation, *, rows, dimension, require_scientific):
    require_scientific()
    admitted=validate_allocation(allocation,rows=rows,dimension=dimension,independent=kind=='independent')
    if sys.platform!='linux' or not hasattr(os,'sched_setaffinity') or not hasattr(os,'pidfd_open') or not hasattr(signal,'pidfd_send_signal'):
        raise ContractError('qualified Linux affinity/resource/pidfd runtime required before creation')
    if not set(allocation['cpu_ids'])<=os.sched_getaffinity(0):raise ContractError('assigned CPU set is unavailable')
    import resource
    before_children=resource.getrusage(resource.RUSAGE_CHILDREN)
    context=multiprocessing.get_context('fork');receiver,sender=context.Pipe(duplex=False)
    expected_parent=creation_parent()
    process=context.Process(target=_child,args=(sender,kind,arguments,allocation,expected_parent),daemon=False)
    start=time.monotonic();complete_deadline=start+allocation['wall_seconds'];work_deadline=complete_deadline-CLEANUP_SECONDS
    received={};pidfd=None;reader=None;initiating_failure=None;transport_timed_out=False;creation_attempted=False
    def receive_bounded():
        try:
            transported=receiver.recv_bytes(maxlength=allocation['result_bytes'])
            received['transport_bytes']=len(transported);decoded=decode(transported)
            if not isinstance(decoded,dict) or decoded.get('status') not in ('complete','failed') or 'model' not in decoded:raise ContractError('malformed numerical result')
            received['outcome']=decoded
        except BaseException as exc:
            received['outcome']={'status':'failed','model':None,'error':error_record(exc,'reader_transport'),'usage':None}
    # Everything from the attempted creation onward is captured. In particular,
    # no startup/close/join/pidfd exception may reach normal multiprocessing exit.
    try:
        creation_attempted=True;process.start();sender.close()
        pidfd=os.pidfd_open(process.pid)  # before any poll/join/reap
        reader=threading.Thread(target=receive_bounded,daemon=True);reader.start()
        reader.join(timeout=max(0.0,work_deadline-time.monotonic()))
        transport_timed_out=reader.is_alive()
        process.join(timeout=max(0.0,work_deadline-time.monotonic()))
    except BaseException as exc:initiating_failure=error_record(exc,'post_creation_setup_or_work')
    closure=close_bounded(process,reader,receiver,pidfd,complete_deadline)
    for where,close in [('sender_close',sender.close),('pidfd_close',lambda:os.close(pidfd) if pidfd is not None else None)]:
        try:close()
        except BaseException as exc:
            closure['errors'].append(error_record(exc,where));closure['owned_stage_escalation_required']=True
    if initiating_failure is not None:closure['owned_stage_escalation_required']=True
    outcome=received.get('outcome',{'status':'failed','model':None,'error':{'type':'MissingResult','message':'no complete numerical result'},'usage':None})
    if initiating_failure is not None or closure['owned_stage_escalation_required'] or transport_timed_out:
        outcome={'status':'failed','model':None,'usage':None,'error':initiating_failure or {'type':'UnresolvedNumericalClosure' if closure['owned_stage_escalation_required'] else 'WallTimeout','message':'finite fit/reader closure failed; owned stage escalation required if unresolved'},'late_worker_outcome':received.get('outcome')}
    outcome['closure']=closure;outcome['creation_attempted']=creation_attempted;outcome['initiating_failure']=initiating_failure
    try:
        after_children=resource.getrusage(resource.RUSAGE_CHILDREN)
        outcome['parent_observed_child_cpu_seconds']=(after_children.ru_utime+after_children.ru_stime)-(before_children.ru_utime+before_children.ru_stime)
        outcome['parent_children_peak_rss_upper_bound_bytes']=after_children.ru_maxrss*1024
        outcome['process_exit_code']=process.exitcode
    except BaseException as exc:
        outcome['parent_observed_child_cpu_seconds']=None;outcome['parent_children_peak_rss_upper_bound_bytes']=None;outcome['process_exit_code']=None
        closure['errors'].append(error_record(exc,'post_creation_usage_or_exit'));closure['owned_stage_escalation_required']=True
        outcome['status']='failed';outcome['model']=None
    outcome['unreaped_child_cpu_seconds']=None if closure['child_unresolved'] is not False else 0
    outcome['parent_child_usage_scope']='RUSAGE_CHILDREN CPU delta and cumulative children RSS upper bound; unresolved counters remain unknown'
    outcome['parent_observed_wall_seconds']=time.monotonic()-start;outcome['allocation']=admitted;outcome['result_transport_bytes']=received.get('transport_bytes')
    usage=outcome.get('usage')
    if outcome['status']=='complete' and (not isinstance(usage,dict) or usage.get('cpu_seconds',float('inf'))>allocation['cpu_seconds'] or usage.get('peak_rss_bytes',float('inf'))>allocation['ram_bytes'] or outcome['parent_observed_wall_seconds']>allocation['wall_seconds'] or outcome['process_exit_code']!=0):
        outcome['status']='failed';outcome['error']={'type':'ObservedResourceOrExitFailure','message':'actual fit closure/resource evidence is missing or exceeds its unchanged ceiling'}
    return outcome
