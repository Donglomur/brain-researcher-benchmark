"""Bounded native-worker transport leaves, independent of scientific parameters.

The cgroup is an actual owned kernel subtree, not a PID/group approximation.
Only a separately qualified Linux deployment may exercise these leaves.
"""
import os
from pathlib import Path
import select
import socket
import struct
import time
import uuid
from .core import Costs, Refusal, decode, encode, exact, need, ordinary, pin


def wire_send(channel, document, deadline, cap):
    body = encode(document)
    need(len(body) <= cap, 'bounded worker frame')
    left = deadline - time.monotonic()
    need(left > 0, 'worker deadline before send')
    channel.settimeout(left)
    channel.sendall(struct.pack('!Q', len(body)) + body)


def wire_receive(channel, deadline, cap):
    def take(n):
        out = bytearray()
        while len(out) < n:
            left = deadline - time.monotonic()
            need(left > 0, 'worker deadline before receive')
            channel.settimeout(left)
            b = channel.recv(min(65536, n - len(out)))
            need(bool(b), 'worker channel closed before complete frame')
            out.extend(b)
        return bytes(out)
    n = struct.unpack('!Q', take(8))[0]
    need(0 < n <= cap, 'bounded worker header')
    return decode(take(n), cap)


class ParentChannel:
    """Drain native stdout/stderr while receiving bounded framed phase RPC."""
    def __init__(self, channel, pipes, deadline, frame_cap, total_cap, log_cap):
        self.channel, self.pipes = channel, dict(pipes)
        self.deadline, self.frame_cap = deadline, frame_cap
        self.total_cap, self.log_cap = total_cap, log_cap
        self.buffer = bytearray()
        self.total = 0
        self.logs = {'stdout': bytearray(), 'stderr': bytearray()}
        for fd in self.pipes:
            os.set_blocking(fd, False)

    def receive(self):
        while True:
            if len(self.buffer) >= 8:
                n = struct.unpack('!Q', self.buffer[:8])[0]
                need(0 < n <= self.frame_cap, 'bounded worker frame header')
                if len(self.buffer) >= n + 8:
                    body = bytes(self.buffer[8:n + 8])
                    del self.buffer[:n + 8]
                    return decode(body, self.frame_cap)
            left = self.deadline - time.monotonic()
            need(left > 0, 'native worker total deadline')
            ready, _, _ = select.select([self.channel, *self.pipes], [], [], min(left, .1))
            for obj in ready:
                if obj is self.channel:
                    b = self.channel.recv(65536)
                    need(bool(b), 'native worker channel closed before terminal record')
                    self.total += len(b)
                    need(self.total <= self.total_cap, 'aggregate worker transport limit')
                    self.buffer.extend(b)
                    need(len(self.buffer) <= self.frame_cap + 8, 'bounded unconsumed worker frame')
                else:
                    b = os.read(obj, 65536)
                    if not b:
                        del self.pipes[obj]  # descriptor still owned by worker
                    else:
                        log = self.logs[self.pipes[obj]]
                        need(len(log) + len(b) <= self.log_cap, 'native diagnostic output limit')
                        log.extend(b)

    def drain_after_exit(self):
        # All descendants have already left the owned cgroup. No writer can
        # remain in that qualified subtree; EAGAIN is a failed closure join.
        for fd, name in list(self.pipes.items()):
            while True:
                b = os.read(fd, 65536)
                if not b:
                    del self.pipes[fd]
                    break
                need(len(self.logs[name]) + len(b) <= self.log_cap, 'terminal native diagnostic output limit')
                self.logs[name].extend(b)


