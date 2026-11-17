"""Original rat geometry/readout and GLM participation-ratio result adapters.

The complete route is code19: 500 repetitions, 500 observations, 300 training
observations and 19 neurons for both areas. Paper CA1=24 is an unresolved source
discrepancy, not silently substituted. No I/O or fitting occurs on import.

Random draws follow the source order, with an explicitly current, serial SVC
seed policy. The historical parallel worker RNG/order is not reconstructed.
"""
from __future__ import annotations

import hashlib
import importlib.metadata
import importlib.util
import json
from pathlib import Path
import sys
import warnings

import numpy as np

_SPEC = importlib.util.spec_from_file_location(
    '_population_geometry_retained_kernels',
    Path(__file__).resolve().parents[1] / 'initial-evaluator-v1/evaluator.py')
K = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = K
_SPEC.loader.exec_module(K)
ContractError = K.ContractError
ANIMALS = tuple(K.ANIMALS)
REGIONS = ('CA1', 'PFC')
SESSIONS = tuple(range(1, 9))
REPETITIONS = 500
OBSERVATIONS = 500
TRAINING = 300
NEURONS = 19
TEACHERS = 500
REGION_SEEDS = {'CA1': 213423, 'PFC': 45342}
GEOMETRY_FIELDS = ('dimensionality', 'alignment', 'signal_noise_factor',
                   'signal_signal_factor', 'normalized_task_dimension',
                   'normalized_latent_dimension', 'weighted_factorization',
                   'generalization_error')
RNG_POLICY = ('Current explicit MT19937 source-style row/unit/teacher/train draws; '
              'serial LinearSVC uses independent per-task seeds derived from the '
              'pre-draw state. Original n_jobs=-1/random_state=None worker stream '
              'and historical unsorted animal order are not authenticated.')
SVC_POLICY = 'current_serial_seeded_v1'
SVC_LITERAL_POLICY = 'source_random_state_none'


def need(condition, message):
    if not condition:
        raise ContractError(message)


def indices(value, n, name, *, count=None):
    a = np.asarray(value)
    need(a.ndim == 1 and a.dtype.kind in 'iu' and a.size > 0
         and len(np.unique(a)) == len(a) and (a >= 0).all() and (a < n).all()
         and (count is None or len(a) == count), name + ' must be unique in-range integer indices')
    return a.astype(np.int64, copy=False)


def identities(value, n, name):
    a = np.asarray(value)
    need(a.shape == (n,) and a.dtype.kind in 'iuU' and len(np.unique(a)) == n,
         name + ' must contain unique native integer or string identities')
    need(bool((a >= 0).all()) if a.dtype.kind in 'iu' else bool((np.char.str_len(a) > 0).all()),
         name + ' must be nonnegative integers or nonempty strings')
    return a


def state(rng):
    need(isinstance(rng, np.random.RandomState), 'explicit numpy RandomState required')
    name, keys, position, has_gauss, cached = rng.get_state()
    return {'algorithm': name, 'keys': keys.tolist(), 'position': int(position),
            'has_gauss': int(has_gauss), 'cached_gaussian': float(cached)}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                     allow_nan=False).encode()).hexdigest()


def array_identity(value):
    a = np.ascontiguousarray(value)
    header = json.dumps({'dtype': a.dtype.str, 'shape': list(a.shape)},
                        sort_keys=True, separators=(',', ':')).encode()
    return {'shape': list(a.shape), 'dtype': a.dtype.str,
            'sha256': hashlib.sha256(header + b'\n' + a.tobytes()).hexdigest()}


