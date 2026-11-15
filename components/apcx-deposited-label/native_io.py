"""Small bounded file adapters for the one APCx native census, no work on import."""
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import time

STABLE = ('st_dev', 'st_ino', 'st_mode', 'st_nlink', 'st_size', 'st_mtime_ns', 'st_ctime_ns')


class Budget:
    def __init__(self, limits, deadline):
        self.limits = dict(limits); self.deadline = deadline
        # Replace a complete state in one assignment. An interrupted completion
        # keeps either the old conservative reservation or the observed return;
        # it cannot expose a refund without its matching outcome observation.
        self._state = ({k: 0 for k in limits}, {}, {}, 0)
    @property
    def used(self): return dict(self._state[0])
    def check(self):
        if time.monotonic() >= self.deadline: raise TimeoutError('original worker horizon')
    def reserve(self, key, amount):
        self.check()
        if type(amount) is not int or amount < 0 or self.used[key] + amount > self.limits[key]:
            raise ValueError('managed cap: ' + key)
    def charge(self, key, amount):
        self.reserve(key, amount)
        used, pending, observed, sequence = self._state
        updated = dict(used); updated[key] += amount
        self._state = (updated, pending, observed, sequence)
    def begin_io(self, key, bound):
        """Charge before I/O; a missing/interrupting return stays unresolved."""
        self.reserve(key, bound)
        used, pending, observed, sequence = self._state
        updated = dict(used); updated[key] += bound
        opened = dict(pending); opened[sequence] = {'category': key, 'bound_bytes': bound}
        self._state = (updated, opened, observed, sequence + 1)
        return sequence
    def complete_io(self, ticket, actual):
        """Reconcile a known return without consulting the clock or signals.

        Native/OS uncertainty before this observation retains the precharge.
        Above-bound observations are charged honestly, then fail closed.
        """
        used, pending, observed, sequence = self._state
        if type(ticket) is not int or ticket not in pending or type(actual) is not int or actual < 0:
            raise ValueError('invalid I/O completion observation')
        item = pending[ticket]; key = item['category']; bound = item['bound_bytes']
        updated = dict(used); updated[key] += actual - bound
        opened = dict(pending); del opened[ticket]
        completed = dict(observed); completed[key] = completed.get(key, 0) + actual
        self._state = (updated, opened, completed, sequence)
        if actual > bound or updated[key] > self.limits[key]:
            raise ValueError('observed I/O exceeded precharged bound')
    def io_snapshot(self):
        used, pending, observed, sequence = self._state
        return {'precharged_operations': sequence,
                'observed_completed_bytes': dict(observed),
                'observed_completed_bytes_semantics': 'Known API return counts or complete ordinary-file extent, not a disk-persistence or native-wire measurement. Final flush/closure and whole original inventory remain required.',
                'unresolved_operations': [{'ticket': k, **v} for k, v in sorted(pending.items())],
                'unresolved_bound_bytes': sum(v['bound_bytes'] for v in pending.values()),
                'unknown_outcome_semantics': 'Unresolved includes interruption before, during or after the OS/native call; the full requested bound remains charged. No exact completed-byte claim for those operations.'}


def ordinary(path, expected_size=None):
    p = Path(path)
    if not p.is_absolute() or '..' in p.parts or any(x.is_symlink() for x in (p, *p.parents)):
        raise ValueError('absolute ordinary path required')
    s = p.lstat()
    if not stat.S_ISREG(s.st_mode) or s.st_nlink != 1:
        raise ValueError('ordinary single-link file required')
    if expected_size is not None and s.st_size != expected_size: raise ValueError('exact file size')
    return s


