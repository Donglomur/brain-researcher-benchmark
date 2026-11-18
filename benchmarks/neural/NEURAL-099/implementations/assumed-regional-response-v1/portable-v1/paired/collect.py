"""Exclusive, bounded evaluator-private prediction journal.

This is a trusted single-controller journal, not an adversarial filesystem
sandbox. No resume or record replacement is implemented. A partial write is
retained and invalidates this instance; it cannot become a completed study.
A COMPLETE.json file is provisional without a successful operator finish
receipt and separately checked chain/files. A late fsync failure can leave this
file on disk; existence alone never grants evaluation eligibility.
No observations, target values, scores or previous predictions are returned to
participants. Whole-study and per-record limits require a later finite grant.
"""
import hashlib
import json
import os
from pathlib import Path


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=True, allow_nan=False).encode('utf-8') + b'\n'


class Journal:
    def __init__(self, path, *, max_total_bytes, max_record_bytes):
        for value in (max_total_bytes, max_record_bytes):
            if type(value) is not int or value <= 0:
                raise ValueError('Explicit positive byte limits required')
        if max_record_bytes > max_total_bytes:
            raise ValueError('Per-record cap exceeds whole-study cap')
        self.path = Path(path)
        # Existing/partial journals must never be adopted or overwritten.
        self.path.mkdir(mode=0o700, parents=False, exist_ok=False)
        os.chmod(self.path, 0o700)
        # Persist the new journal's parent entry before BEGIN/history release.
        parent = os.open(self.path.parent, os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0))
        try:
            os.fsync(parent)
        finally:
            os.close(parent)
        self._total_cap, self._record_cap = max_total_bytes, max_record_bytes
        self._bytes, self._count = 0, 0
        self._chain = '0' * 64
        self._started = self._sealed = self._failed = False

    def _write(self, name, value):
        if self._failed or self._sealed:
            raise ValueError('Journal is closed or failed')
        try:
            data = _canonical(value)
            if len(data) > self._record_cap or self._bytes + len(data) > self._total_cap:
                raise ValueError('Declared output byte budget exceeded; no truncation')
            if not hasattr(os, 'O_NOFOLLOW'):
                raise ValueError('No-follow exclusive output is unsupported')
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | getattr(os, 'O_CLOEXEC', 0)
            fd = os.open(self.path / name, flags, 0o600)
            try:
                os.fchmod(fd, 0o600)
                remaining = memoryview(data)
                while remaining:
                    n = os.write(fd, remaining)
                    if n <= 0:
                        raise OSError('No output progress')
                    remaining = remaining[n:]
                os.fsync(fd)
            finally:
                os.close(fd)
            # Persist the directory entry before reporting a committed record.
            directory = os.open(self.path, os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0))
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
            sha = hashlib.sha256(data).hexdigest()
            self._bytes += len(data)
            self._chain = hashlib.sha256(bytes.fromhex(self._chain) + bytes.fromhex(sha)).hexdigest()
            return {'record_sha256': sha, 'chain_sha256': self._chain, 'logical_bytes': self._bytes}
        except Exception:
            self._failed = True
            raise

    def start(self, value):
        if self._started:
            raise ValueError('Journal already started')
        receipt = self._write('BEGIN.json', value)
        self._started = True
        return receipt

    def commit(self, value):
        if not self._started:
            raise ValueError('Journal not started')
        receipt = self._write(f'{self._count:06d}.json', value)
        self._count += 1
        return receipt

    def seal(self, value):
        if not self._started:
            raise ValueError('Journal not started')
        result = dict(value)
        result['requires_successful_operator_finish_receipt'] = True
        result['locked_records'] = self._count
        result['prior_chain_sha256'] = self._chain
        receipt = self._write('COMPLETE.json', result)
        self._sealed = True
        return receipt
