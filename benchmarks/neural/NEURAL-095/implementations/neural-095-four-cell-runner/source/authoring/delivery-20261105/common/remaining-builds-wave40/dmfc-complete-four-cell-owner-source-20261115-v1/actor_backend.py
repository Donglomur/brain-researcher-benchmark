"""DMFC domain adapter over the shared persistent isolated actor transport.

The closed loader injects the previously accepted `live` module and its one
producer ABI. Scalar decisions never launch numerical containers. Candidate
analysis remains in source-pinned numerical tools with frozen TRAIN artifacts.
"""
import base64
import hmac
import math
import os
from pathlib import Path
import secrets
import socket
import stat
import time

need, encode, sha = live.need, live.encode, live.sha
MAX_UNITS = 46
ACTOR_TASKS = 8
MEMORY = live.MEMORY


class Channel:
    """Task envelopes only; reuse accepted Wire and kernel peer authentication."""
    def __init__(self, path, wire_type, authenticate, deadline, response_cap=262144):
        self.path = Path(path); self.deadline = deadline; self.cap = response_cap
        need(not self.path.exists() and not self.path.is_symlink(), 'fresh actor socket')
        st = self.path.parent.stat()
        need(stat.S_ISDIR(st.st_mode) and stat.S_IMODE(st.st_mode) == 0o700 and st.st_uid == os.geteuid(),
             'private operator socket directory')
        self.wire_type, self.authenticate = wire_type, authenticate
        self.token, self.sequence = secrets.token_hex(32), 1
        self.connection = self.wire = None; self.closed = False
        self.listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.listener.bind(str(self.path)); os.chmod(self.path, 0o600)
        s = self.path.lstat(); self.identity = (s.st_dev, s.st_ino)
        self.listener.listen(1)

    def accept(self, until):
        need(self.connection is None and not self.closed, 'one actor connection')
        self.listener.settimeout(max(.001, min(until, self.deadline) - time.monotonic()))
        self.connection, _ = self.listener.accept()
        need(self.authenticate(self.connection) == os.geteuid(), 'actual kernel peer UID')
        self.wire = self.wire_type(self.connection, self.deadline)

    def receive(self, op, until):
        need(not self.closed and self.wire is not None, 'live actor capability')
        self.wire.deadline = min(until, self.deadline)
        value = self.wire.frame(65536)
        fields = {'seq', 'token', 'op'} | ({'source'} if op == 'freeze' else {'request'} if op == 'public' else set())
        need(type(value) is dict and set(value) == fields and type(value['seq']) is int and
             value['seq'] == self.sequence and value['op'] == op and type(value['token']) is str and
             hmac.compare_digest(value['token'], self.token), 'exact authenticated actor sequence')
        return value.get('source') if op == 'freeze' else value.get('request')

    def answer(self, payload, until, *, status='ok'):
        self.wire.deadline = min(until, self.deadline)
        if status == 'committed':
            need(type(payload) is dict and set(payload) == {'controller_sha256'}, 'exact source commitment reply')
            value = {'seq': self.sequence, 'status': status, **payload}
        else:
            need(status == 'ok', 'public response status')
            value = {'seq': self.sequence, 'status': status, 'payload': payload}
        self.wire.send_frame(value, self.cap)
        self.sequence += 1

    def close(self):
        if self.closed:
            return
        self.closed = True
        try:
            if self.connection is not None:
                self.connection.close()
        finally:
            self.listener.close()
            if self.path.exists() or self.path.is_symlink():
                s = self.path.lstat()
                need(stat.S_ISSOCK(s.st_mode) and (s.st_dev, s.st_ino) == self.identity,
                     'never unlink a replaced socket')
                self.path.unlink()


