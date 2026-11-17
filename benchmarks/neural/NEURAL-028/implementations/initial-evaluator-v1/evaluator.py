"""NEURAL-028 signal-derived construction evaluator; see README for prospective policy."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path

import numpy as np

TASK_ID = 'NEURAL-028'
SOURCE_REVISION = 'ba64ac697f5d9914926baac79399e80707a5f3a6'
AREAS = {'V1': (8,), 'mHV': (0, 1, 2, 9), 'lHV': (5, 6), 'aHV': (3, 4)}
REGIMES = ('unsup', 'sup', 'naive', 'grating')
PHASES = ('before', 'after')


class ContractError(ValueError):
    """Input cannot support the frozen numerical contract."""


def require(condition, message):
    if not condition:
        raise ContractError(message)


def finite(values, name, ndim=None):
    try:
        arr = np.asarray(values, dtype=float)
    except (ValueError, TypeError) as exc:
        raise ContractError(f'{name}: nonnumeric input') from exc
    require(ndim is None or arr.ndim == ndim, f'{name}: wrong dimensionality')
    require(np.all(np.isfinite(arr)), f'{name}: nonfinite value')
    return arr


def integer(values, name):
    arr = finite(values, name, 1)
    require(np.all(arr == np.floor(arr)), f'{name}: must contain integers')
    return arr.astype(np.int64)


def text(value, name):
    require(isinstance(value, str) and bool(value.strip()), f'{name}: nonempty string required')
    return value


def scalar(value, name):
    require(type(value) in (int, float), f'{name}: numeric scalar required')
    require(math.isfinite(value), f'{name}: finite scalar required')
    return float(value)


def boolean(values, name):
    require(isinstance(values, list) and all(type(v) is bool for v in values),
            f'{name}: JSON booleans required')
    return np.array(values, dtype=bool)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                    allow_nan=False).encode()).hexdigest()


def dprime(x1, x2, w1=None, w2=None):
    """Source statistic with ddof=0; undefined denominators stay explicit NaN internally."""
    x1, x2 = finite(x1, 'x1', 2), finite(x2, 'x2', 2)
    require(x1.shape[0] == x2.shape[0], 'dprime neuron counts differ')
    require(x1.shape[1] >= 2 and x2.shape[1] >= 2, 'dprime requires at least two observations per arm')
    moments = []
    for x, weights in ((x1, w1), (x2, w2)):
        w = np.ones(x.shape[1]) if weights is None else finite(weights, 'weights', 1)
        require(w.shape == (x.shape[1],) and np.all(w > 0), 'invalid dprime weights')
        w = w / w.sum()
        # Center before summing: identical 0.1 samples with unequal arm sizes must
        # not acquire rounding-only dispersion and a spurious finite d-prime.
        centered = x - x[:, :1]
        offset = centered @ w
        mean = x[:, 0] + offset
        variance = ((centered - offset[:, None]) ** 2) @ w
        moments.append((mean, np.sqrt(variance)))
    denominator = moments[0][1] + moments[1][1]
    result = np.full(x1.shape[0], np.nan)
    np.divide(2 * (moments[0][0] - moments[1][0]), denominator,
              out=result, where=denominator > 0)
    return result


def nullable(values):
    return [float(v) if math.isfinite(float(v)) else None for v in values]


def fractions(dp, area_ids, threshold, stimulus_dp=None):
    """Retain every area neuron in denominators, withholding fractions if undefined."""
    output = {}
    for area, ids in AREAS.items():
        take = np.isin(area_ids, ids)
        n = int(take.sum())
        defined = np.isfinite(dp[take])
        if stimulus_dp is not None:
            defined &= np.isfinite(stimulus_dp[take])
        missing = n - int(defined.sum())
        item = {'n_neurons': n, 'undefined_neurons': missing, 'fraction': None}
        if n and not missing:
            flag = np.abs(dp[take]) >= threshold if stimulus_dp is None else (
                (dp[take] >= threshold) & (stimulus_dp[take] >= 0))
            item['fraction'] = float(flag.mean())
            if stimulus_dp is None:
                item.update(positive_fraction=float((dp[take] >= threshold).mean()),
                            negative_fraction=float((dp[take] <= -threshold).mean()))
        output[area] = item
    return output


def validate_packet(packet):
    require(isinstance(packet, dict) and packet.get('task_id') == TASK_ID, 'wrong task_id')
    require(type(packet.get('schema_version')) is int and packet['schema_version'] == 1, 'unsupported schema_version')
    protocol = packet.get('protocol', {})
    require(isinstance(protocol, dict), 'protocol must be object')
    require(protocol.get('source_revision') == SOURCE_REVISION, 'source revision mismatch')
    require(protocol.get('data_scope') == 'public_development_only', 'private qualification is not supported')
    text(protocol.get('phase_mapping_evidence'), 'phase_mapping_evidence')
    text(protocol.get('calibration_evidence'), 'calibration_evidence')
    require(protocol.get('selection_frozen_before_outcomes') is True, 'selection must be frozen before outcomes')
    require(protocol.get('fit_phases') == ['before'], 'v1 fits before phase only')
    require(protocol.get('activity_kind') == 'calcium_derived_activity', 'not electrode spike measurements')
    threshold = scalar(protocol.get('selectivity_threshold', 0.3), 'selectivity_threshold')
    require(math.isfinite(threshold) and threshold > 0, 'invalid selectivity threshold')
    require(protocol.get('reward_threshold', 0.3) == 0.3, 'source reward threshold must be 0.3')
    edges = {}
    for field in ('position_edges', 'movement_edges'):
        edges[field] = finite(protocol.get(field), field, 1)
        require(len(edges[field]) >= 2 and np.all(np.diff(edges[field]) > 0), f'{field}: increasing edges required')
    ridge = scalar(protocol.get('ridge_lambda', 0.001), 'ridge_lambda')
    require(math.isfinite(ridge) and ridge > 0, 'ridge_lambda must be positive')
    n_boot = protocol.get('bootstrap_replicates', 1000)
    require(type(n_boot) is int and 100 <= n_boot <= 10000, 'bootstrap_replicates must be 100..10000')
    seed = protocol.get('seed', 0)
    require(type(seed) is int and 0 <= seed < 2**32, 'invalid seed')
    n_shuffle = protocol.get('shuffle_replicates', 100)
    require(type(n_shuffle) is int and 10 <= n_shuffle <= 1000, 'shuffle_replicates must be 10..1000')
    declared = packet.get('session_manifest')
    require(isinstance(declared, list) and bool(declared), 'complete selected session_manifest required')
    expected, animals = {}, {}
    for record in declared:
        require(isinstance(record, dict), 'manifest record must be object')
        key = text(record.get('session_id'), 'session_id')
        require(key not in expected, 'duplicate manifest session_id')
        for field in ('mname', 'datexp', 'blk', 'source_asset_sha256', 'mapping_evidence'):
            text(record.get(field), field)
        require(len(record['source_asset_sha256']) == 64 and all(c in '0123456789abcdef' for c in record['source_asset_sha256']), 'invalid source asset SHA256')
        require(record.get('regime') in REGIMES and record.get('phase') in PHASES, 'unrecognized regime or phase')
        animal = record['mname']
        if animal in animals:
            require(animals[animal] == record['regime'], 'animal assigned to multiple exposure regimes')
        animals[animal] = record['regime']
        expected[key] = record
    tuples = [(r['mname'], r['datexp'], r['blk']) for r in declared]
    require(len(tuples) == len(set(tuples)), 'duplicate biological session tuple')
    require(len(animals) >= 3, 'at least three animals required for held-animal fitting')
    require({'unsup', 'sup'} <= set(animals.values()), 'both reward-free and rewarded regimes required')
    for animal in animals:
        require({r['phase'] for r in declared if r['mname'] == animal} == set(PHASES),
                f'{animal}: incomplete declared before/after population')
    raw = packet.get('sessions')
    require(isinstance(raw, list), 'sessions must be list')
    require(len(raw) == len(expected), 'session population incomplete')
    sessions = []
    seen = set()
    for item in raw:
        require(isinstance(item, dict), 'session must be object')
        key = text(item.get('session_id'), 'session_id')
        require(key in expected and key not in seen, 'unknown or duplicate session')
        seen.add(key)
        meta = expected[key]
        s = dict(meta)
        s['activity'] = finite(item.get('activity'), f'{key}.activity', 2)
        nn, nf = s['activity'].shape
        require(nn > 0 and nf > 0, 'empty activity')
        s['area_ids'] = integer(item.get('area_ids'), 'area_ids')
        require(s['area_ids'].shape == (nn,), 'area/neuron mismatch')
        require(np.all(np.isin(s['area_ids'], list(range(-1, 10)))), 'unknown area ID')
        for field in ('trial_id', 'stimulus_id'):
            s[field] = integer(item.get(field), field)
        for field in ('position', 'movement'):
            s[field] = finite(item.get(field), field, 1)
        for field in ('corridor', 'gray'):
            s[field] = boolean(item.get(field), field)
        for field in ('trial_id', 'stimulus_id', 'position', 'movement', 'corridor', 'gray'):
            require(s[field].shape == (nf,), f'{field}: frame count mismatch; no silent truncation')
        require(not np.any(s['corridor'] & s['gray']), 'corridor and gray masks overlap')
        require(np.all(s['trial_id'] >= 0), 'negative trial IDs')
        require(np.all((s['stimulus_id'] >= 0) & (s['stimulus_id'] <= 6)), 'unknown stimulus ID')
        s['trial_stimulus_id'] = integer(item.get('trial_stimulus_id'), 'trial_stimulus_id')
        nt = len(s['trial_stimulus_id'])
        require(nt > 0 and set(s['trial_id']) == set(range(nt)), 'trial population missing or not zero-based contiguous')
        require(np.all((s['trial_stimulus_id'] >= 0) & (s['trial_stimulus_id'] <= 6)), 'unknown trial stimulus ID')
        require(np.array_equal(s['stimulus_id'], s['trial_stimulus_id'][s['trial_id']]), 'frame/trial stimulus mismatch')
        s['sound_del_pos'] = finite(item.get('sound_del_pos'), 'sound_del_pos', 1)
        require(s['sound_del_pos'].shape == (nt,), 'cue/trial population mismatch')
        s['position_activity'] = finite(item.get('position_activity'), 'position_activity', 3)
        require(s['position_activity'].shape == (nn, nt, 60), 'position_activity must be neurons x trials x 60')
        text(item.get('interpolation_evidence'), 'interpolation_evidence')
        s['valid'] = s['corridor'] & (s['movement'] > 0)
        for stimulus in (0, 2):
            require(np.sum(s['valid'] & (s['stimulus_id'] == stimulus)) >= 2, 'insufficient moving corridor frames per stimulus')
        require(np.any(s['gray'] & (s['movement'] > 0)), 'moving gray baseline absent')
        for field in ('position', 'movement'):
            edge = edges[field + '_edges']
            values = s[field][s['valid']]
            require(np.all((values >= edge[0]) & (values < edge[-1])), f'{field}: eligible frame outside frozen bins')
        pbin = np.searchsorted(edges['position_edges'], s['position'], side='right') - 1
        mbin = np.searchsorted(edges['movement_edges'], s['movement'], side='right') - 1
        s['stratum'] = pbin * (len(edges['movement_edges']) - 1) + mbin
        sessions.append(s)
    return sorted(sessions, key=lambda s: s['session_id']), protocol


def matching_weights(sessions):
    """Uniform common strata across every selected session and both stimuli, no neural selection."""
    supports = []
    for s in sessions:
        for stim in (2, 0):
            idx = s['valid'] & (s['stimulus_id'] == stim)
            values, counts = np.unique(s['stratum'][idx], return_counts=True)
            supports.append(set(values[counts >= 2]))
    common = sorted(set.intersection(*supports))
    require(bool(common), 'no common movement/position support across the complete selected population')
    result = {}
    for s in sessions:
        result[s['session_id']] = {}
        for stim in (2, 0):
            eligible = s['valid'] & (s['stimulus_id'] == stim)
            idx = eligible & np.isin(s['stratum'], common)
            strata, counts = np.unique(s['stratum'][idx], return_counts=True)
            inverse = dict(zip(strata, 1 / counts))
            weights = np.array([inverse[v] / len(common) for v in s['stratum'][idx]])
            result[s['session_id']][stim] = (idx, weights, {
                'eligible_frames': int(eligible.sum()), 'retained_frames': int(idx.sum()),
                'coverage': float(idx.sum() / eligible.sum()),
                'retained_trials': int(len(np.unique(s['trial_id'][idx])))})
    return common, result


def session_metrics(s, matched, threshold):
    idx2 = s['valid'] & (s['stimulus_id'] == 2)
    idx0 = s['valid'] & (s['stimulus_id'] == 0)
    raw = dprime(s['activity'][:, idx2], s['activity'][:, idx0])
    i2, w2, c2 = matched[2]
    i0, w0, c0 = matched[0]
    controlled = dprime(s['activity'][:, i2], s['activity'][:, i0], w2, w0)
    cue = np.mod(s['sound_del_pos'], 60)
    cut = float(cue.mean())  # Source threshold includes every trial, not rewarded trials alone.
    reward_trials = s['trial_stimulus_id'] == 2
    late, early = reward_trials & (cue > cut), reward_trials & (cue <= cut)
    reward_dp = np.full(len(raw), np.nan)
    if late.sum() >= 2 and early.sum() >= 2:
        trial_response = s['position_activity'][:, :, 5:40].mean(axis=2)
        reward_dp = dprime(trial_response[:, late], trial_response[:, early])
    gray = s['gray'] & (s['movement'] > 0)
    baseline = {}
    for area, codes in AREAS.items():
        take = np.isin(s['area_ids'], codes)
        baseline[area] = float(s['activity'][take][:, gray].mean()) if take.any() else None
    return {'session_id': s['session_id'], 'mname': s['mname'], 'regime': s['regime'], 'phase': s['phase'],
            'source_selectivity_dprime': nullable(raw), 'matched_selectivity_dprime': nullable(controlled),
            'source_reward_dprime': nullable(reward_dp),
            'source_selectivity': fractions(raw, s['area_ids'], threshold),
            'matched_selectivity': fractions(controlled, s['area_ids'], threshold),
            'source_reward': fractions(reward_dp, s['area_ids'], 0.3, raw),
            'baseline_activity': baseline,
            'matching': {'stimulus_2': c2, 'stimulus_0': c0},
            'reward_split': {'all_trial_cue_mean_mod60': cut, 'late_stimulus2_trials': int(late.sum()),
                             'early_stimulus2_trials': int(early.sum()), 'behavior_matched': False,
                             'stimulus2_does_not_imply_delivered_reward': True},
            'excluded_nonvisual_neurons': int(np.isin(s['area_ids'], (-1, 7)).sum())}


def interval(values, rng, n_boot):
    """Bootstrap only biological units; singleton results remain descriptive."""
    values = np.asarray(values, dtype=float)
    if len(values) < 2:
        return None
    resamples = rng.choice(values, size=(n_boot, len(values)), replace=True).mean(axis=1)
    return [float(v) for v in np.quantile(resamples, [0.025, 0.975])]


def trial_shuffle_control(sessions, protocol):
    """Whole-trial stimulus null within identical observed movement-position profiles.

    This is a diagnostic under a prospective exchangeability restriction, not a
    calibrated causal test. Reward-cue labels and neural activity are never shuffled.
    """
    rng = np.random.default_rng(protocol.get('seed', 0))
    output = []
    for s in sessions:
        groups = defaultdict(list)
        for trial in range(len(s['trial_stimulus_id'])):
            if s['trial_stimulus_id'][trial] not in (0, 2):
                continue
            values, counts = np.unique(s['stratum'][s['valid'] & (s['trial_id'] == trial)], return_counts=True)
            profile = tuple(zip(values.tolist(), counts.tolist()))
            if profile:
                groups[profile].append(trial)
        exchangeable = [trials for trials in groups.values() if len(set(s['trial_stimulus_id'][trials])) > 1]
        total_trials = int(np.isin(s['trial_stimulus_id'], (0, 2)).sum())
        movable_trials = sum(map(len, exchangeable))
        row = {'session_id': s['session_id'], 'exchangeable_trials': movable_trials,
               'total_stimulus0_2_trials': total_trials, 'fixed_stimulus0_2_trials': total_trials - movable_trials,
               'n_profile_groups': len(exchangeable), 'null_fraction_means': {area: None for area in AREAS},
               'status': 'held_no_exchangeable_trials'}
        if exchangeable:
            draws = {area: [] for area in AREAS}
            for _ in range(protocol.get('shuffle_replicates', 100)):
                labels = s['trial_stimulus_id'].copy()
                for trials in exchangeable:
                    labels[trials] = rng.permutation(labels[trials])
                frame_labels = labels[s['trial_id']]
                dp = dprime(s['activity'][:, s['valid'] & (frame_labels == 2)],
                            s['activity'][:, s['valid'] & (frame_labels == 0)])
                fr = fractions(dp, s['area_ids'], float(protocol.get('selectivity_threshold', 0.3)))
                for area in AREAS:
                    draws[area].append(fr[area]['fraction'])
            row.update(status='computed_diagnostic', replicates=protocol.get('shuffle_replicates', 100))
            row['null_fraction_means'] = {area: float(np.mean(v)) if all(x is not None for x in v) else None
                                           for area, v in draws.items()}
        output.append(row)
    return output


def paired_contrasts(metrics, protocol):
    rng = np.random.default_rng(protocol.get('seed', 0))
    n_boot = protocol.get('bootstrap_replicates', 1000)
    output = {}
    for metric in ('source_selectivity', 'matched_selectivity', 'source_reward', 'baseline_activity'):
        output[metric] = {}
        for area in AREAS:
            groups = defaultdict(lambda: defaultdict(list))
            regime = {}
            for s in metrics:
                value = s[metric][area] if metric == 'baseline_activity' else s[metric][area]['fraction']
                groups[s['mname']][s['phase']].append(value)
                regime[s['mname']] = s['regime']
            deltas, invalid = defaultdict(list), defaultdict(list)
            animal_rows = []
            for animal in sorted(groups):
                phases = groups[animal]
                if any(v is None for phase in PHASES for v in phases[phase]):
                    invalid[regime[animal]].append(animal)
                    animal_rows.append({'mname': animal, 'regime': regime[animal], 'delta': None})
                    continue
                before, after = (float(np.mean(phases[p])) for p in PHASES)
                delta = after - before
                deltas[regime[animal]].append(delta)
                animal_rows.append({'mname': animal, 'regime': regime[animal], 'before': before,
                                    'after': after, 'delta': delta,
                                    'n_before_sessions': len(phases['before']), 'n_after_sessions': len(phases['after'])})
            by_regime = {}
            for name in sorted(set(regime.values())):
                vals = deltas[name]
                complete = not invalid[name] and bool(vals)
                by_regime[name] = {'n_animals': sum(r == name for r in regime.values()),
                                   'undefined_animals': invalid[name], 'mean_delta': float(np.mean(vals)) if complete else None,
                                   'ci95': interval(vals, rng, n_boot) if complete else None,
                                   'inference': 'animal_bootstrap' if complete and len(vals) > 1 else 'descriptive_or_held'}
            cross = {'contrast': 'sup_delta_minus_unsup_delta', 'estimate': None, 'ci95': None}
            if all(by_regime[r]['mean_delta'] is not None for r in ('sup', 'unsup')):
                cross['estimate'] = by_regime['sup']['mean_delta'] - by_regime['unsup']['mean_delta']
                if all(len(deltas[r]) >= 2 for r in ('sup', 'unsup')):
                    sampled = [rng.choice(deltas[r], (n_boot, len(deltas[r])), replace=True).mean(axis=1) for r in ('sup', 'unsup')]
                    cross['ci95'] = [float(v) for v in np.quantile(sampled[0] - sampled[1], [0.025, 0.975])]
            output[metric][area] = {'animals': animal_rows, 'regimes': by_regime, 'between_regime': cross}
    return output


def explanatory_baseline(sessions, protocol):
    """Before-only fitting; entire test animal excluded. Targets never enter predictors."""
    animals = sorted({s['mname'] for s in sessions})
    output = {}
    for area, codes in AREAS.items():
        # Missing an area's measurements in any declared session holds this area's full endpoint.
        absent = [s['session_id'] for s in sessions if not np.isin(s['area_ids'], codes).any()]
        if absent:
            output[area] = {'status': 'held_missing_area', 'sessions': absent}
            continue
        folds = []
        for animal in animals:
            train = [s for s in sessions if s['mname'] != animal and s['phase'] == 'before']
            test = [s for s in sessions if s['mname'] == animal]
            require(len({s['mname'] for s in train}) >= 2, 'fewer than two fitting animals')
            per_animal = {a: sum(s['mname'] == a for s in train) for a in {s['mname'] for s in train}}
            design, target, weights = [], [], []
            for s in train:
                take = s['valid'] & np.isin(s['stimulus_id'], (0, 2))
                x = np.column_stack((s['position'][take], s['movement'][take], (s['stimulus_id'][take] == 2).astype(float)))
                y = s['activity'][np.isin(s['area_ids'], codes)][:, take].mean(axis=0)
                design.append(x)
                target.append(y)
                weights.append(np.full(len(y), 1 / (len(per_animal) * per_animal[s['mname']] * len(y))))
            x, y, w = np.vstack(design), np.concatenate(target), np.concatenate(weights)
            centered_x = x - x[:1]
            xoffset = w @ centered_x
            center = x[0] + xoffset
            scale = np.sqrt(w @ ((centered_x - xoffset) ** 2))
            scale[scale == 0] = 1
            z = (x - center) / scale
            centered_y = y - y[0]
            yoffset = float(w @ centered_y)
            yvariance = float(w @ ((centered_y - yoffset) ** 2))
            models = {}
            for model, n_features in (('behavior_only', 2), ('behavior_plus_stimulus', 3)):
                a = np.column_stack((np.ones(len(z)), z[:, :n_features]))
                penalty = np.diag([0.] + [float(protocol.get('ridge_lambda', 0.001))] * n_features)
                coef = np.linalg.solve(a.T @ (w[:, None] * a) + penalty, a.T @ (w * y))
                rows = []
                for s in test:
                    take = s['valid'] & np.isin(s['stimulus_id'], (0, 2))
                    tx = np.column_stack((s['position'][take], s['movement'][take], (s['stimulus_id'][take] == 2).astype(float)))
                    tz = (tx - center) / scale
                    ty = s['activity'][np.isin(s['area_ids'], codes)][:, take].mean(axis=0)
                    predicted = np.column_stack((np.ones(len(tz)), tz[:, :n_features])) @ coef
                    residual = ty - predicted
                    mse = float(np.mean(residual ** 2))
                    rows.append({'session_id': s['session_id'], 'phase': s['phase'],
                                 'frame_indices': np.flatnonzero(take).tolist(), 'prediction': predicted.tolist(),
                                 'residual': residual.tolist(), 'mse': mse,
                                 'train_variance_scaled_mse': mse / yvariance if yvariance > 0 else None})
                phase_mse = {phase: float(np.mean([row['mse'] for row in rows if row['phase'] == phase])) for phase in PHASES}
                models[model] = {'coefficients': coef.tolist(), 'sessions': rows,
                                 'phase_mse': phase_mse, 'after_minus_before_mse': phase_mse['after'] - phase_mse['before'],
                                 'animal_mse': float(np.mean(list(phase_mse.values())))}
            folds.append({'held_out_mname': animal, 'fitting_mnames': sorted(per_animal),
                          'fitting_session_ids': [s['session_id'] for s in train],
                          'fitting_phases': ['before'], 'feature_center': center.tolist(), 'feature_scale': scale.tolist(),
                          'training_target_variance': yvariance, 'models': models})
        output[area] = {'status': 'computed_public_development', 'folds': folds,
                        'macro_animal_mse': {name: float(np.mean([f['models'][name]['animal_mse'] for f in folds]))
                                             for name in ('behavior_only', 'behavior_plus_stimulus')}}
    return output


def evaluate(packet):
    sessions, protocol = validate_packet(packet)
    common, matches = matching_weights(sessions)
    metrics = [session_metrics(s, matches[s['session_id']], float(protocol.get('selectivity_threshold', 0.3))) for s in sessions]
    result = {'task_id': TASK_ID, 'implementation': 'initial-evaluator-v1',
              'input_sha256': digest(packet), 'protocol_sha256': digest(protocol),
              'scientific_qualification': 'unknown', 'data_scope': 'public_development_only',
              'population': {'animals': sorted({s['mname'] for s in sessions}),
                             'session_ids': [s['session_id'] for s in sessions],
                             'n_sessions': len(sessions), 'n_frames': sum(s['activity'].shape[1] for s in sessions)},
              'matching': {'common_strata': [int(v) for v in common],
                           'estimand': 'equal common movement-position strata across all selected sessions and both stimuli'},
              'sessions': metrics, 'contrasts': paired_contrasts(metrics, protocol),
              'trial_shuffle_control': trial_shuffle_control(sessions, protocol),
              'held_animal_explanation': explanatory_baseline(sessions, protocol),
              'holds': ['authentic_payload_and_complete_native_cohort_not_verified',
                        'native_interpolation_and_cross_session_calibration_not_verified',
                        'source_reward_contrast_is_not_behavior_matched',
                        'source_reference_not_executed', 'scientific_admission_not_established',
                        'public_development_only_no_protected_evaluation']}
    json.dumps(result, allow_nan=False)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('packet', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    packet = json.loads(args.packet.read_text(), parse_constant=lambda x: (_ for _ in ()).throw(ContractError(f'JSON nonfinite: {x}')))
    result = evaluate(packet)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')


if __name__ == '__main__':
    main()