def glm_pr_result(counts, expected_counts, cv_scores, selected_alpha_indices,
                  unit_ids, *, rng, case_id, row_ids):
    """Source format_glm_results for one complete region/session.

    PR uses all eligible recorded-speed rows and independent raw/fitted draws.
    A nonpositive selected mean or fewer than nine valid folds nulls that unit's
    fitted series only. Source NaN population means remain NaN, never dropped.
    """
    x = K.counts_array(counts, len(counts))
    fitted = K.matrix(expected_counts, 'full-row expected counts')
    need(x.shape == fitted.shape and (fitted >= 0).all() and x.shape[1] >= NEURONS,
         'aligned expected counts and at least19 eligible neurons required')
    native_units = identities(unit_ids, x.shape[1], 'unit IDs')
    native_rows = identities(row_ids, len(x), 'GLM row IDs')
    need(case_id in {f'{a}-s{s:02d}-{r}' for a in ANIMALS for s in SESSIONS for r in REGIONS},
         'known complete-panel case ID required')
    scores = np.asarray(cv_scores, dtype=float)
    need(scores.shape == (x.shape[1], 10, 10),
         'complete ten-alpha by ten-fold scores required for every unit')
    selected = np.asarray(selected_alpha_indices)
    need(selected.shape == (x.shape[1],) and selected.dtype.kind in 'iu'
         and (selected >= 0).all() and (selected < 10).all(), 'selected alpha indices invalid')
    valid_all = np.sum(~np.isnan(scores), axis=2)
    with np.errstate(invalid='ignore'):
        means = np.divide(np.nansum(scores, axis=2), valid_all,
                          out=np.full(scores.shape[:2], np.nan), where=valid_all > 0)
    need(np.array_equal(selected, np.argmax(means, axis=1)),
         'selected alpha indices must preserve source argmax of per-alpha nanmeans')
    before = state(rng)
    subsets = [[rng.choice(x.shape[1], NEURONS, replace=False),
                rng.choice(x.shape[1], NEURONS, replace=False)] for _ in range(REPETITIONS)]
    selected_scores = scores[np.arange(x.shape[1]), selected]
    valid = valid_all[np.arange(x.shape[1]), selected]
    selected_means = means[np.arange(x.shape[1]), selected]
    suppressed = (selected_means <= 0) | (valid < 9) | np.isnan(selected_means)
    fitted = fitted.copy()
    fitted[:, suppressed] = 0
    prs = np.asarray([[K.participation_ratio(x[:, a]), K.participation_ratio(fitted[:, b])]
                      for a, b in subsets])
    with np.errstate(invalid='ignore'):
        # nanstd removes only original NaNs; an infinite observation has undefined
        # deviation. It must not become zero through a second NaN omission.
        deviations = np.where(np.isnan(selected_scores), 0, selected_scores - selected_means[:, None])
        variance = np.divide(np.sum(deviations ** 2, axis=1), valid,
                             out=np.full(x.shape[1], np.nan), where=valid > 0)
    sem = np.divide(np.sqrt(variance), np.sqrt(valid),
                    out=np.full(x.shape[1], np.nan), where=valid > 0)
    draws = np.asarray(subsets, dtype=np.int64)
    result = {'raw_pr': float(prs[:, 0].mean()), 'fitted_pr': float(prs[:, 1].mean()),
              'mean_selected_cv_d2': float(selected_means.mean()),
              'suppressed_units': np.flatnonzero(suppressed), 'selected_valid_folds': valid,
              'subset_pr': prs}
    result.update(schema='source_glm_pr_session_v1', condition='current_source_code19',
                  case_id=case_id, row_ids=native_rows,
                  repetitions=REPETITIONS, neuron_count=NEURONS,
                  selected_alpha_indices=selected.copy(),
                  selected_cv_d2_per_unit=selected_means,
                  selected_cv_fold_population_sd=np.sqrt(variance),
                  selected_cv_sem_per_unit=sem, mean_selected_cv_sem=float(np.mean(sem)),
                  unit_ids=native_units, subset_unit_positions=draws,
                  subset_unit_ids=native_units[draws], rng_before=before,
                  rng_after=state(rng), rng_policy=RNG_POLICY,
                  historical_realization_authenticated=False,
                  population_mean_policy='ordinary mean across every unit; NaN remains unavailable',
                  source_unit_policy='CA1=19,PFC=19; paper CA1=24 remains unreconciled')
    return result


