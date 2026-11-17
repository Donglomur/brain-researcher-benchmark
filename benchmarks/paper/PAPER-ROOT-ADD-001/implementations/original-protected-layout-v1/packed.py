"""Operator-private packed predictions with complete original row/request joins.

This collector never executes participant code or validates an OS sandbox. Its
caller must supply a frozen trusted-store schedule and an independently verified
closed-invocation receipt. Hashing that receipt preserves attribution; it does
not turn a claimed closure into qualified execution.
"""
from __future__ import annotations

import hashlib
import io
import json
import math
import os
from pathlib import Path
import stat
import struct

import numpy as np

REQUEST = struct.Struct('<6QdII32s32s32s32s')
JOB = struct.Struct('<7Q4IiI32s32s32s32s48x')
assert REQUEST.size == 192 and JOB.size == 256
CONTEXT_KEYS = ('session_index', 'field_index', 'layer', 'lag_index', 'lag_bins')


def need(ok, message):
    if not ok:
        raise ValueError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def digest(value):
    need(type(value) is str and len(value) == 64 and all(c in '0123456789abcdef' for c in value),
         'Exact SHA256 required')
    return bytes.fromhex(value)


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()


def parse(raw):
    def pairs(rows):
        value = {}
        for k, v in rows:
            need(k not in value, 'Duplicate JSON key')
            value[k] = v
        return value
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=lambda _: need(False, 'Nonfinite JSON'))


def canonical_prediction(raw, shape):
    need(type(shape) is tuple and len(shape) == 2 and all(type(n) is int and n > 0 for n in shape),
         'Positive two-dimensional prediction geometry')
    need(type(raw) is bytes and len(raw) <= 8192 + math.prod(shape) * 8,
         'Bounded raw prediction before parsing')
    stream = io.BytesIO(raw)
    version = np.lib.format.read_magic(stream)
    readers = {(1, 0): np.lib.format.read_array_header_1_0, (2, 0): np.lib.format.read_array_header_2_0}
    need(version in readers, 'Primitive NPY versions only')
    actual, fortran, dtype = readers[version](stream, max_header_size=4096)
    need(tuple(actual) == tuple(shape) and dtype.kind == 'f' and dtype.itemsize in (4, 8)
         and not dtype.hasobject and dtype.fields is None and dtype.subdtype is None
         and stream.tell() + math.prod(shape) * dtype.itemsize == len(raw),
         'Exact finite prediction shape/dtype/extent')
    value = np.frombuffer(raw, dtype=dtype, offset=stream.tell()).reshape(shape, order='F' if fortran else 'C')
    need(np.isfinite(value).all(), 'Every query prediction is finite')
    return np.array(value, dtype='<f8', order='C', copy=True), dtype.itemsize, int(fortran)


