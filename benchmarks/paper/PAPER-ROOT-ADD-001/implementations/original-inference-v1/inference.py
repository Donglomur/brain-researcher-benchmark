"""Complete original Figure3 reference reductions, never an improvement rule.

Source permutation tests flatten three time bins within each of fourteen
sessions. Replaying that procedure does not make42 observations independent
participants, establish causal claims, or replace paired prediction-score deltas.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import stat
import sys
import warnings

import numpy as np

HERE = Path(__file__).resolve().parent
SUPPORT = HERE.parent / 'original-inputs-v1'
SUPPORT_SHA = '2fb51facfbaaba5df5392d3d5e10779fe3888778ca99595b5244382383d68978'
RESULT_BINDING_SHA = '091533a263fdcb1128f21a4af590f4b1563e799184f17575dd4be6cffa66ff9f'
CONTRASTS = (
    ('population', 'syn', 46), ('population', 'word2vec', 46), ('population', 'sem_syn', 46),
    ('syn', 'word2vec', 46), ('syn', 'sem_syn', 46), ('word2vec', 'sem_syn', 46),
    ('syn', 'syn_shuffle', 20), ('word2vec', 'word2vec_shuffle', 20), ('sem_syn', 'sem_syn_shuffle', 20),
)
SOURCE_PERMUTATIONS = 100000


def need(condition, message):
    if not condition:
        raise ValueError(message)


def load_support():
    """Reuse pinned original input/reducer code, restoring module aliases."""
    raw = (SUPPORT / 'SOURCE.json').read_bytes()
    need(hashlib.sha256(raw).hexdigest() == SUPPORT_SHA, 'Reviewed source support changed')
    manifest = json.loads(raw)
    for filename, expected in manifest['files'].items():
        value = (SUPPORT / filename).read_bytes()
        need(len(value) == expected['bytes'] and hashlib.sha256(value).hexdigest() == expected['sha256'],
             'Reviewed support member changed')
    saved, loaded = {}, {}
    try:
        for name in ('inputs', 'prediction', 'workflow'):
            saved[name] = sys.modules.get(name)
            spec = importlib.util.spec_from_file_location('language_bound_' + name, SUPPORT / (name + '.py'))
            module = importlib.util.module_from_spec(spec)
            sys.modules[name] = module
            spec.loader.exec_module(module)
            loaded[name] = module
    finally:
        for name, prior in saved.items():
            if prior is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = prior
    panel, figure3 = loaded['inputs'].reducer()
    return loaded['inputs'], loaded['workflow'], panel, figure3


def permutation_one_sided(left, right, *, seed, permutations=SOURCE_PERMUTATIONS):
    """Source seeded null draws, with undefined inputs refused explicitly.

    A fresh pooled buffer is created each iteration. A private legacy RandomState
    reproduces resetting np.random.seed for this call without altering caller RNG.
    Smaller draw counts are available for engineering controls, not full reports.
    """
    a, b = np.array(left), np.array(right)
    need(a.ndim == b.ndim == 1 and min(len(a), len(b)) >= 2
         and a.dtype.kind == b.dtype.kind == 'f'
         and np.isfinite(a).all() and np.isfinite(b).all(), 'Finite complete observations required; no NaN omission')
    need(type(seed) is int and 0 <= seed < 2**32 and type(permutations) is int
         and 1 <= permutations <= SOURCE_PERMUTATIONS, 'Bounded explicit source permutation schedule')
    observed = a.mean() - b.mean()
    need(np.isfinite(observed), 'Undefined observed mean difference')
    rng, exceedances = np.random.RandomState(seed), 0
    for _ in range(permutations):
        pooled = np.hstack((a, b))
        rng.shuffle(pooled)
        null_delta = pooled[:len(a)].mean() - pooled[-len(b):].mean()
        need(np.isfinite(null_delta), 'Undefined null mean difference')
        exceedances += int(null_delta >= observed)
    return {'observed_mean_difference': float(observed), 'exceedances': exceedances,
            'permutations': permutations, 'p_one_sided_source': exceedances / float(permutations),
            'seed_reset_for_this_contrast': seed, 'tie_rule': '>=', 'add_one_correction': False,
            'complete_source_draw_count': permutations == SOURCE_PERMUTATIONS}


def exponential(x, a, b, c):
    return a * np.exp(b * x) + c


def curve_report(group_selected_means, *, expected_scipy_version):
    """Literal Figure3c curve_fit call; one attempt, no solver retuning."""
    import scipy
    from scipy.optimize import curve_fit
    need(scipy.__version__ == expected_scipy_version, 'Declared SciPy runtime mismatch')
    y = np.asarray(group_selected_means, dtype=np.float64)
    need(y.shape == (5,) and np.isfinite(y).all(), 'Five complete group-selected means required')
    x = np.array([1, 3, 5, 7, 10])
    base = {'source_model': 'a * exp(b * x) + c', 'x_observed': x.tolist(),
            'group_selected_means': y.tolist(), 'initial_parameters': [-8, -.08, .08],
            'weighting': 'unweighted five group-selected means',
            'solver_options': 'curve_fit defaults; no bounds, sigma, method or maxfev override',
            'scipy_version': scipy.__version__, 'attempts': 1}
    with warnings.catch_warnings(record=True) as observed:
        warnings.simplefilter('always')
        try:
            parameters, covariance = curve_fit(exponential, x, y, p0=(-8, -.08, .08))
            grid = np.linspace(min(x), max(x), 100)
            values = exponential(grid, *parameters)
            need(parameters.shape == (3,) and covariance.shape == (3, 3)
                 and np.isfinite(parameters).all() and np.isfinite(values).all(), 'Nonfinite or malformed fitted curve')
            result = {**base, 'status': 'computed', 'parameters': parameters.tolist(),
                      'parameter_names': ['a', 'b', 'c'],
                      'covariance': [[float(v) if np.isfinite(v) else None for v in row] for row in covariance],
                      'covariance_finite_mask': np.isfinite(covariance).tolist(),
                      'x_fit': grid.tolist(), 'y_fit': values.tolist()}
        except (ValueError, RuntimeError, FloatingPointError) as exc:
            result = {**base, 'status': 'failed_without_retry', 'error_type': type(exc).__name__,
                      'error': str(exc)[:512], 'parameters': None, 'covariance': None, 'x_fit': None, 'y_fit': None}
    result['warnings'] = [{'category': type(w.message).__name__, 'message': str(w.message)[:512]} for w in observed]
    return result


def complete_summary(panel, weights, *, permutation_budget, expected_numpy_version, expected_scipy_version):
    """Full existing reductions plus all nine source contrasts and fitted curve."""
    need(type(permutation_budget) is int and permutation_budget >= len(CONTRASTS) * SOURCE_PERMUTATIONS,
         'Reserve all900000 source null draws before reduction')
    need(np.__version__ == expected_numpy_version, 'Declared NumPy runtime mismatch')
    import scipy
    need(scipy.__version__ == expected_scipy_version, 'Declared SciPy runtime mismatch')
    _, workflow, source_panel, figure3 = load_support()
    source_panel.validate_panel(panel)
    need(all(a.dtype.kind == 'f' and a.dtype.itemsize == 8 for fields in panel.values() for a in fields.values()),
         'Complete original-release inference requires float64 panels; no implicit precision conversion')
    result = workflow.summarize_with_weights(panel, weights)
    observations = {field: np.asarray(result['source_permutation_observations'][field], dtype=np.float64)
                    for field in {f for contrast in CONTRASTS for f in contrast[:2]}}
    need(all(a.shape == (42,) for a in observations.values()), 'All14 sessions by3source lags required')
    contrasts = []
    for left, right, seed in CONTRASTS:
        a, b = observations[left], observations[right]
        row = {'left': left, 'right': right, 'alternative': 'left mean greater than right mean',
               'observation_count_each': 42, 'source_seed': seed}
        if not (np.isfinite(a).all() and np.isfinite(b).all()):
            row.update(status='undefined_input_not_tested', p_one_sided_source=None,
                       reason='No rows dropped; literal source NaN-to-zero-p behavior is not accepted as significance')
        else:
            row.update(status='computed', **permutation_one_sided(a, b, seed=seed))
        contrasts.append(row)
    result['figure3b_source_contrasts'] = contrasts
    result['source_permutation_tests_executed'] = all(r['status'] == 'computed' for r in contrasts)
    result['source_inference_scope'] = {
        'aggregation': 'source flattened14-session by3-lag observations; row-major order',
        'people': 8, 'sessions': 14, 'observations_each': 42,
        'independent_participants_claimed': False,
        'pairing_or_sign_flip': False, 'multiplicity_correction_added': False,
        'contextual_vs_time_shuffle_contrast_added': False,
        'random_schedule': 'legacy MT19937 reset for eachcontrast; plotting RNG is irrelevant to these explicit resets',
        'meaning': 'Original descriptive/inferential procedure reenactment, not a new validity or benchmark acceptance rule',
        'improvement_endpoint': 'paired source prediction-score deltas; smaller p-value is never improvement'}
    ngrams = [result['figure3c'][f'ngram{n}'] for n in (1, 3, 5, 7, 10)]
    if any(r['summary'] is None or r['summary']['mean'] is None for r in ngrams):
        result['figure3c_source_fit'] = {'status': 'undefined_input_not_fitted', 'parameters': None,
                                       'reason': 'Complete source selection/means required; no favorable subset'}
    else:
        result['figure3c_source_fit'] = curve_report([r['summary']['mean'] for r in ngrams],
                                                   expected_scipy_version=expected_scipy_version)
    result['numerical_runtime'] = {'numpy': np.__version__, 'scipy': scipy.__version__,
                                  'historical_author_environment_authenticated': False}
    result['scientific_qualification'] = False
    result['independent_AI_reproduction'] = False
    return figure3.finite_json(result)


def author_result_bindings():
    raw = (HERE / 'author-result-bindings.json').read_bytes()
    need(len(raw) == 72017 and hashlib.sha256(raw).hexdigest() == RESULT_BINDING_SHA,
         'Original author-result binding changed')
    return json.loads(raw)


def load_author_panel(archive_path, *, read_limit, working_limit):
    """Read all224 released result arrays directly from the original ZIP."""
    source_inputs, _, source_panel, _ = load_support()
    metadata = author_result_bindings()
    extent = sum(r['bytes'] for r in metadata['members'].values())
    need(type(working_limit) is int and 3 * extent + 16 * 1024**2 <= working_limit,
         'Complete author panel exceeds working allocation')
    panel = {session: {} for session in source_panel.SESSION_UNITS}
    with source_inputs.ArchiveInputs({'analysis.zip': archive_path}, read_limit=read_limit,
                                     working_limit=working_limit, metadata=metadata) as reader:
        for name, row in metadata['members'].items():
            raw = reader.read_member(name)
            shape, fortran, dtype, offset = source_inputs.npy_header(raw)
            need(list(shape) == row['expected_shape'] and offset + math.prod(shape) * dtype.itemsize == len(raw),
                 'Original author result shape/extent mismatch')
            panel[row['session']][row['field']] = np.frombuffer(raw, dtype=dtype, offset=offset).reshape(
                shape, order='F' if fortran else 'C')
        source_panel.validate_panel(panel)
        receipt = {'source': 'provided author result arrays, not new prediction execution',
                   'archive_receipts': reader.archive_receipts, 'member_receipts': reader.member_receipts,
                   'logical_source_read_charge_bytes': reader.charged, 'extracted_files': 0,
                   'source_method_execution_authenticated': False}
    return panel, receipt


def validate_preparation_receipt(prepared):
    """Check complete source lineage; operator trust in the receipt is separate."""
    source_inputs, _, _, _ = load_support()
    metadata = source_inputs.bindings()
    need(prepared.get('schema') == 'language-original-input-preparation/v1'
         and prepared.get('prepared_arrays_persisted') is False
         and type(prepared.get('models_fitted')) is int and prepared['models_fitted'] == 0,
         'Complete original input preparation required')
    def digest(value):
        return isinstance(value, str) and len(value) == 64 and all(c in '0123456789abcdef' for c in value)
    archives = prepared.get('archive_receipts', {})
    required = {row['archive'] for row in metadata['members'].values()}
    need(set(archives) == required, 'Complete preparation archive roster required')
    for name, row in archives.items():
        expected = metadata['archives'][name]
        need(row.get('bytes') == expected['size'] and 'md5:' + str(row.get('md5')) == expected['checksum']
             and digest(row.get('sha256')), 'Preparation archive identity mismatch')
    sessions, weights = prepared.get('sessions', []), prepared.get('population_weights', {})
    order = [row['id'] for row in metadata['sessions']]
    need([row.get('session') for row in sessions] == order
         and weights.get('schema') == 'language-original-population-weights/v1'
         and [row.get('session') for row in weights.get('rows', [])] == order
         and weights.get('archive_receipts') == archives, 'Complete ordered preparation session/weight roster required')
    members = {}
    for row, weight, geometry in zip(sessions, weights['rows'], metadata['sessions']):
        session = geometry['id']
        need(row.get('geometry') == geometry and row.get('csv_row_order_preserved') is True,
             'Original preparation geometry or word order mismatch')
        weight_name = f'data_processed/{session}/self_FR_aligned2word.npy'
        count = weight.get('count')
        need(type(count) is int and 0 < count <= 4096 and weight.get('member') == weight_name
             and weight.get('shape') == [count, geometry['word_rows'], 80]
             and type(weight.get('fortran_order')) is bool
             and 0 < metadata['members'][weight_name]['bytes'] - count * geometry['word_rows'] * 80 * 8 <= 8192,
             'Complete original population weight geometry required')
        expected_names = {name for name in metadata['members'] if
                          (f'/{session}/' in name or name == f'transcription/cleaned/{session}.csv')
                          and name != weight_name}
        received = row.get('input_receipts', {})
        need(set(received) == expected_names and not set(received) & set(members),
             'Complete original per-session input receipts required')
        members.update(received)
        members[weight_name] = weight.get('receipt', {})
        for key, shape in (('original_qid', [geometry['word_rows']]),
                           ('original_timing', [geometry['word_rows'], 2]),
                           ('prepared_population_response', [geometry['time_bins'], 1]),
                           ('prepared_unit_responses', [geometry['time_bins'], geometry['units']])):
            pin = row.get(key, {})
            need(pin.get('shape') == shape and pin.get('dtype') == '<f8' and digest(pin.get('sha256_c_order')),
                 'Complete prepared response/timing identity required')
    need(set(members) == set(metadata['members']) and len(members) == 196,
         'Complete196-member preparation required')
    for name, expected in metadata['members'].items():
        row = members[name]
        need(row.get('archive') == expected['archive'] and row.get('bytes') == expected['bytes']
             and row.get('crc32') == expected['crc32'] and row.get('full_member_crc_verified') is True
             and row.get('array_values_decoded') is (not name.endswith('/self_FR_aligned2word.npy'))
             and digest(row.get('sha256')), 'Preparation member identity mismatch')
    charge = sum(metadata['archives'][a]['size'] + 1 for a in required) + sum(r['bytes'] + 1 for r in metadata['members'].values())
    need(type(prepared.get('logical_source_read_charge_bytes')) is int
         and prepared['logical_source_read_charge_bytes'] == charge, 'Complete preparation source-read accounting required')
    return prepared


def read_preparation_receipt(path, expected_sha256):
    """Bounded stable ordinary JSON; SHA binds a separately trusted operator receipt."""
    p, limit = Path(path).absolute(), 4 * 1024**2
    need(not any(a.is_symlink() for a in (p, *p.parents)), 'No preparation receipt symlinks')
    before = p.lstat()
    need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and 0 < before.st_size <= limit,
         'Bounded ordinary preparation receipt required')
    identity = lambda info: (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)
    flags = os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0)
    with os.fdopen(os.open(p, flags), 'rb') as stream:
        opened = os.fstat(stream.fileno())
        need(stat.S_ISREG(opened.st_mode) and identity(opened) == identity(before), 'Preparation receipt changed before read')
        raw = stream.read(before.st_size + 1)
        need(len(raw) == before.st_size and identity(os.fstat(stream.fileno())) == identity(before)
             and identity(p.lstat()) == identity(before), 'Preparation receipt changed during bounded read')
    need(hashlib.sha256(raw).hexdigest() == expected_sha256, 'Prepared-source receipt identity changed')
    def unique(pairs):
        result = {}
        for key, value in pairs:
            need(key not in result, 'Duplicate preparation JSON key')
            result[key] = value
        return result
    def reject_constant(value):
        raise ValueError('Nonfinite preparation JSON constant: ' + value)
    return validate_preparation_receipt(json.loads(raw, object_pairs_hook=unique, parse_constant=reject_constant))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--author-analysis-archive', required=True)
    parser.add_argument('--preparation-receipt', required=True)
    parser.add_argument('--preparation-sha256', required=True)
    parser.add_argument('--read-limit', type=int, required=True)
    parser.add_argument('--working-limit', type=int, required=True)
    parser.add_argument('--permutation-budget', type=int, required=True)
    parser.add_argument('--numpy-version', required=True)
    parser.add_argument('--scipy-version', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--output-limit', type=int, required=True)
    args = parser.parse_args()
    prepared = read_preparation_receipt(args.preparation_receipt, args.preparation_sha256)
    panel, receipts = load_author_panel(args.author_analysis_archive, read_limit=args.read_limit,
                                       working_limit=args.working_limit)
    result = complete_summary(panel, prepared['population_weights'], permutation_budget=args.permutation_budget,
                              expected_numpy_version=args.numpy_version, expected_scipy_version=args.scipy_version)
    result['provided_author_result_provenance'] = receipts
    result['prepared_input_receipt_sha256'] = args.preparation_sha256
    result['preparation_trust_scope'] = 'Complete structure/source metadata checked; SHA binds a separately trusted operator preparation receipt, not independent execution authentication'
    _, workflow, _, _ = load_support()
    output = workflow.ExclusiveOutput(args.output, byte_limit=args.output_limit)
    output.json('REFERENCE.json', result)


if __name__ == '__main__':
    main()
