"""Concrete reference-worker issuer, phase RPC, remote capture and retirement.

This composes an ORIGINAL live qualification issuer; it cannot issue one from
JSON. No scientific arguments, seeds, grids or populations are supplied here.
Actual Linux/offline/fork-safe/cgroup qualification remains external and closed
until the original operator admits the exact complete programme and namespace.
"""
from dataclasses import dataclass
import base64
import errno
import os
from pathlib import Path
import socket
import signal
import sys
import threading
import time
from .core import Refusal, decode, encode, exact, need, ordinary, pin
from .lifecycle import Custody
from .worker_transport import CgroupTree, ParentChannel, RemoteCostPrefix, wire_receive, wire_send
from .captured_author import CapturedAuthorClosure, capture_author

_REMOTE = {}


@dataclass(frozen=True)
class RemoteCapturedOperation:
    body: bytes
    producer: object
    worker: object
    slot: object
    terminal: bytes


class RemoteWorkerFailure(Refusal):
    """Child error DOCUMENT, never the child's original exception identity."""
    def __init__(self, document):
        self.document = encode(document)
        super().__init__('owned native child failed; remote error document retained')


def transport_plan(plan):
    exact(plan, ('author_root', 'cgroup_parent', 'wall_seconds', 'retirement_seconds',
                 'frame_bytes', 'transport_bytes', 'log_bytes'), 'native transport plan')
    for name in ('author_root', 'cgroup_parent'):
        need(type(plan[name]) is str and Path(plan[name]).is_absolute(), 'absolute selected native namespace')
        ordinary(plan[name])
    for name, upper in (('wall_seconds', 604800), ('retirement_seconds', 300),
                        ('frame_bytes', 4194304), ('transport_bytes', 67108864), ('log_bytes', 1048576)):
        need(type(plan[name]) is int and 0 < plan[name] <= upper, 'finite transport limit: ' + name)
    need(plan['frame_bytes'] >= 1024 and plan['transport_bytes'] >= plan['frame_bytes'], 'coherent frame/transport limits')
    return decode(encode(plan))


class NativeWorkerIssuer:
    """Adapter around an actual deployment issuer, not a replacement authority."""
    def __init__(self, original_issuer, plan):
        need(not isinstance(original_issuer, (dict, str, bytes)) and callable(getattr(original_issuer, 'issue', None)), 'original live issuer')
        self.original, self.plan = original_issuer, encode(transport_plan(plan))
        self.used = False

    def issue(self, request):
        need(not self.used, 'one source transport lease issuance')
        self.used = True
        original = self.original.issue(request)
        custody = Custody('native_worker_lease_issuance')
        try:
            for method in ('require', 'close', 'terminal', 'native_plan'):
                need(callable(getattr(original, method, None)), 'complete original live lease')
            original.require('source_worker_transport:' + pin(self.plan)['sha256'], request['source_sha256'])
            return NativeWorkerLease(original, request['source_sha256'], self.plan)
        except BaseException as exc:
            custody.capture(exc, 'source_lease_admission')
            if callable(getattr(original, 'close', None)):
                custody.attempt('original_lease_close', original.close)
            custody.raise_first()


class NativeWorkerLease:
    def __init__(self, original, source_sha256, plan):
        self.original, self.source_sha256, self.plan = original, source_sha256, plan
        self.parent_pid = os.getpid()
        self.channel = None
        self.active_worker = None
        self.closure = None
        self.captured = None
        self.closed = False
        self.workers = []

    def require(self, phase, source_sha256):
        need(not self.closed and source_sha256 == self.source_sha256, 'original selected live lease')
        if os.getpid() == self.parent_pid:
            return self.original.require(phase, source_sha256)
        worker = self.active_worker
        need(self.channel is not None and worker is not None and worker.child_pid == os.getpid(), 'owned selected child phase channel')
        worker.sequence += 1
        message = {'kind': 'phase', 'sequence': worker.sequence, 'selection': worker.selection_pin,
                   'phase': phase, 'source_sha256': source_sha256}
        worker.send_child(message)
        answer = wire_receive(self.channel, worker.deadline, worker.plan['frame_bytes'])
        exact(answer, ('kind', 'sequence', 'selection', 'allowed'), 'parent phase reply')
        need(answer == {'kind': 'phase_reply', 'sequence': worker.sequence,
                        'selection': worker.selection_pin, 'allowed': True}, 'original parent phase admission')

    def native_plan(self, *args, **kwargs):
        need(os.getpid() == self.parent_pid, 'candidate plan belongs to original parent')
        return self.original.native_plan(*args, **kwargs)

    def terminal(self, *args, **kwargs):
        need(os.getpid() == self.parent_pid, 'candidate terminal belongs to original parent')
        return self.original.terminal(*args, **kwargs)

    def issue_reference_worker(self, host, context, selected, slot):
        need(os.getpid() == self.parent_pid and host.lease is self and context.authority is host, 'original parent lease/context worker issuance')
        worker = NativeWorker(self, host, context, selected, slot)
        self.workers.append(worker)
        return worker

    def load_author_module(self, path):
        need(os.getpid() != self.parent_pid and self.active_worker is not None and self.closure is not None, 'captured imports only inside owned child')
        return self.closure.load(path)

    def close(self):
        need(os.getpid() == self.parent_pid, 'only original parent closes live lease')
        if self.closed:
            return
        self.closed = True
        custody = Custody('native_transport_lease_close')
        for worker in self.workers:
            custody.attempt('reference_worker_close:' + worker.operation, worker.close)
        custody.attempt('original_live_lease_close', self.original.close)
        custody.raise_first()


