"""Source-bound finite-grid VALID co-bps gain selection.

The original evaluator owns likelihood, masking and null-model semantics.
Selection on VALID is development calibration, not held-out improvement.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import re
import stat
import types

GAIN_GRID = ((1, 1), (8, 9), (9, 8), (4, 5), (5, 4), (2, 3), (3, 2), (1, 2), (2, 1))
EVALUATOR_PIN = {'bytes': 18292, 'sha256': '05f49d3cdf7720ae68e0fb76113a9e450e9df3813c6c6837689f23a9be278476'}
PRODUCTION_SHAPE = (574, 35, 45)
META_CAP = 128 * 1024
KERNEL_FILES = {'gain_core.py', 'gain_selector.py', 'gain_transform.py', 'METHOD.json'}
METHOD_PIN = {'bytes': 3001, 'sha256': '5c10c138ccfc86fd43fd2eb8f681ce1aaf3c51235335e17b31a055b5efa647f4'}


def need(condition, message):
    if not condition:
        raise ValueError(message)


def pin(raw):
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def absolute(value):
    need(type(value) is str and not any(c in value for c in ('\0', '\n', '\r')),
         'unambiguous absolute metadata/source path')
    path = Path(value)
    need(path.is_absolute() and '..' not in path.parts and str(path) == value,
         'canonical absolute metadata/source path')
    return path


def validate_pin(value):
    need(type(value) is dict and set(value) == {'bytes', 'sha256'}
         and type(value['bytes']) is int and 0 < value['bytes'] <= META_CAP
         and type(value['sha256']) is str and re.fullmatch('[0-9a-f]{64}', value['sha256']),
         'bounded exact source/metadata pin')
    return value


def descriptor(value):
    need(type(value) is dict and set(value) == {'path', 'bytes', 'sha256'}, 'exact source/metadata descriptor')
    absolute(value['path'])
    validate_pin({k: value[k] for k in ('bytes', 'sha256')})
    return value


def signature(st):
    return (st.st_dev, st.st_ino, st.st_mode, st.st_nlink, st.st_size,
            st.st_mtime_ns, st.st_ctime_ns)


def body(value):
    path = absolute(str(value))
    need(not any(p.is_symlink() for p in (path, *path.parents)), 'no source/metadata path symlink')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        before = os.fstat(stream.fileno())
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
             and 0 < before.st_size <= META_CAP, 'bounded ordinary single-link source/metadata')
        raw = stream.read(META_CAP + 1)
        after = os.fstat(stream.fileno())
    need(len(raw) == before.st_size
         and signature(before) == signature(after) == signature(path.lstat()),
         'stable complete source/metadata authentication')
    return raw


def decode(raw):
    def unique(rows):
        value = {}
        for key, item in rows:
            need(key not in value, 'duplicate JSON field')
            value[key] = item
        return value
    return json.loads(raw, object_pairs_hook=unique,
                      parse_constant=lambda _: need(False, 'finite JSON metadata'))


def checked(value):
    descriptor(value)
    raw = body(value['path'])
    need(pin(raw) == {k: value[k] for k in ('bytes', 'sha256')}, 'selected exact metadata/source bytes')
    return raw


def load_core(source_descriptor):
    """Authenticate the adjacent finite source closure before loading its core."""
    manifest = decode(checked(source_descriptor))
    root = absolute(source_descriptor['path']).parent
    need(Path(source_descriptor['path']).name == 'SOURCE.json'
         and root == Path(__file__).absolute().parent, 'selected adjacent kernel source manifest')
    need(type(manifest) is dict and set(manifest) == {'schema', 'files'}
         and manifest['schema'] == 'smc_gain_kernel_source_v1'
         and type(manifest['files']) is dict and set(manifest['files']) == KERNEL_FILES,
         'exact four-leaf gain kernel manifest')
    need(manifest['files']['METHOD.json'] == METHOD_PIN, 'unchanged predeclared finite gain method')
    admitted = {}
    for name in sorted(KERNEL_FILES):
        expected = validate_pin(manifest['files'][name])
        raw = body(root / name)
        need(pin(raw) == expected, 'exact complete selected kernel source body')
        admitted[name] = raw
    need(Path(__file__).name == 'gain_selector.py', 'fixed selector source filename')
    module = types.ModuleType('_smc_gain_selector_core_' + source_descriptor['sha256'])
    module.__file__ = str(root / 'gain_core.py')
    exec(compile(admitted['gain_core.py'], module.__file__, 'exec'), module.__dict__)
    return module


def load_original_evaluator(evaluator_path):
    """Fixed canonical source; the caller cannot supply a scoring callback."""
    raw = body(evaluator_path)
    need(pin(raw) == EVALUATOR_PIN, 'unchanged original canonical evaluator source')
    expected = {'numpy': '1.26.3', 'scipy': '1.12.0', 'scikit-learn': '1.5.0', 'h5py': '3.10.0'}
    need({name: importlib.metadata.version(name) for name in expected} == expected,
         'selected scientific dependency versions')
    module = types.ModuleType('_smc_gain_original_evaluator')
    module.__file__ = str(absolute(str(evaluator_path)))
    exec(compile(raw, module.__file__, 'exec'), module.__dict__)
    return module


def choose_best(rows):
    """Exact maximum; the first entry wins an exact tie, with no tolerance."""
    need(type(rows) is list and len(rows) == len(GAIN_GRID), 'complete ordered nine-score grid')
    for index, (row, gain) in enumerate(zip(rows, GAIN_GRID)):
        need(type(row) is dict and set(row) == {'index', 'gain', 'executed_gain', 'co_bps'}
             and type(row['index']) is int and row['index'] == index
             and type(row['gain']) is list and len(row['gain']) == 2
             and all(type(x) is int for x in row['gain']) and row['gain'] == list(gain),
             'exact grid order and rational identity')
        need(type(row['co_bps']) is float and math.isfinite(row['co_bps']),
             'every canonical co-bps score must be finite')
    best = rows[0]
    for row in rows[1:]:
        if row['co_bps'] > best['co_bps']:
            best = row
    return dict(best)


def _score_grid(predicted_rates, target, evaluator, transform):
    """Internal numerical seam; production supplies authenticated source modules."""
    import numpy as np
    need(isinstance(predicted_rates, np.ndarray) and isinstance(target, np.ndarray),
         'rate and spike arrays are ndarrays')
    need(predicted_rates.ndim == 3 and predicted_rates.shape == target.shape
         and all(d > 0 for d in predicted_rates.shape), 'same nonempty trial/time/neuron geometry')
    need(predicted_rates.dtype.kind == 'f' and predicted_rates.dtype.itemsize in (4, 8),
         'declared float32 or float64 prediction precision')
    need(bool(np.isfinite(predicted_rates).all()) and bool((predicted_rates >= 0).all()),
         'finite nonnegative prediction rates')
    need(target.dtype.kind in 'fiu' and not bool(np.isinf(target).any())
         and not bool((target < 0).any()), 'nonnegative finite-or-NaN spike observations')
    # Canonical evaluate() casts spikes to float64. Its bits_per_spike endpoint
    # retains NaN masking, null-rate construction and spike-count normalization.
    spikes = target.astype('float', copy=True)
    rows = []
    for index, rational in enumerate(GAIN_GRID):
        gain = list(rational)
        executed = transform.executed_gain(predicted_rates.dtype, gain)
        transformed = transform.scale_block(predicted_rates, gain)
        # Round in the stored source precision first, as the target-free writer
        # does. The canonical NLL may mutate zero rates, so pass a disposable copy.
        canonical_rates = transformed.astype('float', copy=True)
        score = float(evaluator.bits_per_spike(canonical_rates, spikes))
        need(math.isfinite(score), 'nonfinite canonical co-bps; no fallback metric or gain')
        rows.append({'index': index, 'gain': gain, 'executed_gain': executed, 'co_bps': score})
    return {'scores': rows, 'selected': choose_best(rows)}


def select_scores(predicted_rates, target, *, evaluator_path, source_descriptor):
    """Shape-generic numerical seam with authenticated source, never callbacks.

    This API accepts arrays already held by its caller and supplies no target
    custody or process ownership. The protected production route is select().
    """
    core = load_core(source_descriptor)
    transform = core.load_kernel_module('gain_transform', source_descriptor)
    evaluator = load_original_evaluator(evaluator_path)
    return _score_grid(predicted_rates, target, evaluator, transform)


def select(request_path, sha):
    """Bounded-owner entry: freeze method and baseline before protected access."""
    raw = body(request_path)
    need(type(sha) is str and pin(raw)['sha256'] == sha, 'selected exact selection request')
    request = decode(raw)
    need(type(request) is dict
         and set(request) == {'schema', 'source', 'method', 'baseline_freeze', 'target', 'evaluator', 'output_root'}
         and request['schema'] == 'smc_gain_selection_request_v1', 'typed protected gain selection request')
    core = load_core(request['source'])
    prepared = core.prepare_selection(request_path, sha)
    need(prepared['request'] == request and prepared['source'] == request['source']
         and prepared['request_descriptor']['sha256'] == sha,
         'original exact request and source preserved by preparation')
    grade = prepared['module_map']['validation_grade']
    transform = prepared['module_map']['gain_transform']
    snapshot = prepared['baseline_snapshot']
    barrier = prepared['barrier']
    need(Path(barrier['path']).name == 'METHOD_AND_BASELINE_FROZEN.json', 'fixed before-target barrier filename')
    observed_barrier = grade.decode(grade.checked(barrier))
    need(type(observed_barrier) is dict and set(observed_barrier) == {
        'schema', 'request_sha256', 'source', 'method', 'baseline_freeze', 'baseline_snapshot',
        'lineage', 'method_and_baseline_frozen', 'target_accessed'}
        and observed_barrier['schema'] == 'smc_gain_method_baseline_barrier_v1'
        and observed_barrier['request_sha256'] == sha
        and observed_barrier['source'] == request['source']
        and observed_barrier['method'] == request['method']
        and observed_barrier['baseline_freeze'] == request['baseline_freeze']
        and observed_barrier['baseline_snapshot'] == snapshot
        and observed_barrier['lineage'] == prepared['lineage']
        and observed_barrier['method_and_baseline_frozen'] is True
        and observed_barrier['target_accessed'] is False,
        'authenticated source-bound method and complete baseline freeze before target access')
    need(grade.content_pin(snapshot['path']) == {k: snapshot[k] for k in ('bytes', 'sha256')},
         'complete frozen baseline snapshot identity before target access')
    import h5py
    with h5py.File(snapshot['path'], 'r') as h5:
        dataset = h5['mc_maze_20']['eval_rates_heldout']
        need(tuple(dataset.shape) == PRODUCTION_SHAPE, 'exact VALID heldout prediction geometry')
        rates = dataset[()]
    # The source-bound core has authenticated and copied the complete baseline;
    # the immutable barrier above is published before either protected body.
    evaluator = load_original_evaluator(request['evaluator']['path'])
    target_descriptor = grade.authenticate_target(request['target']['path'])
    need(target_descriptor == request['target'], 'exact selected original VALID target descriptor')
    with h5py.File(target_descriptor['path'], 'r') as h5:
        dataset = h5['mc_maze_20']['eval_spikes_heldout']
        need(tuple(dataset.shape) == PRODUCTION_SHAPE, 'exact VALID heldout spike geometry')
        spikes = dataset[()]
    scored = _score_grid(rates, spikes, evaluator, transform)
    need(grade.content_pin(snapshot['path']) == {k: snapshot[k] for k in ('bytes', 'sha256')},
         'baseline snapshot unchanged during complete nine-score selection')
    need(grade.content_pin(target_descriptor['path']) == {k: target_descriptor[k] for k in ('bytes', 'sha256')},
         'VALID target unchanged during complete nine-score selection')
    selected = scored['selected']
    report = {
        'schema': 'smc_gain_selection_report_v1', 'route': 'smc_valid_global_rate_gain_calibration_v1',
        'phase': 'val', 'dataset': 'mc_maze_20', 'status': 'selected_from_all_nine_canonical_co_bps_scores',
        'request_sha256': sha, 'source': request['source'], 'method': request['method'],
        'baseline_freeze': request['baseline_freeze'], 'baseline_snapshot': snapshot,
        'barrier': barrier, 'lineage': prepared['lineage'], 'target': target_descriptor,
        'evaluator': request['evaluator'], 'ordered_scores': scored['scores'],
        'selected_index': selected['index'], 'selected_gain': selected['gain'],
        'selected_executed_gain': selected['executed_gain'], 'selected_co_bps': selected['co_bps'],
        'metric': 'co-bps', 'tie_rule': 'first_exact_maximum',
        'canonical_endpoint': 'original_evaluator.bits_per_spike',
        'selection_is_development_calibration': True, 'heldout_improvement': False,
        'inference_execution_qualified': False, 'physical_owner_qualified': False,
        'scientific_improvement': False, 'SOTA': False,
    }
    return grade.publish(grade.absolute(request['output_root']) / 'SELECTION.json', report)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--request', required=True)
    parser.add_argument('--sha256', required=True)
    parser.parse_args(argv)
    raise ValueError('Protected gain selection requires the selected bounded owner child; use no unbounded selector CLI')


if __name__ == '__main__':
    main()
