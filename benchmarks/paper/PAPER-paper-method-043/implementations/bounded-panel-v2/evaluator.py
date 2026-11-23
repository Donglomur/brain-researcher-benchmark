"""Bounded-memory operator scoring of the existing NeuroPictor prepared panel.

All original subject/stimulus identities and all distractors remain in the panel.
This is arithmetic infrastructure, not native extraction or scientific admission.
"""
from __future__ import annotations

import argparse
from collections import namedtuple
import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np

_PREDECESSOR = Path(__file__).resolve().parents[1] / 'initial-evaluator-v1' / 'evaluator.py'
_spec = importlib.util.spec_from_file_location('neuropictor_arithmetic_v1', _PREDECESSOR)
core = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(core)
ValidationError = core.ValidationError
require = core._require

# Fixed independently of population size; no full N x D normalized feature copy.
FEATURE_BLOCK = 16
MAX_FEATURE_WIDTH = 1_000_000
ArrayLayout = namedtuple('ArrayLayout', ('shape', 'dtype'))


def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


class MappedBundle:
    """Authenticated individual NPY members, aligned through sample identities.

    This deliberately does not accept NPZ: NumPy's NPZ access eagerly expands
    an entire member, even when mmap_mode is supplied.
    """

    def __init__(self, base, spec, samples, extraction):
        require(isinstance(spec, dict), 'bundle must be an object')
        require(spec.get('format') == 'npy-members-v1', 'bundle format must be npy-members-v1')
        require(spec.get('extraction') == extraction, 'extraction recipes differ')
        keys = core._samples(spec.get('samples'))
        expected_keys = core._samples(samples)
        require(set(keys) == set(expected_keys), 'bundle population differs from protected pool')
        expected = {row['sample_id']: row for row in samples}
        require(all(row == expected[row['sample_id']] for row in spec['samples']),
                'subject/stimulus/session identity mismatch')
        positions = {key: i for i, key in enumerate(keys)}
        self.order = np.array([positions[key] for key in expected_keys], dtype=np.int64)
        members = spec.get('arrays')
        require(isinstance(members, dict) and set(members) == set(core.ARRAYS),
                'bundle needs exactly pixels425 and six feature arrays')
        self.arrays = {}
        self.files = {}
        try:
            for key in core.ARRAYS:
                item = members[key]
                require(isinstance(item, dict), f'{key}: member must be an object')
                core._sha(item.get('sha256'), f'{key}: array hash')
                require(isinstance(item.get('path'), str) and item['path'], f'{key}: path required')
                path = (Path(base) / item['path']).resolve(strict=True)
                require(path.is_file(), f'{key}: regular NPY file required')
                before = path.stat()
                require(sha256(path) == item['sha256'], f'{key}: array bytes do not match hash')
                array = np.load(path, allow_pickle=False, mmap_mode='r')
                if not isinstance(array, np.memmap) and hasattr(array, 'close'):
                    array.close()
                require(isinstance(array, np.memmap), f'{key}: individual NPY required, not NPZ')
                try:
                    require(array.dtype.kind in 'fiu' and array.dtype.itemsize <= 8,
                            f'{key}: real numeric array with at most 8-byte elements required')
                    require(array.ndim >= 1, f'{key}: row axis required')
                    require(array.shape[0] == len(keys), f'{key}: row count mismatch')
                    if key == 'pixels425':
                        require(array.shape == (len(keys), 3, 425, 425), 'pixels425 must be [N,3,425,425]')
                    else:
                        require(array.ndim == 2 and 2 <= array.shape[1] <= MAX_FEATURE_WIDTH,
                                f'{key}: features need [N,2<=D<=1000000]')
                    self.arrays[key] = ArrayLayout(array.shape, array.dtype)
                finally:
                    array._mmap.close()
                self.files[key] = (path, item['sha256'], self._identity(before))
                require(self._identity(path.stat()) == self._identity(before), f'{key}: array changed during admission')
        except Exception:
            self.close()
            raise

    @staticmethod
    def _identity(stat):
        return (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)

    def read(self, key, indices):
        require(0 < len(indices) <= (1 if key == 'pixels425' else FEATURE_BLOCK),
                f'{key}: read exceeds bounded row count')
        path = self.files[key][0]
        array = np.load(path, allow_pickle=False, mmap_mode='r')
        try:
            require((array.shape, array.dtype) == self.arrays[key], f'{key}: array layout changed')
            # Advanced indexing copies only bounded rows. Close this mapping
            # immediately: touched pages must not accumulate over all subjects.
            return array[self.order[np.asarray(indices, dtype=np.int64)]]
        finally:
            array._mmap.close()

    def verify_unchanged(self):
        # Actual byte rehash at completion, not only a potentially stale stat.
        for key, (path, expected, identity) in self.files.items():
            require(self._identity(path.stat()) == identity and sha256(path) == expected,
                    f'{key}: array changed during scoring')

    def close(self):
        self.arrays.clear()


