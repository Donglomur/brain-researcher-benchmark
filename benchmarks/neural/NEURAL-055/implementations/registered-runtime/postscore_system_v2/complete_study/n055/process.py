"""Original process observation with held-leader Linux group ownership.

No scientific algorithm changes. A cleanup reserve is carved from the caller's
original deadline; no command retry or fresh cleanup allowance is introduced.
"""
import math
import os
import selectors
import signal
import subprocess
from .common import FailureCarrier, require, pin, diagnostic_type
import stat
import sys
import time

PROC_READ_CAP = 65_536
PROC_ENTRY_CAP = 4096
PROC_STAT_CAP = 4096


def _pinned_platform(metadata_read):
    required = ('wait4', 'waitid', 'P_PID', 'WEXITED', 'WNOHANG', 'WNOWAIT',
                'CLD_EXITED', 'CLD_KILLED', 'CLD_DUMPED', 'waitstatus_to_exitcode')
    if (sys.platform != 'linux' or not all(hasattr(os, name) for name in required)
            or signal.getsignal(signal.SIGCHLD) != signal.SIG_DFL
            or not callable(metadata_read)):
        raise ValueError('Linux waitid/WNOWAIT, default SIGCHLD and selected metadata budget required')
    # Admit the full finite scan cap before Popen; charge actual returned bytes separately.
    metadata_read(PROC_READ_CAP) # Admission only; actual reads are charged below.


class _PinnedGroup:
    """Exclusive child-reaper owner. A proc snapshot is never absence proof."""
    def __init__(self, process, admit_read, actual_read, closure_error):
        self.process = process
        self.admit_read = admit_read
        self.actual_read = actual_read
        self.mark_closure_uncertain = closure_error
        self.usage = None
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

    def _closure_error(self, error):
        self.errors.append(error)
        try:
            self.mark_closure_uncertain(error)
        except BaseException as secondary:
            self.errors.append(secondary)

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
                    raise ValueError('complete proc snapshot exceeds admitted metadata cap')
                self.proc_read_reserved += wanted
                self.admit_read(wanted)
                part = os.read(handle, wanted)
                self.proc_read_bytes += len(part)
                raw.extend(part) # Retain actual prefix before fallible accounting.
                self.actual_read(len(part))
                if not part:
                    break
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
                        self._closure_error(error)
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
                    if self.errors:
                        raise # Preserve original body error; raw close errors remain retained.
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
                        self._closure_error(error)
                        if first is None:
                            first = error
            if root is not None:
                try:
                    os.close(root)
                except BaseException as error:
                    self._closure_error(error)
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
        # wait4. Popen.wait can conceal ECHILD as zero; do not use that shortcut.
        self.observe(deadline, block=True)
        try:
            pid, status, usage = os.wait4(self.pid, os.WNOHANG)
        except ChildProcessError:
            self.wait_ownership_lost = True
            raise
        if pid != self.pid:
            self.wait_ownership_lost = True
            raise RuntimeError('sole wait4 did not return the original terminal child')
        self.reaped = True
        self.usage = usage
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
                'proc_metadata_admission_cap_bytes': PROC_READ_CAP,
                'proc_read_dispatch_reserved_bytes': self.proc_read_reserved,
                'proc_metadata_actual_bytes': self.proc_read_bytes,
                'proc_directory_entries': self.proc_entries,
                'proc_metadata_descriptor_close_errors': len(self.errors),
                'other_group_members_observed': list(self.members),
                'metadata_cost_scope': 'actual_returned_managed_proc_bytes_not_OS_internal_IO'}



def absent(pid):
    """Read-only probe retained for the separately owned postscore role host."""
    try: os.killpg(pid, 0)
    except ProcessLookupError: return True
    return False



class ObservedFailure(Exception):
    def __init__(self, observation):
        self.observation = observation
        super().__init__('original process failed or custody unavailable')