def behavior_result(packet):
    """Original equal-trial mean requires complete epoch trial support.

    Time-bin metadata cannot prove that short trials with no retained midpoint
    are included. Without an explicit full epoch table the result is unavailable.
    """
    full = packet.get('epoch_trials')
    coverage = packet.get('complete_trial_support')
    if full is None and coverage is not None:
        required = {'coverage_sha256', 'design_sha256', 'case_id', 'source_trial_count'}
        need(isinstance(coverage, dict) and required <= set(coverage)
             and coverage['case_id'] == packet.get('case_id')
             and type(coverage['source_trial_count']) is int and coverage['source_trial_count'] > 0,
             'complete-trial provenance/case/count mismatch')
        need(all(isinstance(coverage[k], str) and len(coverage[k]) == 64
                 and all(c in '0123456789abcdef' for c in coverage[k])
                 for k in ('coverage_sha256', 'design_sha256')),
             'complete-trial proof and design hashes required')
        z = K.latents(packet['z'])
        trial = np.asarray(packet['trial'])
        need(trial.shape == (len(z),) and trial.dtype.kind in 'iu' and (trial >= 0).all(),
             'native trial IDs required')
        ids = np.unique(trial)
        need(len(ids) == coverage['source_trial_count'], 'complete source-trial count mismatch')
        correct = []
        for tid in ids:
            values = np.unique(z[trial == tid, 5])
            need(len(values) == 1 and values[0] in (0, 1), 'trial correctness must be constant binary')
            correct.append(values[0])
        return {'accuracy': float(np.mean(correct)), 'status': 'declared_complete_epoch_trial_mean',
                'trial_count': len(ids), 'trial_ids': ids, 'coverage': dict(coverage),
                'source_table_authentication': 'caller authenticated full-trial proof and packet/design; adapter validates count and constant correctness'}
    if full is None:
        return {'accuracy': None, 'status': 'unavailable_complete_epoch_trial_table',
                'reason': 'source groups all original trials by epoch; packet bins may omit short trials'}
    need(isinstance(full, dict) and {'trial_ids', 'correct', 'source_binding'} <= set(full),
         'epoch_trials requires complete trial IDs, correctness and source binding')
    correct = np.asarray(full['correct'])
    trial_ids = identities(full['trial_ids'], len(correct), 'complete epoch trial IDs')
    need(correct.ndim == 1 and len(correct) > 0 and correct.dtype.kind in 'biuf'
         and np.isfinite(correct).all() and np.isin(correct, [0, 1]).all()
         and isinstance(full['source_binding'], str) and bool(full['source_binding'].strip()),
         'finite binary complete-epoch correctness and source binding required')
    bins = np.asarray(packet['trial'])
    z = K.latents(packet['z'])
    need(bins.shape == (len(z),) and np.isin(bins, trial_ids).all(),
         'all packet trials must join complete epoch table')
    for trial_id, value in zip(trial_ids, correct):
        need(np.all(z[bins == trial_id, 5] == value), 'trial correctness differs from packet')
    return {'accuracy': float(correct.mean()), 'status': 'declared_complete_epoch_trial_mean',
            'trial_count': len(correct), 'trial_ids': trial_ids,
            'source_binding': full['source_binding'],
            'source_table_authentication': 'caller supplied; adapter validates join, not upstream completeness'}


def prepare_geometry(packet, region):
    """Keep native row/unit identity through the source derived-speed mask.

    packet x is region-specific unfiltered count data; z has seven original
    latent columns. row_ids identify the original bins, not a new permutation.
    Optional epoch_trials supplies complete trial-level behavior support.
    """
    need(region in REGIONS, 'unknown region')
    need(isinstance(packet, dict) and {'x', 'z', 'unit_ids', 'row_ids', 'trial', 't'} <= set(packet),
         'complete source session packet required')
    z = K.latents(packet['z'])
    x = K.counts_array(packet['x'], len(z))
    native_rows = identities(packet['row_ids'], len(x), 'row IDs')
    native_units = identities(packet['unit_ids'], x.shape[1], 'unit IDs')
    times = np.asarray(packet['t'])
    trials = np.asarray(packet['trial'])
    need(times.shape == trials.shape == (len(z),) and times.dtype.kind in 'fiu'
         and np.isfinite(times).all() and (np.diff(times) > 0).all(),
         'aligned strictly increasing source times and trial IDs required')
    need(trials.dtype.kind in 'iu' and (trials >= 0).all(), 'native nonnegative trial IDs required')
    xx, zz, row_mask, unit_mask = K.prepare_geometry_session(
        z, x, np.full(x.shape[1], region), region)
    need(xx.shape[0] >= OBSERVATIONS and xx.shape[1] >= NEURONS,
         'source geometry requires at least500 rows and19 neurons after its own filters')
    return {'x': xx, 'z': zz, 'row_ids': native_rows[row_mask],
            'unit_ids': native_units[unit_mask], 'behavior': behavior_result(packet),
            't': times[row_mask], 'trial': trials[row_mask],
            'row_mask': row_mask, 'unit_mask': unit_mask,
            'preprocessing': 'full session derived velocity norm>4; rate>0.1Hz; x std+0.01; z population zscore before row subset'}


