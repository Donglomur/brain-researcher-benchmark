"""Observe the trusted NEURAL089 controller process group; native resources have separate closure."""
import os
import selectors
import signal
import subprocess
import time

CAP = 65536


class ChildFailure(RuntimeError):
    def __init__(self, record):
        super().__init__('trusted_stager_child_failed')
        self.record = record


def group_absent(pid):
    try:
        os.killpg(pid, 0)
    except ProcessLookupError:
        return True
    return False


def run(argv, normal_end, cleanup_end, env):
    p = sel = None
    output = bytearray()
    count = 0
    start = time.monotonic()
    record = dict(natural_exit=False, exit_code=None, process_reaped=False,
                  process_group_absent=False, streams_closed=False,
                  timed_out=False, kill_sent=False, error_type=None,
                  timer_disable_error=None, timer_restore_error=None)
    try:
        if not start < normal_end < cleanup_end:
            raise ValueError('child_deadlines')
        p = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, start_new_session=True,
                             env=env, bufsize=0)
        record['pid'] = p.pid
        sel = selectors.DefaultSelector()
        for key, stream in [('out', p.stdout), ('err', p.stderr)]:
            os.set_blocking(stream.fileno(), False)
            sel.register(stream, selectors.EVENT_READ, key)
        while sel.get_map():
            left = normal_end - time.monotonic()
            if left <= 0:
                raise TimeoutError('stager_duration')
            for key, _ in sel.select(min(left, .1)):
                try:
                    block = os.read(key.fileobj.fileno(), min(8192, CAP + 1 - count))
                except BlockingIOError:
                    continue
                if not block:
                    sel.unregister(key.fileobj)
                    continue
                count += len(block)
                if count > CAP:
                    raise ValueError('combined_stream_cap')
                if key.data == 'out':
                    output.extend(block)
        left = normal_end - time.monotonic()
        if left <= 0:
            raise TimeoutError('stager_exit_deadline')
        record['exit_code'] = p.wait(timeout=left)
        record['process_reaped'] = True
        record['natural_exit'] = True
        if record['exit_code'] != 0 or not group_absent(p.pid):
            raise ValueError('natural_zero_and_group_absence')
    except BaseException as error:
        record['error_type'] = type(error).__name__
        record['timed_out'] = isinstance(error, (TimeoutError, subprocess.TimeoutExpired))
    finally:
        # The parent alarm is suspended only for this bounded owned-group cleanup.
        cleanup_start = time.monotonic()
        alarm = (0.0, 0.0)
        try:
            try:
                alarm = signal.setitimer(signal.ITIMER_REAL, 0)
            except BaseException as error:
                record['timer_disable_error'] = type(error).__name__
                if record['error_type'] is None:
                    record['error_type'] = type(error).__name__
                record['timed_out'] = record['timed_out'] or isinstance(error, (TimeoutError, subprocess.TimeoutExpired))
            if p is not None:
                try:
                    absent = group_absent(p.pid)
                except BaseException:
                    absent = False
                if not record['process_reaped'] or not absent:
                    try:
                        os.killpg(p.pid, signal.SIGTERM)
                    except ProcessLookupError:
                        pass
                    except BaseException:
                        pass
                    if not record['process_reaped']:
                        try:
                            record['exit_code'] = p.wait(timeout=max(.001, min(5, cleanup_end - time.monotonic() - 5)))
                            record['process_reaped'] = True
                        except BaseException:
                            pass
                    try:
                        absent = group_absent(p.pid)
                    except BaseException:
                        absent = False
                    if not record['process_reaped'] or not absent:
                        try:
                            os.killpg(p.pid, signal.SIGKILL)
                            record['kill_sent'] = True
                        except ProcessLookupError:
                            pass
                        except BaseException:
                            pass
                        if not record['process_reaped']:
                            try:
                                record['exit_code'] = p.wait(timeout=max(.001, min(5, cleanup_end - time.monotonic())))
                                record['process_reaped'] = True
                            except BaseException:
                                pass
                try:
                    record['process_group_absent'] = group_absent(p.pid)
                except BaseException:
                    record['process_group_absent'] = False
        finally:
            closed = True
            if sel is not None:
                try:
                    sel.close()
                except BaseException:
                    closed = False
            if p is not None:
                for stream in (p.stdout, p.stderr):
                    if stream is not None:
                        try:
                            stream.close()
                        except BaseException:
                            closed = False
            record.update(streams_closed=closed, combined_stream_bytes=count,
                          stdout_bytes=len(output), elapsed_seconds=time.monotonic() - start)
            if alarm[0] > 0:
                try:
                    signal.setitimer(signal.ITIMER_REAL, max(.001, alarm[0] - (time.monotonic() - cleanup_start)))
                except BaseException as error:
                    record['timer_restore_error'] = type(error).__name__
                    if record['error_type'] is None:
                        record['error_type'] = type(error).__name__
                    record['timed_out'] = record['timed_out'] or isinstance(error, (TimeoutError, subprocess.TimeoutExpired))
    good = (record['error_type'] is None and record['natural_exit'] and record['exit_code'] == 0
            and record['process_reaped'] and record['process_group_absent'] and record['streams_closed']
            and time.monotonic() < cleanup_end)
    if not good:
        raise ChildFailure(record)
    return bytes(output), record
