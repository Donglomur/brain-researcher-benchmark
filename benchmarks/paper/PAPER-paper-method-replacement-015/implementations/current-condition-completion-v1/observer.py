"""Bound and preserve both streams of the exact trusted campaign worker.

Owned host process-group closure is not inferred Docker resource closure. The
unchanged per-fold lifecycle must establish those separate container receipts.
"""
import os
import selectors
import signal
import subprocess
import time

from source import need

PIPE_CAP = 65536


class Failure(RuntimeError):
    def __init__(self, observation, stdout, stderr):
        super().__init__('trusted campaign worker did not complete')
        self.observation, self.stdout, self.stderr = observation, stdout, stderr


def absent(pgid):
    try:
        os.killpg(pgid, 0)
    except ProcessLookupError:
        return True
    return False


def observe(argv, deadline, env):
    start = time.monotonic()
    need(deadline - start > 45, 'complete worker observation and cleanup window')
    record = {'natural_exit': False, 'process_reaped': False, 'streams_closed': False,
              'exit_code': None, 'error_type': None, 'kill_sent': False,
              'owned_host_group_absent': False, 'container_absence_inferred': False,
              'cleanup_errors': {}, 'output_overflow': False}
    proc = None
    selector = None
    buffers = {'stdout': bytearray(), 'stderr': bytearray()}
    try:
        proc = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, start_new_session=True,
                                close_fds=True, env=env, bufsize=0, umask=0o077)
        record['pid'] = proc.pid
        selector = selectors.DefaultSelector()
        for name, stream in (('stdout', proc.stdout), ('stderr', proc.stderr)):
            os.set_blocking(stream.fileno(), False)
            selector.register(stream, selectors.EVENT_READ, name)
        while selector.get_map():
            left = deadline - time.monotonic() - 40
            need(left > 0, 'worker observation deadline')
            for key, _ in selector.select(min(left, .1)):
                remaining = PIPE_CAP - sum(map(len, buffers.values()))
                try:
                    chunk = os.read(key.fileobj.fileno(), min(8192, remaining + 1))
                except BlockingIOError:
                    continue
                if not chunk:
                    selector.unregister(key.fileobj)
                    continue
                buffers[key.data].extend(chunk[:remaining])
                if len(chunk) > remaining:
                    record['output_overflow'] = True
                need(len(chunk) <= remaining, 'combined trusted worker stream cap')
        code = proc.wait(timeout=max(.001, deadline - time.monotonic() - 40))
        record.update(natural_exit=True, process_reaped=True, exit_code=code,
                      owned_host_group_absent=absent(proc.pid))
        need(code == 0 and record['owned_host_group_absent'],
             'natural zero worker exit and no remaining owned host process group')
    except BaseException as error:
        record['error_type'] = type(error).__name__
    finally:
        if proc is not None and not record['process_reaped']:
            # The original worker alarm raises into its normal per-fold finally.
            # Only that owned worker/group is signalled; no daemon-wide cleanup.
            try:
                os.kill(proc.pid, signal.SIGALRM)
            except ProcessLookupError:
                pass
            except BaseException as error:
                record['cleanup_errors']['alarm'] = type(error).__name__
            try:
                record['exit_code'] = proc.wait(timeout=max(.001, min(35, deadline - time.monotonic() - 5)))
                record['process_reaped'] = True
            except BaseException as error:
                record['cleanup_errors']['grace_wait'] = type(error).__name__
        group_absent = False
        if proc is not None:
            try:
                group_absent = absent(proc.pid)
            except BaseException as error:
                record['cleanup_errors']['group_observation'] = type(error).__name__
        if proc is not None and (not record['process_reaped'] or not group_absent):
            try:
                os.killpg(proc.pid, signal.SIGKILL)
                record['kill_sent'] = True
            except ProcessLookupError:
                pass
            except BaseException as error:
                record['cleanup_errors']['kill'] = type(error).__name__
            try:
                record['exit_code'] = proc.wait(timeout=max(.001, min(5, deadline - time.monotonic())))
                record['process_reaped'] = True
            except BaseException as error:
                record['cleanup_errors']['final_wait'] = type(error).__name__
        closed = True
        if selector is not None:
            try:
                selector.close()
            except BaseException as error:
                closed = False
                record['cleanup_errors']['selector_close'] = type(error).__name__
        if proc is not None:
            for stream in (proc.stdout, proc.stderr):
                try:
                    stream.close()
                except BaseException as error:
                    closed = False
                    record['cleanup_errors']['stream_close'] = type(error).__name__
            try:
                record['owned_host_group_absent'] = absent(proc.pid)
            except BaseException as error:
                record['owned_host_group_absent'] = False
                record['cleanup_errors']['final_group_observation'] = type(error).__name__
        record.update(streams_closed=closed, stdout_bytes=len(buffers['stdout']),
                      stderr_bytes=len(buffers['stderr']), elapsed_seconds=time.monotonic() - start)
    good = (record['natural_exit'] and record['process_reaped'] and record['streams_closed']
            and record['exit_code'] == 0 and record['error_type'] is None
            and not record['kill_sent'] and record['owned_host_group_absent']
            and not record['cleanup_errors'] and not record['output_overflow']
            and time.monotonic() < deadline)
    result = bytes(buffers['stdout']), bytes(buffers['stderr']), record
    if not good:
        raise Failure(record, result[0], result[1])
    return result