def _unit_block(bundle, key, rows):
    return np.ascontiguousarray(core._unit_rows(np.ascontiguousarray(bundle.read(key, rows))))


def _row_correlations(real_units, predicted_unit):
    # Keep one contiguous feature-axis reduction for every dot product. BLAS
    # matrix/vector kernels may otherwise round equal rows differently when
    # the final distractor block is shorter, changing strict tie decisions.
    return np.clip(np.sum(real_units * predicted_unit, axis=1), -1, 1)


def identification(real, pred, key, indices):
    """Strict column identification with all N-1 real-image distractors.

    Real and predicted features are normalized in blocks, without allocating
    their complete N x D arrays or a complete N x N correlation matrix.
    """
    n = len(indices)
    require(n >= 2, 'two-way identification needs at least two stimuli')
    scores = np.empty(n)
    for start in range(0, n, FEATURE_BLOCK):
        stop = min(start + FEATURE_BLOCK, n)
        selected = indices[start:stop]
        p = _unit_block(pred, key, selected)
        matching = _unit_block(real, key, selected)
        congruent = np.array([_row_correlations(matching[j:j + 1], row)[0]
                             for j, row in enumerate(p)])
        del matching
        successes = np.zeros(stop - start, dtype=np.int64)
        for other in range(0, n, FEATURE_BLOCK):
            end = min(other + FEATURE_BLOCK, n)
            distractors = _unit_block(real, key, indices[other:end])
            cross = np.column_stack([_row_correlations(distractors, row) for row in p])
            better = cross < congruent[None, :]
            # The matching image never becomes its own distractor.
            shared_start, shared_end = max(start, other), min(stop, end)
            if shared_start < shared_end:
                shared = np.arange(shared_start, shared_end)
                better[shared - other, shared - start] = False
            successes += better.sum(axis=0)
        scores[start:stop] = successes / (n - 1)
    return scores


def metric_panel(real, pred, indices):
    require(all(real.arrays[k].shape[1:] == pred.arrays[k].shape[1:] for k in core.ARRAYS),
            'real/pred shape mismatch')
    n = len(indices)
    result = {key: np.empty(n) for key in core.METRICS}
    weights = np.array([.2125, .7154, .0721])
    for position, index in enumerate(indices):
        r = core._numeric(real.read('pixels425', [index])[0], 'real pixels')
        p = core._numeric(pred.read('pixels425', [index])[0], 'pred pixels')
        require(np.all((r >= 0) & (r <= 1)) and np.all((p >= 0) & (p <= 1)),
                'pixels must already be clamped/scaled to [0,1]')
        result['pixcorr'][position] = core.paired_correlation(r.reshape(1, -1), p.reshape(1, -1))[0]
        result['ssim_2d_prospective'][position] = core.ssim_2d(
            np.einsum('chw,c->hw', r, weights), np.einsum('chw,c->hw', p, weights))
    for key in core.FEATURES:
        if key in core.DISTANCES:
            for start in range(0, n, FEATURE_BLOCK):
                stop = min(start + FEATURE_BLOCK, n)
                rows = indices[start:stop]
                result[key][start:stop] = 1 - core.paired_correlation(real.read(key, rows), pred.read(key, rows))
        else:
            result[key] = identification(real, pred, key, indices)
    return result