def readout(points, latents, *, rng, svc_policy):
    """Exact source task filtering/Hebbian error plus serial current SVC route.

    Task-balance filtering sees all500 observations, including eventual test
    rows. Zero Hebbian margins are not errors in the original theta convention.
    """
    x, z = K.matrix(points, 'readout points'), K.matrix(latents, 'readout latents', 4)
    need(svc_policy in (SVC_POLICY, SVC_LITERAL_POLICY),
         'explicit current or literal source SVC policy required; historical RNG is not inferred')
    need(x.shape == (OBSERVATIONS, NEURONS) and len(z) == OBSERVATIONS,
         'readout requires500 observations,19 neurons and4 latents')
    before = state(rng)
    teachers = rng.randn(4, TEACHERS)
    all_labels = np.sign(z @ teachers)
    valid = np.flatnonzero(np.abs(all_labels.mean(axis=0)) < 0.25)
    need(len(valid) > 100, 'source requires strictly more than100 balanced tasks')
    labels = all_labels[:, valid]
    train = rng.choice(OBSERVATIONS, size=TRAINING, replace=False)
    test = np.setdiff1d(np.arange(OBSERVATIONS), train)
    weights = labels[train].T @ x[train] / TRAINING
    predicted = np.sign(x[test] @ weights.T)
    errors = np.mean(-labels[test] * predicted > 0, axis=0)
    from sklearn.svm import LinearSVC
    # The original parallel unspecified worker RNG cannot be reconstructed.
    # Separate seeds avoid changing the source row/unit/teacher/train stream.
    seed_prefix = digest(before)
    svc_seeds = np.array([int(hashlib.sha256((seed_prefix + ':' + str(int(i))).encode()).hexdigest()[:8], 16)
                          for i in valid], dtype=np.uint32)
    svc_errors = []
    warning_records = []
    for column, task in enumerate(valid):
        ytrain = (1 + labels[train, column]) / 2
        ytest = (1 + labels[test, column]) / 2
        classifier = LinearSVC(dual='auto', max_iter=10000,
                               random_state=int(svc_seeds[column]) if svc_policy == SVC_POLICY else None)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            classifier.fit(x[train], ytrain)
            svc_pred = classifier.predict(x[test])
        warning_records.extend({'teacher_index': int(task), 'category': type(w.message).__name__,
                                'message': str(w.message)} for w in caught)
        # The author retains predictions when convergence warnings occur. Keep
        # the warnings visible without silently changing this source behavior.
        svc_errors.append(float(np.mean(svc_pred != ytest)))
    return {'hebbian_error': float(np.mean(errors)),
            'hebbian_task_population_sd': float(np.std(errors)), 'hebbian_task_errors': errors,
            'svc_error': float(np.mean(svc_errors)), 'svc_task_errors': np.asarray(svc_errors),
            'teacher_identity': array_identity(teachers), 'valid_teacher_indices': valid,
            'pre_teacher_state_sha256': seed_prefix, 'latent_identity': array_identity(z),
            'training_positions': train, 'test_positions': test,
            'svc_seeds': svc_seeds if svc_policy == SVC_POLICY else None,
            'svc_policy': svc_policy,
            'svc_parameters': {'dual': 'auto', 'max_iter': 10000, 'n_jobs': 1,
                               'random_state_policy': 'separate SHA256(pre-teacher MT19937 state, original teacher index)' if svc_policy == SVC_POLICY else 'literal random_state=None; runtime global RNG and worker history unbound'},
            'runtime': {k: importlib.metadata.version(k) for k in ('numpy', 'scipy', 'scikit-learn')},
            'warnings': warning_records, 'rng_before': before, 'rng_after': state(rng),
            'full500_row_task_balance_exposure': True,
            'rng_policy': RNG_POLICY if svc_policy == SVC_POLICY else
                          'Literal random_state=None, serial callable; global runtime RNG unbound; historical parallel realization unauthenticated'}