class PackedWriter:
    """One bounded private stream per product kind, not one file per invocation.

    One complete job's pooled predictions remain in RAM and are written once in
    original supported-row order. Held requests are processed in original sorted
    qid order. Immutable private qid/time maps are bound by SHA and must remain
    available in the separately authenticated trusted store for independent
    recovery. Targets never enter a participant output or this collector.
    """
    def __init__(self, root, *, store_sha256, candidate_sha256, schedule_sha256,
                 job_context_sha256, expected_job_contexts, condition, expected_jobs,
                 expected_requests, output_limit, working_limit):
        for x in (store_sha256, candidate_sha256, schedule_sha256, job_context_sha256):
            digest(x)
        need(condition in ('paper_data', 'paper_data_author_code'), 'Exact paper information condition')
        need(all(type(n) is int and n > 0 for n in (expected_jobs, expected_requests, output_limit, working_limit)),
             'Explicit finite complete-run declarations')
        need(type(expected_job_contexts) in (list, tuple) and len(expected_job_contexts) == expected_jobs
             and expected_jobs <= 58926 and expected_jobs * 1024 + 1048576 <= working_limit,
             'Complete bounded frozen job context roster before authentication')
        self.fixed_working = expected_jobs * 1024 + 1048576
        context_hash, contexts = hashlib.sha256(), []
        for row in expected_job_contexts:
            need(type(row) is dict and set(row) == set(CONTEXT_KEYS)
                 and all(type(v) is int for v in row.values()), 'Exact frozen job coordinates')
            context_hash.update(encoded(row))
            contexts.append(tuple(row[k] for k in CONTEXT_KEYS))
        need(context_hash.hexdigest() == job_context_sha256, 'Complete frozen job order digest')
        self.expected_contexts = tuple(contexts)
        self.root = Path(root).absolute()
        need(not any(p.is_symlink() for p in self.root.parents), 'No private output symlink ancestors')
        self.root.mkdir(mode=0o700)
        self.bindings = {'store_sha256': store_sha256, 'candidate_sha256': candidate_sha256,
                         'schedule_sha256': schedule_sha256, 'job_context_sha256': job_context_sha256,
                         'condition': condition}
        self.expected_jobs, self.expected_requests = expected_jobs, expected_requests
        self.limit, self.working = output_limit, working_limit
        self.reserved, self.written, self.jobs, self.requests = 0, 0, 0, 0
        self.streams, self.hashes, self.bytes = {}, {}, {}
        self.active, self.failed, self.finished = None, False, False
        try:
            for name in ('PREDICTIONS.f64le', 'REQUESTS.bin', 'JOBS.bin'):
                fd = os.open(self.root / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL
                             | getattr(os, 'O_NOFOLLOW', 0), 0o600)
                os.set_inheritable(fd, False)
                os.fchmod(fd, 0o600)
                self.streams[name] = os.fdopen(fd, 'wb')
                self.hashes[name], self.bytes[name] = hashlib.sha256(), 0
        except BaseException:
            self.close()
            raise

    def write(self, name, raw):
        need(not self.failed and not self.finished, 'Unfailed open collector')
        need(self.written + len(raw) <= self.reserved <= self.limit, 'Reserved private bytes before write')
        self.written += len(raw)
        try:
            need(self.streams[name].write(raw) == len(raw), 'Complete private product write')
        except BaseException:
            self.failed = True
            raise
        self.hashes[name].update(raw)
        self.bytes[name] += len(raw)

    def begin_job(self, *, context, qid, time_indices, outputs, support_class_sha256,
                  expected_request_hashes):
        need(not self.failed and not self.finished and self.active is None
             and self.jobs < self.expected_jobs, 'One active original job in declared run')
        need(set(context) == {'session_index', 'field_index', 'layer', 'lag_index', 'lag_bins'}
             and all(type(v) is int for v in context.values()), 'Exact original job coordinates')
        need(tuple(context[k] for k in CONTEXT_KEYS) == self.expected_contexts[self.jobs],
             'Exact next globally frozen job, not only matching cardinality')
        need(0 <= context['session_index'] < 14 and 0 <= context['field_index'] < 16
             and 0 <= context['layer'] < 33 and 0 <= context['lag_index'] < 40
             and -20 <= context['lag_bins'] < 20, 'Original source coordinate ranges')
        digest(support_class_sha256)
        need(type(outputs) is int and 1 <= outputs <= 82 and qid.ndim == time_indices.ndim == 1
             and qid.dtype == np.float64 and time_indices.dtype == np.int64
             and len(qid) == len(time_indices) and 2 <= len(qid) <= 144111, 'Bounded original row-map metadata')
        extent = len(qid) * outputs * 8
        need(self.fixed_working + 4 * extent + 512 * len(qid) + 1048576 <= self.working,
             'One-job workspace admitted before array scans or allocation')
        need(np.isfinite(qid).all() and np.all(qid == np.floor(qid)) and np.all(np.abs(qid) < 2**53)
             and np.all(time_indices >= 0) and np.all(np.diff(time_indices) > 0), 'Original ordered qid/time maps')
        labels = np.unique(qid)
        need(len(labels) >= 2 and len(expected_request_hashes) == len(labels)
             and self.requests + len(labels) <= self.expected_requests, 'Complete original held-qid request roster')
        expected = tuple(expected_request_hashes)
        for value in expected:
            digest(value)
        reserve = extent + REQUEST.size * len(labels) + JOB.size
        need(self.reserved + reserve + 65536 <= self.limit, 'Whole job plus final manifest reserved before requests')
        self.reserved += reserve
        self.active = {'context': dict(context), 'qid': qid.copy(), 'time_indices': time_indices.copy(),
                       'labels': labels, 'expected': expected, 'outputs': outputs, 'next': 0,
                       'support_class_sha256': support_class_sha256, 'first_request': self.requests,
                       'prediction_offset': self.bytes['PREDICTIONS.f64le'],
                       'predictions': np.full((len(qid), outputs), np.nan, dtype='<f8')}

    def accept(self, *, held_qid, request_sha256, raw_prediction, closure):
        """Only after the trusted provider has independently verified closure.

        This exact receipt schema prevents missing/ambiguous provenance. It is
        not an attestation mechanism and never grants runtime qualification.
        """
        need(not self.failed and self.active is not None, 'Active original job required')
        try:
            a = self.active
            need(type(held_qid) in (int, float) and a['next'] < len(a['labels'])
                 and held_qid == float(a['labels'][a['next']])
                 and request_sha256 == a['expected'][a['next']], 'Original held-qid order and frozen view identity')
            digest(request_sha256)
            rows = np.flatnonzero(a['qid'] == held_qid)
            need(type(raw_prediction) is bytes and len(raw_prediction) <= 8192 + len(rows) * a['outputs'] * 8,
                 'Transport byte cap before hashing or parsing')
            need(type(closure) is dict and set(closure) == {'schema', 'request_sha256', 'candidate_sha256',
                 'provider_source_sha256', 'natural_exit_zero', 'owned_processes_absent',
                 'private_view_retired', 'transport_sha256'}
                 and closure['schema'] == 'language-private-invocation-closure/v1'
                 and closure['request_sha256'] == request_sha256
                 and closure['candidate_sha256'] == self.bindings['candidate_sha256']
                 and closure['transport_sha256'] == sha(raw_prediction)
                 and all(closure[k] is True for k in ('natural_exit_zero', 'owned_processes_absent', 'private_view_retired')),
                 'Complete trusted-provider closed-invocation provenance before prediction parsing')
            digest(closure['provider_source_sha256'])
            value, itemsize, fortran = canonical_prediction(raw_prediction, (int(len(rows)), a['outputs']))
            payload = value.tobytes(order='C')
            record = REQUEST.pack(self.requests, self.jobs, len(rows), a['outputs'],
                                  a['prediction_offset'], len(payload), float(held_qid), itemsize, fortran,
                                  digest(request_sha256), digest(sha(raw_prediction)), digest(sha(payload)),
                                  digest(sha(encoded(closure))))
            self.write('REQUESTS.bin', record)
            a['predictions'][rows] = value
            a['next'] += 1
            self.requests += 1
        except BaseException:
            self.failed = True
            raise

    def finish_job(self):
        need(not self.failed and self.active is not None, 'Unfailed active job required')
        a = self.active
        need(a['next'] == len(a['labels']) and np.isfinite(a['predictions']).all(),
             'Every original held-qid prediction before pooled job product')
        payload = a['predictions'].tobytes(order='C')
        c = a['context']
        record = JOB.pack(self.jobs, a['first_request'], len(a['labels']), len(a['qid']), a['outputs'],
                          a['prediction_offset'], len(payload), c['session_index'], c['field_index'],
                          c['layer'], c['lag_index'], c['lag_bins'], 0,
                          digest(sha(a['qid'].astype('<f8').tobytes())),
                          digest(sha(a['time_indices'].astype('<i8').tobytes())),
                          digest(a['support_class_sha256']), digest(sha(payload)))
        self.write('PREDICTIONS.f64le', payload)
        self.write('JOBS.bin', record)
        prediction = a['predictions']
        prediction.setflags(write=False)
        self.jobs += 1
        self.active = None
        return prediction

    def finish(self):
        need(not self.failed and not self.finished and self.active is None
             and self.jobs == self.expected_jobs and self.requests == self.expected_requests,
             'Exact complete original job/request lattice before final receipt')
        try:
            for stream in self.streams.values():
                stream.flush(); os.fsync(stream.fileno())
            self.close()
        except BaseException:
            self.failed = True
            raise
        result = {'schema': 'language-original-packed-predictions/v1', **self.bindings,
                  'jobs': self.jobs, 'requests': self.requests, 'request_record_bytes': REQUEST.size,
                  'job_record_bytes': JOB.size, 'prediction_dtype': '<f8',
                  'files': {n: {'bytes': self.bytes[n], 'sha256': self.hashes[n].hexdigest()} for n in self.streams},
                  'request_payload_layout': 'Each request names its job matrix base; qid/time maps in the immutable private store select the original rows. Request payload bytes are not asserted contiguous on disk.',
                  'incoming_header_bytes_retained': False, 'incoming_transport_hashes_retained': True,
                  'all_prediction_values_retained': True, 'targets_in_participant_output': False,
                  'request_identity_semantics': 'Caller-frozen opaque SHA; generating an authentic immutable-view identity remains a separate reviewed adapter.',
                  'closure_records_independently_verified_by_collector': False,
                  'protected_execution_qualified': False, 'scientific_qualification': False}
        raw = encoded(result)
        need(len(raw) <= 65536 and self.written + len(raw) <= self.limit, 'Bounded final manifest')
        try:
            fd = os.open(self.root / 'MANIFEST.json', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, 'wb') as stream:
                os.fchmod(stream.fileno(), 0o600)
                self.written += len(raw)
                need(stream.write(raw) == len(raw), 'Complete final manifest write')
                stream.flush(); os.fsync(stream.fileno())
        except BaseException:
            self.failed = True
            raise
        self.finished = True
        return result

    def close(self):
        first = None
        for stream in self.streams.values():
            try:
                stream.close()
            except BaseException as error:
                self.failed = True
                if first is None:
                    first = error
        if first is not None:
            raise first