class ActorBackend(live.LiveBackend):
    """Same Cell/Study API, persistent actor and at most18 numerical units/cell.

    actor_factory(started_us, deadline_us, backend) returns the shared admitted
    Supervisor and this channel after writing the exact task invitation. It
    never supplies public/private data mounts to the actor.
    """
    def __init__(self, *, actor_factory, preparation_tool_id, **kwargs):
        super().__init__(**kwargs)
        need(preparation_tool_id in self.tools, 'TRAIN code is a committed numerical tool')
        self.preparation_tool_id = preparation_tool_id; self.factory = actor_factory
        self.actor = self.channel = None; self.actor_absent = True
        self.actor_receipt = None; self.actor_clock = None; self.frozen_batch = None

    def _public(self, expected, until):
        request = self.channel.receive('public', until)
        need(request == expected, 'exact host-owned phase and pending request')

    def _actor_start(self, deadline_us):
        need(self.actor is None, 'fresh actor once per cell')
        started = deadline_us - self.limits.preparation_wall_us
        self.actor_clock = started
        self.actor, self.channel = self.factory(started, started + self.limits.wall_us, self)
        self.actor_absent = False
        self.actor.launch(); until = min(deadline_us / 1000000, time.monotonic() + 20)
        self.channel.accept(until)
        source = self.channel.receive('freeze', until)
        need(type(source) is str and source.encode() == self.source, 'actor freezes its exact admitted source')
        self.channel.answer({'controller_sha256': sha(self.source)}, until, status='committed')

    def _actor_stop(self):
        if self.actor is None or self.actor_absent:
            return
        try:
            self.actor_receipt = self.actor.stop()
            need(self.actor_receipt.get('absence_verified') is True, 'actor creator and container absent')
            self.actor_absent = True
        finally:
            self.channel.close()

    def operate(self, request, *, reservation, deadline_us, memory_bytes):
        need(not self.closed and isinstance(reservation, self.api.Usage) and reservation.calls == 1 and
             reservation.model_input_tokens == reservation.model_output_tokens == reservation.model_cost_microusd == 0,
             'exact offline ABI and no provider account')
        need(memory_bytes == MEMORY and type(deadline_us) is int, 'fixed whole memory/deadline')
        need(type(request) is dict and set(request) == {'operation', 'payload'}, 'exact operation')
        op, payload = request['operation'], request['payload']
        until = min(deadline_us / 1000000, time.monotonic() + (10 if op == 'decide' else 96))
        cpu = 0
        try:
            if op == 'prepare':
                need(self.state == 'preparation' and payload is None, 'once-only TRAIN preparation')
                self._actor_start(deadline_us)
                self._public({'kind': 'prepare'}, until)
                answer, cpu = self._invoke(self.tools[self.preparation_tool_id], 'prepare', None, reservation, until)
                need(type(answer) is dict and set(answer) == {'artifact_base64'} and type(answer['artifact_base64']) is str
                     and len(answer['artifact_base64']) <= 4 * ((live.ARTIFACT_CAP + 2) // 3), 'bounded TRAIN artifact')
                self.artifact = base64.b64decode(answer['artifact_base64'], validate=True)
                need(0 < len(self.artifact) <= live.ARTIFACT_CAP, 'nonempty frozen artifact')
                live.write(self.root / 'fitted.bin', self.artifact, live.ARTIFACT_CAP)
                self.state = 'prepared'; result = {'training_artifacts_sha256': sha(self.artifact)}
                self.channel.answer(result, until)
            elif op == 'decide':
                need(self.state == 'query' and not hasattr(self, 'pending_tool') and self.decisions < 258 and
                     payload == {'case_id': self.ids[self.decisions], 'completed_cases': self.decisions,
                                 'full_query_batch_visible': True}, 'ordered full258 decisions')
                self._public({'kind': 'next'}, until)
                self.channel.answer(payload, until)
                value = self.channel.receive('public', until)
                need(type(value) is dict and set(value) == {'kind', 'action'} and value['kind'] == 'action',
                     'actor action envelope')
                result = value['action']
                need(type(result) is dict and result.get('action') in ('predict', 'tool'), 'allowed actor action')
                if result['action'] == 'predict':
                    need(set(result) == {'action', 'case_id', 'prediction_ms'} and result['case_id'] == self.ids[self.decisions]
                         and type(result['prediction_ms']) in (int, float) and math.isfinite(result['prediction_ms']), 'finite current prediction')
                    if self.mode == 'frozen_program':
                        need(self.frozen_batch is not None and result['prediction_ms'] == self.frozen_batch[self.decisions],
                             'frozen actor cannot adapt the committed full-batch program')
                    self.decisions += 1
                else:
                    limit = 1 if self.mode == 'frozen_program' else live.MAX_TOOLS
                    need(set(result) == {'action', 'tool_id', 'arguments'} and result['tool_id'] in self.tools and
                         type(result['arguments']) is dict and self.tool_calls < limit, 'mode-specific fixed numerical tool bound')
                    if self.mode == 'frozen_program':
                        need(result['tool_id'] == self.preparation_tool_id and result['arguments'] == {},
                             'frozen mode has only its one committed full-batch program')
                    self.pending_tool = live.decode(encode(result))
                self.channel.answer({'accepted': True}, until)
            elif op == 'tool':
                need(self.state == 'query' and hasattr(self, 'pending_tool') and
                     payload == {'case_id': self.ids[self.decisions], **self.pending_tool}, 'only pending admitted tool')
                tool = self.pending_tool
                self._public({'kind': 'tool', 'tool_id': tool['tool_id'], 'arguments': tool['arguments']}, until)
                del self.pending_tool; self.tool_calls += 1
                result, cpu = self._invoke(self.tools[tool['tool_id']], 'tool', payload, reservation, until)
                need(len(encode(result)) <= live.STATE_CAP, 'bounded numerical observation')
                if self.mode == 'frozen_program':
                    need(type(result) is dict and set(result) == {'case_id', 'prediction_ms'} and
                         result['case_id'] == list(self.ids) and type(result['prediction_ms']) is list and
                         len(result['prediction_ms']) == 258 and all(type(x) in (int, float) and math.isfinite(x)
                         for x in result['prediction_ms']), 'complete unchanged frozen batch')
                    self.frozen_batch = tuple(result['prediction_ms'])
                self.channel.answer(result, until)
            elif op == 'export':
                need(self.state == 'query' and self.decisions == 258 and not hasattr(self, 'pending_tool'),
                     'all258 decisions before terminal actor request')
                self.channel.receive('finish', until)
                self._actor_stop()  # no reply/private feedback to a live actor
                reply = super().operate(request, reservation=reservation, deadline_us=deadline_us, memory_bytes=memory_bytes)
                result, cpu = reply.payload, reply.usage.cpu_us
            else:
                raise ValueError('unknown operation')
            now = time.monotonic_ns() // 1000
            need(self.actor_clock is not None and now >= self.actor_clock, 'original monotonic actor accounting')
            actor_cpu = ACTOR_TASKS * (now - self.actor_clock)
            self.actor_clock = now
            return self.api.Reply(result, self.api.Usage(calls=1, cpu_us=cpu + actor_cpu), MEMORY,
                                  sha(self.source), 'preparation' if op == 'prepare' else self.mode)
        except BaseException:
            self.state = 'failed'
            raise

    def _absence(self):
        return dict.fromkeys(self.api.ABSENCE, self.actor_absent and self.executor.absence())

    def stop(self):
        try:
            self._actor_stop()
        finally:
            self.closed = True
        return self._absence()
