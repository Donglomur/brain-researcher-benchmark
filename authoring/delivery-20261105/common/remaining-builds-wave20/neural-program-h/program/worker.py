"""Trusted sandbox entry for untrusted analysis/method source.

Executed only in the qualified readonly offline image. Models are deserialized
inside that sandbox, never by the host/controller/grader. No actual run here.
"""
import hashlib
import json
import os
from pathlib import Path
import pickle
import random
import sys
import time
import types


def need(ok, message):
    if not ok:
        raise ValueError(message)


def pin(body):
    return {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}


def pairs(values):
    result = {}
    for key, value in values:
        need(key not in result, 'duplicate JSON key')
        result[key] = value
    return result


def parse(raw):
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite JSON')))


def read(path, expected, cap):
    path = Path(path)
    st = path.lstat()
    need(path.is_file() and not path.is_symlink() and st.st_nlink == 1 and st.st_size <= cap,
         'ordinary bounded sandbox input')
    raw = path.read_bytes()
    need(pin(raw) == expected, 'sandbox input body pin')
    return raw


def output(name, body, caps):
    need(name in caps and len(body) <= caps[name], 'bounded fixed output')
    path = Path('/output')/name
    before = path.lstat()
    need(path.is_file() and not path.is_symlink() and before.st_nlink == 1,
         'precreated fixed output inode')
    with path.open('wb') as stream:
        stream.write(body); stream.flush(); os.fsync(stream.fileno())
    after = path.lstat()
    need((before.st_dev, before.st_ino) == (after.st_dev, after.st_ino), 'output inode substitution')