def geometry_repetition(points, latents, row_ids, unit_ids, *, rng, repetition, svc_policy):
    """One original-size draw; no relaxation argument exists for source sizes."""
    x, z = K.matrix(points, 'geometry points'), K.matrix(latents, 'geometry latents', 4)
    need(len(x) == len(z) and len(x) >= OBSERVATIONS and x.shape[1] >= NEURONS,
         'complete geometry row/neuron support required')
    need(type(repetition) is int and 0 <= repetition < REPETITIONS,
         'source repetition must be0..499')
    native_rows = identities(row_ids, len(x), 'row IDs')
    native_units = identities(unit_ids, x.shape[1], 'unit IDs')
    before = state(rng)
    rows = rng.choice(len(x), OBSERVATIONS, replace=False)
    units = rng.choice(x.shape[1], NEURONS, replace=False)
    xx, zz = x[rows][:, units], z[rows]
    joined = np.column_stack([xx, zz])
    joined -= joined.mean(axis=0)
    cov = joined.T @ joined / OBSERVATIONS
    phi = cov[:NEURONS, NEURONS:]
    need((np.linalg.norm(phi, axis=0) > 0).all(),
         'uncoupled latent makes source normalized coding-direction factor undefined')
    geometry = K.geometry_from_covariance(cov[:NEURONS, :NEURONS], phi,
                                          cov[NEURONS:, NEURONS:], TRAINING)
    empirical = readout(xx, zz, rng=rng, svc_policy=svc_policy)
    return {'schema': 'source_raw_geometry_repetition_v1', 'repetition': repetition,
            'condition': 'current_source_code19',
            'geometry_fields': list(GEOMETRY_FIELDS),
            'geometry_values': np.asarray([geometry[k] for k in GEOMETRY_FIELDS]),
            'theory_error': geometry['theory_error'], 'readout': empirical,
            'row_positions': rows, 'unit_positions': units,
            'row_ids': native_rows[rows], 'unit_ids': native_units[units],
            'training_row_ids': native_rows[rows[empirical['training_positions']]],
            'test_row_ids': native_rows[rows[empirical['test_positions']]],
            'rng_before': before, 'rng_after': state(rng),
            'historical_realization_authenticated': False, 'rng_policy': RNG_POLICY}


def geometry_plan():
    """All64000 raw geometry jobs in explicit current source-loop order."""
    for region in REGIONS:
        for repetition in range(REPETITIONS):
            for animal in ANIMALS:
                for session in SESSIONS:
                    yield {'case_id': f'{animal}-s{session:02d}-{region}',
                           'animal': animal, 'session': session, 'region': region,
                           'repetition': repetition, 'region_seed': REGION_SEEDS[region]}


def iter_geometry_panel(load_session, *, svc_policy):
    """Execute complete source-shaped panel, streaming one result at a time.

    Caller owns authentic input admission and persistence. This iterator never
    fits a Poisson GLM or substitutes GLM D2 for the geometry/readout family.
    """
    need(svc_policy in (SVC_POLICY, SVC_LITERAL_POLICY), 'explicit current or literal source SVC policy required')
    generators = {r: np.random.RandomState(REGION_SEEDS[r]) for r in REGIONS}
    for job in geometry_plan():
        packet = load_session(job['animal'], job['session'] - 1, job['region'])
        prepared = prepare_geometry(packet, job['region'])
        result = geometry_repetition(prepared['x'], prepared['z'], prepared['row_ids'],
                                     prepared['unit_ids'], rng=generators[job['region']],
                                     repetition=job['repetition'], svc_policy=svc_policy)
        yield {**job, **result, 'behavior': prepared['behavior'],
               'selected_times': prepared['t'][result['row_positions']],
               'selected_trial_ids': prepared['trial'][result['row_positions']]}


