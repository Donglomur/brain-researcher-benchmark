"""Stdlib child ownership established before launch, independent of persistence.
A bounded wait may remain unresolved; that state is never relabelled completion.
Also mounted as a trusted standalone module for the container supervisor.
"""
import os
import signal
import subprocess
import sys
import time


class ProcessCustodyError(RuntimeError):
    def __init__(self, message, observation):
        super().__init__(message)
        self.original_observation = observation


class OwnedProcess:
    def __init__(self, command, wall_s, cleanup_s, group=True):
        self.command = command
        self.wall_s = wall_s
        self.cleanup_s = cleanup_s
        self.group = group
        self.proc = None
        self.started = None
        self.observation = {'argv': command, 'launched': False, 'wait_completed': False,
                            'exit_code': None, 'cpu_s': None, 'cleanup_errors': [], 'timeout': False,
                            'forced_wait_completed': False, 'group_quiescent': False if group else None,
                            'containment_scope': 'original_process_group' if group else 'direct_child_only',
                            'descendant_wait_receipts': [], 'descendant_usage_qualified': False}

    def __enter__(self):
        return self

    def start(self, **kwargs):
        if self.proc is not None:
            raise RuntimeError('Owned child cannot be relaunched')
        self.started = time.monotonic()
        # The object is already registered and under __exit__ before Popen.
        self.proc = subprocess.Popen(self.command, **kwargs)
        self.observation.update({'launched': True, 'pid': self.proc.pid})
        if self.group:
            try:
                pgid = os.getpgid(self.proc.pid)
                self.observation.update({'original_pgid': pgid, 'group_identity_verified': pgid == self.proc.pid})
                if pgid != self.proc.pid:
                    raise ProcessCustodyError('Owned child did not create its selected process group', dict(self.observation))
            except BaseException:
                self.observation['group_identity_unresolved'] = True
                raise
        return self.proc

    def _kill(self):
        # Never re-signal a PID after an original-wait identity failure. A PID
        # could have been reaped/reused; the explicit hold needs outside recovery.
        if (self.observation.get('kill_requested') or self.observation.get('wait_identity_unresolved') or
                self.observation.get('group_identity_unresolved') or self.observation['wait_completed']):
            return
        try:
            (os.killpg if self.group and self.observation.get('group_identity_verified') else os.kill)(self.proc.pid, signal.SIGKILL)
            self.observation['kill_requested'] = True
        except ProcessLookupError:
            pass  # A subsequent original wait is still required.
        except BaseException as error:
            self.observation['cleanup_errors'].append(type(error).__name__ + ': ' + str(error))

    def _containment(self):
        """Observe original group absence separately; never invent descendant waits.

        A nonempty/unknown group is an unresolved hold, not permission to signal a
        recycled PID after leader reaping. The first unresolved observation is
        terminal for this ownership record; later recovery is separate evidence.
        """
        if not self.group:
            return
        if self.observation.get('group_quiescent'):
            return
        if self.observation.get('group_containment_unresolved'):
            raise ProcessCustodyError('Original process-group custody unresolved', dict(self.observation))
        detail = {'observed_monotonic': time.monotonic(), 'leader_wait_completed': self.observation['wait_completed'],
                  'pgid': self.observation.get('original_pgid'), 'method': 'killpg_signal_zero_only',
                  'not_an_original_descendant_wait': True}
        try:
            if not self.observation.get('group_identity_verified'):
                raise RuntimeError('Original group identity was not established before wait')
            os.killpg(self.observation['original_pgid'], 0)
        except ProcessLookupError:
            detail['state'] = 'ABSENT';self.observation['group_quiescent'] = True
            self.observation['group_containment_observation'] = detail
            return
        except BaseException as error:
            detail.update(state='UNKNOWN', error=type(error).__name__ + ': ' + str(error))
        else:
            detail['state'] = 'PRESENT_AFTER_LEADER_WAIT'
        self.observation.update({'group_containment_observation': detail,
                                 'group_containment_unresolved': True, 'unresolved_hold': True})
        raise ProcessCustodyError('Original process-group custody unresolved', dict(self.observation))

    def wait(self, force=False):
        if self.proc is None:
            return self.observation
        if self.observation['wait_completed']:
            self._containment()
            return self.observation
        deadline = self.started + self.wall_s
        cleanup_deadline = time.monotonic() + self.cleanup_s if force else None
        if force:
            self._kill()
        while True:
            try:
                pid, status, usage = os.wait4(self.proc.pid, os.WNOHANG)
            except InterruptedError:
                continue
            except BaseException as error:
                self.observation['wait_identity_unresolved'] = True
                self.observation['cleanup_errors'].append(type(error).__name__ + ': ' + str(error))
                break
            if pid:
                self.proc.returncode = os.waitstatus_to_exitcode(status)
                self.observation.update({'wait_completed': True, 'forced_wait_completed': bool(self.observation.get('kill_requested')),
                    'leader_wait_observed_monotonic': time.monotonic(),
                    'exit_code': self.proc.returncode, 'signal': -self.proc.returncode if self.proc.returncode < 0 else None,
                    'wall_s': time.monotonic() - self.started, 'cpu_s': usage.ru_utime + usage.ru_stime,
                    'peak_rss_bytes': usage.ru_maxrss * (1 if sys.platform == 'darwin' else 1024),
                    'io_blocks': {'input': usage.ru_inblock, 'output': usage.ru_oublock}})
                self._containment()
                return self.observation
            now = time.monotonic()
            if cleanup_deadline is None and now >= deadline:
                self.observation['timeout'] = True
                self._kill()
                cleanup_deadline = now + self.cleanup_s
            if cleanup_deadline is not None and now >= cleanup_deadline:
                self.observation['cleanup_errors'].append('Bounded original wait deadline exhausted')
                break
            time.sleep(.005)
        self.observation['unresolved_hold'] = True
        raise ProcessCustodyError('Original child wait unresolved', dict(self.observation))

    def __exit__(self, kind, error, traceback):
        if error is not None:
            self.observation.setdefault('primary_error', type(error).__name__ + ': ' + str(error))
        try:
            self.wait(force=error is not None)
        except BaseException as cleanup:
            self.observation['unresolved_hold'] = True
            if error is None:
                raise
            # Never replace the first failure with cleanup or persistence failure.
            self.observation['cleanup_errors'].append(type(cleanup).__name__ + ': ' + str(cleanup))
        return False

    @property
    def settled(self):
        return self.proc is None or (self.observation['wait_completed'] and
                                    (not self.group or self.observation.get('group_quiescent') is True))
