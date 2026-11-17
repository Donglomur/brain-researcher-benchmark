"""Owned native processes, literal captured mounts, duplex protocol and closure.

Constructing these classes has no effects. start() is an actual Docker operation
and must run only under a separately selected/qualified complete operation owner.
"""
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import selectors
import shutil
import signal
import stat
import struct
import subprocess
import tempfile
import time
import uuid
import enclosure
import wire
from wire import need


def lexical_disjoint(early, private):
    """Reject forbidden overlap before ANY stat/open/resolve on an early role."""
    def lexical(value):
        p = Path(value)
        need(p.is_absolute() and '..' not in p.parts, 'absolute lexical role path')
        return p
    left, right = tuple(map(lexical, early)), tuple(map(lexical, private))
    for a in left:
        for b in right:
            need(a != b and a not in b.parents and b not in a.parents, 'early/private-owner overlap')


def capture(path, expected_bytes, expected_sha):
    path = Path(path)
    need(path.is_absolute() and '..' not in path.parts, 'absolute selected source')
    need(all(not p.is_symlink() for p in (path, *path.parents)), 'no source symlink component')
    need(type(expected_bytes) is int and 0 < expected_bytes <= 1048576 and
         re.fullmatch('[0-9a-f]{64}', expected_sha), 'bounded selected source identity')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and
             before.st_size == expected_bytes, 'ordinary exact selected source')
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            body = stream.read(expected_bytes + 1)
        after, linked = os.fstat(fd), path.lstat()
        attrs = ('st_dev', 'st_ino', 'st_mode', 'st_nlink', 'st_size', 'st_mtime_ns', 'st_ctime_ns')
        need(all(getattr(before, k) == getattr(after, k) == getattr(linked, k) for k in attrs)
             and len(body) == expected_bytes and hashlib.sha256(body).hexdigest() == expected_sha,
             'same-open complete selected source bytes')
        return body
    finally:
        os.close(fd)


def strict(raw):
    def pairs(rows):
        out = {}
        for key, value in rows:
            need(key not in out, 'duplicate JSON key'); out[key] = value
        return out
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda _: need(False, 'nonfinite JSON'))


def raise_all(primary, failures):
    if primary is not None:
        if failures:
            raise BaseExceptionGroup('original error followed by cleanup failures', [primary, *failures])
        raise primary
    if failures:
        raise BaseExceptionGroup('cleanup failures', failures)


def require_group_absence(pid):
    try:
        os.killpg(pid, 0)
    except ProcessLookupError:
        return
    raise RuntimeError('Owned local process group still exists after reap')