def session_result(repetitions, glm_result, *, case_id, behavior):
    """Reduce all500 draws without discarding failures or changing support."""
    need(case_id in {f'{a}-s{s:02d}-{r}' for a in ANIMALS for s in SESSIONS for r in REGIONS},
         'unknown complete-panel case ID')
    need(isinstance(behavior, dict) and behavior.get('status') in
         ('unavailable_complete_epoch_trial_table', 'declared_complete_epoch_trial_mean'),
         'explicit source behavior provenance/unavailability required')
    behavior_accuracy = behavior['accuracy']
    if behavior_accuracy is not None:
        need(np.isscalar(behavior_accuracy) and not isinstance(behavior_accuracy, (bool, np.bool_))
             and np.isfinite(behavior_accuracy) and 0 <= behavior_accuracy <= 1,
             'source trial-level behavior accuracy required')
    rows = list(repetitions)
    need(len(rows) == REPETITIONS and [r.get('repetition') for r in rows] == list(range(REPETITIONS)),
         'every ordered source repetition0..499 required')
    need(all(r.get('case_id', case_id) == case_id and r.get('condition') == 'current_source_code19'
             and r.get('geometry_fields') == list(GEOMETRY_FIELDS) for r in rows),
         'mixed case, condition or geometry fields')
    svc_policy = rows[0]['readout'].get('svc_policy')
    need(svc_policy in (SVC_POLICY, SVC_LITERAL_POLICY)
         and all(r['readout'].get('svc_policy') == svc_policy for r in rows),
         'one explicit SVC recipe required across all500 repetitions')
    geom = np.asarray([r['geometry_values'] for r in rows], dtype=float)
    need(geom.shape == (REPETITIONS, 8) and not np.isnan(geom).any()
         and not np.isneginf(geom).any()
         and np.isfinite(geom[:, [0, 1, 3, 4, 5, 6, 7]]).all(),
         'invalid geometry outputs; only exact noise-free signal-noise factor may be+inf')
    errors = np.asarray([[np.nan if behavior_accuracy is None else behavior_accuracy,
                          r['readout']['hebbian_error'], r['theory_error'], r['readout']['svc_error']]
                         for r in rows])
    need(errors.shape == (REPETITIONS, 4) and np.isfinite(errors[:, 1:]).all()
         and ((0 <= errors[:, 1:]) & (errors[:, 1:] <= 1)).all(), 'invalid complete readout results')
    need(glm_result.get('schema') == 'source_glm_pr_session_v1'
         and glm_result.get('condition') == 'current_source_code19'
         and glm_result.get('case_id') == case_id
         and np.asarray(glm_result.get('subset_pr')).shape == (REPETITIONS, 2),
         'complete source GLM PR result required')
    return {'schema': 'source_population_geometry_session_v1', 'case_id': case_id,
            'condition': 'current_source_code19', 'repetitions': REPETITIONS,
            'svc_policy': svc_policy,
            'behavior': behavior,
            'error_fields': ['behavior_accuracy', 'hebbian_error', 'theory_error', 'svc_error'],
            'errors': errors, 'mean_errors': errors.mean(axis=0),
            'geometry_fields': list(GEOMETRY_FIELDS), 'geometry': geom,
            'mean_geometry': geom.mean(axis=0),
            'glm_raw_pr': glm_result['raw_pr'], 'glm_expected_pr': glm_result['fitted_pr'],
            'glm_pr_draws': glm_result['subset_pr'],
            'glm_mean_selected_cv_d2': glm_result['mean_selected_cv_d2'],
            'glm_mean_selected_cv_sem': glm_result['mean_selected_cv_sem'],
            'historical_realization_authenticated': False,
            'role': 'source result reduction; no scientific success threshold or improvement claim'}


def panel_result(sessions):
    """Figure data arrays, learning trajectories and descriptive behavior R2.

    Eight animals carry repeated sessions. Pearson R2 below is the original
    descriptive64-pair figure calculation, not64 independent-animal inference.
    Mixed-effects trend fits and historical numeric qualification remain open.
    """
    rows = list(sessions)
    expected = [f'{a}-s{s:02d}-{r}' for a in ANIMALS for s in SESSIONS for r in REGIONS]
    need(len(rows) == 128 and len({r.get('case_id') for r in rows}) == 128
         and {r.get('case_id') for r in rows} == set(expected), 'all128 distinct source sessions required')
    by_id = {r['case_id']: r for r in rows}
    svc_policy = rows[0].get('svc_policy')
    need(svc_policy in (SVC_POLICY, SVC_LITERAL_POLICY)
         and all(r.get('svc_policy') == svc_policy for r in rows),
         'one explicit SVC recipe required across all128 sessions')
    output = {}
    for region in REGIONS:
        ordered = [[by_id[f'{a}-s{s:02d}-{region}'] for s in SESSIONS] for a in ANIMALS]
        need(all(r.get('schema') == 'source_population_geometry_session_v1'
                 and r.get('condition') == 'current_source_code19' and r.get('repetitions') == REPETITIONS
                 for rat in ordered for r in rat), 'wrong session schema or reduced source support')
        errors = np.asarray([[r['errors'] for r in rat] for rat in ordered]).transpose(2, 0, 1, 3)
        geometry = np.asarray([[r['geometry'] for r in rat] for rat in ordered]).transpose(2, 0, 1, 3)
        need(errors.shape == (500, 8, 8, 4) and geometry.shape == (500, 8, 8, 8),
             'complete figure result shapes required')
        behavior = 1 - errors.mean(axis=0)[:, :, 0]
        theory = errors.mean(axis=0)[:, :, 2]
        centered_b = behavior.ravel() - behavior.mean()
        centered_t = theory.ravel() - theory.mean()
        denominator = np.sqrt(np.sum(centered_b ** 2) * np.sum(centered_t ** 2))
        r2 = float((centered_b @ centered_t / denominator) ** 2) if np.isfinite(denominator) and denominator > 0 else None
        output[region] = {'errors': errors, 'geometry': geometry,
                          'glm_participation_ratios': np.asarray([[[r['glm_raw_pr'], r['glm_expected_pr']]
                                                                  for r in rat] for rat in ordered]),
                          'learning_mean_errors': errors.mean(axis=(0, 1)),
                          'learning_mean_geometry': geometry.mean(axis=(0, 1)),
                          'behavior_theory_pearson_r2': r2,
                          'behavior_status': 'complete' if np.isfinite(behavior).all() else 'unavailable_complete_epoch_trial_table',
                          'behavior_theory_pairs': 64, 'independent_animals': 8}
    return {'schema': 'source_population_geometry_panel_v1', 'condition': 'current_source_code19',
            'svc_policy': svc_policy,
            'animal_order': list(ANIMALS), 'session_order': list(SESSIONS), 'regions': output,
            'source_sizes': {'repetitions': 500, 'observations': 500, 'training': 300, 'neurons': 19},
            'historical_realization_authenticated': False,
            'holds': ['CA1 paper24 versus active code19 neurons',
                      'CA1 paper behavior/readout R2 .48 versus figure caption .49',
                      'original worker RNG and unsorted file order not recovered',
                      'mixed-effects trends require separate explicit source_trends invocation and statsmodels runtime',
                      'source null-unit regional D2 aggregation is not independently qualified',
                      'no authentic fits, source comparator qualification or improvement established']}


