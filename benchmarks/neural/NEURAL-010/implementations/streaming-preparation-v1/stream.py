"""Operator-only, full-cohort streaming preparation with anchored resume.

Local input import only: acquisition is separately authorized and accounted.
No model, scoring, download, automatic retry, or viewer implementation is here.
"""
import argparse
import contextlib
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import stat
import sys
import time

from original import Original, encoded, need, path, pin, strict

EVENT_CAP = 65536
RECEIPT_CAP = 262144
META_CAP = 32 * 1048576
CONFIG_CAP = 1048576
PIN_RE = re.compile(r'[0-9a-f]{64}\Z')
COUNTERS = ('read_bytes', 'write_bytes', 'input_bytes', 'attempts')
PREFLIGHT_READ_BYTES = 43 * 1048576
PREFLIGHT_WRITE_BYTES = 2 * CONFIG_CAP + 4 * EVENT_CAP


def descriptor(value):
    need(type(value) is dict and set(value) == {'bytes', 'sha256'}
         and type(value['bytes']) is int and value['bytes'] > 0
         and type(value['sha256']) is str and PIN_RE.fullmatch(value['sha256']), 'exact descriptor')
    return value


def stamp(s):
    return [s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns]


def ordinary(p):
    p = path(str(p))
    s = p.lstat()
    need(stat.S_ISREG(s.st_mode) and s.st_nlink == 1, 'ordinary single-link file')
    return stamp(s)


def sync_dir(p):
    p = path(str(p))
    fd = os.open(p, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def mkdir(p):
    p = path(str(p))
    os.mkdir(p, 0o700)
    sync_dir(p)
    sync_dir(p.parent)


def parents(p, root):
    p, root = path(str(p)), path(str(root))
    need(p.is_relative_to(root), 'owned descendant directory')
    q = root
    for part in p.relative_to(root).parts:
        q = q / part
        if q.exists():
            need(not q.is_symlink() and q.is_dir(), 'ordinary owned directory')
        else:
            mkdir(q)


def put(p, body):
    """Create only. A torn write is preserved and requires operator recovery."""
    p = path(str(p))
    fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o400)
    try:
        remaining = memoryview(body)
        while remaining:
            n = os.write(fd, remaining)
            need(n > 0, 'complete owned write')
            remaining = remaining[n:]
        os.fsync(fd)
    finally:
        os.close(fd)
    sync_dir(p.parent)


