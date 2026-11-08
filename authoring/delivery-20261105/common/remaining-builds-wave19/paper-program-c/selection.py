"""Independent operator evaluation of the actual training-selection criterion.

These future functions import the private historical implementation only when
explicitly called. They must never be installed/reachable in candidate A's
image. No fit, native import or authentic evaluation is performed in BUILD.
"""
from core import HMM, REVISION, identity, need, validate_runs
from likelihood import validate_hmm


def environment(proof):
    need(proof['role'] == 'reference' and proof['source_revision'] == REVISION
         and proof['image_digest'] and proof['inventory_sha256'],
         'Separately attested exact historical private operator image')
    import tensorflow as tf
    need(tf.__version__ == '2.9.1', 'Exact historical TensorFlow recipe')
    return tf


def restore_effective_parameters(model, parameters):
    """Restore exactly admitted effective emissions, or refuse native selection.

    The historical covariance setter takes the pre-epsilon covariance and casts
    it to float32; the layer getter adds epsilon. No added ridge, clipping or
    approximate round-trip tolerance is introduced. Refusal leaves valid
    mathematical outputs retained, with native selection support unavailable.
    """
    import numpy as np
    means = np.asarray(parameters['means'], dtype='float64')
    covs = np.asarray(parameters['covariances'], dtype='float64')
    transition = np.asarray(parameters['transition'], dtype='float64')
    initial = np.asarray(parameters['initial'], dtype='float64')
    epsilon = float(model.model.get_layer('covs').epsilon)
    need(np.isfinite(epsilon) and epsilon >= 0, 'Bound historical covariance-layer epsilon')
    base = covs - epsilon*np.eye(covs.shape[-1])[None, :, :]
    need(np.isfinite(base).all(), 'Representable pre-epsilon covariance')
    try:
        for x in base:
            np.linalg.cholesky(x.astype('float32'))
    except np.linalg.LinAlgError as error:
        raise ValueError('Admitted covariance outside exact historical setter domain') from error
    model.set_means(means)
    model.set_covariances(base)
    model.set_trans_prob(transition)
    model.set_state_probs_t0(initial)
    actual_means, actual_covs = model.get_means_covariances()
    need(np.array_equal(np.asarray(actual_means), means)
         and np.array_equal(np.asarray(actual_covs), covs)
         and np.array_equal(np.asarray(model.get_trans_prob()), transition)
         and np.array_equal(np.asarray(model.state_probs_t0), initial),
         'Exact effective-parameter round trip; no silent cast, epsilon or repair')
    return {'effective_parameters_identical': True, 'historical_layer_epsilon': epsilon,
            'tolerance': 0, 'additional_ridge': 0}


def held_hmm(rows, parameters, job, training_binding, expected_training_binding, proof):
    """Source free_energy, not whole-run exact likelihood or submitted scalar."""
    need(job['phase'] == 'held_hmm' and training_binding == expected_training_binding,
         'Independently frozen real/surrogate training view')
    validate_runs(rows, job['branch'], job['fold'], 'train')
    d, k, rate = HMM[job['branch']]
    validate_hmm(parameters, d, k)
    environment(proof)
    import numpy as np
    from osl_dynamics.data import Data
    from osl_dynamics.models.hmm import Config, Model
    xs = [np.asarray(r['observations'], dtype='float64') for r in rows]
    need(all(x.ndim == 2 and x.shape[1] == d and len(x) >= 2000 and np.isfinite(x).all() for x in xs),
         'Every complete training run supports native sequences; no query input')
    model = Model(Config(n_states=k, n_channels=d, sequence_length=2000,
                         learn_means=job['branch'] == 'elekta_ae', learn_covariances=True,
                         batch_size=32, learning_rate=.01, n_epochs=20))
    restoration = restore_effective_parameters(model, parameters)
    value = float(model.free_energy(Data(xs, sampling_frequency=rate)))
    need(np.isfinite(value), 'Finite independently recomputed source training free energy')
    return {'available': True, 'value': value, 'criterion': 'historical_model_free_energy_on_training_sequences',
            'candidate_supplied': False, 'query_used': False,
            'evidence_mode': 'independent_exact_source_parameter_evaluation',
            'training_binding': training_binding, 'effective_parameter_restoration': restoration,
            'native_execution_requires_actual_external_closure': True}


