"""Deterministic ownership controls: no child, OS signal or scientific input."""
import errno
import importlib.util
from pathlib import Path
import signal
import subprocess
import types
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('viewer_owned_exit', Path(__file__).with_name('owned_exit.py'))
o = importlib.util.module_from_spec(spec)
spec.loader.exec_module(o)


class Child:
    pid = 4567

    def __init__(self, events, returncode=None, final=0):
        self.events, self.returncode, self.final = events, returncode, final

    def poll(self):
        raise AssertionError('poll would reap and is forbidden')

    def communicate(self):
        raise AssertionError('communicate would reap and is forbidden')

    def wait(self, timeout):
        self.events.append(('wait', timeout))
        if isinstance(self.final, Exception):
            raise self.final
        self.returncode = self.final
        return self.final


class Observer:
    def __init__(self, child, events, exited=True):
        self.child, self.events, self.exit_observed = child, events, exited

    def close(self):
        self.events.append(('close',))


class OwnedExitControls(unittest.TestCase):
    def cleanup(self, *, returncode=None, final=0, signal_error=None, probe_present=False,
                sigchld=True, observer_mismatch=False):
        events = []
        child = Child(events, returncode, final)
        observer = Observer(Child(events) if observer_mismatch else child, events)
        def killpg(pid, sig):
            events.append(('killpg', pid, sig))
            if sig == signal.SIGKILL:
                self.assertIsNone(child.returncode, 'signal must precede reap')
                if signal_error:
                    raise signal_error
            elif not probe_present:
                raise ProcessLookupError(errno.ESRCH, 'gone')
        with patch.object(o, '_default_sigchld', return_value=sigchld), \
                patch.object(o.os, 'getpgid', side_effect=ProcessLookupError(errno.ESRCH, 'zombie')) as group_query, \
                patch.object(o.os, 'killpg', side_effect=killpg), \
                patch.object(o.time, 'monotonic', return_value=10.0):
            result = o.stop_and_reap(child, observer, 10.0)
            group_query.assert_not_called()
        return result, events

    def test_signal_precedes_sole_reap_and_only_zero_probes_follow(self):
        result, events = self.cleanup()
        self.assertEqual(events[:3], [('killpg', 4567, signal.SIGKILL), ('wait', 0.0), ('killpg', 4567, 0)])
        self.assertTrue(result['cleanup_complete'])
        self.assertEqual(result['returncode'], 0)
        self.assertFalse(result['descendant_containment_qualified'])

    def test_reaped_handle_never_signalled(self):
        result, events = self.cleanup(returncode=0)
        self.assertEqual(result['error'], 'reaped_or_invalid_child')
        self.assertEqual(events, [('close',)])

    def test_pid_reuse_after_reap_only_causes_conservative_failure(self):
        result, events = self.cleanup(probe_present=True)
        self.assertEqual(result['error'], 'group_absence_unverified')
        self.assertFalse(result['cleanup_complete'])
        self.assertEqual([e[2] for e in events if e[0] == 'killpg'], [signal.SIGKILL, 0])

    def test_darwin_zombie_permission_error_reaps_then_probes_without_kill(self):
        result, events = self.cleanup(signal_error=PermissionError(errno.EPERM, 'zombie'))
        self.assertTrue(result['cleanup_complete'])
        self.assertEqual(result['group_signal'], 'permission_denied')
        self.assertEqual(result['group_signal_errno'], errno.EPERM)
        self.assertEqual([e[2] for e in events if e[0] == 'killpg'], [signal.SIGKILL, 0])

    def test_changed_policy_and_observer_fail_before_signal(self):
        for kwargs, error in (({'sigchld': False}, 'sigchld_policy_changed'),
                              ({'observer_mismatch': True}, 'observer_child_mismatch')):
            with self.subTest(error=error):
                result, events = self.cleanup(**kwargs)
                self.assertEqual(result['error'], error)
                self.assertFalse(any(e[0] in ('killpg', 'wait') for e in events))

    def test_reap_timeout_does_not_probe_or_signal_again(self):
        result, events = self.cleanup(final=subprocess.TimeoutExpired('owned', 0))
        self.assertEqual(result['error'], 'child_reap_deadline')
        self.assertEqual([e[2] for e in events if e[0] == 'killpg'], [signal.SIGKILL])
        self.assertFalse(result['reaped'])

    def test_unsupported_platform_and_auto_reap_policy_refuse(self):
        with patch.object(o.sys, 'platform', 'unsupported'), patch.object(o, '_default_sigchld', return_value=True):
            with self.assertRaises(RuntimeError):
                o.preflight()
        with patch.object(o, '_default_sigchld', return_value=False):
            with self.assertRaises(RuntimeError):
                o.preflight()

    def test_linux_notification_never_reaps_child(self):
        events = []
        child = Child(events)
        with patch.object(o, 'preflight', return_value='linux_pidfd'), \
                patch.object(o, '_default_sigchld', return_value=True), \
                patch.object(o.os, 'pidfd_open', return_value=91, create=True) as opened, \
                patch.object(o.os, 'set_inheritable') as inherit, \
                patch.object(o.select, 'select', return_value=([91], [], [])), \
                patch.object(o.os, 'close') as closed, \
                patch.object(o.time, 'monotonic', return_value=1.0):
            watcher = o.ExitObserver(child)
            self.assertTrue(watcher.wait(2.0))
            watcher.close()
            opened.assert_called_once_with(child.pid, 0)
            inherit.assert_called_once_with(91, False)
            closed.assert_called_once_with(91)
        self.assertEqual(events, [])
        self.assertIsNone(child.returncode)

    def kqueue_context(self, queue, event_factory):
        # Explicit fake constants keep this same source control portable on Linux.
        return patch.multiple(o.select, kqueue=lambda: queue, kevent=event_factory,
                              KQ_FILTER_PROC=-5, KQ_EV_ADD=1, KQ_EV_ONESHOT=16,
                              KQ_EV_ERROR=16384, KQ_NOTE_EXIT=2147483648, create=True)

    def test_darwin_notification_and_timeout_do_not_reap(self):
        events, calls = [], []
        child = Child(events)
        exited = types.SimpleNamespace(ident=child.pid, filter=-5, flags=0, fflags=2147483648, data=0)
        class Queue:
            def control(self, changes, count, timeout):
                calls.append((changes, count, timeout))
                return [] if len(calls) < 3 else [exited]
            def close(self):
                calls.append('closed')
        with patch.object(o, 'preflight', return_value='darwin_kqueue'), \
                patch.object(o, '_default_sigchld', return_value=True), \
                self.kqueue_context(Queue(), lambda *args, **kwargs: (args, kwargs)), \
                patch.object(o.time, 'monotonic', return_value=1.0):
            watcher = o.ExitObserver(child)
            self.assertFalse(watcher.wait(2.0))
            self.assertTrue(watcher.wait(2.0))
            watcher.close()
        self.assertEqual(events, [])
        self.assertEqual(calls[-1], 'closed')

    def test_darwin_registration_esrch_is_not_resolved_by_poll(self):
        events, closed = [], []
        child = Child(events)
        class Queue:
            def control(self, changes, count, timeout):
                raise ProcessLookupError(errno.ESRCH, 'already exited')
            def close(self):
                closed.append(True)
        with patch.object(o, 'preflight', return_value='darwin_kqueue'), \
                self.kqueue_context(Queue(), lambda *args, **kwargs: (args, kwargs)):
            with self.assertRaises(ProcessLookupError):
                o.ExitObserver(child)
        self.assertEqual(events, [])
        self.assertEqual(closed, [True])
        self.assertIsNone(child.returncode)

    def constructor_failure_cleanup(self, backend, failure):
        events = []
        child = Child(events)
        class Queue:
            def control(self, changes, count, timeout):
                raise failure
            def close(self):
                events.append(('observer_closed',))
        def killpg(pid, sig):
            events.append(('killpg', pid, sig))
            if sig == 0:
                raise ProcessLookupError(errno.ESRCH, 'gone')
            self.assertIsNone(child.returncode)
        with patch.object(o, 'preflight', return_value=backend), \
                patch.object(o, '_default_sigchld', return_value=True), \
                patch.object(o.os, 'pidfd_open', side_effect=failure, create=True), \
                self.kqueue_context(Queue(), lambda *args, **kwargs: (args, kwargs)), \
                patch.object(o.os, 'getpgid', side_effect=ProcessLookupError(errno.ESRCH, 'zombie')) as queried, \
                patch.object(o.os, 'killpg', side_effect=killpg), \
                patch.object(o.time, 'monotonic', return_value=1.0):
            with self.assertRaises(OSError):
                o.ExitObserver(child)
            self.assertIsNone(child.returncode)
            result = o.stop_and_reap(child, None, 2.0)
            queried.assert_not_called()
        self.assertTrue(result['cleanup_complete'])
        self.assertFalse(result['exit_observed_before_stop'])
        self.assertEqual([event[0] for event in events if event[0] != 'observer_closed'],
                         ['killpg', 'wait', 'killpg'])
        self.assertEqual(result['returncode'], 0)

    def test_darwin_constructor_esrch_keeps_handle_for_owned_cleanup(self):
        self.constructor_failure_cleanup('darwin_kqueue', ProcessLookupError(errno.ESRCH, 'zombie'))

    def test_linux_pidfd_unavailable_keeps_handle_for_owned_cleanup(self):
        for failure in (OSError(errno.ENOSYS, 'unsupported'), PermissionError(errno.EPERM, 'denied')):
            with self.subTest(errno=failure.errno):
                self.constructor_failure_cleanup('linux_pidfd', failure)


if __name__ == '__main__':
    unittest.main()