def recover_job(job_raw, requests_raw, payload, *, qid, time_indices, expected_context,
                expected_request_hashes, support_class_sha256, job_ordinal, first_request,
                prediction_offset, working_limit):
    """Recover one authenticated job for the unchanged private Pearson kernel.

    The caller must first authenticate the three packed files and immutable row
    store. This decoder checks complete per-request joins; it is not a model or
    a replacement correlation calculation.
    """
    need(type(job_raw) is bytes and len(job_raw) == JOB.size, 'One complete packed job record')
    row = JOB.unpack(job_raw)
    ordinal, start, count, n, d, offset, size = row[:7]
    need(ordinal == job_ordinal and start == first_request and offset == prediction_offset
         and 2 <= n <= 144111 and 1 <= d <= 82 and 2 <= count <= n
         and size == n * d * 8 and type(payload) is bytes and len(payload) == size
         and type(requests_raw) is bytes and len(requests_raw) == count * REQUEST.size,
         'Exact next bounded packed job and request extents')
    need(type(working_limit) is int and 4 * (size + len(requests_raw)) + 512 * n + 1048576 <= working_limit,
         'Admit job recovery before array scans')
    context = dict(zip(CONTEXT_KEYS, row[7:12]))
    need(context == expected_context and row[12] == 0 and row[-2] == digest(support_class_sha256),
         'Exact frozen original coordinates and private response-support class')
    need(qid.shape == time_indices.shape == (n,) and qid.dtype == np.float64 and time_indices.dtype == np.int64
         and sha(qid.astype('<f8').tobytes()) == row[-4].hex()
         and sha(time_indices.astype('<i8').tobytes()) == row[-3].hex()
         and sha(payload) == row[-1].hex(), 'Authenticated original qid/time map and prediction payload')
    prediction = np.frombuffer(payload, dtype='<f8').reshape(n, d)
    need(np.isfinite(prediction).all(), 'Complete finite original predictions')
    labels = np.unique(qid)
    need(len(labels) == count == len(expected_request_hashes), 'Complete frozen held-qid roster')
    for i, label in enumerate(labels):
        request = REQUEST.unpack_from(requests_raw, i * REQUEST.size)
        selected = prediction[qid == label]
        need(request[:7] == (first_request + i, job_ordinal, len(selected), d, prediction_offset,
                             selected.nbytes, float(label))
             and request[7] in (4, 8) and request[8] in (0, 1)
             and request[9] == digest(expected_request_hashes[i])
             and request[11].hex() == sha(selected.tobytes(order='C')),
             'Every held request preserves its exact original rows and raw numeric prediction values')
    return prediction