class MeteredReader(io.RawIOBase):
    """One original FD, counted reads, no mmap and no path/URI fallback."""
    def __init__(self, path, size, budget, kind='input_bytes'):
        super().__init__(); self.path = Path(path); self.size = size; self.budget = budget; self.kind = kind
        before = ordinary(self.path, size)
        self.fd = os.open(self.path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        self.initial = os.fstat(self.fd)
        if any(getattr(before, k) != getattr(self.initial, k) for k in STABLE):
            os.close(self.fd); raise ValueError('open identity changed')
    def readable(self): return True
    def writable(self): return False
    def seekable(self): return True
    def tell(self): return os.lseek(self.fd, 0, os.SEEK_CUR)
    def seek(self, offset, whence=0):
        self.budget.check()
        if type(offset) is not int or whence not in (0, 1, 2): raise ValueError('seek arguments')
        position = offset + (self.tell() if whence == 1 else self.size if whence == 2 else 0)
        if not 0 <= position <= self.size: raise ValueError('seek outside selected file')
        return os.lseek(self.fd, position, os.SEEK_SET)
    def read(self, size=-1):
        self.budget.check()
        if type(size) is not int or size < -1: raise ValueError('read size')
        n = self.size - self.tell() if size == -1 else min(size, self.size - self.tell())
        ticket = self.budget.begin_io(self.kind, n)
        body = os.read(self.fd, n)
        self.budget.complete_io(ticket, len(body))
        self.budget.check()
        return body
    def readinto(self, target):
        b = self.read(len(target)); target[:len(b)] = b; return len(b)
    def identity(self):
        now = os.fstat(self.fd); path_now = ordinary(self.path, self.size)
        if any(getattr(now, k) != getattr(self.initial, k) or getattr(path_now, k) != getattr(self.initial, k) for k in STABLE):
            raise ValueError('original file identity changed')
        return {'device': now.st_dev, 'inode': now.st_ino, 'links': now.st_nlink, 'bytes': now.st_size}
    def close(self):
        if not self.closed:
            try: self.identity()
            finally: os.close(self.fd); super().close()


def full_digest(reader):
    reader.seek(0); sha = hashlib.sha256(); md5 = hashlib.md5(); total = 0
    while total < reader.size:
        b = reader.read(min(65536, reader.size - total))
        if not b: raise ValueError('premature original EOF')
        total += len(b); sha.update(b); md5.update(b)
    if reader.read(1): raise ValueError('original trailing bytes')
    reader.identity()
    return {'bytes': total, 'sha256': sha.hexdigest(), 'md5': md5.hexdigest()}


def hash_regular(path, size, budget, kind):
    with MeteredReader(path, size, budget, kind) as reader: return full_digest(reader)


class OutputStore:
    def __init__(self, root, budget, per_file=268435456):
        self.root = Path(root); self.budget = budget; self.per_file = per_file; self.files = []
    def line_writer(self, name):
        if Path(name).name != name or name in self.files: raise ValueError('fresh flat output name')
        self.files.append(name); return Lines(self, name)
    def json(self, name, value):
        with self.line_writer(name) as out: out.write(value, maximum=1048576)


class Lines:
    def __init__(self, store, name):
        self.store = store; self.name = name; self.written = 0; self.stream = None
    def __enter__(self):
        fd = os.open(self.store.root / self.name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        self.stream = os.fdopen(fd, 'wb'); return self
    def write(self, value, maximum=1048576):
        b = (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()
        if len(b) > maximum or self.written + len(b) > self.store.per_file: raise ValueError('whole output file cap')
        ticket = self.store.budget.begin_io('retained_bytes', len(b))
        self.written += len(b)
        actual = self.stream.write(b)
        self.store.budget.complete_io(ticket, actual)
        self.written += actual - len(b)
        if actual != len(b): raise OSError('short owned output write')
        self.store.budget.check()
    def __exit__(self, *args):
        try: self.stream.flush(); os.fsync(self.stream.fileno())
        finally: self.stream.close()


def inventory_outputs(store):
    rows = []
    for p in sorted(store.root.iterdir()):
        if p.name not in store.files: raise ValueError('unexpected owned output')
        s = ordinary(p)
        pin = hash_regular(p, s.st_size, store.budget, 'output_read_bytes')
        rows.append({'name': p.name, **pin})
    return {'files': rows, 'bytes': sum(r['bytes'] for r in rows),
            'self_and_later_worker_receipt_excluded': True, 'not_a_public_export': True}
