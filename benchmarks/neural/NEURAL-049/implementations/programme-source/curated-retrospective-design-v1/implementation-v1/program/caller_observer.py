"""Bounded caller observation of the unchanged NEURAL060 outer process.

Derived from the authenticated neural-program-f/program/process.py (6,710 B,
791ea3b0bab72ef4487b3c3fdd47a828f8effaa27ebf7a6872e3b4ed324e074d).
This observes the newly created process group and NEVER sends a mutating signal.
Forced cleanup is deliberately unavailable; uncertain survivors require separately
selected inspection. A numeric PID/PGID never confers signal custody. Nested worker/container custody
must be independently established by the original outer journal and observer.
No target/model/prediction body is opened here. Both stream prefixes survive a
failure; incomplete EOF, cleanup or timer facts never become success.
"""
import math
import os
import selectors
import signal
import subprocess
import time

CAP = 65536
CHUNK = 8192


class ChildFailure(RuntimeError):
    def __init__(self, bundle):
        super().__init__('neural060_caller_child_failed')
        self.bundle = bundle
        self.record = bundle['record']
        self.stdout = bundle['stdout']
        self.stderr = bundle['stderr']


def group_absent(pid):
    try:
        os.killpg(pid, 0)
    except ProcessLookupError:
        return True
    return False


def number(value):
    return type(value) in (int, float) and math.isfinite(value)


