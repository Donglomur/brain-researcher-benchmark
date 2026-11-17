"""Frozen raw prediction submissions to private original-task scoring.

No candidate Python is imported or executed. This operator adapter authenticates
raw prediction products against privately regenerated original held-qid requests.
It does not provide a protected candidate execution or delivery environment.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import io
import json
import math
import os
from pathlib import Path
import stat

import numpy as np

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / 'original-inference-v1'
SOURCE_SHA = '4a948a5d549a59630b8f879d499ec596ed79fd1dff428601756dccfe2265a4da'
CONDITIONS = ('paper_data', 'paper_data_author_code')
CONTEXT_KEYS = ('session', 'field', 'family', 'layer', 'lag_index', 'lag_bins', 'held_qid')


def need(value, message):
    if not value:
        raise ValueError(message)


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()


def pin(raw):
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def parse(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            need(key not in result, 'Duplicate JSON key')
            result[key] = value
        return result
    def constant(_):
        raise ValueError('Nonfinite JSON constant')
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)


def digest(value):
    return isinstance(value, str) and len(value) == 64 and all(c in '0123456789abcdef' for c in value)


def load_source():
    raw = (SOURCE / 'SOURCE.json').read_bytes()
    need(pin(raw)['sha256'] == SOURCE_SHA, 'Original inference source descriptor changed')
    manifest = parse(raw)
    for name, identity in {**manifest['files'], **manifest['dependencies']}.items():
        need(pin((SOURCE / name).read_bytes()) == identity, 'Original source member/dependency changed')
    spec = importlib.util.spec_from_file_location('language_frozen_reference_inference', SOURCE / 'inference.py')
    inference = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(inference)
    inputs, workflow, panel, figure3 = inference.load_support()
    return inference, inputs, workflow, panel, figure3


def array_identity(value):
    value = np.ascontiguousarray(value)
    need(value.dtype.kind in 'fi' and not value.dtype.hasobject and np.isfinite(value).all(),
         'Finite primitive request array required')
    return {'shape': list(value.shape), 'dtype': value.dtype.str, **pin(value.tobytes())}


def request_identity(train_x, train_y, query_x, context):
    """Bind authoritative arrays/rows before any participant request is delivered."""
    need(set(context) == set(CONTEXT_KEYS) | {'train_time_indices', 'test_time_indices', 'train_qid'},
         'Exact original held-qid request context required')
    need(train_x.ndim == train_y.ndim == query_x.ndim == 2
         and train_x.shape[1] == query_x.shape[1] == 30
         and len(train_x) == len(train_y) == len(context['train_qid']) == len(context['train_time_indices'])
         and len(query_x) == len(context['test_time_indices']) and min(len(train_x), len(query_x)) > 0,
         'Original training/query geometry required')
    need(all(a.dtype == np.float64 for a in (train_x, train_y, query_x))
         and np.all(context['train_qid'] != context['held_qid']), 'Original float64 inputs and held-qid exclusion required')
    for name in ('train_time_indices', 'test_time_indices'):
        a = context[name]
        need(a.ndim == 1 and a.dtype.kind in 'iu' and np.all(a >= 0)
             and (len(a) < 2 or np.all(a[1:] > a[:-1])), 'Strict ordered original row identities required')
    need(not np.intersect1d(context['train_time_indices'], context['test_time_indices']).size,
         'Training and query row identities overlap')
    descriptor = {'schema': 'language-original-held-qid-request/v1',
                  'original_inference_source_sha256': SOURCE_SHA,
                  'context': {k: context[k] for k in CONTEXT_KEYS},
                  'arrays': {key: array_identity(value) for key, value in {
                      'train_x': train_x, 'train_y': train_y, 'query_x': query_x,
                      'train_time_indices': context['train_time_indices'],
                      'query_time_indices': context['test_time_indices'],
                      'train_qid': context['train_qid']}.items()},
                  'prediction_shape': [len(query_x), train_y.shape[1]],
                  'query_targets_in_request': False}
    return descriptor, pin(encoded(descriptor))['sha256']


def export_request(train_x, train_y, query_x, context, output, *, working_limit):
    """Write one fold's permitted inputs; caller must supply a fresh isolated destination.

    Never package other folds together for candidate access: their training
    labels can reveal this fold's held-out responses. This function is not an
    OS sandbox and does not grant a candidate access to the operator process.
    """
    descriptor, request_sha = request_identity(train_x, train_y, query_x, context)
    arrays = {'train_x': train_x, 'train_y': train_y, 'query_x': query_x,
              'train_time_indices': context['train_time_indices'],
              'query_time_indices': context['test_time_indices'], 'train_qid': context['train_qid']}
    extent = sum(a.nbytes for a in arrays.values()) + 65536 * len(arrays)
    need(type(working_limit) is int and 4 * extent <= working_limit,
         'One complete request exceeds working allocation')
    need(output.written + extent <= output.limit, 'Reserve complete request before serialization')
    files = {}
    for key, value in arrays.items():
        buffer = io.BytesIO(); np.save(buffer, value, allow_pickle=False)
        files[key] = output.write(key + '.npy', buffer.getvalue())
    output.json('REQUEST.json', {'schema': 'language-original-held-qid-packet/v1',
                                'request_sha256': request_sha, 'descriptor': descriptor, 'files': files,
                                'scope': 'This fold only; no query targets, other folds, references or private products.'})
    return request_sha


def file_identity(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def ordinary(path, *, maximum):
    path = Path(path).absolute()
    need(not any(p.is_symlink() for p in (path, *path.parents)), 'No submission symlink paths')
    before = path.lstat()
    need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and 0 < before.st_size <= maximum,
         'Bounded ordinary submission file required')
    stream = os.fdopen(os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0)), 'rb')
    try:
        opened = os.fstat(stream.fileno())
        need(stat.S_ISREG(opened.st_mode) and file_identity(opened) == file_identity(before), 'Submission changed before open')
    except BaseException:
        stream.close()
        raise
    return path, stream, before


def read_file(path, *, maximum):
    path, stream, before = ordinary(path, maximum=maximum)
    with stream:
        raw = stream.read(before.st_size + 1)
        need(len(raw) == before.st_size and file_identity(os.fstat(stream.fileno())) == file_identity(before)
             and file_identity(path.lstat()) == file_identity(before), 'Submission changed during bounded read')
    return raw


class Submission:
    """Consume one immutable ordered JSONL index; never execute participant code."""
    def __init__(self, root, *, manifest_sha256, candidate_sha256, condition,
                 max_requests, read_limit, working_limit):
        need(digest(manifest_sha256) and digest(candidate_sha256) and condition in CONDITIONS,
             'Explicit operator-frozen submission/code identity and information condition required')
        need(all(type(n) is int and n > 0 for n in (max_requests, read_limit, working_limit)),
             'Positive finite submission resource declarations required')
        self.root = Path(root).absolute()
        need(self.root.is_dir() and not any(p.is_symlink() for p in (self.root, *self.root.parents)),
             'Ordinary submission root required')
        self.read_limit, self.working_limit, self.charged = read_limit, working_limit, 0
        need(read_limit > 1, 'Submission read allocation exhausted before manifest')
        raw = read_file(self.root / 'SUBMISSION.json', maximum=min(65536, read_limit - 1))
        self.charge(len(raw) + 1)
        need(pin(raw)['sha256'] == manifest_sha256, 'Frozen submission manifest mismatch')
        manifest = parse(raw)
        need(set(manifest) == {'schema', 'candidate_sha256', 'condition', 'requests', 'request_count'}
             and manifest['schema'] == 'language-original-raw-prediction-submission/v1'
             and manifest['candidate_sha256'] == candidate_sha256 and manifest['condition'] == condition,
             'Exact source-native raw prediction submission required')
        need(type(manifest['request_count']) is int and 0 < manifest['request_count'] <= max_requests,
             'Complete frozen request count exceeds allocation')
        index = manifest['requests']
        need(set(index) == {'bytes', 'sha256'} and type(index['bytes']) is int and index['bytes'] > 0
             and digest(index['sha256']) and index['bytes'] <= read_limit - self.charged,
             'Bounded frozen request index required')
        self.manifest, self.manifest_sha256 = manifest, manifest_sha256
        self.path, self.stream, self.before = ordinary(self.root / 'REQUESTS.jsonl', maximum=index['bytes'])
        self.consumed, self.prediction_receipts_digest = 0, hashlib.sha256()
        try:
            need(self.before.st_size == index['bytes'], 'Exact request index size required')
            sha, count = hashlib.sha256(), 0
            self.charge(index['bytes'] + 1)
            while True:
                chunk = self.stream.read(min(65536, index['bytes'] + 1 - count))
                if not chunk:
                    break
                count += len(chunk); sha.update(chunk)
                need(count <= index['bytes'], 'Request index grew')
            need(count == index['bytes'] and sha.hexdigest() == index['sha256'], 'Frozen request index mismatch')
            self.stable()
            self.stream.seek(0)
        except BaseException:
            self.close()
            raise

    def charge(self, size):
        need(self.charged + size <= self.read_limit, 'Submission read allocation exhausted')
        self.charged += size

    def stable(self):
        need(file_identity(os.fstat(self.stream.fileno())) == file_identity(self.before)
             and file_identity(self.path.lstat()) == file_identity(self.before), 'Frozen request index changed')

    def __call__(self, train_x, train_y, query_x, context):
        descriptor, request_sha = request_identity(train_x, train_y, query_x, context)
        need(self.consumed < self.manifest['request_count'], 'Missing source prediction request')
        self.stable()
        available = self.read_limit - self.charged - 1
        need(available > 0, 'Submission read allocation exhausted before request')
        line = self.stream.readline(min(8193, available))
        self.charge(len(line) + 1)
        need(0 < len(line) <= 8192 and line.endswith(b'\n'), 'Bounded complete request-index line required')
        row = parse(line)
        need(set(row) == {'ordinal', 'request_sha256', 'prediction'}
             and type(row['ordinal']) is int and row['ordinal'] == self.consumed
             and row['request_sha256'] == request_sha, 'Source fold/row/input identity or ordering mismatch')
        expected = row['prediction']
        name = f'predictions/{self.consumed:09d}.npy'
        need(set(expected) == {'path', 'bytes', 'sha256'} and expected['path'] == name
             and type(expected['bytes']) is int and 0 < expected['bytes'] <= self.working_limit // 4
             and digest(expected['sha256']), 'Exact bounded raw-prediction product required')
        self.charge(expected['bytes'] + 1)
        raw = read_file(self.root / name, maximum=expected['bytes'])
        need(pin(raw) == {k: expected[k] for k in ('bytes', 'sha256')}, 'Frozen prediction bytes changed')
        stream = io.BytesIO(raw)
        version = np.lib.format.read_magic(stream)
        readers = {(1, 0): np.lib.format.read_array_header_1_0, (2, 0): np.lib.format.read_array_header_2_0}
        need(version in readers, 'Primitive prediction NPY versions only')
        shape, fortran, dtype = readers[version](stream, max_header_size=4096)
        need(list(shape) == descriptor['prediction_shape'] and dtype.kind == 'f' and dtype.itemsize in (4, 8)
             and dtype.fields is None and dtype.subdtype is None and not dtype.hasobject
             and stream.tell() + math.prod(shape) * dtype.itemsize == len(raw), 'Raw prediction geometry/dtype/extent mismatch')
        prediction = np.frombuffer(raw, dtype=dtype, offset=stream.tell()).reshape(shape, order='F' if fortran else 'C')
        need(np.isfinite(prediction).all(), 'Every query prediction must be finite')
        self.prediction_receipts_digest.update(encoded(row))
        self.consumed += 1
        return prediction

    def finish(self):
        self.stable()
        self.charge(1)
        need(self.consumed == self.manifest['request_count'] and self.stream.read(1) == b'',
             'Incomplete or extra prediction requests')
        # scandir streams entries; os.walk would first materialize an unbounded
        # hostile directory listing before any per-entry allocation guard.
        root_names = set()
        with os.scandir(self.root) as entries:
            for entry in entries:
                need(len(root_names) < 3 and entry.name in ('SUBMISSION.json', 'REQUESTS.jsonl', 'predictions'),
                     'Unreferenced submission artifact')
                need(not entry.is_symlink() and (entry.is_dir(follow_symlinks=False) if entry.name == 'predictions'
                     else entry.is_file(follow_symlinks=False) and entry.stat(follow_symlinks=False).st_nlink == 1),
                     'Ordinary submission inventory required')
                root_names.add(entry.name)
        need(root_names == {'SUBMISSION.json', 'REQUESTS.jsonl', 'predictions'}, 'Complete submission root roster required')
        file_count = 0
        with os.scandir(self.root / 'predictions') as entries:
            for entry in entries:
                need(file_count < self.consumed, 'Excess submission file count')
                name = entry.name
                permitted = len(name) == 13 and name.endswith('.npy') and name[:9].isascii() and name[:9].isdigit()
                need(permitted and int(name[:9]) < self.consumed and entry.is_file(follow_symlinks=False)
                     and entry.stat(follow_symlinks=False).st_nlink == 1, 'Unreferenced or nonordinary prediction artifact')
                file_count += 1
        need(file_count == self.consumed, 'Complete unique submitted file roster required')
        return {'manifest_sha256': self.manifest_sha256, 'candidate_sha256': self.manifest['candidate_sha256'],
                'condition': self.manifest['condition'], 'raw_prediction_requests': self.consumed,
                'ordered_prediction_products_sha256': self.prediction_receipts_digest.hexdigest(),
                'logical_submission_read_charge_bytes': self.charged,
                'candidate_code_executed_by_scorer': False, 'candidate_execution_authenticated': False}

    def close(self):
        if getattr(self, 'stream', None) is not None:
            self.stream.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


class PrivateProducts:
    """Retain original row-level predictions/targets for independent private scoring."""
    def __init__(self, output, *, working_limit):
        self.output, self.working_limit, self.jobs = output, working_limit, 0
        self.digest = hashlib.sha256()

    def __call__(self, record):
        arrays = {key: record[key] for key in ('qid', 'time_indices', 'predictions', 'targets', 'correlations')}
        extent = sum(a.nbytes for a in arrays.values()) + 65536 * len(arrays)
        need(4 * extent <= self.working_limit, 'Private observation products exceed working allocation')
        need(self.output.written + extent <= self.output.limit, 'Reserve complete private product before compression')
        buffer = io.BytesIO()
        np.savez_compressed(buffer, **arrays)
        metadata = {k: record[k] for k in ('session', 'field', 'family', 'layer', 'lag_index', 'lag_bins', 'folds')}
        product = self.output.write(f'private-products/{self.jobs:06d}.npz', buffer.getvalue())
        meta = self.output.json(f'private-products/{self.jobs:06d}.json', {**metadata, 'array_product': product,
                                'access': 'operator-private; contains held-out targets, never participant input'})
        self.digest.update(encoded({'arrays': product, 'metadata': meta}))
        self.jobs += 1


def score_complete(reader, submission, output, *, max_requests, working_limit,
                   reference_archive, reference_read_limit, permutation_budget, numpy_version, scipy_version):
    inference, _, workflow, source_panel, figure3 = load_source()
    need(list(reader.geometry) == list(source_panel.SESSION_UNITS), 'Complete original14-session roster required')
    weights = reader.population_weights()
    products = PrivateProducts(output, working_limit=working_limit)
    panel, sessions, requests = {}, [], 0
    for session in source_panel.SESSION_UNITS:
        data = reader.load_session(session)
        fields, receipt = workflow.compute_session(data, submission, max_requests=max_requests - requests, sink=products)
        requests += receipt['sentence_prediction_requests']
        panel[session] = fields
        sessions.append({'session': session, 'computation': receipt})
        for field, filename in source_panel.SOURCE_FILES.items():
            buffer = io.BytesIO(); np.save(buffer, fields[field], allow_pickle=False)
            output.write(f'result_llm/{session}/{filename}', buffer.getvalue())
    need(products.jobs == 58926, 'Complete58,926-job private observation products required')
    submission_receipt = submission.finish()
    need(submission_receipt['raw_prediction_requests'] == requests, 'Complete source request accounting required')
    source_panel.validate_panel(panel)
    reference, reference_receipts = inference.load_author_panel(reference_archive, read_limit=reference_read_limit,
                                                               working_limit=working_limit)
    candidate_summary = inference.complete_summary(panel, weights, permutation_budget=permutation_budget,
                        expected_numpy_version=numpy_version, expected_scipy_version=scipy_version)
    comparison = figure3.compare(panel, reference)
    result = {'schema': 'language-original-prediction-submission-score/v1',
              'source_inference_sha256': SOURCE_SHA, 'submission': submission_receipt,
              'sessions': sessions, 'jobs': products.jobs, 'private_product_trace_sha256': products.digest.hexdigest(),
              'original_input_archive_receipts': reader.archive_receipts,
              'original_input_read_charge_bytes': reader.charged,
              'author_reference': reference_receipts, 'candidate_complete_source_summary': candidate_summary,
              'continuous_comparison': comparison,
              'interpretation': 'Continuous full-panel discrepancies and original14-session paired score deltas; not binary reproduction, independent AI execution or scientific superiority.',
              'protected_execution_qualified': False, 'scientific_qualification': False,
              'independent_AI_reproduction': False, 'candidate_improvement_admitted': False}
    output.json('SCORE.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('data-archive', 'dnn-archive', 'transcription-archive', 'reference-archive', 'submission-root',
                 'submission-sha256', 'candidate-sha256', 'numpy-version', 'scipy-version', 'output'):
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--condition', required=True, choices=CONDITIONS)
    for name in ('max-requests', 'input-read-limit', 'submission-read-limit', 'reference-read-limit',
                 'working-limit', 'output-limit', 'permutation-budget'):
        parser.add_argument('--' + name, required=True, type=int)
    args = parser.parse_args()
    _, inputs, workflow, _, _ = load_source()
    with Submission(args.submission_root, manifest_sha256=args.submission_sha256,
                    candidate_sha256=args.candidate_sha256, condition=args.condition,
                    max_requests=args.max_requests, read_limit=args.submission_read_limit,
                    working_limit=args.working_limit) as submission:
        paths = {'data_processed.zip': args.data_archive, 'DNN.zip': args.dnn_archive,
                 'transcription.zip': args.transcription_archive}
        with inputs.ArchiveInputs(paths, read_limit=args.input_read_limit, working_limit=args.working_limit) as reader:
            output = workflow.ExclusiveOutput(args.output, byte_limit=args.output_limit)
            score_complete(reader, submission, output, max_requests=args.max_requests, working_limit=args.working_limit,
                           reference_archive=args.reference_archive, reference_read_limit=args.reference_read_limit,
                           permutation_budget=args.permutation_budget, numpy_version=args.numpy_version,
                           scipy_version=args.scipy_version)


if __name__ == '__main__':
    main()