def mixed_trend(values, *, quadratic):
    """Source Figure7 random-intercept trend with default MixedLM.fit options.

    This callable performs a model fit only when explicitly invoked. Local
    construction does not assert that statsmodels exists or that any authentic
    trend has been fit. Source convergence warnings and outputs are retained.
    """
    g = K.matrix(values, 'eight-rat eight-session trend')
    need(g.shape == (8, 8) and type(quadratic) is bool,
         'complete8-rat by8-session source trend required')
    try:
        import pandas as pd
        import statsmodels.formula.api as smf
    except ImportError as exc:
        raise ContractError('source trend requires an existing pandas/statsmodels runtime; no fallback fit') from exc
    time = np.tile(np.arange(8), 8)
    subject = np.repeat(np.arange(8), 8).astype(str)
    frame = pd.DataFrame({'Y': g.reshape(-1), 'time': time, 'subject': subject})
    if quadratic:
        frame['time_squared'] = time ** 2
    formula = 'Y ~ time + time_squared' if quadratic else 'Y ~ time'
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        fitted = smf.mixedlm(formula, frame, groups=frame['subject']).fit()
    fields = ['Intercept', 'time', 'time_squared'] if quadratic else ['Intercept', 'time']
    fixed = {name: float(fitted.params[name]) for name in fields}
    curve_time = np.arange(8)
    curve = fixed['Intercept'] + fixed['time'] * curve_time
    if quadratic:
        curve += fixed['time_squared'] * curve_time ** 2
    return {'schema': 'source_population_geometry_mixed_trend_v1', 'formula': formula,
            'time_values': curve_time, 'fitted_values': curve,
            'fixed_parameters': fixed,
            'fixed_pvalues': {name: float(fitted.pvalues[name]) for name in fields},
            'all_parameters': {str(k): float(v) for k, v in fitted.params.items()},
            'all_pvalues': {str(k): float(v) for k, v in fitted.pvalues.items()},
            'converged': bool(fitted.converged), 'reml': bool(fitted.reml),
            'fit_options': 'author .fit() defaults; no optimizer or REML override',
            'grouping': 'random intercept per animal, all eight repeated sessions',
            'independent_animals': 8, 'observations': 64,
            'warnings': [{'category': type(w.message).__name__, 'message': str(w.message)} for w in caught],
            'runtime': {k: importlib.metadata.version(k) for k in ('numpy', 'pandas', 'scipy', 'statsmodels')},
            'historical_result_authenticated': False}