class Observation:
    def __init__(self, ident, argv, origin, deadline):
        self.id = ident; self.argv = list(argv); self.origin = origin; self.deadline = deadline
        self.pid = None; self.returncode = None; self.natural = False
        self.reaped = False; self.group_absent = False
        self.stdout = bytearray(); self.stderr = bytearray()
        self.cpu_seconds = None; self.end = None
        self.errors = FailureCarrier(); self.published = False; self.publication = None
        self.owned_streams = []; self.stream_closure = []; self.owned_selector = None
        self.selector_closed = None; self.group_owner = None; self.ownership = None
        self.stdout_eof = False; self.stderr_eof = False; self.work_deadline = None

    def document(self):
        return dict(id=self.id, argv=self.argv, origin=self.origin, deadline=self.deadline,
                    pid=self.pid, returncode=self.returncode, natural=self.natural,
                    reaped=self.reaped, group_absent=self.group_absent,
                    stdout=pin(self.stdout), stderr=pin(self.stderr), cpu_seconds=self.cpu_seconds,
                    end=self.end, errors=self.errors.document(), published=self.published,
                    publication=self.publication, stream_closure=self.stream_closure,
                    selector_closed=self.selector_closed, stdout_eof=self.stdout_eof,
                    stderr_eof=self.stderr_eof, work_deadline=self.work_deadline,
                    process_ownership=self.ownership)


