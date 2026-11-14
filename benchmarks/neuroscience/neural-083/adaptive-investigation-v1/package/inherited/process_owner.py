"""One bounded trusted child group; separate native resources remain its obligation.

All consumed stdout/stderr bytes, including the first over-limit byte, are
retained on failure. No command retry, native cleanup guess or success receipt
is synthesized. Group containment applies only to this trusted child group.
"""
import base64
import math
import os
import selectors
import signal
import subprocess
import sys
import stat
import time


class ChildFailure(RuntimeError):
    def __init__(self, record, original=None, actual_owner=None):
        super().__init__('selected trusted child did not complete')
        self.record = record
        self.original_error = original
        self.actual_owner = actual_owner


# This exact helper is embedded in the three existing owner bodies, not imported.
PROC_READ_CAP = 65_536
PROC_ENTRY_CAP = 4096
PROC_STAT_CAP = 4096


def _pinned_platform(metadata_read):
    required = ('waitid', 'P_PID', 'WEXITED', 'WNOHANG', 'WNOWAIT',
                'CLD_EXITED', 'CLD_KILLED', 'CLD_DUMPED', 'waitstatus_to_exitcode')
    if (sys.platform != 'linux' or not all(hasattr(os, name) for name in required)
            or signal.getsignal(signal.SIGCHLD) != signal.SIG_DFL
            or not callable(metadata_read)):
        raise ValueError('Linux waitid/WNOWAIT, default SIGCHLD and selected metadata budget required')
    # Explicit whole grant is charged before Popen; failed/partial scans are not refunded.
    metadata_read(PROC_READ_CAP)