class NativeCommand:
    """Own every local CLI process. Never shell, inherit stdio, or renew owner time."""
    def __init__(self, executable, socket, request, owner):
        need(Path(executable).is_absolute() and type(socket) is str and socket.startswith('unix:///') and
             not any(c in socket for c in '\n\r\x00'), 'explicit local Docker endpoint')
        self.prefix = [str(executable), '--host', socket]
        self.request, self.owner, self.events = request, owner, []

    def spawn(self, arguments):
        self.owner.tick()
        # No user Docker context, credentials, plugin settings, proxy, or host
        # Python environment is forwarded. Executable qualification is a
        # separate operator prerequisite; a path is not an executable proof.
        return subprocess.Popen(self.prefix + list(arguments), stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0,
                                close_fds=True, start_new_session=True,
                                env={'PATH': '/usr/bin:/bin', 'LANG': 'C', 'LC_ALL': 'C'})

    def run(self, arguments, *, cleanup=False):
        # Cleanup has its own finite command timeout, never an extension granting
        # scientific work after the original owner deadline.
        if not cleanup:
            self.owner.tick()
        start = time.monotonic_ns()
        deadline = start + self.request['command_seconds'] * 1000000000
        if not cleanup:
            deadline = min(deadline, self.owner.deadline)
        proc = None; sel = None
        out, err = bytearray(), bytearray(); primary = None; failures = []
        try:
            proc = (subprocess.Popen(self.prefix + list(arguments), stdin=subprocess.DEVNULL,
                     stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0, close_fds=True,
                     start_new_session=True, env={'PATH': '/usr/bin:/bin', 'LANG': 'C', 'LC_ALL': 'C'})
                    if cleanup else self.spawn(arguments))
            # Ownership begins at spawn return, before any stream/selector setup.
            if proc.stdin is not None:
                proc.stdin.close()
            sel = selectors.DefaultSelector()
            for stream, name in ((proc.stdout, 'out'), (proc.stderr, 'err')):
                os.set_blocking(stream.fileno(), False); sel.register(stream, selectors.EVENT_READ, name)
            while sel.get_map():
                need(time.monotonic_ns() < deadline, 'native control deadline')
                for key, _ in sel.select(min(.1, max(0, (deadline-time.monotonic_ns())/1e9))):
                    part = os.read(key.fd, 65536)
                    if not part:
                        sel.unregister(key.fileobj); continue
                    target = out if key.data == 'out' else err
                    need(len(out) + len(err) + len(part) <= self.request['command_bytes'], 'native control byte cap')
                    target.extend(part)
            proc.wait(timeout=max(.001, (deadline-time.monotonic_ns())/1e9))
            need(proc.returncode == 0, 'native control nonzero exit: ' + str(arguments[0]))
            require_group_absence(proc.pid)
        except BaseException as error:
            primary = error
        finally:
            if sel is not None:
                try: sel.close()
                except BaseException as error: failures.append(error)
            if proc is not None:
                # A reaped leader does not imply its process group is empty.
                if primary is not None or failures:
                    try: os.killpg(proc.pid, signal.SIGKILL)
                    except ProcessLookupError: pass
                    except BaseException as error: failures.append(error)
                try: proc.wait(timeout=self.request['command_seconds'])
                except BaseException as error: failures.append(error)
                try: require_group_absence(proc.pid)
                except BaseException as error: failures.append(error)
                for stream in (proc.stdin, proc.stdout, proc.stderr):
                    if stream is not None:
                        try: stream.close()
                        except BaseException as error: failures.append(error)
        self.events.append({'argv': tuple(arguments), 'pid': None if proc is None else proc.pid,
                            'exit': None if proc is None else proc.returncode,
                            'stdout_bytes': len(out), 'stderr_bytes': len(err),
                            'start_ns': start, 'finish_ns': time.monotonic_ns(),
                            'failed': primary is not None or bool(failures)})
        raise_all(primary, failures)
        return bytes(out)


@dataclass(frozen=True)
class ClosedChild:
    binding: dict
    container_id: str
    local_pid: int
    exit_code: int
    requests: int
    stdout_bytes: int
    stderr_bytes: int
    removed: bool
    qualified: bool = False


