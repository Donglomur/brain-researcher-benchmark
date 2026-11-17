#!/usr/bin/env python3
"""Recreate the exact released source namespace, without importing its code."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import time

TASK = 'NEURAL-058'
HERE = Path(__file__).absolute().parent
MAP_PIN = (139763, '6bcd2528b1a0598260e6270930457685a80fd3e2db0cdb19448e09b0bee1b45e')
RECEIPT = 'SOURCE_PREPARATION.json'
MEMBERS = 326
TERMINAL_RESERVE = 65536
FAILURE_DIAGNOSTIC_CAP = 4096


def need(value, message):
    if not value:
        raise ValueError(message)


def canonical(value):
    path = Path(value)
    need(path.is_absolute() and str(path) == str(value) and
         not str(value).startswith('//') and '\\' not in str(value) and
         all(part not in ('', '.', '..') for part in str(value).split('/')[1:]),
         'canonical absolute path required')
    return path


def relative(value):
    need(type(value) is str and value and not value.startswith('/') and
         '\\' not in value and '\0' not in value and
         all(part not in ('', '.', '..') for part in value.split('/')) and
         str(Path(value)) == value, 'ordinary relative source path required')
    return value


def directories(path):
    for parent in reversed((path, *path.parents)):
        need(stat.S_ISDIR(os.lstat(parent).st_mode), 'ordinary directory ancestry required')


def stamp(value):
    return (value.st_dev, value.st_ino, value.st_mode, value.st_nlink,
            value.st_size, value.st_mtime_ns, value.st_ctime_ns)


class Budget:
    """Prospective byte/I/O limits; live bytes count retained source buffers only."""
    def __init__(self, reads, writes, live, seconds):
        for value in (reads, writes, live):
            need(type(value) is int and value > 0, 'positive integer byte budgets required')
        need(type(seconds) in (int, float) and math.isfinite(seconds) and seconds > 0,
             'positive finite deadline required')
        self.limits = {'read_bytes': reads, 'write_bytes': writes, 'live_source_buffer_bytes': live}
        self.start = time.monotonic()
        self.deadline = self.start + seconds
        need(math.isfinite(self.deadline), 'finite deadline required')
        self.read_reserved = self.read_observed = self.write_reserved = self.write_observed = 0
        self.live = self.peak_live = 0

    def tick(self):
        need(self.start <= time.monotonic() < self.deadline, 'source preparation deadline exceeded')

    def reserve_read(self, count):
        self.tick()
        need(self.read_reserved + count <= self.limits['read_bytes'], 'read byte budget exceeded')
        self.read_reserved += count

    def reserve_write(self, count):
        self.tick()
        need(self.write_reserved + count <= self.limits['write_bytes'], 'write byte budget exceeded')
        self.write_reserved += count

    def acquire(self, count):
        need(self.live + count <= self.limits['live_source_buffer_bytes'],
             'live source buffer budget exceeded')
        self.live += count
        self.peak_live = max(self.peak_live, self.live)

    def release(self, count):
        self.live -= count
        need(self.live >= 0, 'source buffer accounting underflow')

    def snapshot(self):
        return {'limits': self.limits, 'read_reserved': self.read_reserved,
                'read_observed': self.read_observed, 'write_reserved': self.write_reserved,
                'write_observed': self.write_observed, 'peak_live_source_buffer_bytes': self.peak_live,
                'elapsed_seconds': time.monotonic() - self.start,
                'physical_memory_and_cpu_unmeasured': True}


def capture(path, expected, budget):
    """Return one authenticated body; caller releases its logical live-buffer charge."""
    path = canonical(str(path))
    directories(path.parent)
    count, digest = expected['bytes'], expected['sha256']
    need(type(count) is int and 0 < count <= 2 * 2**20, 'bounded source extent required')
    need(type(digest) is str and len(digest) == 64 and
         all(c in '0123456789abcdef' for c in digest), 'source SHA-256 required')
    budget.reserve_read(count + 1)
    budget.acquire(count * 2 + 1)
    fd = None
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        initial = os.fstat(fd)
        need(stat.S_ISREG(initial.st_mode) and initial.st_nlink == 1 and initial.st_size == count,
             'exact ordinary source file required')
        blocks = []
        remaining = count
        while remaining:
            budget.tick()
            block = os.read(fd, min(65536, remaining))
            budget.read_observed += len(block)
            need(bool(block), 'short source read')
            blocks.append(block)
            remaining -= len(block)
        extra = os.read(fd, 1)
        budget.read_observed += len(extra)
        body = b''.join(blocks)
        need(not extra and stamp(initial) == stamp(os.fstat(fd)) == stamp(os.lstat(path)),
             'source changed during capture')
        need(hashlib.sha256(body).hexdigest() == digest, 'source hash mismatch')
        budget.tick()
    except BaseException:
        budget.release(count * 2 + 1)
        raise
    finally:
        if fd is not None:
            os.close(fd)
    budget.release(count + 1)
    return body


class Destination:
    def __init__(self, path):
        self.path = path
        directories(path.parent)
        need(not os.path.lexists(path), 'destination must be absent')
        path.mkdir(mode=0o700)
        self.fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        self.identity = os.fstat(self.fd)
        try:
            self.check()
        except BaseException:
            os.close(self.fd)
            self.fd = None
            raise

    def check(self):
        directories(self.path.parent)
        current = os.lstat(self.path)
        need(stat.S_ISDIR(current.st_mode) and
             (current.st_dev, current.st_ino) == (self.identity.st_dev, self.identity.st_ino),
             'destination directory identity changed')

    def publish(self, name, body, budget):
        relative(name)
        self.check()
        budget.reserve_write(len(body))
        budget.reserve_read(len(body) + 1)
        # Charge readback plus its transient read chunk, in addition to the
        # caller's retained body. This is source content, not allocator/RSS size.
        budget.acquire(len(body) * 2 + 1)
        parent = os.dup(self.fd)
        fd = None
        try:
            parts = name.split('/')
            for part in parts[:-1]:
                try:
                    os.mkdir(part, 0o700, dir_fd=parent)
                except FileExistsError:
                    pass
                child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
                os.close(parent)
                parent = child
            fd = os.open(parts[-1], os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                         0o600, dir_fd=parent)
            view = memoryview(body)
            while view:
                budget.tick()
                written = os.write(fd, view)
                need(written > 0, 'short source write')
                budget.write_observed += written
                view = view[written:]
            os.fsync(fd)
            os.lseek(fd, 0, os.SEEK_SET)
            actual = bytearray()
            while len(actual) < len(body):
                budget.tick()
                block = os.read(fd, min(65536, len(body) - len(actual)))
                budget.read_observed += len(block)
                need(bool(block), 'short output readback')
                actual.extend(block)
            extra = os.read(fd, 1)
            budget.read_observed += len(extra)
            info = os.fstat(fd)
            named = os.stat(parts[-1], dir_fd=parent, follow_symlinks=False)
            need(not extra and actual == body and stat.S_ISREG(info.st_mode) and
                 info.st_nlink == 1 and info.st_size == len(body) and stamp(info) == stamp(named),
                 'output body or identity changed')
            os.fsync(parent)
            self.check()
            budget.tick()
        finally:
            if fd is not None:
                os.close(fd)
            os.close(parent)
            budget.release(len(body) * 2 + 1)

    def close(self):
        fd, self.fd = self.fd, None
        if fd is not None:
            os.close(fd)


def strict_pairs(rows):
    result = {}
    for key, value in rows:
        need(key not in result, 'duplicate source map key')
        result[key] = value
    return result


def load_map(budget):
    body = capture(HERE / 'SOURCE_MAP.json', {'bytes': MAP_PIN[0], 'sha256': MAP_PIN[1]}, budget)
    try:
        doc = json.loads(body, object_pairs_hook=strict_pairs)
    finally:
        budget.release(len(body))
        del body
    need(set(doc) == {'schema', 'task_id', 'members', 'files', 'source_only',
                      'runtime_authorization', 'scientific_qualification'} and
         doc['schema'] == 'neural058_source_namespace_v1' and doc['task_id'] == TASK and
         doc['members'] == MEMBERS and doc['source_only'] is True and
         doc['runtime_authorization'] is False and doc['scientific_qualification'] is False,
         'exact unqualified source map required')
    rows = doc['files']
    need(type(rows) is list and len(rows) == MEMBERS, 'complete source map required')
    seen = set()
    for row in rows:
        need(type(row) is dict and set(row) == {'logical_path', 'current_path', 'bytes', 'sha256'},
             'exact source map member required')
        relative(row['logical_path'])
        relative(row['current_path'])
        need(row['logical_path'] not in seen, 'duplicate logical source path')
        seen.add(row['logical_path'])
    return rows


def prepare(repository, destination, budget):
    repository, destination = canonical(str(repository)), canonical(str(destination))
    directories(repository)
    need(not destination.is_relative_to(repository) and not repository.is_relative_to(destination),
         'source and destination must be disjoint')
    need(not os.path.lexists(destination), 'destination must be absent')
    # Reserve the bounded receipt/terminal allowance prospectively, including
    # runs that fail during source capture. Filesystem writes are also charged
    # individually below; the allowance is deliberately conservative.
    budget.reserve_write(TERMINAL_RESERVE)
    rows = load_map(budget)
    # Every public prerequisite is admitted before output creation. Copies are
    # freshly recaptured to detect source changes during preparation.
    for row in rows:
        body = capture(repository / row['current_path'], row, budget)
        budget.release(len(body))
        del body
    owner = Destination(destination)
    try:
        for row in rows:
            body = capture(repository / row['current_path'], row, budget)
            try:
                owner.publish(row['logical_path'], body, budget)
            finally:
                budget.release(len(body))
                del body
        # The prospective reservation covers the bounded receipt and terminal
        # report. It is reported as reservation, never as observed physical I/O.
        receipt = {'schema': 'neural058_source_preparation_v1', 'task_id': TASK,
                   'members': MEMBERS, 'source_bytes': sum(row['bytes'] for row in rows),
                   'source_map_sha256': MAP_PIN[1], 'runtime_authorization': False,
                   'scientific_execution': False, 'scientific_qualification': False,
                   'state': 'source_prepared_not_qualified',
                   'before_receipt_and_terminal': budget.snapshot()}
        body = (json.dumps(receipt, sort_keys=True, indent=2, allow_nan=False) + '\n').encode()
        need(len(body) < TERMINAL_RESERVE // 2, 'bounded preparation receipt required')
        budget.acquire(len(body))
        try:
            owner.publish(RECEIPT, body, budget)
        finally:
            budget.release(len(body))
        owner.check()
        result = {**receipt, 'receipt': str(destination / RECEIPT), 'budget': budget.snapshot()}
        need(len(json.dumps(result, allow_nan=False).encode()) < TERMINAL_RESERVE // 2,
             'bounded terminal report required')
        budget.tick()
        return result
    finally:
        owner.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repository', required=True)
    parser.add_argument('--destination', required=True)
    parser.add_argument('--max-read-bytes', type=int, required=True)
    parser.add_argument('--max-write-bytes', type=int, required=True)
    parser.add_argument('--max-live-bytes', type=int, required=True)
    parser.add_argument('--deadline-seconds', type=float, required=True)
    args = parser.parse_args()
    try:
        budget = Budget(args.max_read_bytes, args.max_write_bytes, args.max_live_bytes,
                        args.deadline_seconds)
        result = prepare(args.repository, args.destination, budget)
        print(json.dumps(result, sort_keys=True, allow_nan=False))
        return 0
    except (ValueError, OSError, TimeoutError) as error:
        # Refusing an invalid/tiny budget still needs a bounded diagnostic.
        # This separate fixed allowance is not reported as a source-copy write.
        detail = str(error).encode('utf-8', errors='replace')[:512].decode('utf-8', errors='ignore')
        diagnostic = json.dumps({'status': 'source_preparation_failed', 'error': detail,
                                 'error_type': type(error).__name__,
                                 'runtime_authorization': False, 'scientific_execution': False})
        need(len(diagnostic.encode()) + 1 <= FAILURE_DIAGNOSTIC_CAP, 'bounded failure diagnostic')
        print(diagnostic)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
