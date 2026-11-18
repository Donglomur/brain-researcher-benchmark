"""Finite owned POSIX worker process; no sandbox or provider qualification."""
import hashlib
import json
import os
import signal
import subprocess
import time

ENVIRONMENT = {
    'LANG': 'C', 'LC_ALL': 'C', 'PYTHONHASHSEED': '0', 'PYTHONNOUSERSITE': '1',
    'PYTHONDONTWRITEBYTECODE': '1', 'OMP_NUM_THREADS': '1', 'OPENBLAS_NUM_THREADS': '1',
    'MKL_NUM_THREADS': '1', 'VECLIB_MAXIMUM_THREADS': '1', 'NUMEXPR_NUM_THREADS': '1',
}


class OwnershipRefusal(RuntimeError):
    pass


def require(ok, message):
    if not ok:
        raise OwnershipRefusal(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('ascii')


def detached(value):
    return json.loads(canonical(value))


def fd_signature(fd):
    info = os.fstat(fd)
    return (info.st_dev, info.st_ino, info.st_mode)


class OwnedProcess:
    """A fresh trusted worker and session, with its leader held unreaped.

    Do not expose this object to participant code or access its Popen object.
    All TERM/KILL group signals precede the only wait/reap attempt. Holding the
    leader unreaped prevents reuse of its numeric PID/group before signaling.
    The worker must not escape its session; this primitive cannot prove that
    property and is not a containment boundary for hostile candidate code.
    """
    def __init__(self, command, *, cwd, term_grace_seconds=0.05, close_timeout_seconds=2.0):
        require(os.name == 'posix', 'POSIX worker transport required')
        require(type(command) is list and 0 < len(command) <= 128
                and all(type(x) is str and 0 < len(x.encode('utf-8')) <= 4096 and '\x00' not in x for x in command)
                and os.path.isabs(command[0]), 'bounded absolute-executable command required')
        require(type(cwd) is str and os.path.isabs(cwd) and '\x00' not in cwd,
                'explicit trusted absolute working directory required')
        require(type(term_grace_seconds) in (int, float) and type(close_timeout_seconds) in (int, float)
                and 0 <= term_grace_seconds <= 1 and term_grace_seconds < close_timeout_seconds <= 5,
                'finite worker cleanup limits required')
        self._owner = os.getpid()
        self._term_grace = float(term_grace_seconds)
        self._close_limit = float(close_timeout_seconds)
        self._fds = {}; self._transferred = False; self._closed = None
        self._proc = None; self._pid = None
        self._spawn = {'schema': 'dosei_owned_process_spawn_v1', 'owner_pid': self._owner,
            'fresh_session_requested': True, 'leader_polled_or_reaped_before_cleanup': False,
            'command_sha256': hashlib.sha256(canonical(command)).hexdigest(),
            'environment_sha256': hashlib.sha256(canonical(ENVIRONMENT)).hexdigest(),
            'environment_inherited': False, 'extra_fds_inherited': False,
            'stderr_policy': 'merged_into_framed_stdout; unframed diagnostics invalidate and may be only partially retained',
            'hostile_process_containment_qualified': False}
        try:
            self._proc = subprocess.Popen(command, cwd=cwd, env=dict(ENVIRONMENT),
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                close_fds=True, start_new_session=True, bufsize=0)
            self._pid = self._proc.pid
            self._spawn['leader_pid'] = self._pid
            self._spawn['process_group_id'] = self._pid
            read_fd = os.dup(self._proc.stdout.fileno())
            self._fds[read_fd] = None
            self._fds[read_fd] = fd_signature(read_fd)
            write_fd = os.dup(self._proc.stdin.fileno())
            self._fds[write_fd] = None
            self._fds[write_fd] = fd_signature(write_fd)
            for fd in self._fds:
                os.set_inheritable(fd, False)
            self._read_fd, self._write_fd = read_fd, write_fd
            self._proc.stdout.close(); self._proc.stdin.close()
        except BaseException:
            if self._proc is not None:
                if self._pid is None:self._pid = self._proc.pid
                self.close()
            raise

    def spawn_receipt(self):
        return detached(self._spawn)

    @property
    def leader_pid(self):
        return self._pid

    @property
    def owner_pid(self):
        return self._owner

    def detach_stdio(self):
        """Transfer both descriptors once; recipient must close them on failure."""
        require(os.getpid() == self._owner and self._closed is None and not self._transferred,
                'live same-owner one-time descriptor transfer required')
        require(all(fd_signature(fd) == signature for fd, signature in self._fds.items()),
                'owned descriptor identity changed')
        result = (self._read_fd, self._write_fd)
        self._fds.clear(); self._transferred = True
        return result

    def close(self):
        """Attempt all owned closures/signals before bounded leader wait, once.

        A timeout or error produces incomplete metadata and must invalidate the
        caller's run. The method never sends a group signal after wait/reap,
        including on repeated calls. Transferred descriptors are caller-owned.
        """
        require(os.getpid() == self._owner, 'only original owner may clean worker group')
        if self._closed is not None:
            return detached(self._closed)
        started = time.monotonic(); deadline = started+self._close_limit
        events = []; errors = []; first_interrupt = None
        for fd, expected in list(self._fds.items()):
            try:
                # None exists only during immediate constructor acquisition,
                # before any callback/transfer. It is our exact fresh dup FD.
                if expected is not None and fd_signature(fd) != expected:
                    raise OwnershipRefusal('owned descriptor identity changed before cleanup')
                os.close(fd); events.append({'operation':'close_owned_fd','fd':fd})
            except BaseException as error:
                errors.append({'operation':'close_owned_fd','type':type(error).__name__})
                if not isinstance(error, Exception) and first_interrupt is None:first_interrupt = error
        self._fds.clear()
        for name in ('stdin','stdout'):
            stream = getattr(self._proc, name, None)
            if stream is not None and not stream.closed:
                try: stream.close()
                except BaseException as error:
                    errors.append({'operation':'close_popen_stream','type':type(error).__name__})
                    if not isinstance(error, Exception) and first_interrupt is None:first_interrupt = error
        for sig in (signal.SIGTERM, signal.SIGKILL):
            try:
                # Never poll/wait before this. The unreaped session leader still
                # reserves its numeric identity even if it already exited.
                os.killpg(self._pid, sig)
                events.append({'operation':'signal_owned_group','signal':int(sig),'result':'sent'})
            except ProcessLookupError:
                events.append({'operation':'signal_owned_group','signal':int(sig),'result':'absent'})
            except BaseException as error:
                errors.append({'operation':'signal_owned_group','signal':int(sig),'type':type(error).__name__,
                               'errno':getattr(error,'errno',None)})
                if not isinstance(error, Exception) and first_interrupt is None:first_interrupt = error
            if sig == signal.SIGTERM and self._term_grace:
                try:time.sleep(min(self._term_grace,max(0,deadline-time.monotonic())))
                except BaseException as error:
                    errors.append({'operation':'term_grace','type':type(error).__name__})
                    if not isinstance(error, Exception) and first_interrupt is None:first_interrupt = error
        reaped = False; returncode = None
        try:
            returncode = self._proc.wait(timeout=max(0.001,deadline-time.monotonic()))
            reaped = True; events.append({'operation':'wait_and_reap_leader','returncode':returncode})
        except BaseException as error:
            errors.append({'operation':'wait_and_reap_leader','type':type(error).__name__})
            if not isinstance(error, Exception) and first_interrupt is None:first_interrupt = error
        group_absent = False; absence_probes = 0; group_probe_error = None; probe_denials = 0
        if reaped:
            while True:
                absence_probes += 1
                try:os.killpg(self._pid, 0)
                except ProcessLookupError:
                    group_absent = True; group_probe_error = None; break
                except PermissionError as error:
                    probe_denials += 1
                    group_probe_error = {'type':type(error).__name__,'errno':getattr(error,'errno',None)}
                except BaseException as error:
                    group_probe_error = {'type':type(error).__name__,'errno':getattr(error,'errno',None)}
                    if not isinstance(error, Exception) and first_interrupt is None:first_interrupt = error
                    break
                remaining = deadline-time.monotonic()
                if remaining <= 0:break
                try:time.sleep(min(.01,remaining))
                except BaseException as error:
                    group_probe_error = {'type':type(error).__name__,'errno':getattr(error,'errno',None)}
                    if not isinstance(error, Exception) and first_interrupt is None:first_interrupt = error
                    break
        # A signal denial is never itself absence. Only an observed post-wait
        # ESRCH can resolve that earlier attempt; no new signal is sent here.
        for error in errors:
            error['resolved_by_observed_group_absence'] = bool(reaped and group_absent and
                error['operation'] == 'signal_owned_group' and error['type'] == 'PermissionError')
        self._closed = {'schema':'dosei_owned_process_close_v1','owner_pid':self._owner,
            'leader_pid':self._pid,'process_group_id':self._pid,'events':events,'errors':errors,
            'leader_reaped':reaped,'leader_returncode':returncode,
            'leader_polled_or_reaped_before_group_signals':False,
            'group_signals_after_wait_attempt':False,'stdio_ownership_transferred':self._transferred,
            'post_wait_group_absence_observed':group_absent,'post_wait_group_absence_probes':absence_probes,
            'post_wait_group_permission_denials_observed':probe_denials,
            'post_wait_group_probe_error':group_probe_error,
            'elapsed_seconds':time.monotonic()-started,
            'complete':reaped and group_absent and group_probe_error is None and
                not any(not error['resolved_by_observed_group_absence'] for error in errors),
            'escaped_descendant_absence_proven':False}
        if first_interrupt is not None:
            raise first_interrupt
        return detached(self._closed)
