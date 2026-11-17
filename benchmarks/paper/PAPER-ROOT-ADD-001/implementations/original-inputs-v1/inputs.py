"""Authenticated original archive inputs; no model fit or scientific scoring.

Checksums authenticate the released bytes, not held-out custody or numerical
parity. Numeric bodies are loaded one session at a time. Population weight files
are streamed for their shape/extent/CRC/SHA only, never deserialized with pickle.
"""
from __future__ import annotations

import csv
import hashlib
import importlib.util
import io
import json
import math
import os
from pathlib import Path, PurePosixPath
import stat
import sys
import zipfile

import numpy as np

HERE = Path(__file__).resolve().parent
BINDINGS_SHA = '3b9466d243a86fec32b99a6bf71816c90bd54ef45a292f3e475adce5eeb8e1e7'
FAMILIES = ('context', 'random_token', 'ngram1', 'ngram3', 'ngram5',
            'ngram7', 'ngram10', 'sem_syn', 'word2vec', 'syn')


def need(condition, message):
    if not condition:
        raise ValueError(message)


def pin(raw):
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def bindings():
    raw = (HERE / 'source-bindings.json').read_bytes()
    need(len(raw) == 58852 and pin(raw)['sha256'] == BINDINGS_SHA,
         'Original input binding changed')
    return json.loads(raw)


def reducer():
    """Load the exact previously reviewed reducer without changing its source."""
    meta = bindings()
    modules = {}
    for filename in ('source_panel.py', 'figure3.py'):
        relative = '../original-figure3-v1/' + filename
        path = HERE / relative
        need(pin(path.read_bytes()) == meta['reducer_dependencies'][relative],
             'Original reducer dependency changed')
        spec = importlib.util.spec_from_file_location('language_bound_' + filename[:-3], path)
        module = importlib.util.module_from_spec(spec)
        old = sys.modules.get('source_panel')
        try:
            if 'source_panel.py' in modules:
                sys.modules['source_panel'] = modules['source_panel.py']
            spec.loader.exec_module(module)
        finally:
            if old is None:
                sys.modules.pop('source_panel', None)
            else:
                sys.modules['source_panel'] = old
        modules[filename] = module
    return modules['source_panel.py'], modules['figure3.py']


def feature_member(session, family):
    if family in ('sem_syn', 'word2vec', 'syn'):
        return f'DNN/{session}/sem_syn/{family}_R_embeddings_pca.npy'
    name = ('vicuna7b' if family == 'context' else
            'vicuna7b_random_token_randtok' if family == 'random_token' else
            'vicuna7b_' + family[5:] + 'gram')
    return f'DNN/{session}/llama/{name}_R_embeddings_pca.npy'


def npy_header(raw):
    stream = io.BytesIO(raw)
    version = np.lib.format.read_magic(stream)
    readers = {(1, 0): np.lib.format.read_array_header_1_0,
               (2, 0): np.lib.format.read_array_header_2_0}
    need(version in readers, 'Only primitive NPY versions 1 and 2')
    shape, fortran, dtype = readers[version](stream, max_header_size=4096)
    need(1 <= len(shape) <= 3 and all(type(n) is int and n > 0 for n in shape),
         'Positive one to three dimensional source geometry')
    need(dtype.fields is None and dtype.subdtype is None and dtype.kind == 'f'
         and dtype.itemsize == 8 and not dtype.hasobject, 'Source float64 numeric NPY required')
    return shape, fortran, dtype, stream.tell()


def decode_numeric(raw, expected, *, allow_nan=False):
    shape, fortran, dtype, offset = npy_header(raw)
    need(list(shape) == expected['shape'] and fortran == expected['fortran_order']
         and str(dtype) == expected['dtype'], 'Exact original numeric header required')
    need(len(raw) == offset + math.prod(shape) * dtype.itemsize, 'Exact numeric body extent')
    value = np.frombuffer(raw, dtype=dtype, offset=offset).reshape(shape, order='F' if fortran else 'C')
    need(not np.isinf(value).any() and (allow_nan or np.isfinite(value).all()),
         'Nonfinite source numeric input')
    return value