def source_trends(panel):
    """All14 original figure linear/quadratic fits, no optional outlier deletion."""
    need(panel.get('schema') == 'source_population_geometry_panel_v1'
         and panel.get('condition') == 'current_source_code19'
         and panel.get('animal_order') == list(ANIMALS)
         and panel.get('session_order') == list(SESSIONS)
         and set(panel.get('regions', {})) == set(REGIONS), 'complete source figure panel required')
    fits = []
    # Notebook loops PFC then CA1, four raw metrics then task-related PR.
    for region in ('PFC', 'CA1'):
        results = panel['regions'][region]
        geometry = np.asarray(results['geometry'], dtype=float)
        dims = np.asarray(results['glm_participation_ratios'], dtype=float)
        need(geometry.shape == (500, 8, 8, 8) and dims.shape == (8, 8, 2),
             'complete source geometry and GLM PR figure inputs required')
        averaged = geometry.mean(axis=0)
        for index, name in enumerate(GEOMETRY_FIELDS[:4]):
            fits.append({'region': region, 'measure': name, 'model': 'quadratic',
                         'result': mixed_trend(averaged[:, :, index], quadratic=True)})
        fits.append({'region': region, 'measure': 'signal_signal_factor', 'model': 'linear',
                     'result': mixed_trend(averaged[:, :, 3], quadratic=False)})
        for quadratic in (True, False):
            fits.append({'region': region, 'measure': 'glm_expected_participation_ratio',
                         'model': 'quadratic' if quadratic else 'linear',
                         'result': mixed_trend(dims[:, :, 1], quadratic=quadratic)})
    return {'schema': 'source_population_geometry_all_trends_v1', 'fits': fits,
            'fit_count': 14, 'excluded_animals': [], 'source_exclude_CA1_outlier': False,
            'multiple_comparisons': adjust_source_trends(fits),
            'interpretation': 'source model coefficients/pvalues; larger effect or smaller p is not improvement'}


def adjust_source_trends(fits):
    """Original Figure table:14 linear+10 quadratic tests, BH FDR alpha=.01.

    The source assumes all ten quadratic rows have nonmissing coefficients and
    p-values. A failed fit cannot silently shrink this multiple-testing family.
    """
    import pandas as pd
    need(len(fits) == 14, 'all14 source trend fits required')
    rows = []
    for item in fits:
        need(item['model'] in ('quadratic', 'linear'), 'unknown source trend model')
        result = item['result']
        quad = item['model'] == 'quadratic'
        rows.append({'Area': item['region'], 'model': 'Quad.' if quad else 'Linear',
                     'meas': item['measure'], 'blin': result['fixed_parameters']['time'],
                     'plin': result['fixed_pvalues']['time'],
                     'bquad': result['fixed_parameters']['time_squared'] if quad else np.nan,
                     'pquad': result['fixed_pvalues']['time_squared'] if quad else np.nan})
    frame = pd.DataFrame(rows).sort_values('bquad')
    quadratic = frame.dropna()
    need(len(quadratic) == 10 and (frame['model'] == 'Linear').sum() == 4
         and (frame.iloc[-4:]['model'] == 'Linear').all(),
         'source FDR requires ten complete quadratic rows and four linear rows')
    p = np.concatenate([frame['plin'].values, quadratic['pquad'].values]).astype(float)
    need(p.shape == (24,) and np.isfinite(p).all() and ((p >= 0) & (p <= 1)).all(),
         'all24 finite source coefficient p-values required')
    order = np.argsort(p)
    sorted_p = p[order]
    fraction = np.arange(1, 25) / 24
    adjusted_sorted = np.minimum.accumulate((sorted_p / fraction)[::-1])[::-1]
    adjusted_sorted = np.minimum(adjusted_sorted, 1)
    reject_sorted = sorted_p <= fraction * .01
    if np.any(reject_sorted):
        reject_sorted[:np.flatnonzero(reject_sorted)[-1] + 1] = True
    adjusted = np.empty(24)
    rejected = np.empty(24, dtype=bool)
    adjusted[order], rejected[order] = adjusted_sorted, reject_sorted
    source_index = frame.index.to_numpy(copy=True)
    frame['p lin. adj.'] = adjusted[:14]
    quad_adjusted = np.full(14, np.nan)
    quad_adjusted[:-4] = adjusted[14:]
    frame['p quad. adj.'] = quad_adjusted
    frame = frame.sort_values('model', ascending=False)
    return {'method': 'fdr_bh', 'alpha': .01, 'tests': 24,
            'source_bquad_sorted_fit_indices': source_index,
            'source_concatenated_pvalues': p, 'adjusted_pvalues': adjusted,
            'rejected': rejected, 'table_rows': frame.to_dict(orient='records'),
            'implementation': 'independent Benjamini-Hochberg step-up equivalent to source multipletests',
            'interpretation': 'source statistical table only; rejection is not a benchmark improvement criterion'}