class ProcessRunner:
    def __init__(self, budget, journal, carrier):
        self.budget = budget; self.journal = journal; self.carrier = carrier; self.originals = []

    def run(self, ident, argv, deadline, stream_cap, kind='host_control', cwd=None, env=None, poll_service=None):
        origin = self.budget.clock(); deadline = min(deadline, self.budget.deadline)
        obs = Observation(ident, argv, origin, deadline)
        self.originals.append(obs); self.carrier.retain(obs)
        proc = selector = group = None; forced = False

        def fail(exc, stage):
            obs.errors.fail(exc, stage); self.carrier.fail(exc, stage + ':' + ident)

        def boundary(stage):
            self.budget.check(stage, obs.work_deadline)

        try:
            require(type(stream_cap) is int and stream_cap > 0, 'positive combined stream cap')
            require(math.isfinite(deadline) and deadline > origin, 'finite original deadline')
            # Shorten work, never extend the original lifetime. This is independent
            # of the enclosing native phase's existing cleanup reserve.
            reserve = min(0.25, (deadline - origin) / 10)
            obs.work_deadline = deadline - reserve
            self.budget.admit('before original launch', obs.work_deadline)
            # Admission checks the finite maximum; actual /proc returns are
            # charged by the helper to the unchanged actual-read counter.
            _pinned_platform(self.budget.admit_read)
            self.journal.json(ident + '-INTENT.json', dict(id=ident, argv=list(argv),
                              origin=origin, deadline=deadline, work_deadline=obs.work_deadline))
            boundary('after durable intent before dispatch')
            proc = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, start_new_session=True,
                                    bufsize=0, cwd=cwd, env=env)
            obs.owned_streams = [proc.stdout, proc.stderr]; obs.pid = proc.pid
            group = _PinnedGroup(proc, self.budget.admit_read, self.budget.read,
                lambda error: self.budget.uncertain(ident + ":proc-metadata", "managed_descriptor_closure", error))
            obs.group_owner = group; self.carrier.retain(group)
            selector = selectors.DefaultSelector(); obs.owned_selector = selector
            obs.selector_closed = False
            for name, stream in [('stdout', proc.stdout), ('stderr', proc.stderr)]:
                os.set_blocking(stream.fileno(), False)
                selector.register(stream, selectors.EVENT_READ, name)
            while selector.get_map() or group.terminal is None:
                boundary('before original observation poll')
                if poll_service is not None:
                    poll_service(obs.work_deadline)
                    boundary('after original service poll')
                for key, _ in selector.select(min(.02, max(0, obs.work_deadline - self.budget.clock()))):
                    wanted = min(65536, stream_cap + 1 - len(obs.stdout) - len(obs.stderr))
                    try:
                        chunk = os.read(key.fileobj.fileno(), wanted)
                    except BlockingIOError:
                        continue
                    if not chunk:
                        setattr(obs, key.data + '_eof', True)
                        selector.unregister(key.fileobj)
                        continue
                    getattr(obs, key.data).extend(chunk)
                    self.budget.stream(len(chunk))
                    require(len(obs.stdout) + len(obs.stderr) <= stream_cap, 'original received-stream cap')
                    boundary('after original stream return')
                group.observe(obs.work_deadline)
                boundary('after original held wait/sample')
            obs.returncode = group.terminal; obs.natural = True
            require(obs.returncode == 0, 'original nonzero exit')
            require(not group.other_members(obs.work_deadline), 'original group outlived leader')
            require(not group.errors, 'all observed proc metadata descriptors closed')
            boundary('after complete held-group snapshot')
        except BaseException as exc:
            fail(exc, 'process')
        finally:
            if proc is not None:
                if group is None:
                    fail(RuntimeError('original group owner unavailable'), 'group-owner')
                else:
                    if obs.errors.first is not None:
                        try:
                            forced = True # Conservative from attempted destructive signal.
                            group.send(signal.SIGKILL, deadline)
                        except ProcessLookupError:
                            pass
                        except BaseException as exc:
                            fail(exc, 'held-group-kill')
                    try:
                        obs.returncode = group.reap(deadline)
                    except BaseException as exc:
                        fail(exc, 'sole-original-reap')
                    # Reap can succeed before a later status check raises. Keep
                    # the real ownership/usage facts, never synthesize success.
                    obs.reaped = group.reaped
                    if group.usage is not None:
                        obs.cpu_seconds = group.usage.ru_utime + group.usage.ru_stime
                    if group.reaped:
                        obs.returncode = proc.returncode
                        try:
                            obs.group_absent = group.absent_after_reap()
                        except BaseException as exc:
                            fail(exc, 'read-only-group-final')
                    obs.ownership = group.evidence()
                for role, stream in zip(('stdout', 'stderr'), obs.owned_streams):
                    closure = {'role': role, 'closed': False}; obs.stream_closure.append(closure)
                    try:
                        stream.close(); closure['closed'] = True
                    except BaseException as exc:
                        fail(exc, 'pipe-close'); closure['error_type'] = diagnostic_type(exc)
                        self.budget.uncertain(ident + ':' + role, 'managed_descriptor_closure', exc)
            if selector is not None:
                try:
                    selector.close(); obs.selector_closed = True
                except BaseException as exc:
                    fail(exc, 'selector-close')
                    self.budget.uncertain(ident + ':selector', 'managed_descriptor_closure', exc)
            obs.natural = obs.natural and not forced
            try:
                obs.end = self.budget.clock()
            except BaseException as exc:
                fail(exc, 'final-clock')
                self.budget.unknown.append({'operation': ident, 'quantity': 'wall_seconds'})
            try:
                self.budget.physical(ident, dict(kind=kind, cpu_seconds=obs.cpu_seconds,
                    wall_seconds=None if obs.end is None else obs.end-origin,
                    returncode=obs.returncode, natural=obs.natural, reaped=obs.reaped,
                    group_absent=obs.group_absent, stdout_bytes=len(obs.stdout), stderr_bytes=len(obs.stderr)))
                self.budget.check('after final CPU/closure', deadline)
                require(proc is not None and obs.reaped and obs.group_absent, 'original closure established')
            except BaseException as exc:
                fail(exc, 'final-cost-admission')
        try:
            self.journal.write(ident + '-stdout.txt', bytes(obs.stdout))
            self.journal.write(ident + '-stderr.txt', bytes(obs.stderr))
            obs.publication = self.journal.json(ident + '-PROCESS.json', obs.document()); obs.published = True
            self.budget.check('after original process publication', deadline)
        except BaseException as exc:
            fail(exc, 'process-publication')
        try:
            obs.end = self.budget.clock()
        except BaseException as exc:
            fail(exc, 'post-publication-clock')
            self.budget.unknown.append({'operation': ident, 'quantity': 'whole_wall_seconds'})
        if obs.errors.first is not None or not obs.published:
            raise ObservedFailure(obs)
        return obs
