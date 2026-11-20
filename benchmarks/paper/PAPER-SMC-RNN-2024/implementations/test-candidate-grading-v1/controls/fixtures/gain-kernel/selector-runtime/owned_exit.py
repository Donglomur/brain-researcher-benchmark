"""Keep an exclusively owned session leader unreaped until group cleanup.

Call preflight before Popen(start_new_session=True), then construct ExitObserver
immediately. The trusted launcher must use start_new_session=True; this module
does not infer that fact from a Popen handle. Its initial group is therefore the
child PID. Do not rediscover that identity with getpgid after exit: Darwin may
exclude an unreaped zombie from that query. No other code may poll, wait, communicate, reap, change SIGCHLD or
install native SA_NOCLDWAIT while this owner is active. The trusted parent must
not have a native auto-reap policy; Python's signal handler query cannot prove
that absence. These are operator-process preconditions, not a hostile-parent
sandbox. A group signal does not contain descendants which escaped that group.

The existing viewer transports retain their own protocols, deadlines, journals
and child pipes. This helper neither launches code nor reads scientific inputs.
"""
from __future__ import annotations

import errno
import math
import os
import select
import signal
import subprocess
import sys
import time


def _default_sigchld():
    return hasattr(signal, 'SIGCHLD') and signal.getsignal(signal.SIGCHLD) == signal.SIG_DFL


def preflight():
    """Refuse unsupported observers or a declared reaping handler before launch."""
    if not _default_sigchld():
        raise RuntimeError('Exclusive default-SIGCHLD ownership required')
    if sys.platform == 'darwin' and all(hasattr(select, name) for name in
            ('kqueue', 'kevent', 'KQ_FILTER_PROC', 'KQ_EV_ADD', 'KQ_EV_ONESHOT',
             'KQ_EV_ERROR', 'KQ_NOTE_EXIT')):
        return 'darwin_kqueue'
    if sys.platform.startswith('linux') and hasattr(os, 'pidfd_open'):
        return 'linux_pidfd'
    raise RuntimeError('Non-reaping exit observation is unavailable')


def _owned(child):
    # Do not replace this direct attribute access with Popen.poll(): poll reaps.
    return type(child.pid) is int and child.pid > 1 and child.returncode is None


def _remaining(deadline):
    if type(deadline) not in (float, int) or not math.isfinite(deadline):
        raise ValueError('Finite absolute monotonic deadline required')
    return max(0.0, deadline - time.monotonic())


class ExitObserver:
    """Kernel exit notification without consuming the child's exit status."""
    def __init__(self, child):
        self.child = child
        self.backend = preflight()
        self.exit_observed = False
        self.closed = False
        self.fd = None
        self.queue = None
        if not _owned(child):
            raise RuntimeError('Unreaped child handle required')
        try:
            if self.backend == 'linux_pidfd':
                self.fd = os.pidfd_open(child.pid, 0)
                os.set_inheritable(self.fd, False)
            else:
                self.queue = select.kqueue()
                event = select.kevent(child.pid, filter=select.KQ_FILTER_PROC,
                                     flags=select.KQ_EV_ADD | select.KQ_EV_ONESHOT,
                                     fflags=select.KQ_NOTE_EXIT)
                self._events(self.queue.control([event], 1, 0))
        except BaseException:
            # ESRCH during Darwin registration is not resolved by poll()/wait().
            # The caller still owns its unreaped child and must enter cleanup.
            self.close()
            raise

    def _events(self, events):
        for event in events:
            if event.flags & select.KQ_EV_ERROR:
                raise OSError(event.data, 'Process observation registration failed')
            if event.ident != self.child.pid or event.filter != select.KQ_FILTER_PROC:
                raise RuntimeError('Unexpected process observation')
            if not event.fflags & select.KQ_NOTE_EXIT:
                raise RuntimeError('Exit event required')
            self.exit_observed = True

    def wait(self, deadline):
        if self.closed or not _owned(self.child) or not _default_sigchld():
            raise RuntimeError('Exclusive unreaped child ownership was lost')
        remaining = _remaining(deadline)
        if self.exit_observed:
            return True
        if self.backend == 'linux_pidfd':
            ready, _, _ = select.select([self.fd], [], [], remaining)
            self.exit_observed = bool(ready)
        else:
            self._events(self.queue.control(None, 1, remaining))
        return self.exit_observed

    def close(self):
        if self.closed:
            return
        self.closed = True
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None
        if self.queue is not None:
            self.queue.close()
            self.queue = None


def stop_and_reap(child, observer, deadline):
    """Signal the owned group before the sole wait; never signal it after reap.

After reaping, signal 0 only observes possible group presence. PID reuse can
therefore cause a conservative failure, but cannot cause a signal to a new group.
No receipt establishes containment of descendants which changed process group.
"""
    _remaining(deadline)
    result = {'schema': 'viewer-owned-process-cleanup/v1', 'pid': child.pid,
              'exit_observed_before_stop': bool(observer and observer.exit_observed),
              'leader_unreaped_before_signal': False, 'group_signal': 'not_attempted',
              'group_signal_errno': None, 'reaped': False, 'returncode': child.returncode,
              'group_absence_observed': False, 'cleanup_complete': False,
              'descendant_containment_qualified': False, 'error': None}
    try:
        if not _owned(child):
            result['error'] = 'reaped_or_invalid_child'
            return result
        if not _default_sigchld():
            result['error'] = 'sigchld_policy_changed'
            return result
        if observer is not None and observer.child is not child:
            result['error'] = 'observer_child_mismatch'
            return result
        # The trusted Popen(start_new_session=True) call established this group
        # before child code ran. Exclusive unreaped custody reserves its PID.
        # A fresh getpgid query is neither needed nor reliable for Darwin zombies.
        result['leader_unreaped_before_signal'] = True
        try:
            os.killpg(child.pid, signal.SIGKILL)
            result['group_signal'] = 'sent'
        except ProcessLookupError:
            result['group_signal'] = 'absent'
        except OSError as exc:
            result['group_signal'] = 'permission_denied' if exc.errno == errno.EPERM else 'error'
            result['group_signal_errno'] = exc.errno
        # No signal to this numeric group occurs below this point. The leader is
        # still unreaped when wait starts, including the Darwin zombie-EPERM case.
        try:
            result['returncode'] = child.wait(timeout=_remaining(deadline))
            result['reaped'] = True
        except subprocess.TimeoutExpired:
            result['error'] = 'child_reap_deadline'
            return result
        except ChildProcessError:
            result['error'] = 'exclusive_waiter_ownership_lost'
            return result
        while True:
            try:
                os.killpg(child.pid, 0)
            except ProcessLookupError:
                result['group_absence_observed'] = True
                break
            except OSError:
                # Permission denial is presence/unknown, never absence.
                pass
            remaining = _remaining(deadline)
            if remaining <= 0:
                result['error'] = 'group_absence_unverified'
                break
            time.sleep(min(0.01, remaining))
        result['cleanup_complete'] = result['reaped'] and result['group_absence_observed']
        if result['group_signal'] == 'error':
            result['error'] = 'group_signal_failed'
            result['cleanup_complete'] = False
        return result
    finally:
        if observer is not None and observer.child is child:
            observer.close()