def _conditions(conditions):
    require(isinstance(conditions, list) and len(conditions) == 3, 'three conditions required: pretrained,target_only,neural_free')
    require(all(isinstance(c, dict) for c in conditions), 'condition must be an object')
    require({c.get('role') for c in conditions} == {'pretrained', 'target_only', 'neural_free'}, 'condition roles differ')
    names = [c.get('name') for c in conditions]
    require(all(isinstance(n, str) and n for n in names) and len(set(names)) == 3, 'unique condition names required')
    matched = ('target_training_membership_sha256', 'diffusion_prior_sha256', 'tuning_budget_sha256',
               'generation_budget_sha256', 'encoder_initialization_sha256')
    anchor = conditions[0]
    for c in conditions:
        for key in matched:
            core._sha(c.get(key), key)
            require(c[key] == anchor[key], f'unmatched comparator {key}')
        core._sha(c.get('checkpoint_sha256'), 'checkpoint')
        core._sha(c.get('initialization_exposure_sha256'), 'initialization exposure')
        require(c.get('encoder_route') in ('released_encoder', 'raw_pretrained_encoder', 'random_init'), 'encoder route missing')
        require(c['encoder_route'] == anchor['encoder_route'], 'encoder route differs; multi-subject effect confounded')
        if c['role'] == 'pretrained':
            require(c.get('image_pretraining_route') in ('raw_multi_subject', 'released_multi_subject_checkpoint'), 'pretrained route missing')
        else:
            require(c.get('image_pretraining_route') == 'none', 'target-only/neural-free cannot use multi-subject checkpoint')
        require(c.get('neural_input') is (c['role'] != 'neural_free'), 'neural-free control declaration mismatch')


def evaluate(manifest, base=Path('.')):
    protocol = manifest['protocol']
    groups = core.validate_protocol(protocol)
    conditions = manifest.get('conditions')
    _conditions(conditions)
    samples, extraction = protocol['samples'], protocol['extraction']
    reference = MappedBundle(base, manifest['reference'], samples, extraction)
    outputs = {}
    try:
        for condition in conditions:
            prediction = MappedBundle(base, condition['bundle'], samples, extraction)
            try:
                by_subject = {}
                for subject in sorted(groups):
                    indices = [i for i, row in enumerate(samples) if row['subject_id'] == subject]
                    panel = metric_panel(reference, prediction, indices)
                    by_subject[subject] = {'n': len(indices), 'sample_ids': [samples[i]['sample_id'] for i in indices],
                        'mean': {key: float(values.mean()) for key, values in panel.items()},
                        'per_stimulus': {key: values.tolist() for key, values in panel.items()}}
                prediction.verify_unchanged()
                outputs[condition['role']] = {'name': condition['name'], 'by_subject': by_subject,
                    'macro_subject_mean': {key: float(np.mean([s['mean'][key] for s in by_subject.values()])) for key in core.METRICS},
                    'image_pretraining_route': condition['image_pretraining_route'], 'encoder_route': condition['encoder_route']}
            finally:
                prediction.close()
        reference.verify_unchanged()
    finally:
        reference.close()
    return {'task_id': core.TASK_ID, 'source_commit': core.SOURCE_COMMIT, 'status': 'engineering_panel_only',
        'scope': protocol['scope'], 'n_subjects': len(groups), 'n_subject_stimuli': len(samples),
        'conditions': outputs,
        'pretrained_minus_comparator': {role: {key: outputs['pretrained']['macro_subject_mean'][key] - outputs[role]['macro_subject_mean'][key]
            for key in core.METRICS} for role in ('target_only', 'neural_free')},
        'directions': {key: 'lower' if key in core.DISTANCES else 'higher' for key in core.METRICS},
        'research_qualified': False, 'native_equivalence_verified': False, 'full_contract_complete': False,
        'holds': core.HOLDS,
        'receipt_limit': 'Hashes and declarations bind supplied evidence; they do not independently verify its truth.',
        'storage': {'format': 'npy-members-v1', 'feature_block_rows': FEATURE_BLOCK, 'pixel_rows_in_memory': 1,
                    'population_subsampling': False, 'full_population_runtime_measured': False}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    try:
        content = args.manifest.read_bytes()
        result = evaluate(json.loads(content), args.manifest.resolve().parent)
        result['input_manifest_sha256'] = hashlib.sha256(content).hexdigest()
        result['runtime'] = {'numpy': np.__version__, 'scipy': __import__('scipy').__version__}
        with args.output.open('x') as handle:
            json.dump(result, handle, indent=2, allow_nan=False)
            handle.write('\n')
    except (ValidationError, KeyError, OSError, ValueError, TypeError, IndexError) as exc:
        parser.exit(2, f'evaluation rejected: {exc}\n')


if __name__ == '__main__':
    main()