def main():
    # stdout/stderr are final untrusted tool-result byte artifacts. The host
    # retains its own immutable action/transport transcript independently.
    for fd, name in ((1, 'stdout.log'), (2, 'stderr.log')):
        opened = os.open('/output/'+name, os.O_WRONLY | os.O_TRUNC | os.O_NOFOLLOW)
        os.dup2(opened, fd); os.close(opened)
    start = time.monotonic()
    request_raw = Path('/input/REQUEST.json').read_bytes()
    request = parse(request_raw)
    need(request['schema'] == 'neural060_worker_request_v1', 'worker request schema')
    clock = request['clock']
    # Host absolute monotonic values are provenance only: a Docker VM may have
    # a different monotonic epoch. Host separately enforces its original cutoff.
    local_seconds = clock['local_duration_cap']
    need(type(local_seconds) in (int, float) and local_seconds > 0, 'supplementary local time cap')
    def tick():
        need(time.monotonic()-start < local_seconds, 'supplementary local cutoff')
    caps = request['output_caps']
    state = {'schema': 'neural060_worker_work_v1', 'request': pin(request_raw),
             'kind': request['kind'], 'entered': True, 'completed': False,
             'error_type': None, 'original_clock': clock}
    def journal():
        output('WORK.json', json.dumps(state, allow_nan=False, sort_keys=True).encode(), caps)
    journal()
    try:
        tick()
        kind = request['kind']
        need(kind in ('fit', 'infer', 'python'), 'worker phase kind')
        seed = request['seed']
        need(type(seed) is int and 0 <= seed < 2**32, 'fixed numerical seed')
        random.seed(seed)
        import numpy as np
        need(np.__version__ == request['environment']['numpy'], 'qualified NumPy version')
        need(sys.version.split()[0] == request['environment']['python'], 'qualified Python version')
        np.random.seed(seed)
        if kind == 'python':
            source = read('/input/analysis.py', request['source'], 131072)
            # Numeric exploration is genuinely executed here after activation;
            # no callback supplies a fake finished investigation.
            namespace = {'__name__': '__main__', '__file__': '/input/analysis.py'}
            exec(compile(source, '/input/analysis.py', 'exec'), namespace)
            tick()
            state['completed'] = True; journal()
            return
        role = request['role']
        need(role in ('nuisance', 'joint'), 'information role; no shift flag')
        source = read('/trusted/method.py', request['source'], 131072)
        module = types.ModuleType('neural060_candidate_method')
        module.__file__ = '/trusted/method.py'
        # Stable module identity is needed for ordinary sklearn/custom pickle
        # state. This registration exists only inside this disposable sandbox.
        sys.modules[module.__name__] = module
        exec(compile(source, module.__file__, 'exec'), module.__dict__)
        files = request['files']
        def rows(split):
            key = split+'/context.json'
            obj = parse(read('/input/'+key, files[key], request['input_cap']))
            need(obj['schema'] == 'neural060_context_v2' and obj['split'] == split
                 and type(obj['rows']) is list and obj['rows'], 'complete typed context')
            if split == 'test':
                need(all('wheel_speed' not in row for row in obj['rows']), 'no query targets')
            return obj['rows']
        def counts(split, ordered):
            if role == 'nuisance':
                need(split+'/neural.h5' not in files, 'no nuisance neural descriptor')
                return None
            import h5py
            need(h5py.__version__ == request['environment']['h5py'], 'qualified h5py version')
            key = split+'/neural.h5'
            # Body authentication precedes HDF5 interpretation. The host also
            # binds complete all-unit membership independently of this worker.
            read('/input/'+key, files[key], request['input_cap'])
            with h5py.File('/input/'+key, 'r') as stream:
                need(set(stream) == {'case_ids', 'counts'}, 'counts-only HDF5')
                need(all(isinstance(stream.get(n, getlink=True), h5py.HardLink) for n in stream),
                     'ordinary HDF5 datasets only')
                ids = [bytes(x).decode('ascii') for x in stream['case_ids'][()]]
                need(ids == [row['case_id'] for row in ordered], 'ordered HDF5/context case join')
                values = stream['counts'][()]
                need(values.dtype == np.dtype('uint32') and values.ndim == 3
                     and values.shape[0] == len(ordered) and values.shape[1] == 50
                     and values.shape[2] == request['unit_count'], 'all-unit count geometry')
            return values
        recipe = request['recipe']
        if kind == 'fit':
            need(set(files) == {'train/context.json', 'val/context.json'} |
                 ({'train/neural.h5', 'val/neural.h5'} if role == 'joint' else set()),
                 'final fit receives original train/validation only')
            train, val = rows('train'), rows('val')
            train_counts, val_counts = counts('train', train), counts('val', val)
            tick()
            state['method_entered'] = True; journal()
            fitted = module.select_fit(train, val, train_counts, val_counts, recipe, seed)
            tick()
            bundle = {'schema': 'neural060_fitted_state_v1', 'source': request['source'],
                      'role': role, 'recipe': recipe, 'seed': seed, 'state': fitted,
                      'fit_request': pin(request_raw)}
            raw = pickle.dumps(bundle, protocol=5)
            output('model.pkl', raw, caps)
        else:
            need(set(files) == {'test/context.json'} | ({'test/neural.h5'} if role == 'joint' else set()),
                 'prediction-only test view')
            model = read('/model/model.pkl', request['model'], request['model_cap'])
            bundle = pickle.loads(model)
            need(bundle['schema'] == 'neural060_fitted_state_v1' and bundle['source'] == request['source']
                 and bundle['role'] == role and bundle['recipe'] == recipe and bundle['seed'] == seed,
                 'same sealed method/recipe/RNG state')
            query = rows('test'); neural = counts('test', query)
            tick(); state['method_entered'] = True; journal()
            predicted = module.predict(bundle['state'], query, neural, recipe)
            values = np.asarray(predicted)
            need(values.dtype.kind in 'fiu' and values.shape == (len(query), 50)
                 and np.isfinite(values).all(), 'complete finite50 predictions')
            result = {'schema': 'neural060_candidate_predictions_v1',
                      'request': pin(request_raw), 'source': request['source'], 'model': request['model'],
                      'rows': [{'case_id': row['case_id'], 'prediction': v.tolist()}
                               for row, v in zip(query, values.astype(np.float64))]}
            output('PREDICTIONS.json', json.dumps(result, allow_nan=False, separators=(',', ':')).encode(), caps)
        tick(); state['completed'] = True; journal()
    except BaseException as error:
        state['error_type'] = type(error).__name__
        state['error'] = str(error)
        state['completed'] = False
        journal()
        raise


if __name__ == '__main__':
    main()