class ParticipantChild:
    def __init__(self, command, root, bodies, method, binding, owner):
        self.command, self.request, self.owner = command, command.request, owner
        self.root, self.bodies, self.method, self.binding = Path(root), bodies, method, binding
        self.name = 'n061-' + uuid.uuid4().hex
        self.directory = None; self.container_id = None; self.proc = None; self.create_started = False
        self.sequence = 0; self.out_bytes = 0; self.err_bytes = 0
        self.closed = False; self.failed = None; self.eofs = set(); self.events = []

    def start(self):
        self.owner.tick(); enclosure.validate_request(self.request)
        need(self.proc is None and self.directory is None, 'fresh child only')
        need(set(self.bodies) == {'child.py', 'wire.py', 'worker.py', 'contracts.py'}, 'exact trusted child source set')
        self.deadline = min(self.owner.deadline, time.monotonic_ns() + self.request['wall_seconds'] * 1000000000)
        try:
            self.directory = Path(tempfile.mkdtemp(prefix='n061-owned-', dir=self.root))
            self.directory.chmod(0o755)
            trusted = self.directory / 'trusted'; trusted.mkdir(); trusted.chmod(0o755)
            for name, body in self.bodies.items():
                path = trusted / name; path.write_bytes(body); path.chmod(0o444)
            method = self.directory / 'method.py'; method.write_bytes(self.method); method.chmod(0o444)
            mounts = enclosure.canonical_mounts(trusted, method)
            argv = enclosure.create_argv(self.name, mounts, self.request)
            self.create_started = True
            raw = self.command.run(argv)
            cid = raw.decode('ascii').strip()
            need(re.fullmatch('[0-9a-f]{64}', cid), 'complete original created container ID')
            self.container_id = cid
            info = strict(self.command.run(['inspect', cid]))
            need(type(info) is list and len(info) == 1 and info[0]['Id'] == cid, 'same original container')
            enclosure.verify(info[0], self.name, mounts, self.request)
            self.proc = self.command.spawn(['start', '--attach', '--interactive', cid])
            for stream in (self.proc.stdin, self.proc.stdout, self.proc.stderr):
                os.set_blocking(stream.fileno(), False)
            self.pending = wire.frame({'binding': self.binding}, self.request['frame_bytes'])
            return self
        except BaseException as error:
            self.failed = error
            failures = []
            try: self.abort()
            except BaseException as cleanup: failures.append(cleanup)
            raise_all(error, failures)

    def request_operation(self, operation, payload):
        need(self.proc is not None and not self.closed and self.failed is None, 'live original fitted child')
        sel = None; primary = None; failures = []; result = None
        try:
            request = {'version': 'N061_CHILD_V1', 'sequence': self.sequence, 'binding': self.binding,
                       'operation': operation, 'payload': payload}
            outgoing = self.pending + wire.frame(request, self.request['frame_bytes']); self.pending = b''
            self.owner.reserve('write_bytes', len(outgoing))
            output = bytearray(); position = 0; expected = None; sel = selectors.DefaultSelector()

            for stream, events, label in ((self.proc.stdin, selectors.EVENT_WRITE, 'in'),
                                          (self.proc.stdout, selectors.EVENT_READ, 'out'),
                                          (self.proc.stderr, selectors.EVENT_READ, 'err')):
                sel.register(stream, events, label)
            while expected is None or len(output) < expected:
                self.owner.tick(); need(time.monotonic_ns() < self.deadline, 'whole child deadline')
                for key, _ in sel.select(.1):
                    if key.data == 'in':
                        count = os.write(key.fd, outgoing[position:position + 65536]); position += count
                        if position == len(outgoing): sel.unregister(key.fileobj)
                        continue
                    part = os.read(key.fd, 65536)
                    if not part:
                        self.eofs.add(key.data); sel.unregister(key.fileobj)
                        need(key.data != 'out', 'child stdout EOF before complete response')
                        continue
                    self.owner.reserve('read_bytes', len(part))
                    if key.data == 'err':
                        self.err_bytes += len(part)
                        need(self.err_bytes <= self.request['stderr_bytes'], 'whole child stderr cap')
                    else:
                        self.out_bytes += len(part)
                        need(len(output) + len(part) <= self.request['frame_bytes'] + 8, 'response cap')
                        output.extend(part)
                        if expected is None and len(output) >= 8:
                            size = struct.unpack('>Q', output[:8])[0]
                            need(0 < size <= self.request['frame_bytes'], 'response declared extent'); expected = size + 8
                        need(expected is None or len(output) <= expected, 'unsolicited/trailing response bytes')
            need(position == len(outgoing), 'response cannot precede complete input')
            response = wire.decode(bytes(output[8:]), self.request['frame_bytes'])
            need(type(response) is dict and set(response) == {'version', 'sequence', 'binding', 'operation', 'result'} and
                 all(response[key] == request[key] for key in ('version', 'sequence', 'binding', 'operation')),
                 'exact original request response inverse')
            result = response['result']
        except BaseException as error:
            primary = error
        finally:
            if sel is not None:
                try: sel.close()
                except BaseException as error: failures.append(error)
        if primary is not None or failures:
            self.failed = primary if primary is not None else failures[0]
            raise_all(primary, failures)
        self.events.append((self.sequence, operation)); self.sequence += 1
        return result

    def finish(self):
        need(self.failed is None and not self.closed and self.proc is not None and
             self.events and self.events[-1][1] == 'retire', 'successful explicit retirement required')
        sel = None; primary = None; failures = []; closure = None
        try:
            self.proc.stdin.close()
            sel = selectors.DefaultSelector()
            for stream, label in ((self.proc.stdout, 'out'), (self.proc.stderr, 'err')):
                if label not in self.eofs: sel.register(stream, selectors.EVENT_READ, label)
            while sel.get_map():
                self.owner.tick(); need(time.monotonic_ns() < self.deadline, 'closure deadline not renewed')
                for key, _ in sel.select(.1):
                    part = os.read(key.fd, 65536)
                    if not part:
                        self.eofs.add(key.data); sel.unregister(key.fileobj); continue
                    self.owner.reserve('read_bytes', len(part))
                    need(key.data == 'err', 'trailing stdout after retirement')
                    self.err_bytes += len(part); need(self.err_bytes <= self.request['stderr_bytes'], 'whole stderr cap')
            self.proc.wait(timeout=max(.001, (self.deadline-time.monotonic_ns())/1e9))
            need(self.proc.returncode == 0 and self.eofs == {'out', 'err'}, 'zero local exit and both original EOFs')
            require_group_absence(self.proc.pid)
            info = strict(self.command.run(['inspect', self.container_id]))
            need(type(info) is list and len(info) == 1 and info[0]['Id'] == self.container_id, 'same exited container')
            state = info[0]['State']
            need(state['Status'] == 'exited' and state['Running'] is False and state['Pid'] == 0 and
                 state['ExitCode'] == 0 and state['OOMKilled'] is False and not state.get('Error'),
                 'outside observed native exit; no OOM or daemon error')
            self.command.run(['rm', self.container_id])
            remaining = self.command.run(['container', 'ls', '-aq', '--no-trunc', '--filter', 'id=' + self.container_id])
            need(remaining.strip() == b'', 'successful daemon absence query')
            for stream in (self.proc.stdout, self.proc.stderr): stream.close()
            shutil.rmtree(self.directory)
            closure = ClosedChild(self.binding, self.container_id, self.proc.pid, 0, self.sequence,
                                  self.out_bytes, self.err_bytes, True)
        except BaseException as error:
            primary = error; self.failed = error
        finally:
            if sel is not None:
                try: sel.close()
                except BaseException as error: failures.append(error)
        if primary is None and not failures:
            self.closed = True
            return closure
        try: self.abort()
        except BaseException as error: failures.append(error)
        raise_all(primary, failures)

    def abort(self):
        """Attempt all exact owned cleanup; unresolved resources remain open."""
        failures = []
        # Name is fixed before create, so partial create output retains a target.
        if self.create_started and not self.closed:
            target = self.container_id or self.name
            try: self.command.run(['rm', '--force', target], cleanup=True)
            except BaseException as error: failures.append(error)
            selector = 'id=' + self.container_id if self.container_id else 'name=^/' + self.name + '$'
            try:
                remaining = self.command.run(['container', 'ls', '-aq', '--no-trunc', '--filter', selector], cleanup=True)
                need(remaining.strip() == b'', 'owned container still present after cleanup')
            except BaseException as error: failures.append(error)
        if self.proc is not None:
            # Always target the original group; leader exit/reap is insufficient.
            try: os.killpg(self.proc.pid, signal.SIGKILL)
            except ProcessLookupError: pass
            except BaseException as error: failures.append(error)
            try: self.proc.wait(timeout=self.request['command_seconds'])
            except BaseException as error: failures.append(error)
            try: require_group_absence(self.proc.pid)
            except BaseException as error: failures.append(error)
            for stream in (self.proc.stdin, self.proc.stdout, self.proc.stderr):
                try: stream.close()
                except BaseException as error: failures.append(error)
        if self.directory is not None:
            try: shutil.rmtree(self.directory)
            except FileNotFoundError: pass
            except BaseException as error: failures.append(error)
        if not failures:
            self.closed = True
        raise_all(None, failures)
