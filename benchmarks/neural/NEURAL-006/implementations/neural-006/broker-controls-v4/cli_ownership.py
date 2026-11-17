"""Linux CPython3.11.18 amendment of the exact exclusive wait owner; no execution on import."""
import os
import signal
import sys
import threading
import sysconfig

def need(ok, reason):
    if not ok:
        raise ValueError(reason)


class ChildOwner:
    """The sole waiter. Injected ops are used only by the separately pinned inert checks."""
    def __init__(self, guard, ops=os):
        self.guard = guard
        self.ops = ops
        self.pid = None
        self.state = 'not_spawned'
        self.signal_authority = False
        self.stop_attempted = False
        self.wait_calls = 0
        self.zero_results = 0
        self.raw_status = None
        self.returncode = None
        self.group_probe = 'not_observed'
        self.signal_operations = []

    def adopt(self, pid):
        need(self.state == 'not_spawned' and type(pid) is int and pid > 0, 'one exact child adoption')
        self.pid = pid
        self.state = 'owned_unreaped'
        self.signal_authority = True

    def wait_once(self):
        need(self.state == 'owned_unreaped', 'wait requires original unreaped child')
        # Retire BEFORE guard or wait. Any exception/ambiguous result loses ownership.
        self.signal_authority = False
        self.state = 'wait_in_progress'
        self.wait_calls += 1
        try:
            self.guard()
            got, status = self.ops.waitpid(self.pid, os.WNOHANG)
            need(type(got) is int and type(status) is int, 'exact builtin wait result')
            if got == 0:
                need(status == 0, 'zero wait status')
                self.guard()
                self.zero_results += 1
                self.state = 'owned_unreaped'
                self.signal_authority = not self.stop_attempted
                return False
            need(got == self.pid, 'wait returned another child')
            need(os.WIFEXITED(status) or os.WIFSIGNALED(status), 'terminal original wait status')
            # No operation after this point can reacquire destructive authority.
            self.raw_status = status
            self.returncode = os.waitstatus_to_exitcode(status)
            self.state = 'reaped'
            return True
        except BaseException:
            self.state = 'ownership_lost'
            self.signal_authority = False
            raise

    def stop_unreaped(self):
        # A terminal/lost owner never performs even an attempted destructive signal.
        if self.state != 'owned_unreaped' or not self.signal_authority:
            return False
        self.signal_authority = False
        self.stop_attempted = True
        try:
            self.guard()
        except BaseException:
            self.state = 'ownership_lost'
            raise
        # Exclusive wait ownership plus a default/reinstalled SIGCHLD retains the
        # original PID even if it has already become a zombie. The PID therefore
        # cannot name a different process group before this owner reaps.
        self.signal_operations.append('unreaped_group_SIGKILL')
        try:
            self.ops.killpg(self.pid, signal.SIGKILL)
        except ProcessLookupError:
            # Child may not yet have executed setsid. Its still-unreaped exact PID
            # remains ours. No wait occurs between these two bounded operations.
            self.signal_operations.append('unreaped_pre_setsid_PID_SIGKILL')
            try:
                self.ops.kill(self.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        return True

    def observe_absence(self):
        need(self.pid is not None, 'group probe needs original child identity')
        # Numeric PGID after reaping is only a read-only observation. A reused
        # group can cause a conservative refusal, never cleanup of that group.
        try:
            self.ops.killpg(self.pid, 0)
        except ProcessLookupError:
            self.group_probe = 'absent'
            return True
        except BaseException:
            self.group_probe = 'unestablished'
            raise
        self.group_probe = 'present_or_reused'
        return False

    def evidence(self):
        return {'pid': self.pid, 'state': self.state, 'signal_authority': self.signal_authority,
                'stop_attempted': self.stop_attempted, 'wait_calls': self.wait_calls,
                'zero_wait_results': self.zero_results, 'raw_wait_status': self.raw_status,
                'returncode': self.returncode, 'group_probe': self.group_probe,
                'signal_operations': list(self.signal_operations)}


def capture_configurable_handlers(signal_api=signal):
    """Capture only signals that can carry a configurable child-reaping handler.

    Mac CPython may report None for SIGKILL/SIGSTOP. They cannot be caught,
    ignored or blocked, so neither can execute a competing waiter. None remains
    forbidden for every catchable signal; no signal disposition is reset here.
    """
    handlers = {}
    for number in sorted(signal_api.valid_signals()):
        if number in (signal_api.SIGKILL, signal_api.SIGSTOP):
            continue
        handler = signal_api.getsignal(number)
        allowed = handler in (signal_api.SIG_DFL, signal_api.SIG_IGN) or (
            number == signal_api.SIGINT and handler is signal_api.default_int_handler)
        need(allowed, 'no unknown or arbitrary child-reaping signal handler')
        handlers[number] = handler
    need(handlers[signal_api.SIGCHLD] == signal_api.SIG_DFL,
         'inherited SIGCHLD must be default')
    return handlers


def guard_configurable_handlers(handlers, signal_api=signal):
    need(all(signal_api.getsignal(n) is h or signal_api.getsignal(n) == h
             for n, h in handlers.items()), 'wait-owner signal dispositions unchanged')


def exclusive_admission():
    need(sys.platform == 'linux' and sys.implementation.name == 'cpython' and
         sys.version_info[:3] == (3, 11, 18), 'selected Linux CPython 3.11.18 only')
    need(sys.flags.isolated and sys.flags.no_site and sys.flags.dont_write_bytecode and not sys.flags.optimize,
         'fresh isolated -I -S -B supervisor')
    need(sys.gettrace() is None and sys.getprofile() is None, 'no external trace/profile hooks')
    need(sysconfig.get_config_var('HAVE_SIGACTION') == 1, 'selected sigaction implementation required')
    main = threading.main_thread()
    def threads():
        need(threading.current_thread() is main and threading.enumerate() == [main],
             'exclusive single main thread wait ownership')
    threads()
    handlers = capture_configurable_handlers()
    # CPython v3.11.18 commit26badd80 PyOS_setsig installs SA_ONSTACK, replacing flags, so this
    # also removes inherited SA_NOCLDWAIT. Do not infer flags from getsignal.
    signal.signal(signal.SIGCHLD, signal.SIG_DFL)
    def guard():
        threads()
        need(sys.gettrace() is None and sys.getprofile() is None, 'wait-owner hooks unchanged')
        guard_configurable_handlers(handlers)
    guard()
    return guard, handlers
