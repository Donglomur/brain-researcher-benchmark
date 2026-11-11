"""Real bounded RPC to a separately qualified model/agent harness.

The benchmark does not implement or trust the candidate model itself. The
operator's source-pinned external harness must enforce token/model/session
policy; its independently collected usage remains a deployment gate.
"""
import os
from pathlib import Path
import socket
import stat
import struct
import time
from .custody import encode, need, parse, pin


class Harness:
    def __init__(self, profile, budget):
        self.profile, self.budget = profile, budget
        self.session = None
        self.request_id = None
        self.begin_attempted = False
        self.requested_limits = None
        self.transcript = []
        self.closed = False
        # Reserve one cleanup request/response before any session creation.
        budget.charge_write(65540)
        budget.charge_read(65540)

    def rpc(self, request, *, cleanup=False):
        # Cleanup remains attempted if the normal operation deadline passed;
        # it still has a bounded independent timeout and cannot grant success.
        timeout = min(2., max(.001, self.budget.deadline - time.monotonic())) if cleanup else min(5., self.budget.deadline - time.monotonic())
        need(timeout > 0, 'harness deadline')
        cutoff = time.monotonic() + timeout
        path = Path(self.profile['control_socket'])
        need(path.is_absolute() and not any(p.is_symlink() for p in (path, *path.parents))
             and stat.S_ISSOCK(path.stat().st_mode), 'selected ordinary Unix harness socket')
        raw = encode(request)
        need(len(raw) <= 65536, 'bounded harness request')
        if not cleanup:
            self.budget.charge_write(len(raw) + 4)
            self.budget.charge_read(65540)
        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        primary = None
        try:
            client.settimeout(timeout); client.connect(str(path))
            pid, uid, gid = struct.unpack('3i', client.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
            need((pid, uid, gid) == tuple(self.profile['peer_credentials']), 'qualified exact harness peer')
            client.sendall(struct.pack('!I', len(raw)) + raw)
            def receive(n):
                blocks = []
                while n:
                    remaining = cutoff - time.monotonic()
                    need(remaining > 0, 'whole harness frame deadline')
                    client.settimeout(remaining)
                    part = client.recv(n)
                    need(bool(part), 'complete harness frame')
                    blocks.append(part); n -= len(part)
                return b''.join(blocks)
            length = struct.unpack('!I', receive(4))[0]
            need(length <= 65536, 'bounded harness response')
            body = receive(length)
            client.shutdown(socket.SHUT_WR)
            need(client.recv(1) == b'', 'exact harness response EOF')
            response = parse(body)
            self.transcript.append({'request': pin(raw), 'response': pin(body), 'operation': request['operation'],
                                    'cleanup': cleanup, 'observed_peer': [pid, uid, gid]})
            self.budget.write_completed += len(raw) + 4
            self.budget.read_completed += len(body) + 4
            return response
        except BaseException as error:
            primary = error; raise
        finally:
            try:
                client.close()
            except BaseException as error:
                if primary is not None:
                    primary.add_note('Harness socket close: ' + type(error).__name__)
                    primary.cleanup_uncertain = True
                else:
                    raise

    def begin(self, *, selection_id, condition, prompt_sha256, token_limit, invocation_limit):
        need(self.session is None, 'one fresh independent session')
        self.request_id = selection_id + ':' + condition
        self.requested_limits = {'tokens': token_limit, 'invocations': invocation_limit}
        self.begin_attempted = True
        result = self.rpc({'schema': 'neural098-agent-harness-request-v1', 'operation': 'begin',
                           'request_id': self.request_id,
                           'selection_id': selection_id, 'condition': condition,
                           'model': self.profile['model'], 'prompt_sha256': prompt_sha256,
                           'max_tokens': token_limit, 'max_invocations': invocation_limit,
                           'feedback': 'none', 'family': 'cogitate-family'})
        if type(result) is dict and type(result.get('session_id')) is str and 0 < len(result['session_id']) <= 256:
            self.session = result
        need(type(result) is dict and set(result) == {'schema', 'session_id', 'request_id', 'model_socket', 'accepted',
             'model', 'max_tokens', 'max_invocations'} and result['schema'] == 'neural098-agent-harness-session-v1'
             and result['accepted'] is True and result['request_id'] == self.request_id and self.session is not None
             and result['model'] == self.profile['model']
             and result['max_tokens'] == token_limit and result['max_invocations'] == invocation_limit,
             'exact accepted fresh model session')
        self.session = result
        endpoint = Path(result['model_socket'])
        need(endpoint.is_absolute() and endpoint.parent == Path(self.profile['session_socket_parent'])
             and not endpoint.is_symlink() and stat.S_ISSOCK(endpoint.stat().st_mode), 'only selected model session socket')
        return result

    def close(self):
        if self.closed:
            return None
        # Record closure attempt before RPC: no blind second call after ambiguity.
        self.closed = True
        if not self.begin_attempted:
            return None
        session_id = None if self.session is None else self.session['session_id']
        result = self.rpc({'schema': 'neural098-agent-harness-request-v1', 'operation': 'close',
                           'request_id': self.request_id, 'session_id': session_id}, cleanup=True)
        need(type(result) is dict and set(result) == {'schema', 'session_id', 'request_id', 'closed', 'usage', 'failure'}
             and result['schema'] == 'neural098-agent-harness-closure-v1'
             and result['request_id'] == self.request_id
             and (session_id is None or result['session_id'] == session_id) and result['closed'] is True
             and result['failure'] is None, 'complete independent provider closure')
        usage = result['usage']
        need(type(usage) is dict and set(usage) == {'tokens', 'invocations'}
             and all(type(v) is int and v >= 0 for v in usage.values())
             and usage['tokens'] <= self.requested_limits['tokens']
             and usage['invocations'] <= self.requested_limits['invocations'], 'trusted actual complete harness usage')
        return result
