"""NEURAL067 attach stream derived from the reviewed NEURAL024 causal pipe.

Only transport bytes are handled here. The caller validates query frames and
admits state/run artifacts after natural container exit and owned absence.
"""
import hashlib
import os
import selectors
import signal
import struct
import subprocess
import time

MAGIC = b'N067STATE1\n'
STATE_CAP = 32 * 1024 * 1024
STATE_HEADER = len(MAGIC) + 8 + 32
STDOUT_CAP = 40000000
STDERR_CAP = 65536
LINE_CAP = 1024
INPUT_CAP = 4096


def need(ok, message):
    if not ok:
        raise ValueError(message)


class Stream:
    def __init__(self, binary, env, identifier, deadline, budget, *, mode):
        need(mode in ('train', 'query'), 'Exact NEURAL067 stream mode')
        need(type(identifier) is str and len(identifier) == 64
             and all(c in '0123456789abcdef' for c in identifier), 'Exact container ID')
        need(type(binary) is str and binary.startswith('/'), 'Pinned absolute Docker binary')
        need(type(env) is dict and type(env.get('DOCKER_HOST')) is str
             and env['DOCKER_HOST'].startswith('unix:///')
             and not env.get('DOCKER_CONTEXT'), 'Explicit local daemon environment')
        self.mode, self.deadline, self.budget = mode, deadline, budget
        self.p = None
        self.sel = None
        self.out = bytearray()
        self.stderr = bytearray()
        self.received = {'stdout': 0, 'stderr': 0}
        self.hashes = {k: hashlib.sha256() for k in self.received}
        self.expecting = mode == 'query'
        self.stdout_eof = False
        self.forced = False
        self.finished = False
        self.natural_returncode = None
        self._header = bytearray()
        self._length = None
        self._state_written = 0
        self._state_hash = hashlib.sha256()
        self._expected_hash = None
        self._sink = None
        self._state_complete = False
        try:
            self.tick()
            self.p = subprocess.Popen(
                [binary, 'container', 'start', '--attach', '--interactive', identifier],
                env=dict(env), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, bufsize=0, start_new_session=True)
            self.sel = selectors.DefaultSelector()
            for name, pipe in [('stdout', self.p.stdout), ('stderr', self.p.stderr)]:
                os.set_blocking(pipe.fileno(), False)
                self.sel.register(pipe, selectors.EVENT_READ, name)
            os.set_blocking(self.p.stdin.fileno(), False)
            if mode == 'train':
                self.p.stdin.close()
                need(self.p.stdin.closed is True, 'Training stdin closed')
            self.tick()
        except BaseException as error:
            closure = self.close(deadline)
            try:
                error.attach_closure = closure
            except BaseException:
                pass
            raise

    def tick(self):
        self.budget.tick()
        need(time.monotonic() < self.deadline, 'Candidate absolute deadline')

    def _training(self, body):
        need(self._sink is not None, 'Training sink installed before reading')
        if len(self._header) < STATE_HEADER:
            take = min(STATE_HEADER - len(self._header), len(body))
            self._header.extend(body[:take])
            body = body[take:]
            if len(self._header) >= len(MAGIC):
                need(bytes(self._header[:len(MAGIC)]) == MAGIC, 'Exact state magic')
            if len(self._header) < STATE_HEADER:
                return
            self._length = struct.unpack('<Q', self._header[len(MAGIC):len(MAGIC) + 8])[0]
            need(0 < self._length <= STATE_CAP, 'One positive bounded opaque state')
            self._expected_hash = bytes(self._header[-32:])
        need(len(body) <= self._length - self._state_written, 'No extra state frame bytes')
        if body:
            self._sink(body)
            self._state_hash.update(body)
            self._state_written += len(body)
        if self._state_written == self._length:
            need(self._state_hash.digest() == self._expected_hash, 'Opaque state SHA256')
            self._state_complete = True

    def ingest(self, name, body):
        need(name in self.received and type(body) is bytes, 'Exact stream byte source')
        cap = STDERR_CAP if name == 'stderr' else (STATE_CAP + STATE_HEADER if self.mode == 'train' else STDOUT_CAP)
        need(len(body) <= cap - self.received[name], 'Total stream cap before retention')
        self.received[name] += len(body)
        self.hashes[name].update(body)
        if name == 'stderr':
            self.stderr.extend(body)
            return
        if self.mode == 'train':
            self._training(body)
            return
        need(self.expecting, 'Unsolicited or pipelined stdout')
        need(len(body) <= LINE_CAP - len(self.out), 'One bounded pending frame')
        proposed = bytes(self.out) + body
        need(b'\n' not in proposed or proposed.index(b'\n') == len(proposed) - 1,
             'Extra or pipelined response bytes')
        proposed.decode('ascii', errors='strict')
        self.out.extend(body)

    def _read_size(self, name):
        if name == 'stderr':
            return min(4096, STDERR_CAP - self.received[name] + 1)
        if self.mode == 'query':
            return min(4096, LINE_CAP - len(self.out) + 1, STDOUT_CAP - self.received[name] + 1)
        if self._state_complete:
            return 1
        return min(32768, STATE_CAP + STATE_HEADER - self.received[name] + 1)

    def pump(self, timeout=.01):
        self.tick()
        for key, _ in self.sel.select(min(timeout, max(0, self.deadline - time.monotonic()))):
            self.tick()
            count = self._read_size(key.data)
            self.budget.read(count)
            try:
                body = os.read(key.fileobj.fileno(), count)
            except BlockingIOError:
                continue
            self.tick()
            if not body:
                self.sel.unregister(key.fileobj)
                if key.data == 'stdout':
                    self.stdout_eof = True
            else:
                self.ingest(key.data, body)

    def idle(self):
        need(self.mode == 'query', 'Query idle operation')
        self.tick()
        need(not self.expecting and not self.out, 'No outstanding reply')
        self.pump(0)
        need(not self.out, 'No speculative frame')

    def line(self):
        need(self.mode == 'query', 'Query line operation')
        self.tick()
        need(self.expecting, 'One reply for one request')
        while not self.out.endswith(b'\n'):
            need(not self.stdout_eof, 'EOF before complete response')
            self.pump()
        result = bytes(self.out)
        self.out.clear()
        self.expecting = False
        self.tick()
        return result

    def send(self, body):
        self.idle()
        need(type(body) is bytes and 0 < len(body) <= INPUT_CAP and body.endswith(b'\n'),
             'Bounded complete input frame')
        body.decode('ascii', errors='strict')
        need(body.count(b'\n') == 1, 'One input frame')
        self.budget.read(len(body))
        position = 0
        while position < len(body):
            self.tick()
            try:
                count = os.write(self.p.stdin.fileno(), body[position:])
                need(type(count) is int and 0 < count <= len(body) - position, 'Complete stdin progress')
                position += count
            except BlockingIOError:
                # A response during incomplete input is unsolicited.
                self.pump()
        self.tick()
        self.expecting = True

    def capture_state(self, sink):
        need(self.mode == 'train' and self._sink is None and callable(sink), 'One training sink')
        self._sink = sink
        while not self.stdout_eof:
            self.pump()
        need(self._state_complete and self._state_written == self._length, 'Complete single opaque state')
        self.tick()
        return {'bytes': self._state_written, 'sha256': self._state_hash.hexdigest()}

    def finish(self):
        self.tick()
        need(not self.finished, 'Single stream finish')
        if self.mode == 'query':
            self.idle()
        else:
            need(self._state_complete and self.stdout_eof, 'State frame complete before finish')
        self.p.stdin.close()
        need(self.p.stdin.closed is True, 'Candidate input stream closed')
        while self.sel.get_map():
            self.pump()
        self.tick()
        rc = self.p.wait(timeout=max(.001, self.deadline - time.monotonic()))
        self.tick()
        need(type(rc) is int and rc == 0 and not self.out, 'Natural attach exit zero')
        self.natural_returncode = rc
        self.finished = True

    def close(self, cleanup_end):
        """Independently attempt every closure; unknown/late closure is explicit."""
        errors = []
        reaped = self.p is None
        absent = self.p is None
        selector_closed = self.sel is None
        streams_closed = {name: self.p is None for name in ('stdin', 'stdout', 'stderr')}
        if self.p is not None:
            running = True
            try:
                running = self.p.poll() is None
            except BaseException as error:
                errors.append(('poll', type(error).__name__))
            if running:
                self.forced = True
                try:
                    os.killpg(self.p.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                except BaseException as error:
                    errors.append(('kill_group', type(error).__name__))
            try:
                rc = self.p.wait(timeout=max(.001, min(1, cleanup_end - time.monotonic())))
                need(type(rc) is int, 'Observed attach reap')
                reaped = True
            except BaseException as error:
                errors.append(('reap', type(error).__name__))
            try:
                os.killpg(self.p.pid, 0)
                self.forced = True
                try:
                    os.killpg(self.p.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                try:
                    os.killpg(self.p.pid, 0)
                except ProcessLookupError:
                    absent = True
            except ProcessLookupError:
                absent = True
            except BaseException as error:
                errors.append(('group_absence', type(error).__name__))
            if not absent:
                errors.append(('group_absence', 'Unconfirmed'))
        if self.sel is not None:
            try:
                self.sel.close()
                selector_closed = True
            except BaseException as error:
                errors.append(('selector_close', type(error).__name__))
        if self.p is not None:
            for name in ('stdin', 'stdout', 'stderr'):
                pipe = getattr(self.p, name, None)
                try:
                    need(pipe is not None, 'Owned attach pipe exists')
                    pipe.close()
                    need(pipe.closed is True, 'Observed pipe closure')
                    streams_closed[name] = True
                except BaseException as error:
                    errors.append((name + '_close', type(error).__name__))
        deadline_met = time.monotonic() < cleanup_end
        if not deadline_met:
            errors.append(('cleanup_deadline', 'Expired'))
        return {'attach_reaped': reaped, 'attach_group_absent': absent,
                'streams_closed': streams_closed, 'selector_closed': selector_closed,
                'forced_attach_stop': self.forced, 'finished': self.finished,
                'natural_returncode': self.natural_returncode, 'deadline_met': deadline_met,
                'error_type': errors[0][1] if errors else None, 'cleanup_errors': errors,
                'received_bytes': dict(self.received),
                'stream_sha256': {k: v.hexdigest() for k, v in self.hashes.items()}}
