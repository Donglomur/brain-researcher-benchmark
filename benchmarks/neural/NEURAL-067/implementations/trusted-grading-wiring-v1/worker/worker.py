"""NEURAL067 trusted preparation/assembly/grade only; never executes candidate code.

Source-only construction. A successful file is not admission: the enclosing host
must observe natural zero exit, exact outputs, source pins and resource absence.
"""
import argparse
import hashlib
import io
import json
import math
import os
from pathlib import Path
import signal
import stat
import struct
import sys
import time
import types

BINDING_PIN = {'bytes': 11286, 'sha256': 'd299251c6c48f0b5d67fe93649736b4a551f51a4bc736c5a05a83260ba6f6fb5'}
ARMS = ('neural', 'clock', 'neural_clock', 'shifted_neural_clock')
CACHE_FORMAT = '<176Hdq'
CACHE_ROW_BYTES = 368
JOURNAL_FORMAT = '<Q7d32s32s32s'
JOURNAL_ROW_BYTES = 160
JOURNAL_HEADER_BYTES = 4096
CAPS = {'train': 60_000_000, 'query': 14_000_000, 'assemble': 8_200_000, 'grade': 1_000_000}
SOURCE_NAMES = ('public/common.py', 'public/array_io.py')


def need(ok, message):
    if not ok:
        raise ValueError(message)