def read(p, expected=None, cap=META_CAP, tick=lambda: None):
    if expected is not None:
        descriptor(expected)
        need(expected['bytes'] <= cap, 'read descriptor cap')
    fd = os.open(path(str(p)), os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        a = os.fstat(fd)
        need(stat.S_ISREG(a.st_mode) and a.st_nlink == 1 and 0 < a.st_size <= cap, 'bounded ordinary input')
        if expected is not None:
            need(a.st_size == expected['bytes'], 'exact input extent')
        data = bytearray()
        while len(data) <= cap:
            chunk = os.read(fd, min(65536, cap + 1 - len(data)))
            if not chunk:
                break
            data.extend(chunk)
            tick()
        need(stamp(a) == stamp(os.fstat(fd)), 'input stable through capture')
        data = bytes(data)
        need(len(data) <= cap and (expected is None or pin(data) == expected), 'input identity')
        return data
    finally:
        os.close(fd)


def hash_file(p, cap, tick=lambda: None):
    fd = os.open(path(str(p)), os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        a = os.fstat(fd)
        need(stat.S_ISREG(a.st_mode) and a.st_nlink == 1 and 0 < a.st_size <= cap, 'bounded ordinary payload')
        digest = hashlib.sha256()
        n = 0
        while n <= cap:
            chunk = os.read(fd, min(1048576, cap + 1 - n))
            if not chunk:
                break
            n += len(chunk)
            digest.update(chunk)
            tick()
        need(n == a.st_size and n <= cap and stamp(a) == stamp(os.fstat(fd)), 'stable complete payload')
        return {'bytes': n, 'sha256': digest.hexdigest()}
    finally:
        os.close(fd)


def sync_file(p):
    fd = os.open(path(str(p)), os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        a = os.fstat(fd)
        need(stat.S_ISREG(a.st_mode) and a.st_nlink == 1, 'owned output')
        os.fsync(fd)
        need(stamp(a) == stamp(os.fstat(fd)), 'stable sync')
    finally:
        os.close(fd)
    sync_dir(p.parent)


def rename_owned(source, destination):
    source, destination = path(str(source)), path(str(destination))
    need(not os.path.lexists(destination), 'rename destination must be wholly absent')
    os.rename(source, destination)
    sync_dir(source.parent)
    if source.parent != destination.parent:
        sync_dir(destination.parent)


def linux_clock():
    """Resume is limited to one Linux boot/monotonic clock domain."""
    boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    need(re.fullmatch(r'[0-9a-f-]{36}', boot), 'Linux boot identity')
    return boot, time.monotonic


def invocation_receipt(directory, invocation_id, root, anchor, command, request_pin,
                       config_pin, clock_domain, clock=time.monotonic):
    """Persist a separately admitted preflight charge before large metadata reads.

    This operator ledger is independent of the signal-operation journal, because
    failed authentication cannot safely append to that journal. The launcher
    must admit its cumulative fixed charges, own its custody and supervise the
    small act of creating this receipt. It is not a resource approval service.
    """
    directory = path(str(directory))
    need(directory.is_dir() and re.fullmatch(r'[a-zA-Z0-9._-]{1,80}', invocation_id)
         and invocation_id not in ('.', '..'), 'existing operator invocation ledger and unique identifier')
    for p in (root, anchor):
        need(directory != p and not directory.is_relative_to(p)
             and not p.is_relative_to(directory), 'independent invocation ledger namespace')
    body = encoded({'schema': 'neural010-streaming-invocation-reservation-v1',
        'invocation_id': invocation_id, 'root': str(root), 'anchor': str(anchor), 'command': command,
        'request': request_pin, 'configuration': config_pin, 'clock_domain': clock_domain,
        'monotonic_start': clock(), 'preflight_read_reserved_bytes': PREFLIGHT_READ_BYTES,
        'preflight_write_reserved_bytes': PREFLIGHT_WRITE_BYTES,
        'charge_retained_on_failure_or_interruption': True,
        'independent_launcher_admission_required': True})
    need(len(body) <= 16384, 'small preflight reservation receipt')
    put(directory / (invocation_id + '.json'), body)
    return pin(body)


class Journal:
    """Generic trusted-operator kernel; production admission is Original + CLI.

    Every operation intent is fsynced locally and in a disjoint operator anchor
    directory before side effects. Both histories must agree exactly at resume.
    The independent launcher must retain anchor custody; this is not a hostile
    filesystem or process sandbox.
    """
    def __init__(self, root, anchor, config_pin, clock_domain, clock=time.monotonic):
        self.root, self.anchor = path(str(root)), path(str(anchor))
        need(self.root != self.anchor and not self.root.is_relative_to(self.anchor)
             and not self.anchor.is_relative_to(self.root), 'disjoint independent anchor namespace')
        self.clock = clock
        body = read(self.root / 'CONFIG.json', config_pin, CONFIG_CAP)
        need(read(self.anchor / 'CONFIG.json', config_pin, CONFIG_CAP) == body, 'external genesis agreement')
        self.config = strict(body)
        need(self.config['root'] == str(self.root) and self.config['anchor'] == str(self.anchor), 'fixed storage identity')
        need(self.config['clock_domain'] == clock_domain, 'same authenticated boot/clock domain')
        self.config_pin = config_pin
        self.limits = self.config['limits']
        self.end = self.config['monotonic_end']
        self.operation_end = min(self.end, self.clock() + self.limits['operation_seconds'])
        self.events = []
        self.total = {k: 0 for k in COUNTERS}
        self.tip = config_pin['sha256']
        self.replay_bytes = len(body) * 2
        local = sorted((self.root / 'journal').iterdir())
        external = sorted((self.anchor / 'journal').iterdir())
        need([p.name for p in local] == [p.name for p in external],
             'journal/anchor mismatch: no unanchored or rolled-back prefix accepted')
        need(len(local) <= self.limits['max_events'], 'journal event bound')
        for i, (a, b) in enumerate(zip(local, external), 1):
            need(a.name == f'{i:08d}.json', 'contiguous exact journal namespace')
            raw = read(a, cap=EVENT_CAP, tick=self.tick)
            need(read(b, pin(raw), EVENT_CAP, self.tick) == raw, 'independent checkpoint agreement')
            self.replay_bytes += 2 * len(raw)
            need(self.replay_bytes <= META_CAP, 'bounded replay metadata')
            event = strict(raw)
            need(set(event) == {'sequence', 'previous', 'kind', 'data', 'charge', 'total', 'clock'}, 'exact journal event')
            need(event['sequence'] == i and type(event['sequence']) is int
                 and event['previous'] == self.tip, 'journal chain')
            need(type(event['clock']) in (int, float) and math.isfinite(event['clock'])
                 and self.config['monotonic_start'] <= event['clock'] <= self.clock(), 'nonfuture same-domain clock')
            if self.events:
                need(event['clock'] >= self.events[-1]['clock'], 'nondecreasing journal time')
            self._charge(event['charge'])
            need(event['total'] == self.total, 'cumulative nonrefunded reservations')
            self.events.append(event)
            self.tip = pin(raw)['sha256']
        self.tick()

    @staticmethod
    def initialize(root, anchor, backend, limits, clock_domain, clock=time.monotonic,
                   invocation_ledger=None):
        root, anchor = path(str(root)), path(str(anchor))
        need(not root.exists() and not anchor.exists() and root != anchor
             and not root.is_relative_to(anchor) and not anchor.is_relative_to(root), 'fresh disjoint owned roots')
        expected = {*COUNTERS, 'operation_seconds', 'whole_seconds', 'project_peak_bytes',
                    'minimum_free_bytes', 'max_events'}
        need(type(limits) is dict and set(limits) == expected, 'exact fixed resource limits')
        for k, v in limits.items():
            need(type(v) is int and v > 0, 'positive integral resource ceiling')
        need(limits['max_events'] <= 10000, 'finite journal events')
        now = clock()
        config = {'schema': 'neural010-streaming-config-v1', 'root': str(root), 'anchor': str(anchor),
                  'clock_domain': clock_domain, 'monotonic_start': now,
                  'monotonic_end': now + limits['whole_seconds'], 'limits': limits,
                  'backend_identity': backend.identity, 'invocation_ledger': invocation_ledger}
        body = encoded(config)
        need(len(body) <= CONFIG_CAP, 'configuration extent')
        # Genesis allocation is externally reserved before init, including a
        # possible interrupted root/anchor creation. Never adopt an old root.
        mkdir(root)
        mkdir(anchor)
        for p in (root / 'journal', anchor / 'journal', root / 'work', root / 'pending'):
            mkdir(p)
        for p in (root / 'pending/public', root / 'pending/private', root / 'pending/public/signals'):
            mkdir(p)
        put(root / 'CONFIG.json', body)
        put(anchor / 'CONFIG.json', body)
        fd = os.open(root / 'LOCK', os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        os.fsync(fd)
        os.close(fd)
        sync_dir(root)
        result = Journal(root, anchor, pin(body), clock_domain, clock)
        result.append('genesis', {'configuration': pin(body)}, write_bytes=2 * len(body),
                      read_bytes=getattr(getattr(backend, 'bootstrap', None), 'read_bytes', 0))
        return pin(body)

    def tick(self):
        need(self.config['monotonic_start'] <= self.clock() < self.operation_end,
             'original campaign/operation deadline; no reset at resume')

    def _charge(self, charge):
        need(type(charge) is dict and set(charge) == set(COUNTERS), 'exact counter vector')
        for k in COUNTERS:
            need(type(charge[k]) is int and charge[k] >= 0, 'nonnegative typed reservation')
            self.total[k] += charge[k]
            need(self.total[k] <= self.limits[k], 'cumulative ' + k + ' limit')

    def append(self, kind, data, **charge):
        self.tick()
        need(len(self.events) < self.limits['max_events'], 'journal event capacity')
        increments = {k: charge.pop(k, 0) for k in COUNTERS}
        need(not charge, 'unknown counter')
        # Conservative metadata journal cost is charged before both create-only
        # writes. Failed or partial frames are never silently discarded.
        increments['write_bytes'] += 2 * EVENT_CAP
        total = {k: self.total[k] + increments[k] for k in COUNTERS}
        for k in COUNTERS:
            need(type(increments[k]) is int and increments[k] >= 0 and total[k] <= self.limits[k],
                 'pre-effect cumulative ' + k + ' admission')
        event = {'sequence': len(self.events) + 1, 'previous': self.tip, 'kind': kind, 'data': data,
                 'charge': increments, 'total': total, 'clock': self.clock()}
        body = encoded(event)
        need(len(body) <= EVENT_CAP, 'journal frame bound')
        need(self.replay_bytes + 2 * len(body) <= META_CAP, 'journal replay capacity')
        name = f'{event["sequence"]:08d}.json'
        put(self.root / 'journal' / name, body)
        put(self.anchor / 'journal' / name, body)
        self.events.append(event)
        self.total = total
        self.tip = pin(body)['sha256']
        self.replay_bytes += 2 * len(body)
        return event

    @contextlib.contextmanager
    def locked(self):
        fd = os.open(path(str(self.root / 'LOCK')), os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK)
        try:
            need(stat.S_ISREG(os.fstat(fd).st_mode) and os.fstat(fd).st_nlink == 1, 'ordinary lock file')
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            # Object creation may precede lock acquisition. Never act on a stale
            # replay if another process appended in that interval.
            local = sorted(p.name for p in (self.root / 'journal').iterdir())
            need(local == [f'{i:08d}.json' for i in range(1, len(self.events) + 1)], 'stale journal object')
            yield
        finally:
            os.close(fd)


class Engine:
    """Generic generated-test seam; CLI always constructs pinned Original."""
    def __init__(self, journal, backend):
        self.j, self.b = journal, backend
        need(journal.config['backend_identity'] == backend.identity, 'same sources, metadata, annotations and private-key identities')
        self.rows = {r['path']: r for r in backend.rows}
        self.bindings = {b['source_path']: b for b in backend.bindings}
        need(len(self.rows) == backend.expected_records and set(self.rows) == set(self.bindings), 'complete unique source binding')
        need(len({b['patient_id'] for b in backend.bindings}) == backend.expected_people, 'biological identity support')
        self.attempts, self.completed, self.cleaned = {}, {}, set()
        self.final_intent, self.published = None, None
        self._replay()

    def _replay(self):
        for e in self.j.events:
            k, d = e['kind'], e['data']
            if k in ('genesis', 'open', 'verify', 'view_intent', 'view_complete'):
                continue
            if k == 'begin':
                a = str(e['sequence'])
                need(a not in self.attempts and d['record'] in self.rows
                     and d['record'] not in self.completed and self.final_intent is None, 'legal fresh attempt')
                need(not any(x['status'] == 'active' for x in self.attempts.values()), 'one pending producer')
                self.attempts[a] = {'record': d['record'], 'status': 'active', 'staged': None,
                                    'cleanup_intent': None, 'source_stamp': None}
            elif k == 'staged':
                a = self.attempts[d['attempt']]
                need(a['status'] == 'active' and a['staged'] is None, 'one authenticated staging completion')
                a['staged'], a['source_stamp'] = d['source'], d['stamp']
                need(d['source'] == {n: self.rows[a['record']][n] for n in ('bytes', 'sha256')}, 'locked staged identity')
            elif k == 'commit':
                a = self.attempts[d['attempt']]
                need(a['status'] == 'active' and a['staged'] is not None
                     and a['record'] not in self.completed, 'authenticated attempt completion')
                descriptor(d['receipt'])
                a['status'], a['receipt'] = 'complete', d['receipt']
                self.completed[a['record']] = d['attempt']
            elif k == 'abort':
                a = self.attempts[d['attempt']]
                need(a['status'] == 'active', 'abort only unresolved attempt')
                descriptor(d['quiescence_evidence'])
                a['status'] = 'aborted'
            elif k == 'cleanup_intent':
                a = self.attempts[d['attempt']]
                need(a['status'] == 'complete' and a['cleanup_intent'] is None, 'cleanup follows durable record commit')
                need(d['stamp'] == a['source_stamp'] and d['source'] == a['staged'], 'cleanup exact owned source')
                a['cleanup_intent'] = d
            elif k == 'cleaned':
                a = self.attempts[d['attempt']]
                need(a['status'] == 'complete' and a['cleanup_intent'] is not None
                     and d['attempt'] not in self.cleaned, 'authorized cleanup completion')
                self.cleaned.add(d['attempt'])
            elif k == 'final_intent':
                need(self.final_intent is None and self.published is None
                     and len(self.completed) == self.b.expected_records
                     and not any(x['status'] == 'active' for x in self.attempts.values()), 'full-support finalization intent')
                self.final_intent = d
            elif k == 'published':
                need(self.final_intent is not None and self.published is None, 'one final publication')
                self.published = d
            else:
                raise ValueError('unknown journal transition')

    def refresh(self):
        self.attempts, self.completed, self.cleaned = {}, {}, set()
        self.final_intent, self.published = None, None
        self._replay()

    def open(self):
        self.j.append('open', {'backend': pin(encoded(self.b.identity))},
                      read_bytes=self.j.replay_bytes + getattr(getattr(self.b, 'bootstrap', None), 'read_bytes', 0))

    def payload_root(self):
        pending = path(str(self.j.root / 'pending'))
        prepared = path(str(self.j.root / 'prepared'))
        need(pending.exists() != prepared.exists(), 'one owned payload tree')
        if prepared.exists():
            need(self.final_intent is not None, 'no unexplained published tree')
            return prepared
        need(self.published is None, 'published tree cannot revert to pending')
        return pending

    def projection(self, record):
        return path(str(self.payload_root() / 'public/signals' / (self.bindings[record]['recording_id'] + '.h5')))

    def receipt_path(self, attempt):
        return self.j.root / 'work' / attempt / 'RECEIPT.json'

    def read_receipt(self, record):
        a = self.completed[record]
        body = read(self.receipt_path(a), self.attempts[a]['receipt'], RECEIPT_CAP, self.j.tick)
        r = strict(body)
        need(r['schema'] == 'neural010-streaming-record-v1' and r['record'] == record
             and r['attempt'] == a and r['binding'] == self.bindings[record], 'exact completed record receipt')
        row = self.rows[record]
        need(r['source'] == {k: row[k] for k in ('bytes', 'sha256')}, 'original complete source descriptor')
        # Recompute all semantic rows, including original annotations, with the
        # newly authenticated original closure. Never trust saved target tables.
        expected = self.b.record(row, self.bindings[record], r['header'], r['projection'])
        need(r['payload'] == expected, 'original semantic record agreement')
        return r

    def verify_completed(self):
        charge = sum(self.attempts[a]['receipt']['bytes'] + 1 for a in self.completed.values())
        # Projection descriptors are inside authenticated receipts. First reserve
        # their complete original ceilings, before opening any retained payload.
        charge += sum(2 * self.rows[r]['bytes'] + 8 * 1048576 + 1 for r in self.completed)
        self.j.append('verify', {'records': len(self.completed)}, read_bytes=charge)
        records = []
        for row in self.b.rows:
            if row['path'] not in self.completed:
                continue
            r = self.read_receipt(row['path'])
            need(hash_file(self.projection(row['path']), 2 * row['bytes'] + 8 * 1048576,
                           self.j.tick) == r['projection'], 'retained projection reauthentication')
            records.append(r['payload'])
        return records

    def process(self, record, source):
        need(self.final_intent is None and record in self.rows and record not in self.completed,
             'uncompleted original record before finalization')
        need(not any(a['status'] == 'active' for a in self.attempts.values()), 'pending attempt needs explicit recovery')
        need(all(a in self.cleaned for a in self.completed.values()), 'retire committed owned staging before next source')
        row = self.rows[record]
        source = path(str(source))
        need(not source.is_relative_to(self.j.root) and not source.is_relative_to(self.j.anchor), 'independent external input path')
        before = ordinary(source)
        need(before[2] == row['bytes'], 'locked source extent')
        ceiling = 2 * row['bytes'] + 8 * 1048576
        need(16 * row['bytes'] + 16 * 1048576 <= self.j.limits['project_peak_bytes'], 'original memory admission')
        needed = row['bytes'] + ceiling + RECEIPT_CAP + 8 * EVENT_CAP
        need(shutil.disk_usage(self.j.root).free - needed >= self.j.limits['minimum_free_bytes'], 'pre-effect disk floor')
        event = self.j.append('begin', {'record': record, 'external_source': str(source)},
            read_bytes=4 * row['bytes'] + ceiling + 4,
            write_bytes=row['bytes'] + ceiling + RECEIPT_CAP,
            input_bytes=row['bytes'], attempts=1)
        attempt = str(event['sequence'])
        self.refresh()
        work = self.j.root / 'work' / attempt
        mkdir(work)
        staged = path(str(work / 'source.edf'))
        fd = os.open(source, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        out = None
        digest, n = hashlib.sha256(), 0
        try:
            out = os.open(staged, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o400)
            need(stamp(os.fstat(fd)) == before, 'source unchanged before copy')
            while n <= row['bytes']:
                part = os.read(fd, min(1048576, row['bytes'] + 1 - n))
                if not part:
                    break
                n += len(part)
                need(n <= row['bytes'], 'no oversized source write')
                digest.update(part)
                remaining = memoryview(part)
                while remaining:
                    wrote = os.write(out, remaining)
                    need(wrote > 0, 'complete source staging')
                    remaining = remaining[wrote:]
                self.j.tick()
            need(stamp(os.fstat(fd)) == before, 'external source stable through copy')
            need({'bytes': n, 'sha256': digest.hexdigest()} == {k: row[k] for k in ('bytes', 'sha256')},
                 'complete locked source authentication')
            os.fsync(out)
        finally:
            os.close(fd)
            if out is not None:
                os.close(out)
        sync_dir(work)
        source_stamp = ordinary(staged)
        self.j.append('staged', {'attempt': attempt, 'source': {k: row[k] for k in ('bytes', 'sha256')},
                                'stamp': source_stamp})
        destination = self.projection(record)
        need(not destination.exists(), 'no existing projection adoption or overwrite')
        header = self.b.project(staged, destination, row)
        self.j.tick()
        need(ordinary(staged) == source_stamp, 'staged source stable through original conversion')
        sync_file(destination)
        projection = hash_file(destination, ceiling, self.j.tick)
        payload = self.b.record(row, self.bindings[record], header, projection)
        receipt = {'schema': 'neural010-streaming-record-v1', 'attempt': attempt, 'record': record,
                   'source': {k: row[k] for k in ('bytes', 'sha256')}, 'binding': self.bindings[record],
                   'header': header, 'projection': projection, 'payload': payload}
        body = encoded(receipt)
        need(len(body) <= RECEIPT_CAP, 'bounded complete record receipt')
        put(self.receipt_path(attempt), body)
        self.j.append('commit', {'attempt': attempt, 'receipt': pin(body)})
        self.refresh()
        self.cleanup(attempt)

    def cleanup(self, attempt):
        need(attempt in self.attempts and self.attempts[attempt]['status'] == 'complete', 'only committed source retirement')
        if attempt in self.cleaned:
            need(not path(str(self.j.root / 'work' / attempt / 'source.edf')).exists(), 'cleaned source must not reappear')
            return
        a = self.attempts[attempt]
        row = self.rows[a['record']]
        self.j.append('verify', {'cleanup_attempt': attempt},
            read_bytes=self.attempts[attempt]['receipt']['bytes'] + row['bytes'] +
            (2 * row['bytes'] + 8 * 1048576) + 3)
        receipt = self.read_receipt(a['record'])
        need(hash_file(self.projection(a['record']), 2 * row['bytes'] + 8 * 1048576,
                       self.j.tick) == receipt['projection'], 'durable retained projection before source cleanup')
        p = path(str(self.j.root / 'work' / attempt / 'source.edf'))
        if p.exists():
            need(ordinary(p) == a['source_stamp'], 'exact original owned staging inode')
            need(hash_file(p, row['bytes'], self.j.tick) == a['staged'], 'owned staging content before retirement')
            if a['cleanup_intent'] is None:
                self.j.append('cleanup_intent', {'attempt': attempt, 'source': a['staged'], 'stamp': a['source_stamp']})
                self.refresh()
            # No external path, glob, recursive delete or failed source cleanup.
            need(ordinary(p) == a['source_stamp'], 'cleanup source unchanged after durable intent')
            os.unlink(p)
            sync_dir(p.parent)
        else:
            need(a['cleanup_intent'] is not None, 'missing source without authorized cleanup')
        self.j.append('cleaned', {'attempt': attempt})
        self.refresh()

    def abort(self, attempt, proof_path, proof_pin):
        """Operator-only recovery after separately evidenced producer quiescence.

        A proof pin binds supplied evidence; it does not establish that evidence's
        truth. Independent process qualification must authorize this command.
        """
        need(attempt in self.attempts and self.attempts[attempt]['status'] == 'active', 'one pending attempt only')
        descriptor(proof_pin)
        need(proof_pin['bytes'] <= EVENT_CAP, 'bounded independent quiescence evidence')
        proof_path = path(str(proof_path))
        need(not proof_path.is_relative_to(self.j.root) and not proof_path.is_relative_to(self.j.anchor), 'external recovery evidence')
        self.j.append('verify', {'recovery_evidence': proof_pin}, read_bytes=proof_pin['bytes'] + 1)
        read(proof_path, proof_pin, EVENT_CAP, self.j.tick)
        a = self.attempts[attempt]
        projection = self.projection(a['record'])
        # Keep every incomplete staging file and partial projection. Rename only
        # this attempt's owned output; a completed record is never abortable.
        if projection.exists():
            ordinary(projection)
            quarantine = path(str(self.j.root / 'work' / attempt / 'aborted-projection.h5'))
            need(not quarantine.exists(), 'fresh partial projection quarantine')
            self.j.append('verify', {'quarantine_attempt': attempt, 'quiescence_evidence': proof_pin})
            rename_owned(projection, quarantine)
        self.j.append('abort', {'attempt': attempt, 'quiescence_evidence': proof_pin})
        self.refresh()

    def finalize(self):
        need(len(self.completed) == self.b.expected_records and set(self.completed) == set(self.rows)
             and all(a in self.cleaned for a in self.completed.values())
             and not any(a['status'] == 'active' for a in self.attempts.values()), 'complete prepared and retired cohort only')
        records = self.verify_completed()
        expected_signals = {b['recording_id'] + '.h5' for b in self.b.bindings}
        need({p.name for p in (self.payload_root() / 'public/signals').iterdir()} == expected_signals,
             'exact complete signal publication namespace')
        payloads = self.b.payloads(records)
        pins = {n: pin(b) for n, b in payloads.items()}
        if self.final_intent is None:
            self.j.append('final_intent', {'payloads': pins, 'records': self.b.expected_records,
                'people': self.b.expected_people, 'views': self.b.expected_views},
                write_bytes=sum(len(b) for b in payloads.values()) + EVENT_CAP,
                read_bytes=sum(len(b) + 1 for b in payloads.values()) + EVENT_CAP)
            self.refresh()
        need(self.final_intent['payloads'] == pins, 'same complete final payloads across resume')
        # Every resumed/repeated finalization authenticates metadata again and
        # therefore gets a fresh nonrefunded read reservation.
        self.j.append('verify', {'final_payloads': pin(encoded(pins))},
                      read_bytes=sum(len(b) + 1 for b in payloads.values()) + EVENT_CAP)
        root = self.payload_root()
        for name, body in payloads.items():
            p = root / name
            parents(p.parent, root)
            if p.exists():
                need(read(p, pins[name], max(META_CAP, len(body)), self.j.tick) == body, 'exact prior finalization payload')
            else:
                need(root.name == 'pending', 'published payload cannot be repaired')
                put(p, body)
        receipt = {'schema': 'neural010-streaming-preparation-v1',
                   'status': 'complete_source_preparation_not_execution_or_scientific_qualification',
                   'configuration': self.j.config_pin, 'records': self.b.expected_records,
                   'people': self.b.expected_people, 'views': self.b.expected_views,
                   'view_materialization': 'lazy_exact_original_bytes', 'payloads': pins,
                   'final_intent': pin(encoded(self.final_intent)), 'models_or_scores': 0,
                   'legacy_prepare_executed': False, 'assessment_release_authorized': False}
        receipt_body = encoded(receipt)
        need(len(receipt_body) <= EVENT_CAP, 'bounded final receipt')
        rp = root / 'private/STREAMING_PREPARATION.json'
        if rp.exists():
            need(read(rp, pin(receipt_body), EVENT_CAP, self.j.tick) == receipt_body, 'same final source receipt')
        else:
            need(root.name == 'pending', 'no postpublication repair')
            put(rp, receipt_body)
        if root.name == 'pending':
            # Same-filesystem atomic directory rename; no signal byte copying.
            need(not (self.j.root / 'prepared').exists(), 'fresh publication path')
            rename_owned(root, self.j.root / 'prepared')
        if self.published is None:
            self.j.append('published', {'receipt': pin(receipt_body)})
            self.refresh()
        else:
            need(self.published == {'receipt': pin(receipt_body)}, 'immutable publication acknowledgment')
        return receipt

    def export_views(self, names):
        need(self.published is not None, 'views only after complete source publication')
        need(type(names) is list and names and len(names) == len(set(names))
             and all(type(n) is str for n in names), 'unique selected view names')
        records = self.verify_completed()
        root = self.payload_root()
        index_pin = self.final_intent['payloads']['private/VIEWS.json']
        self.j.append('verify', {'view_index': index_pin}, read_bytes=index_pin['bytes'] + 1)
        index = strict(read(root / 'private/VIEWS.json', index_pin, META_CAP, self.j.tick))
        selected = {v['name']: v for v in index['views'] if v['name'] in names}
        need(set(selected) == set(names), 'exact indexed outer/inner views')
        completed = []
        for view in self.b.view_documents(records):
            name = view['name']
            if name not in selected:
                continue
            bodies = {k: view[k] for k in selected[name]['artifacts']}
            need({k: pin(v) for k, v in bodies.items()} == selected[name]['artifacts'], 'exact original view bytes')
            self.j.append('view_intent', {'name': name, 'artifacts': selected[name]['artifacts']},
                          write_bytes=sum(len(b) for b in bodies.values()),
                          read_bytes=sum(len(b) + 1 for b in bodies.values()))
            directory = root / 'private/views' / name
            need(directory.is_relative_to(root / 'private/views'), 'owned view path')
            parents(directory, root)
            for filename, body in bodies.items():
                p = directory / filename
                if p.exists():
                    need(read(p, pin(body), META_CAP, self.j.tick) == body, 'immutable cached view')
                else:
                    put(p, body)
            self.j.append('view_complete', {'name': name, 'artifacts': selected[name]['artifacts']})
            completed.append(name)
        need(set(completed) == set(names) and len(completed) == len(names), 'all selected original views produced')
        return [selected[n] for n in names]


def consume_stream(engine, input_stream, acknowledge):
    """Bounded operator JSONL transport, under an external hard deadline."""
    engine.verify_completed()
    remaining = len(engine.rows) - len(engine.completed)
    for index in range(remaining + 1):
        # Reserve before a potentially blocking read, including failed/EOF
        # lines. An independently supervised launcher interrupts a stalled pipe.
        engine.j.append('verify', {'operator_input_line': index}, read_bytes=16385)
        line = input_stream.readline(16385)
        if not line:
            need(set(engine.completed) == set(engine.rows), 'source stream ended before full cohort')
            return engine.finalize()
        need(index < remaining, 'no source input after complete cohort')
        need(len(line) <= 16384 and line.endswith(b'\n'), 'bounded complete operator input line')
        item = strict(line)
        need(type(item) is dict and set(item) == {'record', 'source'}, 'exact source stream member')
        engine.process(item['record'], path(item['source']))
        acknowledge({'source_record_committed': item['record'],
                     'completed_records': len(engine.completed), 'journal_tip': engine.j.tip})
    raise ValueError('source stream did not terminate')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['init', 'check', 'process', 'stream', 'cleanup', 'abort', 'finalize', 'view'])
    for n in ('root', 'anchor', 'request'):
        parser.add_argument('--' + n, required=True)
    parser.add_argument('--invocation-directory', required=True)
    parser.add_argument('--invocation-id', required=True)
    parser.add_argument('--request-sha256', required=True)
    parser.add_argument('--request-bytes', type=int, required=True)
    parser.add_argument('--config-sha256')
    parser.add_argument('--config-bytes', type=int)
    parser.add_argument('--limits')
    parser.add_argument('--record')
    parser.add_argument('--source')
    parser.add_argument('--attempt')
    parser.add_argument('--proof')
    parser.add_argument('--proof-sha256')
    parser.add_argument('--proof-bytes', type=int)
    parser.add_argument('--view', action='append')
    args = parser.parse_args()
    request_pin = {'bytes': args.request_bytes, 'sha256': args.request_sha256}
    descriptor(request_pin)
    root, anchor = path(args.root), path(args.anchor)
    domain, clock = linux_clock()
    config_pin = None if args.command == 'init' else descriptor(
        {'bytes': args.config_bytes, 'sha256': args.config_sha256})
    invocation = invocation_receipt(path(args.invocation_directory), args.invocation_id,
        root, anchor, args.command, request_pin, config_pin, domain, clock)
    request = strict(read(path(args.request), descriptor(request_pin), CONFIG_CAP))
    backend = Original(request)
    # Do not expose the private key or input/source metadata through either root.
    for operand in [request['key_path'], request['lock_path'], request['metadata_root'], request['original_source_root']]:
        q = path(operand)
        need(not q.is_relative_to(root) and not root.is_relative_to(q)
             and not q.is_relative_to(anchor) and not anchor.is_relative_to(q), 'independent source/operator namespaces')
    if args.command == 'init':
        need(args.limits is not None, 'selected resource envelope required')
        limits = strict(read(path(args.limits), cap=EVENT_CAP))
        result = Journal.initialize(root, anchor, backend, limits, domain, clock,
                                    invocation_ledger=args.invocation_directory)
        print(json.dumps({'configuration': result, 'invocation_reservation': invocation,
                          'readiness': 'not_qualified'}, sort_keys=True))
        return
    journal = Journal(root, anchor, config_pin, domain, clock)
    need(journal.config['invocation_ledger'] == args.invocation_directory, 'fixed independent invocation ledger')
    with journal.locked():
        engine = Engine(journal, backend)
        engine.open()
        if args.command == 'check':
            engine.verify_completed()
        elif args.command == 'process':
            need(args.record is not None and args.source is not None, 'one original record/input path')
            engine.verify_completed()
            engine.process(args.record, path(args.source))
        elif args.command == 'stream':
            # External source owner can acquire one locked original, send its
            # path, wait for the completed acknowledgment, then retire its own
            # input. Acquisition/retries are outside this no-network component.
            consume_stream(engine, sys.stdin.buffer,
                           lambda value: print(json.dumps(value, sort_keys=True), flush=True))
        elif args.command == 'cleanup':
            need(args.attempt is not None, 'completed attempt to retire')
            engine.cleanup(args.attempt)
        elif args.command == 'abort':
            need(args.attempt is not None and args.proof is not None, 'explicit attempt and independent quiescence evidence')
            engine.abort(args.attempt, path(args.proof),
                         {'bytes': args.proof_bytes, 'sha256': args.proof_sha256})
        elif args.command == 'finalize':
            engine.finalize()
        elif args.command == 'view':
            need(args.view is not None, 'exact selected view name')
            engine.export_views(args.view)
        print(json.dumps({'completed_records': len(engine.completed), 'expected_records': 686,
                          'published': engine.published is not None,
                          'journal_sequence': len(journal.events), 'journal_tip': journal.tip,
                          'cumulative_reserved': journal.total,
                          'readiness': 'not_qualified'}, sort_keys=True))


if __name__ == '__main__':
    main()
