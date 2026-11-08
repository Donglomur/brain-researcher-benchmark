"""Bounded source/runtime primitives; no data, network or process at import."""
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import time
import sys


class Refusal(ValueError):
    pass


def cleanup_preserving(action):
    """Preserve the primary failure and a distinct cleanup failure (Python3.11+)."""
    primary = sys.exception()
    try:
        return action()
    except BaseException as cleanup:
        if primary is not None:
            raise BaseExceptionGroup('primary operation and cleanup both failed', [primary, cleanup]) from None
        raise


def close_preserving(fd):
    return cleanup_preserving(lambda: os.close(fd))


def need(condition, reason):
    if not condition:
        raise Refusal(reason)


def integer(value, minimum=0, maximum=None):
    need(type(value) is int and value >= minimum and (maximum is None or value <= maximum),
         'bounded ordinary integer required')
    return value


def finite(value):
    need(type(value) in (int, float), 'ordinary number; bool refused')
    try:
        value = float(value)
    except (OverflowError, ValueError) as error:
        raise Refusal('binary64 overflow') from error
    need(math.isfinite(value), 'finite binary64 required')
    return value


def pin(body):
    need(type(body) is bytes, 'captured bytes required')
    return {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}


def descriptor(value):
    need(type(value) is dict and set(value) == {'bytes', 'sha256'}, 'exact byte descriptor')
    integer(value['bytes'])
    text = value['sha256']
    need(type(text) is str and len(text) == 64 and all(x in '0123456789abcdef' for x in text),
         'lowercase SHA256 required')
    return dict(value)


def encoded(value):
    return json.dumps(value, ensure_ascii=True, allow_nan=False, sort_keys=True,
                      separators=(',', ':')).encode('utf-8')


def parse(body):
    need(type(body) is bytes, 'one captured JSON body required')
    def pairs(items):
        result = {}
        for key, value in items:
            need(key not in result, 'duplicate JSON key')
            result[key] = value
        return result
    text = body.decode('utf-8')
    depth = 0
    quoted = escaped = False
    for char in text:
        if quoted:
            if escaped:
                escaped = False
            elif char == '\\':
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
        elif char in '[{':
            depth += 1
            need(depth <= 64, 'JSON nesting bound')
        elif char in ']}':
            depth -= 1
    try:
        return json.loads(text, object_pairs_hook=pairs,
                          parse_constant=lambda _: (_ for _ in ()).throw(Refusal('nonfinite JSON literal')))
    except (ValueError, RecursionError, UnicodeError) as error:
        raise Refusal('invalid bounded JSON') from error


def relative(name):
    need(type(name) is str and name and '\\' not in name and '\x00' not in name,
         'ordinary relative path')
    path = Path(name)
    need(not path.is_absolute() and all(x not in ('', '.', '..') for x in name.split('/')),
         'no absolute or traversing path')
    return path


def stamp(st):
    return (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns)


class Budget:
    """Logical reservations and original clocks; not physical I/O/RSS telemetry."""
    def __init__(self, origin, deadline, read_cap, write_cap, clock=time.monotonic):
        self.origin, self.deadline = finite(origin), finite(deadline)
        need(self.deadline > self.origin, 'positive original clock span')
        self.read_cap, self.write_cap = integer(read_cap), integer(write_cap)
        self.read_bytes = self.write_bytes = 0
        self.clock = clock
        self.tick()

    def tick(self, cutoff=None):
        now = finite(self.clock())
        need(self.origin <= now < min(self.deadline, cutoff if cutoff is not None else self.deadline),
             'original enclosing/phase deadline expired or clock changed')
        return now

    def reserve_read(self, count):
        self.tick()
        count = integer(count)
        need(self.read_bytes + count <= self.read_cap, 'source/input read reservation exhausted')
        self.read_bytes += count

    def reserve_write(self, count):
        self.tick()
        count = integer(count)
        need(self.write_bytes + count <= self.write_cap, 'retained/write reservation exhausted')
        self.write_bytes += count

    def record(self):
        return {'origin': self.origin, 'deadline': self.deadline,
                'observed': self.tick(), 'read_reserved_bytes': self.read_bytes,
                'write_reserved_bytes': self.write_bytes,
                'logical_reservations_not_measured_physical_usage': True}


def canonical(path):
    text = os.fspath(path)
    need(type(text) is str and text.startswith('/') and not text.startswith('//')
         and '\\' not in text and '\x00' not in text, 'canonical absolute path')
    need(text == '/' or (not text.endswith('/') and all(x not in ('', '.', '..')
         for x in text.split('/')[1:])), 'canonical absolute spelling')
    return Path(text)


def disjoint(a, b):
    a, b = canonical(a), canonical(b)
    return a != b and a not in b.parents and b not in a.parents


def parent_chain(path):
    """Lexical/symlink guard, not proof against physical mount/firmlink aliases."""
    path = canonical(path)
    for parent in reversed(path.parents):
        need(stat.S_ISDIR(os.lstat(parent).st_mode), 'ordinary directory parents only')
    return path