class NativeWorker:
    def __init__(self, lease, host, context, selected, slot):
        self.lease, self.host, self.context, self.slot = lease, host, context, slot
        self.operation = selected['operation']
        self.selected = encode(selected)
        self.selection_pin = pin(self.selected)
        self.producer = None
        self.plan = decode(lease.plan)
        self.used = self.closed = self.terminal_closed = False
        self.pid = self.child_pid = None
        self.status = None
        self.tree = self.prefix = self.channel_owner = None
        self.sockets, self.fds = [], []
        self.socket_close_attempted, self.fd_close_attempted = set(), set()
        self.sequence = 0
        self.capture = None
        self.remote_terminal = None
        self.deadline = None
        self.custody = Custody('native_worker:' + self.operation)
        # Before sockets, cgroup creation, fork, or another fallible acquisition.
        slot.register_issued(self)

    def require(self, phase, host, producer, selected):
        need(host is self.host and host.lease is self.lease and encode(selected) == self.selected, 'same selected worker host and frozen entrypoints')
        if phase == 'issuance':
            need(self.producer is None and not self.used and not self.closed, 'one actual producer binding')
            self.producer = producer
        need(producer is self.producer and producer.worker is self and producer.slot is self.slot, 'original worker/producer/slot binding')
        if phase.startswith('inside_selected_process:') or phase == 'capture':
            need(os.getpid() == self.child_pid and os.getpid() != self.lease.parent_pid and self.lease.active_worker is self, 'actual selected child identity')
        else:
            need(os.getpid() == self.lease.parent_pid, 'original parent worker consumer')
            need(not self.closed or phase == 'after_capture', 'worker already retired')
        self.lease.require('reference_worker:' + self.operation + ':' + phase, self.host.source_sha256)

    def send_child(self, document):
        wire_send(self.lease.channel, document, self.deadline, self.plan['frame_bytes'])

    def _close_socket(self, channel):
        if id(channel) not in self.socket_close_attempted:
            self.socket_close_attempted.add(id(channel))
            channel.close()

    def _close_fd(self, fd):
        if fd not in self.fd_close_attempted:
            self.fd_close_attempted.add(fd)
            os.close(fd)

    def _acquire(self):
        need(sys.platform == 'linux' and hasattr(os, 'fork'), 'qualified Linux fork deployment required')
        need(len(threading.enumerate()) == 1, 'no live Python helper threads at native fork')
        need(not any(k.split('.')[0] in ('numpy', 'torch', 'scipy') for k in sys.modules), 'numerical runtime imported only in fresh child')
        self.lease.require('fork_safe_offline_cgroup_runtime:' + pin(self.lease.plan)['sha256'], self.host.source_sha256)
        if self.lease.captured is None:
            self.lease.captured = capture_author(self.plan['author_root'], self.context.cost, self.host)
        self.tree = CgroupTree(self.plan['cgroup_parent'])
        self.tree.create()
        parent, child = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sockets.extend((parent, child))
        logs = {}
        for name in ('stdout', 'stderr'):
            reader, writer = os.pipe()
            self.fds.extend((reader, writer))
            logs[name] = (reader, writer)
        self.prefix = RemoteCostPrefix(self.context.cost, self.selection_pin)
        self.deadline = time.monotonic() + self.plan['wall_seconds']
        self.prefix.dispatched = True  # fork failure effects remain conservatively unknown
        pid = os.fork()
        if pid == 0:
            self._child(parent, child, logs)
            os._exit(125)
        self.pid = pid  # own exact child immediately; never signal a numeric PID
        self._close_socket(child)
        for reader, writer in logs.values():
            self._close_fd(writer)
        self.tree.attach(pid)  # child cannot execute its entrypoint until GO
        self.channel_owner = ParentChannel(parent, {r: name for name, (r, _) in logs.items()},
                                          self.deadline, self.plan['frame_bytes'], self.plan['transport_bytes'], self.plan['log_bytes'])
        wire_send(parent, {'kind': 'go', 'selection': self.selection_pin}, self.deadline, self.plan['frame_bytes'])
        return parent

    def _child(self, parent, child, logs):
        # No cloned original lease method is called on this side. All phases
        # return over this one inherited channel to the original parent owner.
        self.child_pid = os.getpid()
        self.lease.channel, self.lease.active_worker = child, self
        custody = Custody('native_child:' + self.operation)
        capture = None
        try:
            parent.close()
            for name, target in (('stdout', 1), ('stderr', 2)):
                os.dup2(logs[name][1], target)
            null = os.open('/dev/null', os.O_RDONLY)
            os.dup2(null, 0)
            keep = {0, 1, 2, child.fileno()}
            for item in os.listdir('/proc/self/fd'):
                fd = int(item)
                if fd not in keep:
                    try:
                        os.close(fd)
                    except OSError as exc:
                        if exc.errno != errno.EBADF:
                            raise
            go = wire_receive(child, self.deadline, self.plan['frame_bytes'])
            need(go == {'kind': 'go', 'selection': self.selection_pin}, 'parent attached worker before source entry')
            self.prefix.child_reset()
            self.lease.closure = CapturedAuthorClosure(self.lease.captured, self.plan['author_root'])
            self.lease.closure.install()
            capture = self.producer.execute_in_selected_worker()
            self.producer.capture_owner.admit(capture)
        except BaseException as exc:
            custody.capture(exc, 'fixed_native_source_entry')
        if self.lease.closure is not None:
            custody.attempt('captured_author_closure_close', self.lease.closure.close)
        for name, stream in (('stdout', sys.stdout), ('stderr', sys.stderr)):
            custody.attempt(name + '_flush', stream.flush)
        try:
            self.sequence += 1
            terminal = {'kind': 'terminal', 'sequence': self.sequence, 'selection': self.selection_pin,
                        'status': 'failed' if custody.first is not None else 'complete',
                        'capture': base64.b64encode(capture.body).decode('ascii') if capture is not None and custody.first is None else None,
                        'cost_prefix': self.prefix.child_document(), 'failure': custody.snapshot()}
            self.send_child(terminal)
            answer = wire_receive(child, self.deadline, self.plan['frame_bytes'])
            need(answer == {'kind': 'terminal_ack', 'selection': self.selection_pin, 'sequence': self.sequence}, 'same parent terminal admission')
            child.close()
            os._exit(0 if custody.first is None else 1)
        except BaseException:
            # Parent records EOF/missing prefix as unknown and kills the owned
            # tree. There is no retry, arbitrary pickling or exception object IPC.
            os._exit(126)

    def _serve(self, parent):
        sequence = 0
        while True:
            message = self.channel_owner.receive()
            need(type(message) is dict and message.get('selection') == self.selection_pin, 'owned channel selection')
            need(type(message.get('sequence')) is int and message['sequence'] == sequence + 1, 'one ordered worker message')
            sequence += 1
            if message.get('kind') == 'phase':
                exact(message, ('kind', 'sequence', 'selection', 'phase', 'source_sha256'), 'child phase request')
                need(type(message['phase']) is str and 0 < len(message['phase']) <= 8192 and message['source_sha256'] == self.host.source_sha256, 'bounded original phase request')
                self.lease.original.require(message['phase'], message['source_sha256'])
                wire_send(parent, {'kind': 'phase_reply', 'sequence': sequence, 'selection': self.selection_pin, 'allowed': True}, self.deadline, self.plan['frame_bytes'])
            else:
                exact(message, ('kind', 'sequence', 'selection', 'status', 'capture', 'cost_prefix', 'failure'), 'worker terminal record')
                need(message['kind'] == 'terminal' and message['status'] in ('complete', 'failed'), 'worker terminal disposition')
                self.remote_terminal = encode(message)
                self.prefix.admit(message['cost_prefix'])
                wire_send(parent, {'kind': 'terminal_ack', 'selection': self.selection_pin, 'sequence': sequence}, self.deadline, self.plan['frame_bytes'])
                return message

    def _wait(self, deadline):
        if self.pid is None or self.status is not None:
            return
        while True:
            pid, status = os.waitpid(self.pid, os.WNOHANG)
            if pid == self.pid:
                self.status = status
                return
            need(time.monotonic() < deadline, 'owned worker reap deadline')
            time.sleep(.01)

    def close(self):
        if self.closed:
            self.custody.raise_first()
            return
        self.closed = True
        deadline = time.monotonic() + self.plan['retirement_seconds']
        # Before GO the exact child cannot have spawned descendants. If cgroup
        # attachment failed, it is still our unreaped child and cannot have a
        # recycled PID. No numeric signal is sent after any successful reap.
        if self.pid is not None and self.status is None and (self.tree is None or not self.tree.attached):
            self.custody.attempt('unattached_blocked_child_kill', lambda: os.kill(self.pid, signal.SIGKILL))
        # A terminal child has received ACK and gets a bounded chance to exit.
        # On every other path kill the actual cgroup before waiting. Cgroup
        # operations never address a recycled PID or process-group number.
        if self.remote_terminal is not None and self.pid is not None:
            self.custody.attempt('terminal_child_reap', lambda: self._wait(min(deadline, time.monotonic() + 1)))
        if self.tree is not None:
            self.tree.retire(deadline, self.custody)
        self.custody.attempt('owned_child_reap', lambda: self._wait(deadline))
        if self.channel_owner is not None and self.tree is not None and self.tree.populated_zero:
            self.custody.attempt('terminal_diagnostic_drain', self.channel_owner.drain_after_exit)
        for index, channel in enumerate(self.sockets):
            self.custody.attempt('socket_close:' + str(index), lambda channel=channel: self._close_socket(channel))
        for index, fd in enumerate(self.fds):
            self.custody.attempt('pipe_close:' + str(index), lambda fd=fd: self._close_fd(fd))
        if self.prefix is not None:
            self.custody.attempt('undispatched_reservation_release', self.prefix.release_undispatched)
        self.terminal_closed = (self.pid is not None and self.status is not None and self.tree is not None
                                and self.tree.populated_zero and self.tree.removed and self.custody.first is None)
        self.custody.raise_first()

    def dispatch(self, producer):
        need(producer is self.producer and not self.used and not self.closed, 'one original worker dispatch')
        self.used = True
        message = None
        try:
            parent = self._acquire()
            message = self._serve(parent)
        except BaseException as exc:
            self.custody.capture(exc, 'worker_dispatch')
        self.custody.attempt('worker_retirement', self.close)
        self.custody.raise_first()
        need(self.terminal_closed, 'complete owned child/tree retirement')
        if message['status'] != 'complete':
            raise RemoteWorkerFailure(message)
        need(os.waitstatus_to_exitcode(self.status) == 0, 'successful owned child exit')
        need(type(message['capture']) is str and message['failure']['first_error'] is None, 'successful remote capture record')
        body = base64.b64decode(message['capture'], validate=True)
        decode(body)  # preserve existing bounded capture-row contract
        capture = RemoteCapturedOperation(body, producer, self, self.slot, self.remote_terminal)
        _REMOTE[id(capture)] = (capture, producer, self, self.slot, self.selection_pin)
        self.capture = producer.capture = capture
        return capture

    def observation(self):
        message = decode(self.remote_terminal, self.plan['frame_bytes']) if self.remote_terminal is not None else None
        return {'selection': self.selection_pin, 'operation': self.operation,
                'child_pid': self.pid, 'wait_status': self.status,
                'close_attempted': self.closed, 'terminal_closed': self.terminal_closed,
                'terminal_pin': pin(self.remote_terminal) if self.remote_terminal else None,
                'remote_failure_document': message['failure'] if message is not None else None,
                'remote_status': message['status'] if message is not None else None,
                'original_child_exception_identity': 'not transported',
                'ordinary_cost_owner': self.prefix.observation() if self.prefix else None,
                'diagnostic_pins': {k: pin(bytes(v)) for k, v in self.channel_owner.logs.items()} if self.channel_owner else None,
                'tree_populated_zero': self.tree.populated_zero if self.tree else False,
                'tree_removed': self.tree.removed if self.tree else False,
                'failure_custody': self.custody.snapshot(), 'scientific_qualification_granted': False}

    def admit_capture(self, capture):
        row = _REMOTE.get(id(capture))
        need(type(capture) is RemoteCapturedOperation and row is not None and row[0] is capture
             and row[1] is self.producer and row[2] is self and row[3] is self.slot
             and row[4] == self.selection_pin and capture is self.capture
             and self.terminal_closed and capture.terminal == self.remote_terminal,
             'same source-owned remote capture after actual owned tree retirement')
        return capture


def run_reference_programme(original_issuer, request, transport, design, cost,
                            native_plans, bindings, input_root, output_root, device):
    """Actual complete reference assembly, conditional on original live authority.

    NativeContext and run_programme enforce the unchanged full operation roster
    and scientific plan checks. This API supplies no missing scientific values.
    """
    from .sandbox import QualifiedHost
    from .native_context import NativeContext
    from .reference_assembly import run_programme
    host = QualifiedHost.from_live_operator(NativeWorkerIssuer(original_issuer, transport), request)
    custody = Custody('source_native_reference_programme')
    result = None
    try:
        NativeContext(host, native_plans, input_root, output_root, cost, device)
        result = run_programme(host, design, cost, bindings)
    except BaseException as exc:
        custody.capture(exc, 'complete_reference_programme')
    custody.attempt('original_host_close', host.close)
    custody.raise_first()
    return result
