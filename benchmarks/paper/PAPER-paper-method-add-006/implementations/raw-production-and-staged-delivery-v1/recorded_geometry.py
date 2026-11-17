"""Add raw SVC test predictions to the unchanged source geometry calculation.

The two functions below derive from the pinned original geometry_results.py.
Only names, explicit recording-budget checks, prediction validation/copying and
readout dispatch differ. No model fit, predict call or random draw is added.
The extra matrix preserves finite float64 source predictions, with axes test_positions by
valid_teacher_indices. A prediction budget bounds that retained float64 matrix,
not input arrays, the original algorithm's working set or serialized metadata.
The exact allocation is known after teacher balancing. An insufficient positive
budget therefore raises after RNG consumption; callers must discard or restore
that RNG on any exception, never continue its stream as a completed draw.
An 800000-byte allowance covers all 500 possible retained teachers.

Original task balance filtering sees all 500 latent rows; its information
exposure is preserved rather than relabelled as fully hidden-target selection.
"""
from __future__ import annotations

import hashlib
import importlib.metadata
import warnings

import numpy as np
from dependency_loader import R

K = R.K
need = R.need
state = R.state
digest = R.digest
array_identity = R.array_identity
identities = R.identities
OBSERVATIONS = R.OBSERVATIONS
TRAINING = R.TRAINING
NEURONS = R.NEURONS
TEACHERS = R.TEACHERS
REPETITIONS = R.REPETITIONS
SVC_POLICY = R.SVC_POLICY
SVC_LITERAL_POLICY = R.SVC_LITERAL_POLICY
RNG_POLICY = R.RNG_POLICY
GEOMETRY_FIELDS = R.GEOMETRY_FIELDS


def _prediction_budget(value):
    need(type(value) is int and value > 0,
         'max_prediction_bytes must be a positive integer')


def readout_recorded(points, latents, *, rng, svc_policy, max_prediction_bytes):
    """Exact source task filtering/Hebbian error plus serial current SVC route.

    Task-balance filtering sees all500 observations, including eventual test
    rows. Zero Hebbian margins are not errors in the original theta convention.
    """
    _prediction_budget(max_prediction_bytes)
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
    required_bytes = (OBSERVATIONS - TRAINING) * len(valid) * np.dtype(np.float64).itemsize
    need(required_bytes <= max_prediction_bytes,
         'raw SVC prediction allocation exceeds max_prediction_bytes')
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
    svc_predictions = np.empty((len(test), len(valid)), dtype=np.float64)
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
        values = np.asarray(svc_pred)
        need(values.shape == (len(test),) and values.dtype == np.dtype(np.float64)
             and np.isfinite(values).all(),
             'raw SVC predictions require one finite numeric value per test row in original float64 dtype')
        svc_predictions[:, column] = values
        svc_errors.append(float(np.mean(svc_pred != ytest)))
    return {'svc_test_predictions': svc_predictions,
            'hebbian_error': float(np.mean(errors)),
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



def geometry_repetition_recorded(points, latents, row_ids, unit_ids, *, rng, repetition,
                                 svc_policy, max_prediction_bytes):
    """One original-size draw; no relaxation argument exists for source sizes."""
    _prediction_budget(max_prediction_bytes)
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
    empirical = readout_recorded(xx, zz, rng=rng, svc_policy=svc_policy,
                                 max_prediction_bytes=max_prediction_bytes)
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

