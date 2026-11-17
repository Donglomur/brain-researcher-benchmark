"""NEURAL-020 frozen tensor projection and condition-wise NLB co-smoothing scorer.

This module never downloads data, executes candidate code, or asserts acquisition
qualification. See provenance.json and the task documentation for retained gates.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import zipfile
from pathlib import Path
import numpy as np

TASK_ID = 'NEURAL-020'
CONTRACT_SHA256 = '8b922ac0214da6a1cb1ca5c0320cab90aaf6dab0e51f8ce44a552b0ecfcc718a'
NLB_COMMIT = '42f8410b88e12db136910fa2f888b025ea0aa2ae'
SOURCE_TRIALS = 826
SOURCE_UNITS = 65
EPSILON = 1e-9
GATES = [
    'native_time_rate_conversion_bump_labels_and_official_unit_mask',
    'full_payload_identity_alignment_missingness_and_public_private_hash_qualification',
    'prospective_selection_split_protocol_and_access_budget_freeze',
    'authentic_signal_derived_reference_and_independent_comparator_execution',
    'independent_scientific_replication_and_admission_criteria',
    'public_development_data_no_contamination_resistant_holdout',
    'single_subject_single_session_no_population_replication',
    'data_and_code_rights_attribution_and_payload_release_review',
]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def exact_keys(value, keys, name):
    require(isinstance(value, dict) and set(value) == set(keys), name + ': unexpected or missing fields')


def real_array(value, name):
    array = np.asarray(value)
    require(array.dtype.kind in 'fiu', name + ': real numeric array required')
    # Reject unsafe unsigned/integer conversion before float conversion.
    if array.dtype.kind in 'iu':
        require(np.all(array <= 2**53), name + ': integers exceed exact float64 domain')
    return array.astype(np.float64, copy=False)


def counts_array(value, name):
    array = real_array(value, name)
    values = array[~np.isnan(array)]
    require(np.isfinite(values).all() and np.all(values >= 0) and
            np.all(values <= 2**53) and np.all(values == np.floor(values)),
            name + ': finite nonnegative integer counts or fixed NaN missingness required')
    return array


def unique_ids(value, name):
    require(isinstance(value, (list, tuple)), name + ': one-dimensional ID sequence required')
    items = list(value)
    require(all(isinstance(x, str) and 0 < len(x) <= 128 for x in items)
            and len(items) == len(set(items)), name + ': unique bounded text IDs required')
    return items


def canonical_digest(metadata, arrays):
    digest = hashlib.sha256(json.dumps(metadata, sort_keys=True, separators=(',', ':'),
                                       allow_nan=False).encode())
    for name in sorted(arrays):
        array = np.ascontiguousarray(arrays[name])
        digest.update(name.encode())
        digest.update(str(array.dtype).encode())
        digest.update(json.dumps(array.shape).encode())
        digest.update(array.tobytes())
    return digest.hexdigest()


def poisson_bits_per_spike(target_counts, expected_counts):
    """Pinned NLB equation; exact-zero rates alone become 1e-9.

    A condition subset receives its own per-unit evaluation mean. Factorial
    terms cancel. Fixed target NaNs alone define missingness; every prediction
    must be finite/nonnegative, including unscored cells (strict input policy).
    """
    target = counts_array(target_counts, 'target_counts')
    rates = real_array(expected_counts, 'expected_counts')
    require(target.ndim == 3 and all(n > 0 for n in target.shape) and rates.shape == target.shape,
            'matching nonempty trial x time x heldout-unit arrays required')
    require(np.isfinite(rates).all() and np.all(rates >= 0), 'predictions must be finite and nonnegative')
    valid = ~np.isnan(target)
    valid_per_unit = valid.sum(axis=(0, 1))
    require(np.all(valid_per_unit > 0), 'every fixed heldout unit needs observed target cells')
    target_safe = np.where(valid, target, 0.0)
    with np.errstate(over='ignore', invalid='ignore'):
        sums = target_safe.sum(axis=(0, 1), dtype=np.float64)
        total = float(sums.sum())
    require(math.isfinite(total), 'target sum overflow')
    means = sums / valid_per_unit
    means = np.where(means == 0, EPSILON, means)
    safe_rates = np.where(rates == 0, EPSILON, rates)
    if total == 0:
        return {'status': 'undefined_zero_target_spikes', 'co_bps': None,
                'target_spikes': 0.0, 'valid_cells': int(valid.sum())}
    observed = target[valid]
    null = np.broadcast_to(means, target.shape)[valid]
    predicted = safe_rates[valid]
    with np.errstate(over='ignore', invalid='ignore'):
        terms = observed * (np.log(predicted) - np.log(null)) + null - predicted
        gain = float(np.sum(terms, dtype=np.float64))
    require(math.isfinite(gain), 'likelihood ratio overflow or nonfinite')
    score = gain / total / math.log(2.0)
    require(math.isfinite(score), 'nonfinite co-bps')
    return {'status': 'scored', 'co_bps': score, 'target_spikes': total,
            'valid_cells': int(valid.sum()), 'log_likelihood_gain_nats': gain}


def _metadata(meta, spikes):
    exact_keys(meta, ['schema_version', 'task_id', 'contract_sha256', 'source',
                     'bin_width_ms', 'unit_ids', 'heldout_mask', 'trial_roster',
                     'protocol', 'conversion_receipt'], 'metadata')
    require(type(meta['schema_version']) is int and meta['schema_version'] == 1
            and meta['task_id'] == TASK_ID and meta['contract_sha256'] == CONTRACT_SHA256,
            'task/contract/schema identity mismatch')
    source = meta['source']
    expected = {'dandiset': '000127', 'version': '0.220113.0359', 'subject': 'Han',
                'session_start_time': '2017-12-07T17:06:09.727000-05:00',
                'asset_id': 'ded26b6c-418d-43f5-8a37-dfd072c2dbd4',
                'asset_sha256': '639b1a03ab813f96fec76681110a1634942476badc0fd4c93d406c24701f5db2'}
    require(source == expected, 'exact Han training asset identity required')
    width = meta['bin_width_ms']
    require(type(width) is int and width in (5, 20), 'official 5 or 20 ms bin width required')
    ids = unique_ids(meta['unit_ids'], 'unit_ids')
    require(len(ids) == SOURCE_UNITS, 'complete 65-unit source population required')
    mask = np.asarray(meta['heldout_mask'])
    require(mask.shape == (SOURCE_UNITS,) and mask.dtype == np.bool_
            and mask.any() and (~mask).any(), 'fixed source heldout mask required')
    roster = meta['trial_roster']
    require(isinstance(roster, list) and len(roster) == SOURCE_TRIALS,
            'complete 826-row training NWB trial roster required; exclusions must stay in roster')
    require(spikes.shape == (SOURCE_TRIALS, 600 // width, SOURCE_UNITS), 'source tensor shape mismatch')
    protocol = meta['protocol']
    exact_keys(protocol, ['protocol_id', 'native_split_roles', 'selection_rationale',
                          'condition_policy', 'access_policy', 'resource_budget'], 'protocol')
    require(all(isinstance(protocol[k], str) and protocol[k].strip() for k in
                ('protocol_id', 'selection_rationale', 'access_policy', 'resource_budget')),
            'frozen protocol rationale/access/resource fields required')
    require(protocol['condition_policy'] == 'report_active_and_perturbed_within_condition_null',
            'this version requires the declared condition-wise endpoint policy')
    roles = protocol['native_split_roles']
    require(isinstance(roles, dict) and roles and
            set(roles.values()) <= {'train', 'eval', 'excluded'} and
            {'train', 'eval'} <= set(roles.values()), 'explicit native split-to-role map required')
    receipt = meta['conversion_receipt']
    exact_keys(receipt, ['nlb_commit', 'alignment_event', 'window_ms', 'rate_units',
                         'mask_source', 'counts_sha256', 'operator_evidence'], 'conversion_receipt')
    require(receipt['nlb_commit'] == NLB_COMMIT and receipt['alignment_event'] == 'move_onset_time'
            and receipt['window_ms'] == [-100, 500] and receipt['rate_units'] == 'spikes_per_bin'
            and receipt['mask_source'] == 'NWB units.heldout', 'native tensor-conversion declaration differs')
    require(isinstance(receipt['operator_evidence'], str) and receipt['operator_evidence'].strip(),
            'conversion evidence identifier required; self-attestation does not clear native holds')
    require(receipt['counts_sha256'] == hashlib.sha256(np.ascontiguousarray(spikes).tobytes()).hexdigest(),
            'source tensor digest differs')
    ids_seen, blocks, intervals, conditions = [], {}, [], set()
    for row in roster:
        exact_keys(row, ['trial_id', 'block_id', 'native_split', 'role', 'ctr_hold_bump',
                         'window_start_seconds', 'window_stop_seconds', 'exclusion_reason'], 'trial row')
        ids_seen.append(row['trial_id'])
        require(isinstance(row['block_id'], str) and row['block_id'], 'continuous block ID required')
        require(row['native_split'] in roles and row['role'] == roles[row['native_split']],
                'trial role differs from frozen native split mapping')
        require(type(row['ctr_hold_bump']) is int and row['ctr_hold_bump'] in (0, 1),
                'active/perturbed ctr_hold_bump must be exact 0/1; unknown labels cannot disappear')
        if row['role'] == 'excluded':
            require(isinstance(row['exclusion_reason'], str) and row['exclusion_reason'].strip(),
                    'every exclusion requires an explicit reason')
        else:
            require(row['exclusion_reason'] is None, 'included trial cannot have an exclusion reason')
            previous = blocks.setdefault(row['block_id'], row['role'])
            require(previous == row['role'], 'whole continuous block crosses train/eval roles')
        start, stop = row['window_start_seconds'], row['window_stop_seconds']
        require(type(start) in (int, float) and type(stop) in (int, float)
                and math.isfinite(start) and math.isfinite(stop) and stop > start
                and math.isclose(stop - start, .6, abs_tol=1e-9, rel_tol=0),
                'aligned trial window must be finite 600 ms in NWB time base')
        if row['role'] != 'excluded':
            intervals.append((start, stop, row['role']))
        if row['role'] == 'eval':
            conditions.add(row['ctr_hold_bump'])
    unique_ids(ids_seen, 'trial roster IDs')
    require(conditions == {0, 1}, 'both active and perturbed evaluation populations are required')
    require(any(r['role'] == 'train' for r in roster), 'training population missing')
    # Track maximal stop separately by role: long within-role overlap must not
    # conceal an interleaved interval from the opposite role.
    stops = {'train': -math.inf, 'eval': -math.inf}
    for start, stop, role in sorted(intervals):
        other = 'eval' if role == 'train' else 'train'
        require(start >= stops[other], 'train/eval trial windows overlap in continuous time')
        stops[role] = max(stops[role], stop)
    return mask


def prepare_packet(metadata, full_counts):
    """Project complete pre-binned source tensors into public/train/private arrays.

    This is an operator-side conversion boundary, not an NWB reader. The full
    population and exclusions remain committed in the private packet digest.
    """
    spikes = counts_array(full_counts, 'source spikes')
    heldout = _metadata(metadata, spikes)
    roster = metadata['trial_roster']
    train_index = [i for i, r in enumerate(roster) if r['role'] == 'train']
    eval_index = [i for i, r in enumerate(roster) if r['role'] == 'eval']
    fingerprint = canonical_digest(metadata, {'source_spikes': spikes})
    bins = np.arange(-100, 500, metadata['bin_width_ms'], dtype=np.int64)
    units = np.asarray(metadata['unit_ids'], dtype='U128')
    # Opaque positional identifiers avoid exposing source trial labels/timestamps.
    query = {'trial_ids': np.asarray(['eval-%04d' % i for i in range(len(eval_index))]),
             'heldin_unit_ids': units[~heldout], 'heldout_unit_ids': units[heldout],
             'bin_left_edges_ms': bins, 'prediction_units': np.asarray('spikes_per_bin'),
             'packet_sha256': np.asarray(fingerprint),
             'visible_counts': spikes[eval_index][:, :, ~heldout]}
    training = {'trial_ids': np.asarray(['train-%04d' % i for i in range(len(train_index))]),
                'heldin_unit_ids': units[~heldout], 'heldout_unit_ids': units[heldout],
                'bin_left_edges_ms': bins, 'packet_sha256': np.asarray(fingerprint),
                'visible_counts': spikes[train_index][:, :, ~heldout],
                'target_counts': spikes[train_index][:, :, heldout]}
    gold = {'trial_ids': query['trial_ids'].copy(), 'heldout_unit_ids': units[heldout],
            'bin_left_edges_ms': bins, 'packet_sha256': np.asarray(fingerprint),
            'target_counts': spikes[eval_index][:, :, heldout],
            'ctr_hold_bump': np.asarray([roster[i]['ctr_hold_bump'] for i in eval_index])}
    # Verify fixed target coverage now, including each condition before export.
    for c in (0, 1):
        targets = gold['target_counts'][gold['ctr_hold_bump'] == c]
        require(np.all((~np.isnan(targets)).sum(axis=(0, 1)) > 0), 'condition has an unobserved heldout unit')
    return query, training, gold


def score_submission(gold, submission):
    exact_keys(gold, ['trial_ids', 'heldout_unit_ids', 'bin_left_edges_ms', 'packet_sha256',
                      'target_counts', 'ctr_hold_bump'], 'private gold')
    exact_keys(submission, ['trial_ids', 'heldout_unit_ids', 'bin_left_edges_ms', 'packet_sha256',
                            'prediction_units', 'expected_counts'], 'submission')
    require(np.asarray(submission['prediction_units']).shape == () and
            str(submission['prediction_units']) == 'spikes_per_bin', 'explicit spikes_per_bin predictions required')
    for field in ('trial_ids', 'heldout_unit_ids', 'bin_left_edges_ms', 'packet_sha256'):
        require(np.array_equal(np.asarray(gold[field]), np.asarray(submission[field])), field + ': identity/order mismatch')
    target = counts_array(gold['target_counts'], 'private targets')
    require(target.ndim == 3, 'private target tensor must have three axes')
    trials = unique_ids(np.asarray(gold['trial_ids']).tolist(), 'gold trial IDs')
    units = unique_ids(np.asarray(gold['heldout_unit_ids']).tolist(), 'gold unit IDs')
    require(target.shape[0] == len(trials) and target.shape[2] == len(units), 'private target identity shape differs')
    bins = np.asarray(gold['bin_left_edges_ms'])
    require(any(np.array_equal(bins, np.arange(-100, 500, width)) for width in (5, 20))
            and target.shape[1] == len(bins), 'private bin grid differs from Area2 window')
    fingerprint = np.asarray(gold['packet_sha256'])
    require(fingerprint.shape == () and isinstance(fingerprint.item(), str) and
            len(fingerprint.item()) == 64 and all(x in '0123456789abcdef' for x in fingerprint.item()),
            'private packet fingerprint invalid')
    labels = np.asarray(gold['ctr_hold_bump'])
    require(labels.shape == (len(trials),) and labels.dtype.kind in 'iu' and
            set(labels.tolist()) == {0, 1}, 'both complete condition populations required')
    rates = real_array(submission['expected_counts'], 'prediction')
    aggregate = poisson_bits_per_spike(target, rates)
    by_condition = {name: poisson_bits_per_spike(target[labels == code], rates[labels == code])
                    for code, name in ((0, 'active'), (1, 'perturbed'))}
    return {'task_id': TASK_ID, 'packet_sha256': fingerprint.item(),
            'status': 'component_scoring_complete', 'data_scope': 'public_development_only',
            'primary_endpoints': by_condition, 'pooled_official_equation_diagnostic': aggregate,
            'null_policy': 'per_unit_evaluation_mean_recomputed_within_each_reported_condition',
            'constant_prediction_diagnostic': bool(np.all(rates == rates[0, 0, :])),
            'evaluation_trials': len(trials), 'heldout_units': len(units),
            'condition_trials': {name: int(np.sum(labels == code)) for code, name in ((0, 'active'), (1, 'perturbed'))},
            'uncertainty': 'single_session_descriptive_only_no_between_animal_inference',
            'research_qualified': False, 'submission_ready': False, 'retained_gates': GATES.copy()}


def mean_rate_reference(training, query):
    """Training-only per-unit mean control; never the evaluation-target null."""
    require(np.array_equal(training['packet_sha256'], query['packet_sha256']), 'training/query packet mismatch')
    for field in ('heldin_unit_ids', 'heldout_unit_ids', 'bin_left_edges_ms'):
        require(np.array_equal(training[field], query[field]), 'training/query ' + field + ' mismatch')
    target = counts_array(training['target_counts'], 'training targets')
    require(target.ndim == 3 and target.shape[0] > 0 and
            target.shape[1:] == (len(query['bin_left_edges_ms']), len(query['heldout_unit_ids'])),
            'training target geometry differs')
    require(np.all((~np.isnan(target)).sum(axis=(0, 1)) > 0), 'training unit has no observed cells')
    mean = np.nanmean(target, axis=(0, 1))
    require(np.isfinite(mean).all(), 'training mean overflow')
    prediction = np.broadcast_to(mean, (len(query['trial_ids']), target.shape[1], target.shape[2])).copy()
    return {**{key: np.asarray(query[key]).copy() for key in
               ('trial_ids', 'heldout_unit_ids', 'bin_left_edges_ms', 'packet_sha256', 'prediction_units')},
            'expected_counts': prediction}


def smoothing_reference(training, query):
    """Pinned Area2 smoothing + Poisson GLM recipe, fitted only on training.

    Missing neural cells are rejected: the native recipe defines no imputation.
    sklearn is imported only for this explicitly requested reference operation.
    Iteration retry and clipping follow the pinned author baseline.
    """
    from sklearn.linear_model import PoissonRegressor
    from scipy.signal.windows import gaussian
    # Reuse train/query identity and training-target coverage checks.
    prototype = mean_rate_reference(training, query)
    train = counts_array(training['visible_counts'], 'training visible counts')
    evaluate = counts_array(query['visible_counts'], 'query visible counts')
    target = counts_array(training['target_counts'], 'training heldout counts')
    require(train.ndim == 3 and evaluate.ndim == 3 and train.shape[:2] == target.shape[:2]
            and train.shape[2] == evaluate.shape[2] == len(query['heldin_unit_ids'])
            and evaluate.shape[:2] == (len(query['trial_ids']), len(query['bin_left_edges_ms'])),
            'smoothing input geometry mismatch')
    require(np.isfinite(train).all() and np.isfinite(evaluate).all() and np.isfinite(target).all(),
            'native smoothing reference requires complete counts; no imputation is implied')
    bins = np.asarray(query['bin_left_edges_ms'])
    require(any(np.array_equal(bins, np.arange(-100, 500, width)) for width in (5, 20)),
            'native Area2 bin grid required')
    width = int(bins[1] - bins[0])
    kernel = gaussian(int(6 * 30 / width), std=int(30 / width), sym=True)
    kernel = kernel / kernel.sum()
    def features(values):
        smooth = np.apply_along_axis(lambda row: np.convolve(row, kernel, mode='same'), 1, values)
        return np.log(smooth + 1e-4).reshape(-1, values.shape[2])
    x_train, x_eval = features(train), features(evaluate)
    y_train = target.reshape(-1, target.shape[2])
    predicted = np.empty((len(x_eval), target.shape[2]), dtype=np.float64)
    iterations = []
    for unit in range(target.shape[2]):
        require(np.any(y_train[:, unit] > 0),
                'native Poisson GLM requires positive total training count for every heldout unit')
        maximum = 500
        while True:
            model = PoissonRegressor(alpha=.01, max_iter=maximum)
            model.fit(x_train, y_train[:, unit])
            if model.n_iter_ == maximum and maximum < 10000:
                maximum *= 5
            else:
                break
        require(model.n_iter_ < maximum, 'native GLM failed to converge within pinned retry budget')
        values = model.predict(x_eval)
        require(np.isfinite(values).all(), 'native GLM prediction overflow')
        predicted[:, unit] = np.clip(values, 1e-9, 1e20)
        iterations.append(int(model.n_iter_))
    prototype['expected_counts'] = predicted.reshape(len(query['trial_ids']), len(bins), target.shape[2])
    audit = {'recipe': 'nlb_area2_smoothing_poisson_heldout', 'nlb_commit': NLB_COMMIT,
             'kernel_sd_ms': 30, 'kernel_length_bins': len(kernel),
             'kernel_std_bins': int(30 / width), 'alpha': .01, 'training_only': True,
             'iterations_by_unit': iterations, 'authentic_reference_qualified': False}
    return prototype, audit


def load_npz(path):
    """Bound data-only archives before NumPy allocates arrays; never unpickle."""
    path = Path(path)
    cap = 128 * 1024**2
    require(path.is_file() and 0 < path.stat().st_size <= cap, 'archive size exceeds 128 MiB')
    with zipfile.ZipFile(path) as bundle:
        entries = bundle.infolist()
        require(0 < len(entries) <= 20 and len({x.filename for x in entries}) == len(entries),
                'archive field count or duplicate field invalid')
        require(sum(x.file_size for x in entries) <= cap, 'expanded archive exceeds 128 MiB')
        for entry in entries:
            require(entry.filename.endswith('.npy') and '/' not in entry.filename
                    and '\\' not in entry.filename and not (entry.flag_bits & 1), 'invalid archive member')
            with bundle.open(entry) as stream:
                version = np.lib.format.read_magic(stream)
                require(version in ((1, 0), (2, 0)), 'unsupported NPY format')
                reader = np.lib.format.read_array_header_1_0 if version == (1, 0) else np.lib.format.read_array_header_2_0
                shape, _, dtype = reader(stream, max_header_size=16384)
                require(not dtype.hasobject and dtype.kind in 'fiuUSb' and len(shape) <= 3,
                        'unsupported archive dtype or rank')
                require(math.prod(shape) * dtype.itemsize <= cap and
                        stream.tell() + math.prod(shape) * dtype.itemsize == entry.file_size,
                        'array allocation/size mismatch')
    with np.load(path, allow_pickle=False) as archive:
        return {key: archive[key] for key in archive.files}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    prepare = commands.add_parser('prepare')
    prepare.add_argument('--metadata', required=True)
    prepare.add_argument('--source-counts', required=True, help='NPZ containing only full_counts')
    prepare.add_argument('--output-directory', required=True, help='new private operator directory')
    score = commands.add_parser('score')
    score.add_argument('--gold', required=True)
    score.add_argument('--submission', required=True)
    score.add_argument('--output', required=True)
    reference = commands.add_parser('mean-reference')
    reference.add_argument('--training', required=True)
    reference.add_argument('--query', required=True)
    reference.add_argument('--output', required=True)
    smooth = commands.add_parser('smoothing-reference')
    smooth.add_argument('--training', required=True)
    smooth.add_argument('--query', required=True)
    smooth.add_argument('--output', required=True)
    smooth.add_argument('--audit', required=True)
    args = parser.parse_args(argv)
    if args.command == 'prepare':
        meta = json.loads(Path(args.metadata).read_text())
        source = load_npz(args.source_counts)
        exact_keys(source, ['full_counts'], 'source archive')
        query, training, gold = prepare_packet(meta, source['full_counts'])
        out = Path(args.output_directory)
        out.mkdir(mode=0o700, parents=False, exist_ok=False)
        for name, content in [('public_query', query), ('public_training', training), ('private_gold', gold)]:
            with (out / (name + '.npz')).open('xb') as stream:
                np.savez_compressed(stream, **content)
        (out / 'private_protocol.json').write_text(json.dumps(meta, indent=2, allow_nan=False) + '\n')
        receipt = {'task_id': TASK_ID, 'packet_sha256': str(query['packet_sha256']),
                   'research_qualified': False, 'submission_ready': False, 'retained_gates': GATES,
                   'files_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(out.iterdir())}}
        (out / 'private_receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    elif args.command == 'score':
        result = score_submission(load_npz(args.gold), load_npz(args.submission))
        with Path(args.output).open('x') as stream:
            json.dump(result, stream, indent=2, allow_nan=False)
            stream.write('\n')
    else:
        training, query = load_npz(args.training), load_npz(args.query)
        if args.command == 'smoothing-reference':
            result, audit = smoothing_reference(training, query)
            with Path(args.audit).open('x') as stream:
                json.dump(audit, stream, indent=2)
                stream.write('\n')
        else:
            result = mean_rate_reference(training, query)
        with Path(args.output).open('xb') as stream:
            np.savez_compressed(stream, **result)


if __name__ == '__main__':
    main()
