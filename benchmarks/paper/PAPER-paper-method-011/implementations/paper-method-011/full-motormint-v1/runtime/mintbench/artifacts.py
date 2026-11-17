"""Exclusive immutable outputs and append-only all-attempt accounting."""
import hashlib
import os
from pathlib import Path
from .validation import exact, ident, integer, finite, encoded, need, digest


def owned(root, relative):
    from .validation import descriptor
    descriptor({'path': relative, 'bytes': 0, 'sha256': '0' * 64})
    root = Path(root)
    need(root.is_absolute(), 'absolute owned output root')
    path = root / relative
    need(path.parent.is_dir() and all(not p.is_symlink() for p in (path, *path.parents)), 'owned output path')
    return path


class Collector:
    def __init__(self, root, relative, case, maximum, budget=None):
        self.path = owned(root, relative)
        self.handle = self.path.open('xb')
        self.budget=budget
        self.case, self.maximum = ident(case), integer(maximum, 1)
        self.h, self.total, self.rows = hashlib.sha256(), 0, 0
        self.finished = False
        self.failure = None

    def row(self, stream, index, sample_id, value):
        need(not self.finished and self.handle is not None, 'collector active')
        ident(stream); ident(sample_id); integer(index)
        record = {'case': self.case, 'stream': stream, 'index': index,
                  'sample_id': sample_id, 'value': value}
        raw = encoded(record) + b'\n'
        need(self.total + len(raw) <= self.maximum, 'whole output byte ceiling')
        if self.budget is not None:self.budget.charge(len(raw))
        self.handle.write(raw); self.h.update(raw)
        self.total += len(raw); self.rows += 1

    def close(self, successful, error=None):
        need(not self.finished, 'collector closes once')
        try:
            self.handle.flush(); os.fsync(self.handle.fileno())
        finally:
            self.handle.close(); self.handle = None; self.finished = True
        self.failure = None if successful else str(error or 'incomplete output')[:500]
        return {'path': self.path.name, 'bytes': self.total, 'sha256': self.h.hexdigest(),
                'rows': self.rows, 'complete': bool(successful), 'failure': self.failure}


class Journal:
    def __init__(self, root, relative, maximum, budget=None):
        self.path = owned(root, relative)
        self.handle = self.path.open('xb')
        self.maximum, self.total, self.count, self.chain = maximum, 0, 0, '0' * 64
        self.ids = set();self.budget=budget

    def append(self, attempt):
        exact(attempt, ('id', 'case', 'role', 'status', 'wall_seconds', 'cpu_seconds',
                        'gpu_seconds', 'token_count', 'bytes_written', 'peak_rss_bytes',
                        'source_sha256', 'output', 'lifecycle', 'error', 'resource_error'), 'all-attempt record')
        ident(attempt['id']); ident(attempt['case'])
        need(attempt['id'] not in self.ids, 'each attempt charged once')
        need(attempt['role'] in ('candidate_A', 'candidate_B', 'reference'), 'trusted process role')
        need(attempt['status'] in ('success', 'failure', 'not_started'), 'attempt outcome')
        for key in ('wall_seconds', 'cpu_seconds', 'gpu_seconds'):
            if attempt[key] is not None:
                finite(attempt[key], nonnegative=True)
        for key in ('token_count', 'bytes_written', 'peak_rss_bytes'):
            if attempt[key] is not None:
                integer(attempt[key])
        need(attempt['resource_error'] is not None or all(attempt[k] is not None for k in
             ('wall_seconds', 'cpu_seconds', 'gpu_seconds', 'token_count', 'bytes_written', 'peak_rss_bytes')), 'unmeasured costs explicitly retained')
        record = {'sequence': self.count, 'previous': self.chain, 'attempt': attempt}
        record['sha256'] = digest(record)
        raw = encoded(record) + b'\n'
        need(self.total + len(raw) <= self.maximum, 'all-attempt journal budget')
        if self.budget is not None:self.budget.charge(len(raw))
        self.handle.write(raw); self.handle.flush(); os.fsync(self.handle.fileno())
        self.chain = record['sha256']; self.total += len(raw); self.count += 1
        self.ids.add(attempt['id'])

    def close(self):
        self.handle.close()
        return {'attempts': self.count, 'bytes': self.total, 'chain_sha256': self.chain}