def native_model(model, literal, prepared_data, read_bytes, max_input_bytes,
                 approved_constructor, expected_constructor_identity, proof):
    """Complete typed state into an operator-constructed approved architecture.

    The operator supplies an already source-approved historical model/config and
    exact authenticated prepared Data, never a candidate pickle/class/callback.
    Full constructor equality is mandatory. DyNeMo's original history criterion
    remains unavailable; this function does not evaluate a substitute.
    """
    from native.assemble import restore_model_state, primitive_npy
    from native.sink import identity as array_identity
    import hashlib
    need(identity(approved_constructor) == expected_constructor_identity,
         'Externally source-approved constructor identity')
    table = {r['key']: r['artifact'] for r in literal['ordered_fields']}
    consumed = 0
    def bounded_read(name, remaining):
        nonlocal consumed
        body = read_bytes(name, min(remaining, max_input_bytes-consumed))
        consumed += len(body)
        need(consumed <= max_input_bytes, 'Combined configuration/weight read allocation')
        return body
    def hydrate(value):
        if type(value) is dict:
            if set(value) == {'$primitive_array'}:
                record = table[value['$primitive_array']]
                body = bounded_read(record['file'], max_input_bytes-consumed)
                need(len(body) == record['bytes'] and hashlib.sha256(body).hexdigest() == record['sha256'],
                     'Typed constructor primitive pin')
                return primitive_npy(body).tolist()
            return {k: hydrate(v) for k, v in value.items()}
        if type(value) is list:
            return [hydrate(v) for v in value]
        return value
    need(hydrate(literal['structured']['training']['config_constructor']) == approved_constructor,
         'Captured constructor matches fixed historical architecture')
    environment(proof)
    actual_constructor = {k: (None if k == 'strategy' or 'regularizer' in k else v)
                          for k, v in vars(model.config).items()}
    need(actual_constructor == approved_constructor, 'Actual operator model has the approved constructor')
    if literal['branch'] == 'ctf_dynemo':
        return {'available': False, 'criterion': 'literal_final_epoch_history_loss',
                'reason': 'final_weights_do_not_reconstruct_training_trajectory',
                'postfit_proxy_evaluated': False}
    coordinates = literal['coordinates']
    need([array_identity(x) for x in prepared_data.arrays] == coordinates['prepared'] and
         [array_identity(x) for x in prepared_data.raw_data_arrays] == coordinates['raw'] and
         float(prepared_data.sampling_frequency) == coordinates['sampling_frequency'] and
         getattr(prepared_data, 'n_embeddings', None) == coordinates['n_embeddings'] and
         getattr(prepared_data, 'n_window', None) == coordinates['n_window'],
         'Actual independent operator training arrays use the complete captured coordinates')
    restored = restore_model_state(model, literal, bounded_read, max_input_bytes=max_input_bytes-consumed)
    import math
    value = float(model.free_energy(prepared_data))
    need(math.isfinite(value), 'Finite source-defined native training free energy')
    return {'available': True, 'value': value, 'restored': restored,
            'criterion': 'historical_model_free_energy_on_training_sequences',
            'coordinate_signature': literal['coordinate_signature'],
            'logical_input_bytes': consumed,
            'candidate_supplied': False, 'query_used': False,
            'evidence_mode': 'independent_exact_source_parameter_evaluation',
            'native_execution_requires_actual_external_closure': True}


def native_hmm_parameters(literal, load, prepared_data, approved_constructor,
                          expected_constructor_identity, proof):
    """A/B/operator HMM selection from mathematical parameters, no Keras ABI.

    Arm A supplies no historical internal variable names, weights, configuration
    or executable implementation. Only the fixed HMM mathematical family and
    original native observables/coordinates are required. The constructor and
    evaluator are independently source-bound private operator infrastructure.
    """
    import math
    from native.sink import identity as array_identity
    branch = literal['branch']
    need(branch in HMM, 'One of the four original native HMM branches')
    need(identity(approved_constructor) == expected_constructor_identity,
         'Externally source-approved exact historical constructor')
    d, k, _ = HMM[branch]
    need(approved_constructor['n_channels'] == d and approved_constructor['n_states'] == k,
         'Original native mathematical family')
    table = {r['key']: r for r in literal['ordered_fields']}
    p = {target: load(table[source]).tolist() for target, source in
         [('means', 'model.means'), ('covariances', 'model.covs'),
          ('transition', 'model.transition'), ('initial', 'model.initial')]}
    validate_hmm(p, d, k)
    c = literal['coordinates']
    need([array_identity(x) for x in prepared_data.arrays] == c['prepared'] and
         [array_identity(x) for x in prepared_data.raw_data_arrays] == c['raw'] and
         float(prepared_data.sampling_frequency) == c['sampling_frequency'] and
         getattr(prepared_data, 'n_embeddings', None) == c['n_embeddings'] and
         getattr(prepared_data, 'n_window', None) == c['n_window'],
         'Actual full operator training input and representation')
    environment(proof)
    import numpy as np
    from osl_dynamics.models.hmm import Config, Model
    model = Model(Config(**approved_constructor))
    restoration = restore_effective_parameters(model, p)
    value = float(model.free_energy(prepared_data))
    need(math.isfinite(value), 'Finite independently evaluated original native HMM criterion')
    return {'available': True, 'value': value,
            'criterion': 'historical_model_free_energy_on_training_sequences',
            'coordinate_signature': literal['coordinate_signature'],
            'candidate_supplied': False, 'query_used': False,
            'evidence_mode': 'independent_exact_source_parameter_evaluation',
            'candidate_framework_or_internal_architecture_required': False,
            'effective_parameter_restoration': restoration,
            'native_execution_requires_actual_external_closure': True}