class PackedReader:
    """Authenticate packed products once; reuse stable private file identities.

    This assumes a trusted host that keeps the authenticated files immutable.
    Stat checks detect ordinary changes, not a hostile host defeating file
    identity or controlling the kernel. Closure proof hashes are retained, but
    the actual provider lifecycle journal must be retained and verified by the
    separate protected execution protocol.
    """
    def __init__(self, root, *, manifest_sha256, bindings, expected_jobs, expected_requests,
                 read_limit, working_limit):
        digest(manifest_sha256)
        need(type(read_limit) is int and read_limit > 0 and type(working_limit) is int and working_limit > 0,
             'Explicit reader resource limits')
        need(working_limit >= 4194304, 'Authentication workspace before opening or hashing packed files')
        need(type(expected_jobs) is int and 0 < expected_jobs <= 58926
             and type(expected_requests) is int and 0 < expected_requests <= 6776076,
             'Bounded exact original job/request declarations')
        self.root = Path(root).absolute()
        need(self.root.is_dir() and not any(p.is_symlink() for p in (self.root, *self.root.parents)),
             'Ordinary private packed root')
        self.limit, self.charged, self.working = read_limit, 0, working_limit
        self.streams, self.stamps = {}, {}
        self.jobs, self.requests, self.prediction_offset, self.failed = 0, 0, 0, False
        self.context_hash = hashlib.sha256()
        try:
            stream = self.open_file('MANIFEST.json', maximum=65536)
            raw = self.read_exact('MANIFEST.json', self.stamps['MANIFEST.json'][2])
            need(sha(raw) == manifest_sha256, 'Frozen packed manifest hash')
            manifest = self.manifest = parse(raw)
            need(manifest['schema'] == 'language-original-packed-predictions/v1'
                 and all(manifest[k] == v for k, v in bindings.items())
                 and set(bindings) == {'store_sha256', 'candidate_sha256', 'schedule_sha256', 'job_context_sha256', 'condition'}
                 and manifest['jobs'] == expected_jobs and manifest['requests'] == expected_requests
                 and manifest['request_record_bytes'] == REQUEST.size and manifest['job_record_bytes'] == JOB.size
                 and manifest['prediction_dtype'] == '<f8'
                 and set(manifest['files']) == {'PREDICTIONS.f64le', 'REQUESTS.bin', 'JOBS.bin'},
                 'Exact complete frozen run and packed schema')
            need(manifest['files']['JOBS.bin']['bytes'] == expected_jobs * JOB.size
                 and manifest['files']['REQUESTS.bin']['bytes'] == expected_requests * REQUEST.size,
                 'Complete fixed record extents')
            self.expected_jobs, self.expected_requests = expected_jobs, expected_requests
            for name, expected in manifest['files'].items():
                need(set(expected) == {'bytes', 'sha256'} and type(expected['bytes']) is int and expected['bytes'] > 0,
                     'Finite private product declaration')
                digest(expected['sha256'])
                stream = self.open_file(name, maximum=expected['bytes'])
                need(self.stamps[name][2] == expected['bytes'], 'Exact private product extent')
                hashed, left = hashlib.sha256(), expected['bytes']
                while left:
                    count = min(left, 1048576)
                    hashed.update(self.read_exact(name, count)); left -= count
                need(hashed.hexdigest() == expected['sha256'], 'Complete private product SHA')
                self.eof(name)
                stream.seek(0)
        except BaseException:
            self.failed = True; self.close(); raise

    @staticmethod
    def stamp(info):
        return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns

    def open_file(self, name, maximum):
        path = self.root / name
        before = path.lstat()
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and 0 < before.st_size <= maximum,
             'Bounded ordinary private product')
        fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0))
        stream = self.streams[name] = os.fdopen(fd, 'rb', buffering=0)
        self.stamps[name] = self.stamp(before)
        self.stable(name)
        return stream

    def stable(self, name):
        need(self.stamp(os.fstat(self.streams[name].fileno())) == self.stamps[name]
             and self.stamp((self.root / name).lstat()) == self.stamps[name], 'Private packed file changed after authentication')

    def read_exact(self, name, size):
        need(type(size) is int and size >= 0 and self.charged + size <= self.limit,
             'Private product read allocation before I/O')
        self.stable(name)
        self.charged += size
        raw = self.streams[name].read(size)
        need(len(raw) == size, 'Exact private product read')
        self.stable(name)
        return raw

    def eof(self, name):
        need(self.charged + 1 <= self.limit, 'EOF probe allocation')
        self.charged += 1
        need(self.streams[name].read(1) == b'', 'No extra packed bytes')
        self.stable(name)

    def next_job(self, *, qid, time_indices, expected_context, expected_request_hashes, support_class_sha256):
        need(not self.failed and self.jobs < self.expected_jobs, 'Next declared original job only')
        try:
            record = self.read_exact('JOBS.bin', JOB.size)
            values = JOB.unpack(record)
            need(values[0] == self.jobs and values[1] == self.requests and values[5] == self.prediction_offset
                 and 2 <= values[3] <= 144111 and 1 <= values[4] <= 82
                 and 2 <= values[2] <= values[3] and values[6] == values[3] * values[4] * 8,
                 'Bounded sequential original job before payload reads')
            size, index_size = values[6], values[2] * REQUEST.size
            need(4 * (size + index_size) + 512 * values[3] + 1048576 <= self.working,
                 'Recoverable job workspace before payload reads')
            indices = self.read_exact('REQUESTS.bin', index_size)
            payload = self.read_exact('PREDICTIONS.f64le', size)
            result = recover_job(record, indices, payload, qid=qid, time_indices=time_indices,
                expected_context=expected_context, expected_request_hashes=expected_request_hashes,
                support_class_sha256=support_class_sha256, job_ordinal=self.jobs,
                first_request=self.requests, prediction_offset=self.prediction_offset, working_limit=self.working)
            self.context_hash.update(encoded(expected_context))
            self.jobs += 1; self.requests += values[2]; self.prediction_offset += size
            return result
        except BaseException:
            self.failed = True
            raise

    def finish(self):
        need(not self.failed and self.jobs == self.expected_jobs and self.requests == self.expected_requests,
             'All original packed jobs and held requests consumed')
        try:
            need(self.context_hash.hexdigest() == self.manifest['job_context_sha256'],
                 'Complete recovered source job order matches frozen context digest')
            for name in self.manifest['files']:
                self.eof(name)
        except BaseException:
            self.failed = True
            raise
        return {'jobs': self.jobs, 'requests': self.requests, 'read_bytes': self.charged,
                'all_numeric_predictions_recovered': True, 'protected_execution_qualified': False,
                'provider_journal_independently_verified': False, 'scientific_qualification': False}

    def close(self):
        first = None
        for stream in self.streams.values():
            try:
                stream.close()
            except BaseException as error:
                self.failed = True
                if first is None:
                    first = error
        if first is not None:
            raise first
