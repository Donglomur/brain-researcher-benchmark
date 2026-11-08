"""Independent operator HMM/static references. No fit runs at import time.

These are future scientific entrypoints, not construction controls. Inputs must
come from the independently prepared operator pool, never a candidate output.
"""
from core import HMM, need, validate_runs


def check_job(job):
    need(job['phase'] == 'held_hmm' and job['role'] == 'reference'
         and job['branch'] in HMM and job['control'] in ('real', 'common_phase', 'independent_phase'),
         'Independent fixed operator role, branch and control')
    need(type(job['fold']) is int and 0 <= job['fold'] < 5 and
         type(job['fit_set']) is int and 0 <= job['fit_set'] < 3 and
         type(job['attempt']) is int and 0 <= job['attempt'] < 10,
         'Predeclared complete attempt identity')


def static(rows, branch, fold):
    """Source-defined matching-space Gaussian; real training rows only."""
    import numpy as np
    validate_runs(rows, branch, fold, 'train')
    x = np.concatenate([np.asarray(r['observations'], dtype='float64') for r in rows])
    need(x.ndim == 2 and x.shape[1] == HMM[branch][0] and len(x) > 1 and np.isfinite(x).all(),
         'Complete finite matching-space training pool')
    anchor = x[0]
    offset = (x-anchor).mean(axis=0)
    residual = (x-anchor)-offset
    cov = residual.T @ residual / len(x)
    ridge = 1e-6 * float(np.trace(cov)) / x.shape[1]
    need(np.isfinite(cov).all() and ridge > 0, 'Nondegenerate fixed training covariance')
    cov += np.eye(x.shape[1])*ridge
    return {'mean': (anchor+offset).tolist(), 'covariance': cov.tolist(), 'ridge': ridge}


def fit(rows, job, training_binding, expected_training_binding, native_environment):
    """One independently executed native-family training attempt.

    The caller is the trusted operator in its separately audited image. The
    binding is frozen before candidate execution. No query argument or candidate
    parameters/features are accepted. A separate controller captures closure.
    """
    check_job(job)
    need(training_binding == expected_training_binding, 'Pinned independently prepared training pool')
    need(native_environment['role'] == 'reference'
         and native_environment['source_revision'] == 'cded3b2ea95efef7b6c089c5e111fd565b716922',
         'Separate historically bound operator environment')
    import numpy as np
    import tensorflow as tf
    from osl_dynamics.data import Data
    from osl_dynamics.models.hmm import Config, Model
    need(tf.__version__ == '2.9.1', 'Selected historical TensorFlow recipe; no silent upgrade')
    validate_runs(rows, job['branch'], job['fold'], 'train')
    d, k, rate = HMM[job['branch']]
    arrays = []
    for r in rows:
        need(set(r) == {'person', 'run', 'observations'}, 'No query or candidate provenance in training view')
        x = np.asarray(r['observations'], dtype='float64')
        need(x.ndim == 2 and x.shape[1] == d and len(x) >= 2000 and np.isfinite(x).all(),
             'Every original training run supports the fixed native sequence')
        arrays.append(x)
    tf.keras.utils.set_random_seed(job['seed'])
    data = Data(arrays, sampling_frequency=rate)
    config = Config(n_states=k, n_channels=d, sequence_length=2000,
                    learn_means=job['branch'] == 'elekta_ae', learn_covariances=True,
                    batch_size=32, learning_rate=.01, n_epochs=20)
    model = Model(config)
    initialization = model.random_state_time_course_initialization(data, n_init=3, n_epochs=1)
    history = model.fit(data)
    literal_fit_state_free_energy = float(model.free_energy(data))
    means, covs = model.get_means_covariances()
    transition = np.asarray(model.get_trans_prob(), dtype='float64')
    initial = np.asarray(model.get_stationary_distribution(), dtype='float64')
    need(initial.shape == (k,) and np.isfinite(initial).all() and (initial >= 0).all()
         and abs(initial.sum()-1) < 1e-10 and np.isfinite(literal_fit_state_free_energy),
         'Valid stationary reference initial distribution and literal fit energy')
    parameters = {'means': np.asarray(means).tolist(), 'covariances': np.asarray(covs).tolist(),
                  'transition': transition.tolist(), 'initial': initial.tolist()}
    # All roles select the same actually exported/admitted parameter state.
    # Native fit may have a different literal state_probs_t0; its diagnostic
    # energy is not substituted for stationary-initial export selection.
    from selection import held_hmm
    try:
        selection = held_hmm(rows, parameters, job, training_binding, expected_training_binding, native_environment)
    except ValueError as error:
        selection = {'available': False, 'reason': str(error),
                     'criterion': 'historical_model_free_energy_on_training_sequences'}
    return {'parameters': parameters, 'training_free_energy': selection.get('value'),
            'literal_fit_state_free_energy_diagnostic': literal_fit_state_free_energy,
            'exported_parameter_selection': selection,
            'training_binding': training_binding, 'job': job,
            'initialization_history': initialization, 'training_history': history,
            'query_read': False, 'model_family': 'historical_osl_gaussian_hmm',
            'historical_seed_parity': False}
