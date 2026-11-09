"""Fixed candidate sandbox entry. Only supervised namespace execution is selected.

This worker has no provider credentials, native/reference outputs, original
metadata or held EEG mounts. The host supervisor independently observes it.
"""
import argparse
import hashlib
import importlib.util
import json
import os
import stat
import sys
import math


def require(ok, message):
    if not ok:
        raise ValueError(message)


def write_new(name, raw):
    require('/' not in name and name not in ('', '.', '..'), 'one output leaf')
    fd = os.open('/output/' + name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o400)
    first = None
    try:
        view = memoryview(raw)
        while view:
            n = os.write(fd, view); require(n > 0, 'complete output write'); view = view[n:]
        os.fsync(fd)
    except BaseException as error:
        first = error; raise
    finally:
        try:
            os.close(fd)
        except BaseException as error:
            if first is None:
                raise
            first.add_note('output close failed: ' + type(error).__name__)
    return {'path': name, 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def bounded_result(value, maximum):
    # Candidate-owned objects already exist. Before serializer allocations,
    # bound the exact plain graph and conservative escaped-string extent.
    stack = [(value, 0)]; nodes = 0; upper = 0; seen = set()
    while stack:
        item, depth = stack.pop(); nodes += 1
        require(nodes <= maximum and depth <= 64, 'bounded plain result graph')
        if type(item) in (dict, list, tuple):
            require(id(item) not in seen, 'acyclic nonaliased plain result graph'); seen.add(id(item))
            upper += 2 + len(item)
            if type(item) is dict:
                require(all(type(k) is str for k in item), 'plain string result keys')
                stack.extend((part, depth + 1) for pair in item.items() for part in pair)
            else:
                stack.extend((part, depth + 1) for part in item)
        elif type(item) is str:
            upper += 2 + 12 * len(item)
        elif type(item) is int:
            require(item.bit_length() <= 4096, 'bounded integer serialization'); upper += 1235
        elif type(item) is float:
            require(math.isfinite(item), 'finite result metadata'); upper += 32
        elif item is None or type(item) is bool:
            upper += 5
        else:
            raise ValueError('plain source-generated JSON types only')
        require(upper <= maximum and len(stack) <= maximum, 'preventive conservative JSON capacity')
    chunks = []; total = 0
    for fragment in json.JSONEncoder(sort_keys=True, separators=(',', ':'), allow_nan=False).iterencode(value):
        part = fragment.encode(); total += len(part)
        require(total <= maximum, 'complete result extent'); chunks.append(part)
    return b''.join(chunks)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--max-request-bytes', type=int, required=True)
    parser.add_argument('--max-result-bytes', type=int, required=True)
    parser.add_argument('--max-validation-bytes', type=int, required=True)
    args = parser.parse_args()
    require(min(args.max_request_bytes, args.max_result_bytes, args.max_validation_bytes) > 0, 'explicit selected extents')
    require(args.max_validation_bytes >= 4 * args.max_result_bytes + 2 * args.max_request_bytes,
            'selected metadata encoding/copy allocation before generated code')
    with open('/request/request.json', 'rb') as source:
        raw = source.read(args.max_request_bytes + 1)
    require(len(raw) <= args.max_request_bytes, 'bounded complete request')
    request = json.loads(raw)
    require(request.get('schema') == 'n079_generated_request_v1' and request.get('phase') in ('training', 'query', 'report', 'inspect'), 'fixed worker phase')
    if request['phase'] == 'query':
        require(args.max_result_bytes >= 6 * 127 * 1800 * 8 and args.max_validation_bytes >= 6 * 127 * 1800 * 25,
                'full query output and validation allocation before generated code')
    # The immutable runtime/environment and physical isolation, not Python
    # language restrictions, enforce the candidate's allowed information set.
    spec = importlib.util.spec_from_file_location('candidate_method', '/program/method.py')
    method = importlib.util.module_from_spec(spec); sys.modules[spec.name] = method; spec.loader.exec_module(method)
    require(callable(getattr(method, 'run', None)), 'source-sealed run(request) interface')
    result = method.run(request)
    files = []
    if request['phase'] == 'query':
        import numpy as np
        require(isinstance(result, np.ndarray) and result.shape == (6, 127, 1800) and result.dtype in (np.float32, np.float64),
                'all six people/full native target grid')
        require(np.isfinite(result).all(), 'finite complete query prediction')
        files.append(write_new('prediction.f64', result.astype('<f8').tobytes(order='C')))
        payload = {'prediction': files[0], 'shape': [6, 127, 1800], 'dtype': '<f8'}
    else:
        require(type(result) is dict, 'typed source-generated result')
        payload = result
    encoded = bounded_result({'schema': 'n079_generated_result_v1', 'phase': request['phase'],
        'request_pin': {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}, 'payload': payload},
        args.max_result_bytes)
    require(len(encoded) <= args.max_result_bytes, 'complete result-index JSON extent')
    write_new('RESULT_INDEX.json', encoded)
    fd = os.open('/output', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    first = None
    try:
        os.fsync(fd)
    except BaseException as error:
        first = error; raise
    finally:
        try:
            os.close(fd)
        except BaseException as error:
            if first is None:
                raise
            first.add_note('output directory close failed: ' + type(error).__name__)


if __name__ == '__main__':
    main()