def identity(body):
    return {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def parse(body):
    def pairs(items):
        out = {}
        for key, value in items:
            need(key not in out, 'duplicate JSON member')
            out[key] = value
        return out
    return json.loads(body, object_pairs_hook=pairs,
                      parse_constant=lambda _: need(False, 'nonfinite JSON'))


def ordinary(path):
    p = Path(path).absolute()
    need('..' not in p.parts and not any(q.is_symlink() for q in (p, *p.parents)), 'literal unlinked path')
    return p


def stamp(s):
    return s.st_dev, s.st_ino, s.st_mode, s.st_nlink, s.st_size, s.st_mtime_ns, s.st_ctime_ns


def capture(path, cap, expected=None):
    p = ordinary(path)
    fd = os.open(p, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and 0 < before.st_size <= cap,
             'bounded single-link regular file')
        if expected is not None:
            need(before.st_size == expected['bytes'], 'pre-read exact extent')
        with os.fdopen(fd, 'rb', closefd=False) as f:
            body = f.read(cap + 1)
        need(len(body) == before.st_size and stamp(before) == stamp(os.fstat(fd)) == stamp(p.lstat()),
             'same-open whole-file identity')
        if expected is not None:
            need(identity(body) == {k: expected[k] for k in ('bytes', 'sha256')}, 'exact captured pin')
        return body
    finally:
        os.close(fd)


def sync(directory):
    fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def load_source(body, name, path):
    module = types.ModuleType(name)
    module.__file__ = str(path)
    sys.modules[name] = module
    exec(compile(body, str(path), 'exec'), module.__dict__)
    return module


def source_bundle(package, binding, mode):
    # Public source only. Private evidence and target bodies stay lazy.
    bodies = {name: capture(package / name, 20_000, binding['files'][name]) for name in SOURCE_NAMES}
    if mode == 'grade':
        root = Path(__file__).parent / 'grading'
        for name, expected in binding['grading_sources'].items():
            bodies['grading/' + name] = capture(root / name, 20_000, expected)
    return bodies


def numerical_modules(package, bodies):
    common = load_source(bodies['public/common.py'], 'common', package / 'public/common.py')
    arrays = load_source(bodies['public/array_io.py'], 'array_io', package / 'public/array_io.py')
    import numpy as np
    scorer = None
    if 'private/scorer.py' in bodies:
        scorer = load_source(bodies['private/scorer.py'], 'neural067_frozen_scorer', package / 'private/scorer.py')
    return np, common, arrays, scorer


class CappedBuffer(io.BytesIO):
    def __init__(self, cap):
        super().__init__()
        self.cap = cap

    def write(self, body):
        need(self.tell() + len(body) <= self.cap, 'preventive serialization cap')
        return super().write(body)


class Output:
    def __init__(self, root, cap, end):
        self.root = ordinary(root)
        need(self.root.is_dir() and not any(self.root.iterdir()), 'fresh empty owned output mount')
        self.cap, self.end, self.used, self.rows = cap, end, 0, []
        self.data = self.root / 'data'
        self.data.mkdir(mode=0o755)
        self.data.chmod(0o755)  # Candidate UID65534 must traverse even under a restrictive image umask.
        sync(self.root)

    def tick(self):
        need(time.monotonic() < self.end, 'worker absolute deadline')

    def put(self, name, body, receipt=False):
        self.tick()
        need(type(body) is bytes and 0 < len(body) <= self.cap - self.used, 'preventive full-output cap')
        need(type(name) is str and Path(name).name == name and name not in ('', '.', '..'), 'flat output name')
        root = self.root if receipt else self.data
        final = root / name
        pending = root / ('.' + name + '.pending')
        self.used += len(body)  # Never refunded if publication fails.
        fd = os.open(pending, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        try:
            with os.fdopen(fd, 'wb', closefd=False) as f:
                need(f.write(body) == len(body), 'complete output write')
                f.flush()
                os.fchmod(fd, 0o444)
                os.fsync(fd)
        finally:
            os.close(fd)
        self.tick()
        os.link(pending, final, follow_symlinks=False)
        pending.unlink()
        sync(root)
        self.tick()
        pin = identity(body)
        if not receipt:
            self.rows.append({'file': name, **pin})
        return pin

    def npz(self, name, np, fields):
        # np.savez writes an uncompressed primitive archive; cap applies during
        # serialization as well as before its eventual filesystem publication.
        b = CappedBuffer(min(2_000_000 if name.endswith('__prediction.npz') else self.cap,
                             self.cap - self.used))
        np.savez(b, **fields)
        return self.put(name, b.getvalue())


def fields_for_arm(arm):
    need(arm in ARMS, 'one exact arm')
    fields = ['velocity', 'eval_mask']
    if arm != 'clock':
        fields.append('spikes')
    if arm != 'neural':
        fields.extend(('time_s', 'trial'))
    return fields


def input_arrays(np, io_module, raw, rows):
    x = io_module.arrays(raw, ('spikes', 'time_s', 'trial'), 40_000_000)
    need(x['spikes'].shape == (rows, 176) and x['spikes'].dtype == np.dtype('uint16')
         and int(x['spikes'].max(initial=0)) <= 255, 'exact prepared counts')
    need(x['time_s'].shape == (rows,) and x['time_s'].dtype == np.dtype('float64')
         and np.isfinite(x['time_s']).all() and np.all(np.diff(x['time_s']) > 0), 'finite original clock')
    need(x['trial'].shape == (rows,) and x['trial'].dtype == np.dtype('int64')
         and np.all(np.diff(x['trial']) >= 0), 'exact monotonic integer trial identity')
    return x


def target_arrays(np, io_module, raw, rows):
    y = io_module.arrays(raw, ('velocity', 'eval_mask'), 40_000_000)
    need(y['velocity'].shape == (rows, 7) and y['velocity'].dtype == np.dtype('float64')
         and np.isfinite(y['velocity']).all(), 'exact native target geometry')
    need(y['eval_mask'].shape == (rows,) and y['eval_mask'].dtype == np.dtype('uint8')
         and np.all((y['eval_mask'] == 0) | (y['eval_mask'] == 1)), 'exact training mask')
    return y


def training_fields(np, x, y, arm):
    """Expose full original rows; shift before any later candidate filtering."""
    fields_for_arm(arm)
    result = {'velocity': y['velocity'], 'eval_mask': y['eval_mask']}
    if arm != 'clock':
        result['spikes'] = (np.roll(x['spikes'], len(x['spikes']) // 2, axis=0)
                            if arm == 'shifted_neural_clock' else x['spikes'])
    if arm != 'neural':
        result.update(time_s=x['time_s'], trial=x['trial'])
    return result


def prepare_train(np, io_module, design, captured, arm, output):
    entries = []
    for row in design['train']:
        output.tick()
        run, n = row['run'], row['n_rows']
        x = input_arrays(np, io_module, captured[f'private/data/{run}/input.npz'], n)
        y = target_arrays(np, io_module, captured[f'private/data/{run}/target.npz'], n)
        file = run + '.npz'
        pin = output.npz(file, np, training_fields(np, x, y, arm))
        entries.append({'run': run, 'n_rows': n, 'file': file, **pin})
    descriptor = {'schema': 'neural067_training_view_v1', 'arm': arm, 'runs': entries,
                  'fields': fields_for_arm(arm), 'rows': sum(r['n_rows'] for r in entries),
                  'source_design_sha256': hashlib.sha256(canonical(design)).hexdigest(),
                  'shift_applied': arm == 'shifted_neural_clock',
                  'shift_rule': 'floor(full_run_rows/2) before filtering; labels/clocks/mask unchanged',
                  'query_fields_or_lengths': False}
    output.put('TRAIN.json', canonical(descriptor))
    return {'training_runs': len(entries), 'arm': arm, 'training_rows': descriptor['rows']}


def encode_cache(np, x):
    n = len(x['time_s'])
    dtype = np.dtype([('spikes', '<u2', (176,)), ('time_s', '<f8'), ('trial', '<i8')], align=False)
    need(dtype.itemsize == CACHE_ROW_BYTES, 'cache fixed extent')
    out = np.empty(n, dtype=dtype)
    for key in ('spikes', 'time_s', 'trial'):
        out[key] = x[key]
    return out.tobytes(order='C')


def prepare_query(np, io_module, design, captured, output):
    entries = []
    for row in design['query']:
        output.tick()
        run, n = row['run'], row['n_rows']
        x = input_arrays(np, io_module, captured[f'private/data/{run}/input.npz'], n)
        raw = encode_cache(np, x)
        need(len(raw) == n * CACHE_ROW_BYTES, 'complete cache rows')
        pin = output.put(run + '.bin', raw)
        entries.append({'run': run, 'n_rows': n, 'file': run + '.bin', 'input_pin': row['input'], **pin})
    output.put('CACHE.json', canonical({'schema': 'neural067_private_query_cache_v1',
        'runs': entries, 'rows': sum(r['n_rows'] for r in entries), 'encoding': CACHE_FORMAT,
        'row_bytes': CACHE_ROW_BYTES, 'source_design_sha256': hashlib.sha256(canonical(design)).hexdigest(),
        'clock_rule': 'time_s minus first/current contiguous TrialNum segment start; no duration normalization',
        'candidate_mount_allowed': False, 'query_target_reads': 0}))
    return {'query_runs': len(entries), 'query_rows': sum(r['n_rows'] for r in entries), 'query_target_reads': 0}


def journal_predictions(np, raw, row, arm):
    n = row['n_rows']
    need(len(raw) == JOURNAL_HEADER_BYTES + n * JOURNAL_ROW_BYTES, 'complete journal extent')
    head, sep, tail = raw[:JOURNAL_HEADER_BYTES].partition(b'\x00')
    need(sep and not any(tail) and head.endswith(b'\n'), 'bounded padded canonical header')
    header = parse(head)
    need(set(header) == {'schema', 'run', 'arm', 'rows', 'encoding', 'input', 'record_bytes', 'header_bytes'}
         and header == {'schema': 'neural067_action_journal_v1', 'run': row['run'], 'arm': arm,
                        'rows': n, 'encoding': JOURNAL_FORMAT, 'input': row['input'],
                        'record_bytes': JOURNAL_ROW_BYTES, 'header_bytes': JOURNAL_HEADER_BYTES}, 'exact journal identity')
    prediction = np.empty((n, 7), dtype=np.float64)
    previous = bytes(32)
    for ordinal in range(n):
        record = raw[JOURNAL_HEADER_BYTES + ordinal * JOURNAL_ROW_BYTES:
                     JOURNAL_HEADER_BYTES + (ordinal + 1) * JOURNAL_ROW_BYTES]
        values = struct.unpack(JOURNAL_FORMAT, record)
        need(values[0] == ordinal and all(math.isfinite(v) for v in values[1:8]), 'ordered finite committed vector')
        need(values[9] == previous and values[10] == hashlib.sha256(record[:128]).digest(), 'journal chain')
        previous = values[10]
        prediction[ordinal] = values[1:8]
    return prediction, previous.hex()


def assemble(np, common, design, descriptors, journals, output):
    expected = [(r['run'], a) for r in design['query'] for a in ARMS]
    need([(x['run'], x['arm']) for x in descriptors] == expected, 'exact ordered 56 journals')
    names = {r['run'] + '__' + arm + '.bin' for r in design['query'] for arm in ARMS}
    need({p.name for p in ordinary(journals).iterdir()} == names, 'no extra journal paths')
    captured = {}
    for desc in descriptors:
        need(set(desc) == {'run', 'arm', 'file', 'bytes', 'sha256', 'final_chain'}, 'exact journal descriptor')
        name = desc['run'] + '__' + desc['arm'] + '.bin'
        need(desc['file'] == name, 'exact journal path')
        captured[(desc['run'], desc['arm'])] = capture(journals / name, 1_000_000, desc)
    entries = []
    for row in design['query']:
        for arm in ARMS:
            output.tick()
            index = expected.index((row['run'], arm))
            prediction, chain = journal_predictions(np, captured[(row['run'], arm)], row, arm)
            need(chain == descriptors[index]['final_chain'], 'closed journal final chain')
            file = row['run'] + '__' + arm + '.npz'
            b = CappedBuffer(2_000_000)
            np.savez(b, prediction=prediction)
            pin = output.put(file, b.getvalue())
            entries.append({'run': row['run'], 'arm': arm, 'file': file, **pin})
    output.put('predictions.json', common.canonical({'schema': 'neural067_predictions_v1',
               'design_sha256': common.digest(design), 'entries': entries}))
    return {'blocks': len(entries), 'rows_per_arm': sum(r['n_rows'] for r in design['query']),
            'causal_claim_requires_host_journals_and_natural_closure': True}


def grade(package, design, binding, journals, descriptors, output, bodies):
    expected = [(r['run'], a) for r in design['query'] for a in ARMS]
    need(type(descriptors) is list and len(descriptors) == 56 and
         [(x.get('run'), x.get('arm')) for x in descriptors] == expected, 'exact ordered 56 journals')
    names = {r + '__' + a + '.bin' for r, a in expected}
    need({p.name for p in ordinary(journals).iterdir()} == names, 'exact closed journal tree')
    # The unchanged bridge checks every descriptor, body, row and chain before
    # the unchanged scorer admits all56 blocks and the lazy target callback runs.
    pins = {x['file']: dict(x) for x in descriptors}
    def load_journal(name):
        output.tick()
        need(name in names, 'declared journal name')
        return capture(journals / name, 1_000_000, pins[name])
    root = Path(__file__).parent / 'grading'
    name = 'original-target-callback-v1/target_callback.py'
    callback = load_source(bodies['grading/' + name], 'neural067_trusted_target_callback', root / name)
    evidence = {'design': package / 'public/design.json',
                'private_bindings': package / 'private/PRIVATE_BINDINGS.json',
                **{n: Path('/grading-evidence') / (n + '.json') for n in binding['grading_evidence']}}
    result = callback.grade_journals(descriptors, load_journal,
        {r['run']: dict(r['input']) for r in design['query']}, package / 'private/data', evidence,
        scorer_path=root / 'session-evaluator-v1/scorer.py',
        bridge_path=root / 'journal-session-bridge-v1/bridge.py')
    need(result['schema'] == 'neural067_session_grade_v1' and
         result['contract_sha256'] == binding['trusted_grading']['contract_sha256'] and
         result['causal_program_execution_verified'] is False, 'unchanged current score contract')
    output.put('score.json', canonical(result))
    return {'status': 'scored_current_session_contract', 'scientific_score_computed': True,
            'scientific_qualification': False, 'causal_program_execution_verified': False,
            'contract_sha256': result['contract_sha256'], 'journal_blocks': 56}


def required_files(design, mode):
    result = set(SOURCE_NAMES) | {'public/design.json'}
    if mode == 'train':
        result |= {f'private/data/{r["run"]}/{name}.npz' for r in design['train'] for name in ('input', 'target')}
    elif mode == 'query':
        result |= {f'private/data/{r["run"]}/input.npz' for r in design['query']}
    elif mode == 'grade':
        result |= {'private/PRIVATE_BINDINGS.json', 'private/data/PREPARATION.json'}
        result |= {f'private/data/{r["run"]}/target.npz' for r in design['query']}
    return result


def execute(invocation_raw, package, output_root, journals=None, submission=None):
    inv = parse(invocation_raw)
    need(inv.get('schema') == 'neural067_worker_invocation_v1' and inv.get('mode') in CAPS, 'exact worker invocation')
    mode = inv['mode']
    extra = {'arm'} if mode == 'train' else {'journals'} if mode == 'assemble' else {'journals', 'grading_evidence'} if mode == 'grade' else set()
    need(set(inv) == {'schema', 'mode', 'design', 'files', 'worker_source'} | extra, 'exact invocation keys')
    own_body = capture(Path(__file__), 100_000, inv['worker_source'])
    binding = parse(capture(Path(__file__).with_name('BINDING.json'), 20_000, BINDING_PIN))
    need(inv['design'] == binding['files']['public/design.json'], 'selected design pin')
    package = ordinary(package)
    design_body = capture(package / 'public/design.json', 10_000, binding['files']['public/design.json'])
    design = parse(design_body)
    need(set(inv['files']) == required_files(design, mode), 'exact mode-specific package allowlist')
    need(all(inv['files'][n] == binding['files'][n] for n in inv['files']), 'selected source/data pins')
    if mode == 'grade':
        need(inv['grading_evidence'] == binding['grading_evidence'], 'fixed private evidence pins')
    bodies = source_bundle(package, binding, mode)
    captured = {}
    if mode in ('train', 'query'):
        for name in sorted(required_files(design, mode) - set(SOURCE_NAMES) - {'public/design.json'}):
            captured[name] = capture(package / name, 8_000_000, binding['files'][name])
    np, common, io_module, scorer = numerical_modules(package, bodies)
    design = common.validate_design(design)
    need(sum(x['n_rows'] for x in design['train']) == 135991 and sum(x['n_rows'] for x in design['query']) == 34490,
         'complete frozen row support')
    need(sys.version_info[:3] == (3, 12, 8) and np.__version__ == '2.2.6', 'declared existing-image software')
    need(all(os.environ.get(k) == '1' for k in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS',
         'NUMEXPR_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS', 'BLIS_NUM_THREADS', 'NUMBA_NUM_THREADS', 'OMP_THREAD_LIMIT')),
         'all numerical thread overrides')
    end = time.monotonic() + 110
    output = Output(output_root, CAPS[mode], end)
    if mode == 'train':
        result = prepare_train(np, io_module, design, captured, inv['arm'], output)
    elif mode == 'query':
        result = prepare_query(np, io_module, design, captured, output)
    elif mode == 'assemble':
        need(journals is not None, 'explicit read-only journal mount')
        result = assemble(np, common, design, inv['journals'], ordinary(journals), output)
    else:
        need(journals is not None and submission is None, 'explicit read-only closed journal mount')
        result = grade(package, design, binding, ordinary(journals), inv['journals'], output, bodies)
    receipt = {'schema': 'neural067_worker_completion_v1', 'mode': mode,
               'invocation': identity(invocation_raw), 'worker_source': identity(own_body),
               'package_files': inv['files'], 'files': {'data/' + r['file']: {k: r[k] for k in ('bytes', 'sha256')} for r in output.rows}, 'result': result,
               'write_bytes_before_receipt': output.used, 'requires_external_natural_exit': True,
               'runtime_qualified': False, 'scientific_qualification': False}
    output.put('WORKER.json', canonical(receipt), receipt=True)
    output.tick()
    return receipt


def main():
    started = time.monotonic()
    def expire(*_):
        raise TimeoutError('worker whole stop')
    for sig in (signal.SIGALRM, signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, expire)
    signal.setitimer(signal.ITIMER_REAL, 115)
    rc = 2
    try:
        p = argparse.ArgumentParser()
        p.add_argument('--invocation', type=Path, required=True)
        p.add_argument('--invocation-sha256', required=True)
        p.add_argument('--package', type=Path, required=True)
        p.add_argument('--output', type=Path, required=True)
        p.add_argument('--journals', type=Path)
        p.add_argument('--submission', type=Path)
        a = p.parse_args()
        body = capture(a.invocation, 100_000)
        need(hashlib.sha256(body).hexdigest() == a.invocation_sha256, 'exact invocation hash')
        result = execute(body, a.package, a.output, a.journals, a.submission)
        print(json.dumps({'status': 'complete', 'mode': result['mode']}), flush=True)
        need(time.monotonic() < started + 115, 'whole worker publication stop')
        rc = 0
    except BaseException:
        # Partial outputs are preserved. A surviving receipt is never admission
        # without externally observed natural zero exit and source/output joins.
        rc = 2
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
    return rc if time.monotonic() < started + 115 else 2


if __name__ == '__main__':
    raise SystemExit(main())