def run(argv, normal_end, cleanup_end, env, cwd):
    """Return {stdout:bytes, stderr:bytes, record:dict}, or ChildFailure(bundle).

    Deadlines are caller-selected absolute host monotonic times. Neither is
    recomputed from this start; an expired deadline cannot acquire extra time.
    The caller must independently reserve memory/output and authenticate source,
    command, environment, cwd, root origin and both selected deadline values.
    """
    p = sel = None
    streams = {'stdout': bytearray(), 'stderr': bytearray()}
    eof = {'stdout': False, 'stderr': False}
    observed = {'stdout': 0, 'stderr': 0}
    start = time.monotonic()
    record = dict(schema='neural060_caller_observation_v1', pid=None,
                  argv=list(argv) if isinstance(argv, (list, tuple)) else None,
                  cwd=cwd, observed_start=start, observed_end=None,
                  normal_end=normal_end, cleanup_end=cleanup_end,
                  normal_deadline=normal_end, cleanup_deadline=cleanup_end,
                  spawn_attempted=False,
                  spawn_returned=False, natural_exit=False, exit_code=None,
                  process_reaped=False, process_group_absent=False,
                  group_probe_error=None, streams_closed=False,
                  selector_closed=False, timed_out=False,
                  term_attempted=False, term_sent=False, term_error=None,
                  kill_attempted=False, kill_sent=False, kill_error=None,
                  cleanup_attempted=False, cleanup_deadline_exhausted=False,
                  cleanup_wait_error=None, error_type=None, error_message=None,
                  error_stage=None, timer_disable_attempted=False,
                  timer_disable_error=None, timer_restore_attempted=False,
                  timer_restore_error=None, timer_previous=None,
                  timer_restore_value=None, parent_timer_elapsed=False,
                  output_overflow=False, normal_closed_at=None,
                  final_closed_at=None, unknown_nested_resource_state=True)
    stage = 'admission'
    record.update(cleanup_mode='observation_and_bounded_wait_only',
                  mutating_signals_disabled=True, no_mutating_signals=True,
                  mutating_signal_count=0, forced_termination_supported=False,
                  wait_attempted=False, cleanup_ownership_unknown=False,
                  forced_termination_available=False)

    def fail(error, where):
        if record['error_type'] is None:
            record.update(error_type=type(error).__name__,
                          error_message=str(error)[:256], error_stage=where)
        if isinstance(error, (TimeoutError, subprocess.TimeoutExpired)):
            record['timed_out'] = True

    def probe():
        if time.monotonic() >= cleanup_end:
            record['cleanup_deadline_exhausted'] = True
            record['process_group_absent'] = False
            return False
        try:
            value = group_absent(p.pid)
            record['process_group_absent'] = value
            return value
        except BaseException as error:
            record['group_probe_error'] = type(error).__name__
            record['process_group_absent'] = False
            fail(error, 'group_probe')
            return False

    def reap_until(end):
        if record['process_reaped'] or record['wait_attempted']:
            return
        left = end - time.monotonic()
        if left <= 0:
            record['cleanup_deadline_exhausted'] = time.monotonic() >= cleanup_end
            return
        try:
            # A wait can reap before raising; never issue a second wait after it.
            record['wait_attempted'] = True
            code = p.wait(timeout=left)
            if type(code) is not int:
                raise TypeError('non_integer_exit_status')
            record['exit_code'] = code
            record['process_reaped'] = True
        except BaseException as error:
            record['cleanup_wait_error'] = type(error).__name__
            record['cleanup_ownership_unknown'] = True
            # Reaping outcome may be unknown. No signals or retry follow.
            if not isinstance(error, subprocess.TimeoutExpired):
                fail(error, 'cleanup_wait')

    try:
        if not (number(start) and number(normal_end) and number(cleanup_end)
                and start < normal_end < cleanup_end):
            raise ValueError('caller_absolute_deadlines')
        if (not isinstance(argv, (list, tuple)) or not argv
                or any(type(x) is not str or not x or '\x00' in x for x in argv)):
            raise ValueError('caller_argv')
        if (type(env) is not dict or any(type(k) is not str or not k
                or '=' in k or '\x00' in k or type(v) is not str or '\x00' in v
                for k, v in env.items())):
            raise ValueError('caller_environment')
        if type(cwd) is not str or not os.path.isabs(cwd) or '\x00' in cwd:
            raise ValueError('caller_cwd')
        stage = 'spawn'
        record['spawn_attempted'] = True
        p = subprocess.Popen(list(argv), stdin=subprocess.DEVNULL,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             start_new_session=True, env=env, cwd=cwd, bufsize=0)
        record.update(pid=p.pid, spawn_returned=True)
        stage = 'stream_setup'
        sel = selectors.DefaultSelector()
        for name, stream in (('stdout', p.stdout), ('stderr', p.stderr)):
            os.set_blocking(stream.fileno(), False)
            sel.register(stream, selectors.EVENT_READ, name)
        stage = 'stream_read'
        while sel.get_map():
            left = normal_end - time.monotonic()
            if left <= 0:
                raise TimeoutError('caller_stream_deadline')
            for key, _ in sel.select(min(left, .1)):
                if time.monotonic() >= normal_end:
                    raise TimeoutError('caller_stream_deadline')
                room = CAP - sum(len(x) for x in streams.values())
                try:
                    block = os.read(key.fileobj.fileno(), min(CHUNK, room + 1))
                except BlockingIOError:
                    continue
                if not block:
                    eof[key.data] = True
                    sel.unregister(key.fileobj)
                    continue
                observed[key.data] += len(block)
                streams[key.data].extend(block[:room])
                if len(block) > room:
                    record['output_overflow'] = True
                    raise ValueError('caller_combined_stream_cap')
        stage = 'natural_wait'
        left = normal_end - time.monotonic()
        if left <= 0:
            raise TimeoutError('caller_exit_deadline')
        record['wait_attempted'] = True
        code = p.wait(timeout=left)
        if type(code) is not int:
            raise TypeError('non_integer_exit_status')
        record.update(exit_code=code, process_reaped=True, natural_exit=True)
        stage = 'natural_group'
        if code != 0 or not probe():
            raise ValueError('caller_natural_zero_and_group_absence')
        record['normal_closed_at'] = time.monotonic()
        if record['normal_closed_at'] >= normal_end:
            raise TimeoutError('caller_natural_closure_deadline')
    except BaseException as error:
        fail(error, stage)
    finally:
        cleanup_start = time.monotonic()
        alarm = None
        if p is not None:
            record['timer_disable_attempted'] = True
            try:
                alarm = signal.setitimer(signal.ITIMER_REAL, 0)
                record['timer_previous'] = list(alarm)
            except BaseException as error:
                record['timer_disable_error'] = type(error).__name__
                fail(error, 'timer_disable')
            try:
                absent = probe()
                if not record['process_reaped'] or not absent:
                    record['cleanup_attempted'] = True
                    # Root-selected limited cleanup: observe and at most one
                    # bounded wait. Never signal a PID, PGID or pidfd, including
                    # when the numeric group survives or is already reused.
                    reap_until(cleanup_end)
                    absent = probe()
                    if not record['process_reaped'] or not absent:
                        record['cleanup_ownership_unknown'] = True
            except BaseException as error:
                record['cleanup_ownership_unknown'] = True
                fail(error, 'cleanup')
        closed = True
        if sel is not None:
            try:
                sel.close()
                record['selector_closed'] = True
            except BaseException as error:
                closed = False
                fail(error, 'selector_close')
        if p is not None:
            for stream in (p.stdout, p.stderr):
                if stream is not None:
                    try:
                        stream.close()
                    except BaseException as error:
                        closed = False
                        fail(error, 'stream_close')
        record['streams_closed'] = p is not None and closed
        if alarm is not None and alarm[0] > 0:
            record['timer_restore_attempted'] = True
            remaining = alarm[0] - (time.monotonic() - cleanup_start)
            if remaining <= 0:
                record['parent_timer_elapsed'] = True
                fail(TimeoutError('inherited_timer_elapsed_during_cleanup'), 'timer_restore')
            try:
                # Restore the old absolute expiry, including its repeat interval.
                # If already expired, promptly deliver the pending alarm; this
                # path is failed, not a grant of a new successful grace period.
                value = max(.000001, remaining)
                signal.setitimer(signal.ITIMER_REAL, value, alarm[1])
                record['timer_restore_value'] = [value, alarm[1]]
            except BaseException as error:
                record['timer_restore_error'] = type(error).__name__
                fail(error, 'timer_restore')
        end = time.monotonic()
        if number(cleanup_end) and end >= cleanup_end:
            record['cleanup_deadline_exhausted'] = True
        record['cleanup_ownership_unknown'] = (record['cleanup_ownership_unknown'] or
            (record['spawn_attempted'] and not record['spawn_returned']) or
            (record['spawn_returned'] and (not record['process_reaped'] or not record['process_group_absent'])))
        record.update(failed_unknown_child_state=record['cleanup_ownership_unknown'],
                      requires_separate_child_inspection=record['cleanup_ownership_unknown'],
                      spawn_ownership_unknown=(record['spawn_attempted'] and not record['spawn_returned']),
                      stdout_eof=eof['stdout'], stderr_eof=eof['stderr'],
                      stdout_bytes=len(streams['stdout']), stderr_bytes=len(streams['stderr']),
                      observed_stdout_bytes=observed['stdout'],
                      observed_stderr_bytes=observed['stderr'],
                      combined_stream_bytes=sum(observed.values()),
                      retained_stream_bytes=sum(len(x) for x in streams.values()),
                      final_closed_at=end, observed_end=end, elapsed_seconds=end - start,
                      cleanup_elapsed_seconds=end - cleanup_start,
                      physical_io_bytes=None, total_host_rss_bytes=None)
    good = (record['error_type'] is None and record['natural_exit']
            and type(record['exit_code']) is int and record['exit_code'] == 0
            and record['process_reaped'] and record['process_group_absent']
            and record['streams_closed'] and record['selector_closed']
            and all(eof.values()) and not record['cleanup_attempted']
            and not record['timed_out'] and not record['parent_timer_elapsed']
            and not record['cleanup_ownership_unknown']
            and number(normal_end) and record['final_closed_at'] < normal_end)
    record['successful_observation'] = good
    bundle = dict(stdout=bytes(streams['stdout']), stderr=bytes(streams['stderr']), record=record)
    if not good:
        if record['error_type'] is None:
            fail(TimeoutError('caller_final_closure_deadline'), 'final_admission')
        raise ChildFailure(bundle)
    return bundle
