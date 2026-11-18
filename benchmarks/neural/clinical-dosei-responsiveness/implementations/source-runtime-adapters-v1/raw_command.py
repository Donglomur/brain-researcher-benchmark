"""Bounded raw stdout/stderr capture for trusted fixed host commands.

This is not a sandbox. The injected process owner retains its leader unreaped
until cleanup signals finish. Candidate Python runs only in a separate Docker
container, never through this host-command primitive.
"""
import hashlib
import json
import math
import os
import select
import time


class CommandFailure(RuntimeError):
    def __init__(self, category, receipt):
        self.category, self.receipt = category, receipt
        super().__init__(category)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('ascii')


def binding(raw):
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def retain(recorder, kind, raw):
    wanted = binding(raw)
    actual = recorder(kind, raw)
    if (type(actual) is not dict or set(actual) != {'bytes', 'sha256'} or
            type(actual['bytes']) is not int or type(actual['sha256']) is not str or actual != wanted):
        raise ValueError('unconfirmed exact original custody')
    return wanted


def run(command, *, cwd, recorder, process_api, timeout_seconds=30, output_limit=2097152):
    """Capture up to limit+1 observed bytes; preserve failure/unknown scope.

    Recorder is a trusted bounded local sink, not arbitrary participant code.
    Outer process supervision must cover recorder latency. A failure retains
    its full output grant; unread output is explicitly unknown, never zero.
    The returned command exit is the reaped leader's exit, not inferred EOF.
    """
    if not (type(timeout_seconds) in (int, float) and math.isfinite(timeout_seconds)
            and 0 < timeout_seconds <= 120 and type(output_limit) is int
            and 1 <= output_limit <= 4194304 and callable(recorder)):
        raise ValueError('bounded command limits required')
    started = time.monotonic(); deadline = started + timeout_seconds
    intent = {'schema': 'dosei_raw_command_intent_v1', 'command': command, 'cwd': cwd,
              'timeout_seconds': timeout_seconds, 'output_limit': output_limit,
              'stderr': 'merged_raw_stdout', 'stdin': 'closed_without_input'}
    intent_binding = retain(recorder, 'command_intent', canonical(intent))
    process = None; fd = None; signature = None; write_fd = None
    prefix = bytearray(); category = None; interruption = None; eof = False
    errors = []; closure = None; spawn = None; original = None
    try:
        if time.monotonic() >= deadline: raise TimeoutError('intent retention consumed deadline')
        process = process_api.OwnedProcess(command, cwd=cwd)
        spawn = process.spawn_receipt()
        fd, write_fd = process.detach_stdio()
        signature = process_api.fd_signature(fd)
        write_signature = process_api.fd_signature(write_fd)
        if process_api.fd_signature(write_fd) != write_signature:
            raise ValueError('stdin descriptor changed')
        closing_write_fd, write_fd = write_fd, None
        # An interrupted close has ambiguous effect. Never retry its numeric
        # descriptor; the failed command's encompassing owner must reconcile it.
        os.close(closing_write_fd)
        os.set_blocking(fd, False)
        while True:
            if time.monotonic() >= deadline:
                category = 'command_wall_timeout'; break
            if process_api.fd_signature(fd) != signature:
                category = 'descriptor_identity'; break
            try:
                ready = select.select([fd], [], [], max(0, deadline-time.monotonic()))[0]
            except InterruptedError:
                continue
            if not ready or time.monotonic() >= deadline:
                category = 'command_wall_timeout'; break
            try:
                piece = os.read(fd, min(65536, output_limit+1-len(prefix)))
            except (InterruptedError, BlockingIOError):
                continue
            if not piece:
                eof = True; break
            prefix.extend(piece)
            if len(prefix) > output_limit:
                category = 'command_output_capacity'; break
    except BaseException as error:
        category = category or 'command_transport_failure'
        errors.append({'phase': 'capture', 'type': type(error).__name__})
        if not isinstance(error, Exception): interruption = error
    finally:
        for descriptor, expected in ((fd, signature), (write_fd, locals().get('write_signature'))):
            if descriptor is None: continue
            try:
                if expected is not None and process_api.fd_signature(descriptor) != expected:
                    raise ValueError('owned descriptor changed before close')
                os.close(descriptor)
            except BaseException as error:
                category = category or 'descriptor_cleanup_failure'
                errors.append({'phase': 'descriptor_close', 'type': type(error).__name__})
                if not isinstance(error, Exception) and interruption is None: interruption = error
        if process is not None:
            try:
                closure = process.close()
                if closure.get('complete') is not True:
                    category = category or 'process_cleanup_unconfirmed'
            except BaseException as error:
                category = category or 'process_cleanup_failure'
                errors.append({'phase': 'process_close', 'type': type(error).__name__})
                if not isinstance(error, Exception) and interruption is None: interruption = error
    raw = bytes(prefix)
    try:
        original = retain(recorder, 'command_output_prefix', raw)
    except BaseException as error:
        category = category or 'output_custody_failure'
        errors.append({'phase': 'output_retention', 'type': type(error).__name__})
        if not isinstance(error, Exception) and interruption is None: interruption = error
    receipt = {'schema': 'dosei_raw_command_receipt_v1', 'intent': intent_binding,
               'spawn': spawn, 'closure': closure, 'observed_prefix': binding(raw),
               'retained_original': original, 'eof_observed': eof,
               'unread_output_bytes': 0 if eof else None,
               'charged_output_bytes': len(raw) if category is None else output_limit+1,
               'failure_category': category, 'errors': errors,
               'returncode': closure.get('leader_returncode') if closure else None,
               'elapsed_seconds': time.monotonic()-started,
               'success': category is None and eof and closure is not None and closure['complete'] is True}
    try:
        receipt['retained_receipt'] = retain(recorder, 'command_receipt', canonical(receipt))
    except BaseException as error:
        receipt['success'] = False
        receipt['failure_category'] = category = category or 'receipt_custody_failure'
        receipt['charged_output_bytes'] = output_limit+1
        if not isinstance(error, Exception) and interruption is None: interruption = error
    if interruption is not None: raise interruption
    if not receipt['success']: raise CommandFailure(category, receipt)
    return {'output': raw, 'receipt': receipt, 'returncode': receipt['returncode']}