def parse_words(raw, geometry):
    rows = list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))))
    need(len(rows) == geometry['word_rows'], 'Original CSV and PCA word counts differ')
    try:
        timing = np.array([[float(r['start_time']), float(r['end_time'])] for r in rows])
        qid = np.array([float(r['qid']) for r in rows])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError('Missing or invalid original timing/qid') from exc
    need(np.isfinite(timing).all() and np.all(timing >= 0)
         and np.all(timing[:, 1] >= timing[:, 0])
         and np.all(timing < (geometry['time_bins'] + 1) / 10)
         and np.all((timing * 10).astype(np.int64) <= geometry['time_bins']),
         'Word interval is outside original neural clock')
    need(np.isfinite(qid).all() and np.all(qid == np.floor(qid))
         and np.all(np.abs(qid) < 2**53), 'Finite exact integer sentence identifiers')
    # Source sentinels >=99990 are retained. Their feature writes still occur;
    # format_qid alone skips assigning them, including in overlapping intervals.
    return timing, qid


def file_identity(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


class ArchiveInputs:
    """Local original release reader. Caller owns OS resource/process limits.

    read_limit charges archive checksum bytes and expanded member bytes plus EOF
    probes. It is a logical admission bound, not total kernel/ZIP seek I/O.
    The optional metadata argument exists for small generated engineering inputs;
    the command-line path always loads the pinned original binding.
    """
    def __init__(self, paths, *, read_limit, working_limit, metadata=None):
        self.meta = bindings() if metadata is None else metadata
        self.geometry = {r['id']: r for r in self.meta['sessions']}
        self.read_limit, self.working_limit = read_limit, working_limit
        need(type(read_limit) is int and read_limit > 0 and type(working_limit) is int
             and working_limit > 0, 'Positive explicit resource limits required')
        required = {r['archive'] for r in self.meta['members'].values()}
        need(set(paths) == required, 'Complete original input archive set required')
        self.charged = 0
        self.streams, self.archives, self.identities = {}, {}, {}
        self.archive_receipts, self.member_receipts = {}, {}
        try:
            for name in sorted(required):
                path = Path(paths[name]).absolute()
                need(not any(p.is_symlink() for p in (path, *path.parents)), 'No source symlink ancestors')
                fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
                stream = os.fdopen(fd, 'rb')
                self.streams[name] = stream
                info = os.fstat(fd)
                expected = self.meta['archives'][name]
                need(stat.S_ISREG(info.st_mode) and info.st_nlink == 1
                     and info.st_size == expected['size'], 'Ordinary exact-size release archive required')
                self.identities[name] = file_identity(info)
                self.charge(info.st_size + 1)
                sha, md5, count = hashlib.sha256(), hashlib.md5(), 0
                while True:
                    raw = stream.read(min(1024 * 1024, info.st_size + 1 - count))
                    if not raw:
                        break
                    sha.update(raw); md5.update(raw); count += len(raw)
                    need(count <= info.st_size, 'Archive grew during authentication')
                need(count == info.st_size and expected['checksum'] == 'md5:' + md5.hexdigest(),
                     'Release archive checksum or extent mismatch')
                self.stable(name)
                self.archive_receipts[name] = {'bytes': count, 'sha256': sha.hexdigest(),
                                               'md5': md5.hexdigest()}
                stream.seek(0)
                archive = self.archives[name] = zipfile.ZipFile(stream)
                infos = archive.infolist()
                need(len(infos) <= 10000 and len({i.filename for i in infos}) == len(infos),
                     'Duplicate or excessive archive members')
                for item in infos:
                    p = PurePosixPath(item.filename)
                    need(not p.is_absolute() and '..' not in p.parts and '\\' not in item.filename
                         and '\x00' not in item.filename and not item.flag_bits & 1,
                         'Unsafe or encrypted archive entry')
            # Complete metadata admission precedes every scientific member read.
            for member, expected in self.meta['members'].items():
                info = self.archives[expected['archive']].getinfo(member)
                need(info.file_size == expected['bytes'] and info.compress_size == expected['compressed_bytes']
                     and f'{info.CRC:08x}' == expected['crc32'] and info.compress_type == zipfile.ZIP_DEFLATED
                     and not stat.S_ISLNK(info.external_attr >> 16), 'Original member binding mismatch')
        except BaseException:
            self.close()
            raise

    def charge(self, count):
        need(self.charged + count <= self.read_limit, 'Logical source-read allocation exceeded')
        self.charged += count

    def stable(self, name):
        need(file_identity(os.fstat(self.streams[name].fileno())) == self.identities[name],
             'Source archive changed after authentication')

    def read_member(self, member, *, header_only=False):
        expected = self.meta['members'][member]
        size, archive_name = expected['bytes'], expected['archive']
        need(header_only or size <= self.working_limit // 3, 'Member exceeds declared working allocation')
        self.charge(size + 1)
        self.stable(archive_name)
        digest, count, chunks = hashlib.sha256(), 0, []
        prefix = bytearray()
        with self.archives[archive_name].open(member) as stream:
            while True:
                raw = stream.read(min(1024 * 1024, size + 1 - count))
                if not raw:
                    break
                count += len(raw)
                need(count <= size, 'Expanded member exceeds source extent')
                digest.update(raw)
                if header_only:
                    prefix.extend(raw[:max(0, 8192 - len(prefix))])
                else:
                    chunks.append(raw)
        need(count == size, 'Truncated original member')
        self.stable(archive_name)
        self.member_receipts[member] = {'archive': archive_name, 'bytes': count,
            'sha256': digest.hexdigest(), 'crc32': expected['crc32'], 'full_member_crc_verified': True,
            'array_values_decoded': not header_only}
        return bytes(prefix) if header_only else b''.join(chunks)

    def population_weights(self):
        rows = []
        for session, geometry in self.geometry.items():
            member = f'data_processed/{session}/self_FR_aligned2word.npy'
            raw = self.read_member(member, header_only=True)
            shape, fortran, dtype, offset = npy_header(raw)
            need(len(shape) == 3 and shape[1:] == (geometry['word_rows'], 80)
                 and shape[0] <= 4096, 'Original (neuron, word, 80) population-weight geometry')
            need(offset + math.prod(shape) * dtype.itemsize == self.meta['members'][member]['bytes'],
                 'Weight header does not describe the exact full member extent')
            rows.append({'session': session, 'count': shape[0], 'shape': list(shape),
                         'fortran_order': fortran, 'member': member,
                         'receipt': dict(self.member_receipts[member])})
        return {'schema': 'language-original-population-weights/v1', 'rows': rows,
                'archive_receipts': dict(self.archive_receipts),
                'value_scope': 'authenticated numeric header and complete member bytes; values not decoded',
                'unit_identity_mapping_authenticated': False}

    def load_session(self, session):
        geometry = self.geometry[session]
        names = {'fr': f'data_processed/{session}/fr_matrix.npy',
                 'speaker': f'data_processed/{session}/speaker_matrix.npy',
                 **{f: feature_member(session, f) for f in FAMILIES}}
        total = sum(self.meta['members'][name]['bytes'] for name in names.values())
        need(total * 4 + 64 * 1024**2 <= self.working_limit,
             'Complete session exceeds conservative source array working allocation')
        values = {}
        for key, name in names.items():
            value = decode_numeric(self.read_member(name), self.meta['members'][name],
                                   allow_nan=key in ('sem_syn', 'word2vec'))
            if key in FAMILIES:
                value = value.reshape(geometry['word_rows'], 30, -1)
                need(value.shape[2] == (1 if key in ('sem_syn', 'word2vec', 'syn') else 33),
                     'Original feature axes')
                if key in ('sem_syn', 'word2vec'):
                    need(np.isfinite(value[~np.isnan(value[:, 0, 0])]).all(), 'Nonfinite retained lexical row')
            values[key] = value
        need(values['fr'].shape == (geometry['time_bins'], geometry['units']), 'Original firing-rate geometry')
        need(values['speaker'].ndim == 2 and values['speaker'].shape[0] == geometry['time_bins']
             and np.isin(values['speaker'][:, 0], [0, 1]).all(), 'Source speaker column0 must be binary')
        csv_member = f'transcription/cleaned/{session}.csv'
        timing, qid = parse_words(self.read_member(csv_member), geometry)
        return {'session': session, 'geometry': geometry, **values, 'timing': timing, 'qid': qid,
                'input_receipts': {n: dict(self.member_receipts[n]) for n in (*names.values(), csv_member)}}

    def close(self):
        for archive in self.archives.values():
            archive.close()
        for stream in self.streams.values():
            stream.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
