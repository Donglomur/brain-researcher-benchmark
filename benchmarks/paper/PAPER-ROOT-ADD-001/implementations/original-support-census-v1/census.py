"""Private source-support census; no firing responses, fits or predictions.

This is authentic support preparation, not a metadata-only operation. ZIP
members are traversed completely for SHA/CRC authentication; only speaker bits
and lexical first-PC missingness are retained from their numeric bodies.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import sys
import zipfile

import numpy as np

HERE = Path(__file__).resolve().parent
INPUTS = HERE.parent / 'original-inputs-v1'
INPUT_SOURCE_SHA = '2fb51facfbaaba5df5392d3d5e10779fe3888778ca99595b5244382383d68978'
PREPARATION_SHA = '562f030780252caa93f51f4aac2a8fb766df0654513ca27a9f0f5e74aaee2578'
SUPPORT_BINDINGS_SHA = '71fb5922970691955119cc2b51b5848d942bbc04a7f38ae68861ddc9648e5350'


def need(ok, message):
    if not ok:
        raise ValueError(message)


def pin(raw):
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()


def parse(raw):
    def pairs(rows):
        result = {}
        for key, value in rows:
            need(key not in result, 'Duplicate JSON key')
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda _: need(False, 'Nonfinite JSON constant'))


def load_source():
    raw = (INPUTS / 'SOURCE.json').read_bytes()
    need(pin(raw)['sha256'] == INPUT_SOURCE_SHA, 'Original input source descriptor changed')
    manifest = parse(raw)
    for name, identity in {**manifest['files'], **manifest['dependencies']}.items():
        need(pin((INPUTS / name).read_bytes()) == identity, 'Original source member changed')
    spec = importlib.util.spec_from_file_location('language_support_original_inputs', INPUTS / 'inputs.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def selected_members(meta):
    return [name for s in meta['sessions'] for name in (
        f"transcription/cleaned/{s['id']}.csv",
        f"data_processed/{s['id']}/speaker_matrix.npy",
        f"DNN/{s['id']}/sem_syn/sem_syn_R_embeddings_pca.npy",
        f"DNN/{s['id']}/sem_syn/word2vec_R_embeddings_pca.npy")]


def support_bindings():
    raw = (HERE / 'support-bindings.json').read_bytes()
    need(pin(raw)['sha256'] == SUPPORT_BINDINGS_SHA, 'Frozen selected support byte ranges')
    return parse(raw)


def identity(info):
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns


class ReadBudget:
    def __init__(self, limit):
        need(type(limit) is int and limit > 0, 'Positive read allocation')
        self.limit, self.used = limit, 0

    def read(self, stream, amount):
        need(type(amount) is int and amount >= 0 and amount <= self.limit - self.used,
             'Read allocation exceeded before operation')
        raw = stream.read(amount)
        self.used += len(raw)
        return raw


class PrivateOutput:
    def __init__(self, root, limit):
        need(type(limit) is int and limit > 0, 'Positive output allocation')
        self.root, self.limit, self.used = Path(root).absolute(), limit, 0
        need(not any(p.is_symlink() for p in self.root.parents), 'No output symlink ancestors')
        self.root.mkdir(mode=0o700)

    def write(self, name, raw):
        relative = Path(name)
        need(not relative.is_absolute() and '..' not in relative.parts, 'Relative private product path')
        need(self.used + len(raw) <= self.limit, 'Cumulative output limit before write')
        path = self.root / relative
        need(not any(p.is_symlink() for p in (path, *path.parents)), 'No private output symlink before directory creation')
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        need(not any(p.is_symlink() for p in (path, *path.parents)), 'No private output symlink')
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0), 0o600)
        with os.fdopen(fd, 'wb') as stream:
            os.fchmod(stream.fileno(), 0o600)
            self.used += len(raw)
            stream.write(raw)
        return {'path': name, **pin(raw)}


class ArchiveView:
    """Count every Python-level compressed/archive read, including repeated seeks."""
    def __init__(self, path, size, budget, allowed_ranges):
        self.path = Path(path).absolute()
        need(not any(p.is_symlink() for p in (self.path, *self.path.parents)), 'No archive symlink')
        before = self.path.lstat()
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size == size,
             'Ordinary exact-size source archive')
        need(type(allowed_ranges) is list and len(allowed_ranges) > 0
             and all(type(r) is list and len(r) == 2 and all(type(x) is int for x in r)
                     and 0 <= r[0] < r[1] <= size for r in allowed_ranges)
             and all(a[1] < b[0] for a, b in zip(allowed_ranges, allowed_ranges[1:])),
             'Sorted disjoint exact allowed byte ranges')
        self.allowed_ranges = tuple(tuple(r) for r in allowed_ranges)
        self.stream = os.fdopen(os.open(self.path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0)
                                      | getattr(os, 'O_NONBLOCK', 0)), 'rb', buffering=0)
        self.stamp, self.budget = identity(before), budget
        try:
            self.stable()
        except BaseException:
            self.stream.close()
            raise

    def stable(self):
        need(identity(os.fstat(self.stream.fileno())) == self.stamp
             and identity(self.path.lstat()) == self.stamp, 'Archive changed during support census')

    def read(self, amount=-1):
        if amount < 0:
            amount = self.stamp[2] - self.tell()
        start = self.tell()
        need(amount == 0 or any(lo <= start and start + amount <= hi for lo, hi in self.allowed_ranges),
             'Backing read outside selected support member/metadata ranges')
        return self.budget.read(self.stream, amount)

    def seek(self, *args):
        position = self.stream.seek(*args)
        need(0 <= position <= self.stamp[2], 'Archive seek outside extent')
        return position

    def tell(self):
        return self.stream.tell()

    def seekable(self):
        return True


class SupportReader:
    def __init__(self, paths, preparation, *, archive_read_limit, expanded_limit, metadata=None, ranges=None):
        self.source = load_source()
        self.meta = self.source.bindings() if metadata is None else metadata
        self.ranges = support_bindings() if ranges is None else ranges
        need(set(paths) == {'transcription.zip', 'data_processed.zip', 'DNN.zip'}, 'Exact three source archives')
        need(type(expanded_limit) is int and expanded_limit > 0, 'Positive expanded member allocation')
        self.budget, self.expanded_limit, self.expanded = ReadBudget(archive_read_limit), expanded_limit, 0
        self.receipts, self.views, self.archives = {}, {}, {}
        names = selected_members(self.meta)
        self.allowed = set(names)
        need(len(names) == len(self.allowed), 'Unique complete support member roster')
        need(set(self.ranges['archives']) == set(paths) and set(self.ranges['members']) == self.allowed,
             'Complete exact selected range/member roster')
        self.expected = {}
        for row in preparation['sessions']:
            for name, value in row['input_receipts'].items():
                if name in self.allowed:
                    need(name not in self.expected, 'Duplicate preparation member')
                    self.expected[name] = value
        need(set(self.expected) == self.allowed, 'Every support member has accepted prior full-byte authentication')
        try:
            for name, path in sorted(paths.items()):
                scope = self.ranges['archives'][name]
                need(scope['size'] == self.meta['archives'][name]['size'], 'Frozen support archive extent')
                view = self.views[name] = ArchiveView(path, scope['size'], self.budget, scope['allowed_ranges'])
                archive = self.archives[name] = zipfile.ZipFile(view)
                infos = archive.infolist()
                need(len(infos) <= 10000 and len({i.filename for i in infos}) == len(infos),
                     'Bounded unique ZIP directory')
            for name in names:
                m = self.meta['members'][name]
                info = self.archives[m['archive']].getinfo(name)
                need(info.file_size == m['bytes'] and info.compress_size == m['compressed_bytes']
                     and f'{info.CRC:08x}' == m['crc32'] and info.compress_type == zipfile.ZIP_DEFLATED
                     and not info.flag_bits & 1 and not stat.S_ISLNK(info.external_attr >> 16),
                     'Exact source-support ZIP member metadata')
                previous = self.expected[name]
                frozen = self.ranges['members'][name]
                need(all(frozen[k] == m[k] for k in ('archive', 'bytes', 'compressed_bytes', 'crc32'))
                     and frozen['expected_full_member_sha256'] == previous['sha256']
                     and (frozen['header_offset'] is None or info.header_offset == frozen['header_offset']),
                     'Exact selected member offset and prior full SHA binding')
                need(previous['archive'] == m['archive'] and previous['bytes'] == m['bytes']
                     and previous['crc32'] == m['crc32'] and previous['full_member_crc_verified'] is True,
                     'Support member agrees with accepted preparation')
        except BaseException:
            self.close()
            raise

    def member(self, name):
        need(name in self.allowed and name not in self.receipts, 'Selected support member once only')
        m = self.meta['members'][name]
        need(self.expanded + m['bytes'] + 1 <= self.expanded_limit, 'Expanded read allocation before member')
        self.expanded += m['bytes'] + 1
        self.views[m['archive']].stable()
        with self.archives[m['archive']].open(name) as stream:
            raw = stream.read(m['bytes'] + 1)
        need(len(raw) == m['bytes'] and pin(raw)['sha256'] == self.expected[name]['sha256'],
             'Complete selected member SHA/extent mismatch')
        self.views[m['archive']].stable()
        self.receipts[name] = {**pin(raw), 'archive': m['archive'], 'crc32': m['crc32'],
                              'full_member_traversed': True, 'matched_accepted_preparation': True}
        return raw

    def session(self, geometry):
        s = geometry['id']
        timing, qid = self.source.parse_words(self.member(f'transcription/cleaned/{s}.csv'), geometry)
        name = f'data_processed/{s}/speaker_matrix.npy'
        raw = self.member(name)
        shape, fortran, dtype, offset = self.source.npy_header(raw)
        self.header(name, raw, shape, fortran, dtype, offset)
        a = np.frombuffer(raw, dtype=dtype, offset=offset).reshape(shape, order='F' if fortran else 'C')
        need(a.ndim == 2 and len(a) == geometry['time_bins'] and np.isin(a[:, 0], (0., 1.)).all(),
             'Source binary speaker column zero')
        speaker = a[:, 0].astype(np.uint8)
        keep = {}
        for family in ('sem_syn', 'word2vec'):
            name = self.source.feature_member(s, family)
            raw = self.member(name)
            shape, fortran, dtype, offset = self.source.npy_header(raw)
            self.header(name, raw, shape, fortran, dtype, offset)
            a = np.frombuffer(raw, dtype=dtype, offset=offset).reshape(shape, order='F' if fortran else 'C')
            need(a.size == geometry['word_rows'] * 30, 'Exact lexical word/PC geometry')
            # Mirrors the accepted reshape before indexing; other components are
            # traversed for SHA/CRC but never used as numeric feature operands.
            first = a.reshape(geometry['word_rows'], 30, 1)[:, 0, 0]
            keep[family] = ~np.isnan(first)
            need(keep[family].any(), 'Nonempty lexical support')
        return timing, qid, speaker, keep

    def header(self, name, raw, shape, fortran, dtype, offset):
        m = self.meta['members'][name]
        need(list(shape) == m['shape'] and fortran == m['fortran_order'] and str(dtype) == m['dtype']
             and len(raw) == offset + int(np.prod(shape)) * dtype.itemsize, 'Exact authenticated numeric header')

    def close(self):
        for archive in self.archives.values():
            archive.close()
        for view in self.views.values():
            view.stream.close()


def label_timeline(timing, qid, time_bins):
    need(timing.shape == (len(qid), 2) and len(qid) > 0 and np.isfinite(timing).all()
         and np.isfinite(qid).all() and np.all(qid == np.floor(qid))
         and np.all(np.abs(qid) < 2**53) and np.all(timing >= 0)
         and np.all(timing[:, 1] >= timing[:, 0]) and np.all(timing < (time_bins + 1) / 10)
         and np.all((timing * 10).astype(np.int64) <= time_bins), 'Exact source timing/qid domain')
    result = np.full(time_bins, 99999., dtype=np.float64)
    for (start, end), label in zip((timing * 10).astype(np.int64), qid):
        if label < 99990:
            result[start:end] = label
    return result


def specs():
    rows = [('population', 'base', 'population', range(-20, 20), False, 33),
            ('unit', 'base', 'unit', range(-20, 20), False, 33),
            ('time_shuffle', 'base', 'population', range(-20, 20), True, 33)]
    rows += [(f, 'base', 'population', (-10,), False, 33) for f in
             ('random_token', 'sentence_swap', 'ngram1', 'ngram3', 'ngram5', 'ngram7', 'ngram10')]
    rows += [(f + suffix, 'base' if f == 'syn' else f, 'population', (-3, -2, -1), bool(suffix), 1)
             for f in ('sem_syn', 'word2vec', 'syn') for suffix in ('', '_shuffle')]
    return rows


def array_sha(value):
    a = np.ascontiguousarray(value)
    return hashlib.sha256(a.tobytes()).hexdigest()


def session_census(geometry, timing, qid, speaker, keep, *, response_member_sha256):
    """Prove support equivalence with source-row lineage, never target values.

    Equal signatures are a sufficient (possibly finer than maximal) equivalence
    partition. They require equal full ordered support, qid grouping and response
    lineage. Each held_qid in a class is a separate isolation unit. Feature jobs
    remain distinct; this signature does NOT authorize union-feature learning.
    """
    n = geometry['time_bins']
    need(type(response_member_sha256) is str and len(response_member_sha256) == 64
         and all(c in '0123456789abcdef' for c in response_member_sha256), 'Authenticated source response lineage')
    need(40 < n <= 144111 and 1 <= geometry['units'] <= 82, 'Bounded original census geometry')
    # Source primitive arrays within these dimensions have128-byte v1 headers.
    # Verify this serialization assumption on the executing NumPy, without data.
    for shape in ((1,), (n,), (1, 1), (n, 30), (n, geometry['units'])):
        for dtype in ('<f8', '<i8'):
            header = io.BytesIO()
            np.lib.format.write_array_header_1_0(header, {'shape': shape, 'fortran_order': False, 'descr': dtype})
            need(len(header.getvalue()) == 128, 'Census NPY header cost profile changed')
    need(speaker.shape == (n,) and np.isin(speaker, (0, 1)).all(), 'Exact speaker support')
    need(set(keep) == {'sem_syn', 'word2vec'} and all(a.dtype == bool and a.shape == qid.shape for a in keep.values()),
         'Both exact lexical inclusion masks')
    timelines = {'base': label_timeline(timing, qid, n)}
    timelines.update({k: label_timeline(timing[a], qid[a], n) for k, a in keep.items()})
    permutation = np.random.RandomState(20).permutation(np.arange(n, dtype=np.int64))
    groups, classes, total_jobs, total_requests = [], {}, 0, 0
    costs = {k: 0 for k in ('request_array_payload_bytes', 'raw_prediction_f64_payload_bytes',
                            'request_npy_header_bytes', 'raw_prediction_npy_header_bytes',
                            'request_json_upper_bytes', 'submission_index_upper_bytes',
                            'private_product_array_payload_bytes', 'private_product_upper_bytes')}
    for field, support_family, target, lags, shuffle, layers in specs():
        for lag_index, lag in enumerate(lags):
            labels = timelines[support_family]
            if lag > 0:
                labels = np.concatenate((np.zeros(lag), labels))[:-lag]
            times = np.flatnonzero((speaker == 1) & (labels < 99990))
            labels = labels[times]
            held, counts = np.unique(labels, return_counts=True)
            need(len(held) >= 2, 'Every original job requires at least two source held-qid groups')
            response_rows = times + min(lag, 0)
            padding = response_rows < 0
            response_rows = response_rows.copy()
            if shuffle:
                response_rows[~padding] = permutation[response_rows[~padding]]
            response_rows[padding] = -1
            signature = {'session': geometry['id'], 'source_response_member_sha256': response_member_sha256,
                         'source_transform': 'centered3bin_population_mean' if target == 'population' else 'centered3bin_units',
                         'ordered_time_indices_sha256': array_sha(times.astype('<i8')),
                         'ordered_qid_sha256': array_sha(labels.astype('<f8')),
                         'ordered_response_source_rows_sha256': array_sha(response_rows.astype('<i8')),
                         'zero_padding_sentinel': -1, 'rows': len(times), 'held_qids': len(held)}
            key = pin(encoded(signature))['sha256']
            if key not in classes:
                classes[key] = {'signature': signature, 'held_qids': held.tolist(), 'query_rows': counts.tolist(),
                                'jobs': 0, 'field_lag_groups': []}
            classes[key]['jobs'] += layers
            classes[key]['field_lag_groups'].append([field, lag_index])
            d, k, t = (geometry['units'] if target == 'unit' else 1), len(held), len(times)
            groups.append({'field': field, 'lag_index': lag_index, 'lag_bins': lag, 'layers': layers,
                           'output_columns': d, 'support_class': key, 'rows': t, 'held_qids': k,
                           'source_requests': layers * k})
            total_jobs += layers
            total_requests += layers * k
            # Six arrays: x train/query, y train, row IDs train/query, qid train.
            costs['request_array_payload_bytes'] += layers * (k * t * 248 + (k - 1) * t * (8 * d + 8))
            costs['raw_prediction_f64_payload_bytes'] += layers * t * d * 8
            costs['request_npy_header_bytes'] += layers * k * 6 * 128
            costs['raw_prediction_npy_header_bytes'] += layers * k * 128
            costs['request_json_upper_bytes'] += layers * k * 8192
            costs['submission_index_upper_bytes'] += layers * k * 8192
            private_payload = 16 * t + 16 * t * d + 8 * d
            costs['private_product_array_payload_bytes'] += layers * private_payload
            # Same bridge array reserve plus conservative fold/JSON row metadata.
            costs['private_product_upper_bytes'] += layers * (private_payload + 5 * 65536 + 64 * t + 1024 * k + 65536)
    need(total_jobs == 4209 and len(groups) == 145, 'Complete original source job lattice')
    return {'session': geometry['id'], 'person': geometry['id'].split('_')[0], 'jobs': total_jobs,
            'source_requests': total_requests, 'support_classes': classes, 'field_lag_groups': groups,
            'proven_class_held_units': sum(len(v['held_qids']) for v in classes.values()),
            'costs': costs, 'partition_is_maximal': False, 'feature_jobs_may_be_combined': False}


def compact_rosters(row):
    """Bind repeated held-group rosters without duplicating them in the receipt.

    The private source masks/CSV timing-qid arrays retain the recoverable source
    operands. This compact report is not a runtime request-manifest replacement.
    """
    for value in row['support_classes'].values():
        held = np.asarray(value.pop('held_qids'), dtype='<f8')
        counts = np.asarray(value.pop('query_rows'), dtype='<i8')
        value['held_roster'] = {'count': len(held), 'held_qid_sha256': array_sha(held),
                                'query_counts_sha256': array_sha(counts),
                                'minimum_query_rows': int(counts.min()), 'maximum_query_rows': int(counts.max())}
    return row


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('data-archive', 'dnn-archive', 'transcription-archive', 'preparation', 'output'):
        p.add_argument('--' + name, required=True)
    for name in ('archive-read-limit', 'expanded-limit', 'output-limit'):
        p.add_argument('--' + name, type=int, required=True)
    a = p.parse_args()
    source = load_source()
    # Reuse the stable bounded ordinary reader; no participant inputs are read.
    spec = importlib.util.spec_from_file_location('language_support_bridge', HERE.parent / 'original-prediction-submission-v1/bridge.py')
    bridge = importlib.util.module_from_spec(spec)
    need(pin((HERE.parent / 'original-prediction-submission-v1/bridge.py').read_bytes())['sha256']
         == '57e6b60773bc75825d165c3a1c3f7de15d2e65565cf63cfff567221f81f92ceb', 'Frozen bridge reader')
    spec.loader.exec_module(bridge)
    prep_raw = bridge.read_file(a.preparation, maximum=87379)
    need(pin(prep_raw)['sha256'] == PREPARATION_SHA, 'Exact accepted preparation receipt')
    prep = parse(prep_raw)
    output = PrivateOutput(a.output, a.output_limit)
    reader = SupportReader({'data_processed.zip': a.data_archive, 'DNN.zip': a.dnn_archive,
                            'transcription.zip': a.transcription_archive}, prep,
                           archive_read_limit=a.archive_read_limit, expanded_limit=a.expanded_limit)
    try:
        rows = []
        for g in source.bindings()['sessions']:
            timing, qid, speaker, keep = reader.session(g)
            prior = next(r for r in prep['sessions'] if r['session'] == g['id'])
            fr_sha = prior['input_receipts'][f"data_processed/{g['id']}/fr_matrix.npy"]['sha256']
            row = session_census(g, timing, qid, speaker, keep, response_member_sha256=fr_sha)
            buffer = io.BytesIO()
            np.savez_compressed(buffer, timing=timing, qid=qid, speaker=speaker,
                                sem_syn_keep=keep['sem_syn'], word2vec_keep=keep['word2vec'])
            row['private_support_bits'] = output.write('private-support/' + g['id'] + '.npz', buffer.getvalue())
            rows.append(compact_rosters(row))
        need(len(rows) == 14 and len({r['person'] for r in rows}) == 8
             and sum(r['jobs'] for r in rows) == 58926 and len(reader.receipts) == 56,
             'Complete original14-session/eight-person/58,926-job/56-member support census')
        result = {'schema': 'language-original-source-support-census/v1', 'sessions': rows,
                  'jobs': 58926, 'original_result_arrays': 224,
                  'source_requests': sum(r['source_requests'] for r in rows),
                  'proven_class_held_units': sum(r['proven_class_held_units'] for r in rows),
                  'costs': {k: sum(r['costs'][k] for r in rows) for k in rows[0]['costs']},
                  'selected_member_receipts': reader.receipts,
                  'support_byte_ranges_sha256': SUPPORT_BINDINGS_SHA,
                  'compressed_archive_read_bytes': reader.budget.used,
                  'expanded_member_admission_bytes': reader.expanded,
                  'preparation_receipt': pin(prep_raw), 'whole_archive_checksums_repeated': False,
                  'authentication': 'Every selected complete member SHA/CRC matches the pinned accepted preparation; archive metadata/seek reads are capped and stable.',
                  'request_identity_hashes_computed': False, 'response_payloads_read': 0,
                  'feature_scope': 'Only first-PC missingness from28 lexical members; whole members traversed/authenticated.',
                  'models_fitted': 0, 'predictions': 0, 'scores': 0, 'scientific_qualification': False,
                  'disclosure': 'Operator-private support and source-row joins. Centered smoothing/global PCA remain inherited source exposure; partition does not prove statistical independence or permit union-feature learning.',
                  'cost_scope': 'Unbatched six-array staging and f64 predictions; costs are cumulative logical payload/serialization bounds, not peak disk or measured kernel I/O. No runtime wall estimate is invented.'}
        output.write('CENSUS.json', encoded(result))
    finally:
        reader.close()


if __name__ == '__main__':
    main()