class _PinnedGroup:
    """Exclusive child-reaper owner. A proc snapshot is never absence proof."""
    def __init__(self, process):
        self.process = process
        self.pid = process.pid
        self.reaped = False
        self.signals_retired = False
        self.wait_ownership_lost = False
        self.terminal = None
        self.signal_events = []
        self.post_reap_probe = False
        self.scan_started = False
        self.proc_entries = self.proc_read_reserved = self.proc_read_bytes = 0
        self.proc_prefixes = []
        self.members = []
        self.errors = []

    def observe(self, deadline, block=False):
        if self.reaped or self.wait_ownership_lost:
            raise RuntimeError('original child wait ownership unavailable')
        while True:
            if time.monotonic() >= deadline:
                raise TimeoutError('original unreaped child observation cutoff')
            try:
                found = os.waitid(os.P_PID, self.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT)
            except ChildProcessError:
                self.wait_ownership_lost = True
                raise
            if found is not None:
                if (found.si_pid != self.pid or found.si_code not in
                        (os.CLD_EXITED, os.CLD_KILLED, os.CLD_DUMPED)):
                    self.wait_ownership_lost = True
                    raise RuntimeError('unexpected original waitid identity or status')
                value = found.si_status if found.si_code == os.CLD_EXITED else -found.si_status
                if self.terminal is not None and self.terminal != value:
                    self.wait_ownership_lost = True
                    raise RuntimeError('original terminal status changed while unreaped')
                self.terminal = value
                return value
            if not block:
                return None
            time.sleep(min(.01, max(0, deadline - time.monotonic())))

    def send(self, sig, deadline):
        if self.signals_retired or self.reaped or self.wait_ownership_lost:
            raise RuntimeError('group signaling permanently retired')
        # WNOWAIT checks wait ownership immediately before every destructive signal.
        self.observe(deadline)
        if os.getpgid(self.pid) != self.pid or os.getsid(self.pid) != self.pid:
            raise RuntimeError('original leader no longer owns its new session/group')
        if time.monotonic() >= deadline:
            raise TimeoutError('original group signal cutoff')
        os.killpg(self.pid, sig)
        self.signal_events.append(int(sig))

    def _stat_body(self, root_fd, name, deadline):
        directory = handle = None
        raw = bytearray()
        self.proc_prefixes.append(raw)
        first = None
        try:
            directory = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                                dir_fd=root_fd)
            handle = os.open('stat', os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                             dir_fd=directory)
            if not stat.S_ISREG(os.fstat(handle).st_mode):
                raise ValueError('ordinary proc stat metadata required')
            while len(raw) <= PROC_STAT_CAP:
                if time.monotonic() >= deadline:
                    raise TimeoutError('original proc snapshot cutoff')
                wanted = min(256, PROC_STAT_CAP + 1 - len(raw))
                if self.proc_read_reserved + wanted > PROC_READ_CAP:
                    raise ValueError('complete proc snapshot exceeds precharged metadata grant')
                self.proc_read_reserved += wanted
                part = os.read(handle, wanted)
                self.proc_read_bytes += len(part)
                if not part:
                    break
                raw.extend(part)
            if len(raw) > PROC_STAT_CAP:
                raise ValueError('proc stat metadata cap')
        except BaseException as error:
            first = error
        finally:
            for fd in (handle, directory):
                if fd is not None:
                    try:
                        os.close(fd)
                    except BaseException as error:
                        self.errors.append(error)
                        if first is None:
                            first = error
        if first is not None:
            raise first
        return bytes(raw)

    def other_members(self, deadline):
        if self.scan_started or self.reaped or self.wait_ownership_lost or self.terminal is None:
            raise RuntimeError('one unreaped-terminal proc snapshot only')
        self.scan_started = True
        root = iterator = None
        first = None
        saw_leader = False
        try:
            root = os.open('/proc', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            iterator = os.scandir(root)
            for item in iterator:
                self.proc_entries += 1
                if self.proc_entries > PROC_ENTRY_CAP or time.monotonic() >= deadline:
                    raise ValueError('bounded complete proc name inventory')
                name = item.name
                if not name.isascii() or not name.isdigit():
                    continue
                try:
                    raw = self._stat_body(root, name, deadline)
                except (FileNotFoundError, ProcessLookupError):
                    # Vanishing proc metadata is ignorable only after known closure.
                    # Keep the original first error; raw close errors remain on this owner.
                    if self.errors:
                        raise
                    # A vanished process does not prove global absence; final probe does.
                    continue
                close = raw.rfind(b')')
                opened = raw.find(b'(')
                fields = raw[close + 1:].split() if close >= 0 else []
                if opened < 1 or close <= opened or len(fields) < 20:
                    raise ValueError('complete proc stat identity')
                pid = int(raw[:opened].strip())
                pgid, session, start = int(fields[2]), int(fields[3]), int(fields[19])
                if pid != int(name):
                    raise ValueError('proc directory/stat PID mismatch')
                if pid == self.pid:
                    if pgid != self.pid or session != self.pid or fields[0] not in (b'Z', b'X'):
                        raise ValueError('original held terminal leader identity')
                    saw_leader = True
                elif pgid == self.pid:
                    self.members.append({'pid': pid, 'start_ticks': start,
                                         'state': fields[0].decode('ascii')})
            if not saw_leader:
                raise ValueError('held leader missing from complete proc view')
            self.observe(deadline)
        except BaseException as error:
            first = error
        finally:
            for resource in (iterator,):
                if resource is not None:
                    try:
                        resource.close()
                    except BaseException as error:
                        self.errors.append(error)
                        if first is None:
                            first = error
            if root is not None:
                try:
                    os.close(root)
                except BaseException as error:
                    self.errors.append(error)
                    if first is None:
                        first = error
        if first is not None:
            raise first
        return tuple(self.members)

    def reap(self, deadline):
        # No signal can ever follow this transition, even if wait fails/times out.
        self.signals_retired = True
        if self.reaped or self.wait_ownership_lost:
            raise RuntimeError('sole original child reap unavailable')
        if time.monotonic() >= deadline:
            raise TimeoutError('original sole reap cutoff')
        # Observe terminal state without reaping, then use one nonblocking real
        # waitpid. Popen.wait can conceal ECHILD as zero; do not use that shortcut.
        self.observe(deadline, block=True)
        try:
            pid, status = os.waitpid(self.pid, os.WNOHANG)
        except ChildProcessError:
            self.wait_ownership_lost = True
            raise
        if pid != self.pid:
            self.wait_ownership_lost = True
            raise RuntimeError('sole waitpid did not return the original terminal child')
        self.reaped = True
        value = os.waitstatus_to_exitcode(status)
        self.process.returncode = value
        if value != self.terminal:
            raise RuntimeError('reaped status differs from original WNOWAIT observation')
        return value

    def absent_after_reap(self):
        if not self.reaped or not self.signals_retired or self.post_reap_probe:
            raise RuntimeError('one read-only final group probe after sole reap')
        self.post_reap_probe = True
        try:
            os.killpg(self.pid, 0)
        except ProcessLookupError:
            return True
        return False  # Includes a reused PGID; never authorize another signal.

    def evidence(self):
        return {'platform': 'linux_waitid_wnowait_proc',
                'exclusive_child_reaper_required': True,
                'leader_exit_observed_unreaped': self.terminal is not None,
                'signals_retired_before_reap': self.signals_retired,
                'wait_ownership_lost': self.wait_ownership_lost,
                'final_read_only_probe_after_reap': self.post_reap_probe,
                'proc_snapshot_is_absence_proof': False,
                'proc_metadata_reserved_bytes': PROC_READ_CAP,
                'proc_read_dispatch_reserved_bytes': self.proc_read_reserved,
                'proc_metadata_actual_bytes': self.proc_read_bytes,
                'proc_directory_entries': self.proc_entries,
                'other_group_members_observed': list(self.members),
                'proc_descriptor_closure_known': not self.errors,
                'proc_cleanup_error_types': [type(error).__name__ for error in self.errors],
                'metadata_cost_scope': 'precharged_managed_proc_reads_not_OS_internal_IO'}


def run(argv, *, normal_end, cleanup_end, env, metadata_read, stream_cap=65_536):
    if not (type(stream_cap) is int and 1 <= stream_cap <= 262_144 and
            all(type(x) in (int, float) and math.isfinite(x) for x in (normal_end, cleanup_end))
            and time.monotonic() < normal_end < cleanup_end):
        raise ValueError('finite original child selection')
    _pinned_platform(metadata_read)
    process = selector = group = None
    primary_exception = None
    data = {'stdout': bytearray(), 'stderr': bytearray()}
    eof = {'stdout': False, 'stderr': False}
    start = time.monotonic()
    record = dict(started=start, natural_exit=False, exit_code=None, process_reaped=False,
                  process_group_absent=False, stdout_eof=False, stderr_eof=False,
                  primary_error=None, cleanup_errors=[], signals_sent=[],
                  normal_end=normal_end, cleanup_end=cleanup_end, stream_cap=stream_cap)
    try:
        process = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, env=env, start_new_session=True, bufsize=0)
        group = _PinnedGroup(process)
        record['pid'] = process.pid
        selector = selectors.DefaultSelector()
        for name in data:
            stream = getattr(process, name)
            os.set_blocking(stream.fileno(), False)
            selector.register(stream, selectors.EVENT_READ, name)
        while selector.get_map():
            left = normal_end - time.monotonic()
            if left <= 0:
                raise TimeoutError('original child work deadline')
            for key, _ in selector.select(min(0.1, left)):
                name = key.data
                try:
                    block = os.read(key.fileobj.fileno(), min(16_384, stream_cap + 1 - len(data[name])))
                except BlockingIOError:
                    continue
                if not block:
                    eof[name] = True
                    selector.unregister(key.fileobj)
                    continue
                data[name].extend(block)
                if len(data[name]) > stream_cap:
                    raise ValueError('consumed stream cap exceeded: ' + name)
        left = normal_end - time.monotonic()
        if left <= 0:
            raise TimeoutError('original child wait deadline')
        record['exit_code'] = group.observe(normal_end, block=True)
        record['natural_exit'] = True
        if record['exit_code'] != 0:
            raise ValueError('child nonzero exit')
        if group.other_members(normal_end):
            raise ValueError('child group members observed after natural leader exit')
        if time.monotonic() >= normal_end:
            raise TimeoutError('natural closure after work deadline')
    except BaseException as error:
        primary_exception = error
        record['primary_error'] = dict(type=type(error).__name__, message=str(error)[:1024])
    finally:
        # Suspend an inherited alarm only while obeying the original cleanup
        # cutoff. All elapsed cleanup time is deducted before restoring it.
        saved_alarm = None
        cleanup_start = time.monotonic()
        try:
            saved_alarm = signal.setitimer(signal.ITIMER_REAL, 0)
        except BaseException as error:
            record['cleanup_errors'].append('alarm-disable:' + type(error).__name__)
        if process is not None:
            if group is None:
                record['cleanup_errors'].append('original-group-owner-unavailable')
            else:
                if record['primary_error'] is not None:
                    if time.monotonic() < cleanup_end:
                        try:
                            group.send(signal.SIGTERM, cleanup_end)
                            record['signals_sent'].append('SIGTERM')
                        except ProcessLookupError:
                            pass
                        except BaseException as error:
                            record['cleanup_errors'].append('term:' + type(error).__name__)
                    if time.monotonic() < cleanup_end:
                        try:
                            group.observe(min(cleanup_end, time.monotonic() + .5), block=True)
                        except TimeoutError:
                            pass
                        except BaseException as error:
                            record['cleanup_errors'].append('unreaped-grace:' + type(error).__name__)
                    if time.monotonic() < cleanup_end:
                        try:
                            group.send(signal.SIGKILL, cleanup_end)
                            record['signals_sent'].append('SIGKILL')
                        except ProcessLookupError:
                            pass
                        except BaseException as error:
                            record['cleanup_errors'].append('kill:' + type(error).__name__)
                try:
                    record['exit_code'] = group.reap(cleanup_end)
                    record['process_reaped'] = True
                except BaseException as error:
                    record['cleanup_errors'].append('sole-reap:' + type(error).__name__)
                if group.reaped:
                    try:
                        record['process_group_absent'] = group.absent_after_reap()
                    except BaseException as error:
                        record['cleanup_errors'].append('final-read-only-group-probe:' + type(error).__name__)
                record['cleanup_errors'].extend('proc-close:' + type(error).__name__
                                                for error in group.errors)
                record['process_ownership'] = group.evidence()
        if selector is not None:
            try:
                selector.close()
            except BaseException as error:
                record['cleanup_errors'].append('selector-close:' + type(error).__name__)
        if process is not None:
            for name in data:
                try:
                    getattr(process, name).close()
                except BaseException as error:
                    record['cleanup_errors'].append(name + '-close:' + type(error).__name__)
        # Capture the exact consumed prefixes before any parent-alarm handback.
        record.update(stdout_eof=eof['stdout'], stderr_eof=eof['stderr'],
                      stdout_base64=base64.b64encode(data['stdout']).decode('ascii'),
                      stderr_base64=base64.b64encode(data['stderr']).decode('ascii'),
                      consumed_bytes={k: len(v) for k, v in data.items()},
                      finished=time.monotonic(), elapsed=time.monotonic()-start,
                      native_resource_closure_inferred=False,
                      parent_alarm_expired_during_cleanup=False, parent_alarm_restored=False)
    try:
        if saved_alarm is not None and saved_alarm[0] > 0:
            remaining = saved_alarm[0] - (time.monotonic()-cleanup_start)
            if remaining <= 0:
                record['parent_alarm_expired_during_cleanup'] = True
                record['cleanup_errors'].append('inherited-parent-alarm-exhausted-during-cleanup')
                if record['primary_error'] is None:
                    primary_exception = TimeoutError('inherited parent alarm exhausted during cleanup')
                    record['primary_error'] = dict(type='TimeoutError',
                        message='inherited parent alarm exhausted during cleanup')
                # Never turn already exhausted time into a new one-microsecond
                # asynchronous exception that can discard the actual record.
            else:
                signal.setitimer(signal.ITIMER_REAL, remaining, saved_alarm[1])
                record['parent_alarm_restored'] = True
        record['finished'] = time.monotonic()
        record['elapsed'] = record['finished'] - start
        good = (group is not None and not group.errors and
                record['primary_error'] is None and not record['cleanup_errors'] and
                record['natural_exit'] and type(record['exit_code']) is int and record['exit_code'] == 0 and
                record['process_reaped'] and record['process_group_absent'] and all(eof.values()) and
                record['finished'] < normal_end)
        if not good:
            raise ChildFailure(record, primary_exception, group)
        return record
    except ChildFailure:
        raise
    except BaseException as error:
        # Includes a one-shot parent handler firing during restoration. Prefixes
        # already exist, and the original error is never overwritten.
        record['cleanup_errors'].append('parent-alarm-handback:' + type(error).__name__)
        if record['primary_error'] is None:
            primary_exception = error
            record['primary_error'] = dict(type=type(error).__name__, message=str(error)[:1024])
        record['finished'] = time.monotonic()
        record['elapsed'] = record['finished'] - start
        raise ChildFailure(record, primary_exception, group) from error