class CgroupTree:
    """Create/attach/kill/wait/remove one owned cgroup-v2 subtree.

    The original lease must qualify the delegated parent and prohibit escape
    (mount/cgroup namespace, credentials and delegation). A cgroup pathname
    alone is neither confinement nor scientific execution authority.
    """
    def __init__(self, parent):
        self.parent = ordinary(parent)
        self.name = 'critical-reference-' + uuid.uuid4().hex
        self.parent_fd = self.fd = None
        self.created = False
        self.attached = False
        self.kill_attempted = False
        self.closed = False
        self.populated_zero = False
        self.removed = False
        from .lifecycle import Custody
        self.custody = Custody('owned_cgroup_tree')
        self.ephemeral = []

    def create(self):
        need(self.parent_fd is None and not self.closed, 'one cgroup acquisition')
        self.parent_fd = os.open(self.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        os.mkdir(self.name, mode=0o700, dir_fd=self.parent_fd)
        self.created = True
        self.fd = os.open(self.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=self.parent_fd)
        # Existence of the v2 kill/event files is checked before child creation.
        need('populated' in self.events(), 'cgroup v2 populated event')
        self.file_operation('cgroup.kill', os.O_WRONLY, lambda fd: None)

    def file_operation(self, name, flags, action):
        from .lifecycle import Custody
        owner = Custody('cgroup_file:' + name)
        fd, result = None, None
        try:
            fd = os.open(name, flags | os.O_NOFOLLOW, dir_fd=self.fd)
            record = {'fd': fd, 'close_attempted': False}
            self.ephemeral.append(record)
            result = action(fd)
        except BaseException as exc:
            owner.capture(exc, 'kernel_file_operation')
        if fd is not None:
            record['close_attempted'] = True
            owner.attempt('kernel_file_close', lambda: os.close(fd))
        self.custody.propagate(owner, name)
        owner.raise_first()
        return result

    def write(self, name, body):
        self.file_operation(name, os.O_WRONLY,
                            lambda fd: need(os.write(fd, body) == len(body), 'complete kernel cgroup command'))

    def events(self):
        def parse(fd):
            body = os.read(fd, 4097)
            need(len(body) <= 4096, 'bounded cgroup events')
            rows = [line.split() for line in body.decode('ascii').splitlines()]
            need(all(len(r) == 2 for r in rows) and len({r[0] for r in rows}) == len(rows), 'unique cgroup events')
            return {k: int(v) for k, v in rows}
        return self.file_operation('cgroup.events', os.O_RDONLY, parse)

    def attach(self, pid):
        need(not self.attached and type(pid) is int and pid > 0, 'one owned worker attachment')
        self.write('cgroup.procs', str(pid).encode('ascii'))
        self.attached = True

    def retire(self, deadline, custody):
        if self.closed:
            return
        self.closed = True
        if self.fd is not None:
            self.kill_attempted = True
            custody.attempt('cgroup_kill', lambda: self.write('cgroup.kill', b'1'))
            def wait_empty():
                while self.events().get('populated') != 0:
                    need(time.monotonic() < deadline, 'cgroup tree retirement deadline')
                    time.sleep(.01)
                self.populated_zero = True
            custody.attempt('cgroup_populated_zero', wait_empty)
            custody.attempt('cgroup_descriptor_close', lambda: os.close(self.fd))
        if self.created and (self.populated_zero or self.fd is None):
            def remove():
                os.rmdir(self.name, dir_fd=self.parent_fd)
                self.removed = True
            custody.attempt('cgroup_remove', remove)
        if self.parent_fd is not None:
            custody.attempt('cgroup_parent_close', lambda: os.close(self.parent_fd))
        custody.propagate(self.custody, 'cgroup_original_kernel_failures')


class RemoteCostPrefix:
    """Explicit remote documentary owner retained on the original Costs ledger.

    Child observations never masquerade as original parent IOOperation objects.
    A missing/malformed prefix keeps reservations outstanding and unknown.
    """
    def __init__(self, cost, selection):
        need(type(cost) is Costs, 'original parent Costs owner')
        self.cost, self.selection = cost, selection
        self.start = {'read': cost.read, 'write': cost.write,
                      'reserved_read': cost.reserved_read, 'reserved_write': cost.reserved_write,
                      'owner_count': len(cost._io_operations)}
        self.held = {}
        self.prefix = None
        self.prefix_body = None
        self.finished = []
        self.dispatched = False
        cost._io_operations.append(self)
        for kind in ('read', 'write'):
            n = getattr(cost, kind + '_limit') - getattr(cost, kind) - getattr(cost, 'reserved_' + kind)
            cost.reserve(kind, n)
            self.held[kind] = n

    def child_reset(self):
        for kind, n in self.held.items():
            setattr(self.cost, 'reserved_' + kind, getattr(self.cost, 'reserved_' + kind) - n)

    def child_document(self):
        return {'selection': self.selection,
                'read': self.cost.read - self.start['read'],
                'write': self.cost.write - self.start['write'],
                'reserved_read': self.cost.reserved_read - self.start['reserved_read'],
                'reserved_write': self.cost.reserved_write - self.start['reserved_write'],
                'operations': [owner.observation() for owner in self.cost._io_operations[self.start['owner_count'] + 1:]]}

    def admit(self, document):
        need(self.prefix is None and not self.finished, 'one remote cost prefix')
        exact(document, ('selection', 'read', 'write', 'reserved_read', 'reserved_write', 'operations'), 'remote cost prefix')
        need(document['selection'] == self.selection and type(document['operations']) is list, 'same remote prefix selection')
        for kind in ('read', 'write'):
            used, held = document[kind], document['reserved_' + kind]
            need(type(used) is int and type(held) is int and 0 <= used and 0 <= held and used + held <= self.held[kind], 'remote bounded ordinary cost prefix')
        self.prefix_body = encode(document)
        self.prefix = decode(self.prefix_body)
        for kind in ('read', 'write'):
            # Keep any child's outstanding reservation on the parent as well.
            released = self.held[kind] - document['reserved_' + kind]
            self.cost.finish(kind, released, document[kind])
            self.finished.append(kind)

    def release_undispatched(self):
        if not self.dispatched and self.prefix is None:
            self.admit({'selection': self.selection, 'read': 0, 'write': 0,
                        'reserved_read': 0, 'reserved_write': 0, 'operations': []})

    def observation(self):
        return {'operation': 'remote_native_prefix', 'selection': self.selection,
                'origin': 'owned child; documentary projection, not parent IOOperation identity',
                'status': 'received' if self.prefix is not None else 'unknown',
                'prefix': decode(self.prefix_body) if self.prefix_body else None, 'prefix_pin': pin(self.prefix_body) if self.prefix_body else None,
                'finished_ledgers': list(self.finished), 'dispatched': self.dispatched,
                'physical_io_cpu_rss': 'UNKNOWN', 'transport_IO': 'separate from ordinary prefix'}