def capture(path, expected, limit, budget, retain=True, readonly=False):
    expected = descriptor(expected)
    need(expected['bytes'] <= integer(limit), 'artifact exceeds selected bound')
    path = parent_chain(path)
    budget.reserve_read(expected['bytes'] + 1)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
             and before.st_size == expected['bytes'], 'ordinary single-link exact-size artifact')
        if readonly:
            need(before.st_mode & 0o222 == 0, 'sealed readonly artifact')
        digest = hashlib.sha256()
        chunks = []
        left = before.st_size
        while left:
            budget.tick()
            body = os.read(fd, min(left, 1 << 20))
            need(body, 'short artifact')
            left -= len(body)
            digest.update(body)
            if retain:
                chunks.append(body)
        need(not os.read(fd, 1), 'artifact grew')
        after = os.fstat(fd)
        need(stamp(before) == stamp(after) == stamp(os.lstat(path)), 'artifact changed while captured')
        need(digest.hexdigest() == expected['sha256'], 'captured body hash mismatch')
        budget.tick()
        return (b''.join(chunks) if retain else None), stamp(after)
    finally:
        close_preserving(fd)


def sync_dir(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        close_preserving(fd)


def fresh(path, budget):
    budget.tick()
    path = parent_chain(path)
    os.mkdir(path, 0o700)
    sync_dir(path.parent)
    return path


def publish(path, body, budget, readonly=False):
    need(type(body) is bytes, 'publish captured bytes only')
    path = parent_chain(path)
    budget.reserve_write(len(body))
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        view = memoryview(body)
        while view:
            budget.tick()
            count = os.write(fd, view)
            need(count > 0, 'short publication')
            view = view[count:]
        if readonly:
            os.fchmod(fd, 0o444)
        os.fsync(fd)
    finally:
        close_preserving(fd)
    sync_dir(path.parent)
    budget.tick()
    return pin(body)


def copy_sealed(source, expected, destination, limit, budget):
    body, _ = capture(source, expected, limit, budget)
    result = publish(destination, body, budget, readonly=True)
    need(result == expected, 'sealed copy identity')
    return result


def seal_output(path, cap, initial_inode, budget):
    """Hash an already naturally closed producer's fixed output inode in chunks."""
    path = parent_chain(path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
             and (before.st_dev, before.st_ino) == tuple(initial_inode)
             and before.st_size <= integer(cap), 'fixed bounded output inode')
        budget.reserve_read(before.st_size + 1)
        digest = hashlib.sha256()
        size = 0
        while size < before.st_size:
            budget.tick()
            block = os.read(fd, min(1048576, before.st_size - size))
            need(block, 'short output')
            size += len(block)
            digest.update(block)
        need(not os.read(fd, 1), 'output grew beyond admitted extent')
        need(size == before.st_size and stamp(before) == stamp(os.fstat(fd)) == stamp(os.lstat(path)),
             'output changed after producer closure')
        os.chmod(path, 0o444, follow_symlinks=False)
        sync_dir(path.parent)
        return {'bytes': size, 'sha256': digest.hexdigest()}
    finally:
        close_preserving(fd)


def capture_new_protected(path, cap, budget):
    """Capture a newly published operator receipt, not a candidate-selected file.

    Caller must bind the protected directory/name/publishing authority in the
    immutable study selection. This is needed for receipts written after dynamic
    authoring; their content hashes cannot honestly be predicted in advance.
    """
    path = parent_chain(path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size <= cap
             and before.st_mode & 0o222 == 0, 'new ordinary readonly protected receipt')
        budget.reserve_read(before.st_size + 1)
        pieces = []
        left = before.st_size
        while left:
            budget.tick()
            part = os.read(fd, min(left, 65536)); need(part, 'short protected receipt')
            pieces.append(part); left -= len(part)
        need(not os.read(fd, 1) and stamp(before) == stamp(os.fstat(fd)) == stamp(os.lstat(path)),
             'protected receipt changed during capture')
        raw = b''.join(pieces)
        return raw, pin(raw)
    finally:
        close_preserving(fd)


def describe_sealed(path, cap, budget):
    path = parent_chain(path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_mode & 0o222 == 0
             and before.st_size <= integer(cap), 'sealed ordinary exact extent')
        budget.reserve_read(before.st_size + 1)
        digest = hashlib.sha256(); count = 0
        while count < before.st_size:
            budget.tick()
            block = os.read(fd, min(1 << 20, before.st_size - count))
            need(block, 'short sealed body'); count += len(block); digest.update(block)
        need(not os.read(fd, 1), 'sealed body grew')
        need(stamp(before) == stamp(os.fstat(fd)) == stamp(os.lstat(path)), 'sealed body changed')
        return {'bytes': count, 'sha256': digest.hexdigest()}
    finally:
        close_preserving(fd)
