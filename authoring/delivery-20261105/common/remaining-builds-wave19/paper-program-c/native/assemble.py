"""Complete future native output admission from primitive arrays, never pickle.

This module admits typed observations, not process closure, biological success,
fit independence or a scientific qualification. External executor evidence and
operator-authenticated context are required by the enclosing program.
"""
import ast
import hashlib
import json
import math
from pathlib import Path
import re
import struct

from .contract import BRANCHES, EVENT_IDS, fields, validate_context, semantic_axes
from .sink import encoded


def strict_json(body):
    def pairs(items):
        out = {}
        for k, v in items:
            if k in out:
                raise ValueError('Duplicate JSON key')
            out[k] = v
        return out
    return json.loads(body, object_pairs_hook=pairs,
                      parse_constant=lambda x: (_ for _ in ()).throw(ValueError('Nonfinite JSON')))


def primitive_npy(body):
    """Decode only bounded-header, C-order, unstructured real NPY, no np.load."""
    import numpy as np
    if len(body) < 10 or body[:6] != b'\x93NUMPY':
        raise ValueError('Primitive NPY required')
    version = tuple(body[6:8])
    if version == (1, 0):
        offset, length = 10, struct.unpack('<H', body[8:10])[0]
    elif version in ((2, 0), (3, 0)) and len(body) >= 12:
        offset, length = 12, struct.unpack('<I', body[8:12])[0]
    else:
        raise ValueError('Supported primitive NPY format')
    if length > 65536 or offset + length > len(body):
        raise ValueError('Bounded complete NPY header')
    header = ast.literal_eval(body[offset:offset + length].decode('utf8' if version == (3, 0) else 'latin1').strip())
    if type(header) is not dict or set(header) != {'descr', 'fortran_order', 'shape'}:
        raise ValueError('Exact NPY header fields')
    if header['fortran_order'] is not False or type(header['descr']) is not str or not re.fullmatch(r'[<>=|][biuf](?:1|2|4|8)', header['descr']):
        raise ValueError('Only unstructured primitive real C-order arrays; no objects/pickle')
    shape = header['shape']
    if type(shape) is not tuple or len(shape) > 8 or any(type(n) is not int or n < 0 for n in shape):
        raise ValueError('Bounded nonnegative shape')
    dtype = np.dtype(header['descr'])
    if dtype.kind not in 'biuf' or dtype.hasobject:
        raise ValueError('Primitive real dtype')
    payload = memoryview(body)[offset + length:]
    if math.prod(shape) * dtype.itemsize != len(payload):
        raise ValueError('Exact NPY numeric body; no truncation/trailing bytes')
    return np.frombuffer(payload, dtype=dtype).reshape(shape)


def coordinate_signature(context, coords):
    """Exact shared coordinate identity; workspace filenames are documentary."""
    identity = {'revision': context['revision'], 'branch': context['branch'],
                'runs': [{k: r[k] for k in ('person_id', 'run_id', 'input_id')} for r in context['runs']],
                'coordinates': {k: coords[k] for k in ('prepared', 'raw', 'sampling_frequency', 'n_embeddings', 'n_window', 'profile', 'preparation_binding', 'pca_components')}}
    return hashlib.sha256(encoded(identity)).hexdigest()


def auxiliary_axes(manifest, records, context):
    """Admit optional A auxiliaries, mandatory trusted B/reference captures.

    These fields do not define the original scientific observable support.
    Supplying optional A internals never grants source or selector authority.
    """
    required_for_role = context['role'] != 'A'
    structured = manifest.get('structured', {})
    state = manifest.get('model_state')
    axes = {'model_weights': [], 'training_arrays': [],
            'include_free_energy': 'model.free_energy' in records}
    if type(structured) is not dict or set(structured) - {'training'}:
        raise ValueError('Exact optional source training metadata container')
    if required_for_role and 'training' not in structured:
        raise ValueError('B/reference requires complete source training configuration and histories')
    if required_for_role and state is None:
        raise ValueError('B/reference requires full ordered model-weight reconstruction ABI')
    if required_for_role and not axes['include_free_energy']:
        raise ValueError('B/reference requires captured native free-energy selection statistic')

    def required(key):
        if key not in records:
            raise ValueError('Missing supplied auxiliary primitive: ' + key)
        return records[key]

    if 'training' in structured:
        training = structured['training']
        expected = {'config', 'config_constructor', 'config_runtime_objects', 'config_kwargs',
                    'init_kwargs', 'fit_kwargs', 'init_history', 'history'}
        if type(training) is not dict or set(training) != expected:
            raise ValueError('Supplied training auxiliary must be complete')
        for key in expected - {'history', 'init_history'}:
            if type(training[key]) is not dict:
                raise ValueError('Supplied training configuration maps must be primitive dictionaries')

        def refs(value):
            if type(value) is dict:
                if '$primitive_array' in value:
                    if set(value) != {'$primitive_array'}:
                        raise ValueError('Exact training primitive reference')
                    key = value['$primitive_array']
                    if type(key) is not str or not key.startswith('training/'):
                        raise ValueError('Safe source training metadata reference')
                    axes['training_arrays'].append({'key': key, 'shape': required(key)['shape']})
                else:
                    for child in value.values():
                        refs(child)
            elif type(value) is list:
                for child in value:
                    refs(child)
        refs(training)
        if len({r['key'] for r in axes['training_arrays']}) != len(axes['training_arrays']):
            raise ValueError('No duplicate primitive history references')
    if state is not None:
        expected = {'family', 'keras_weights', 'nonweight_layer_state', 'complete_model_weight_list',
                    'optimizer_state_exported', 'historical_training_rng_state_exported',
                    'training_trajectory_reconstruction', 'postfit_evaluation_runtime_validated'}
        family = 'dynemo' if context['branch'] == 'ctf_dynemo' else 'hmm'
        if type(state) is not dict or set(state) != expected or state['family'] != family or state['complete_model_weight_list'] is not True:
            raise ValueError('Supplied complete numeric model-state auxiliary ABI')
        if any(state[k] is not False for k in ('optimizer_state_exported', 'historical_training_rng_state_exported', 'training_trajectory_reconstruction', 'postfit_evaluation_runtime_validated')):
            raise ValueError('Auxiliary capture cannot certify trajectory/runtime reconstruction')
        if type(state['keras_weights']) is not list or not state['keras_weights']:
            raise ValueError('Supplied model state requires complete ordered named weights')
        extra = state['nonweight_layer_state']
        if type(extra) is not dict or set(extra) - {'static_loss_scaling_factor.n_batches'} or any(type(v) is not int or v < 1 for v in extra.values()):
            raise ValueError('Reviewed non-weight model state')
        for i, row in enumerate(state['keras_weights']):
            key = 'model.weights/' + str(i).zfill(6)
            if type(row) is not dict or set(row) != {'index', 'key', 'name', 'trainable', 'shape', 'dtype'}:
                raise ValueError('Complete native variable descriptor')
            if row['index'] != i or row['key'] != key or type(row['name']) is not str or not row['name'] or type(row['trainable']) is not bool or row['shape'] != required(key)['shape'] or row['dtype'] != required(key)['dtype']:
                raise ValueError('Complete ordered named native model weights')
            axes['model_weights'].append({'key': key, 'shape': row['shape']})
    return axes


def assemble(root, branch, trusted_context, *, max_total_bytes, read_bytes=None):
    """Read a complete capture under explicit byte cap; return ordered metadata.

    read_bytes is an operator/test I/O dependency, never candidate-provided code.
    No missing field is manufactured. Files remain literal; comparisons are a
    separate view. No subset of people, events, states or spectra is selected.
    """
    import numpy as np
    b = validate_context(trusted_context)
    if branch != trusted_context['branch'] or type(max_total_bytes) is not int or max_total_bytes <= 0:
        raise ValueError('Exact branch and explicit future read cap')
    root = Path(root)
    consumed = 0

    def read(name):
        nonlocal consumed
        if not re.fullmatch(r'[a-zA-Z0-9_.-]+', name):
            raise ValueError('Flat safe capture path')
        remaining = max_total_bytes - consumed
        if read_bytes is None:
            p = root / name
            if root.is_symlink() or p.is_symlink() or not p.is_file() or p.stat().st_size > remaining:
                raise ValueError('Safe regular bounded capture file')
            body = p.read_bytes()
        else:
            body = read_bytes(name, remaining)
        if type(body) is not bytes or len(body) > remaining:
            raise ValueError('Capture read allocation exceeded')
        consumed += len(body)
        return body

    manifest_body = read('CAPTURE.json')
    manifest = strict_json(manifest_body)
    if manifest['schema'] != 'osl19_primitive_native_capture_v1' or manifest['context'] != trusted_context:
        raise ValueError('Capture/context identity')
    if manifest['state_order'] != 'literal_original' or manifest['external_natural_exit_verified'] is not False or manifest['scientific_qualification'] is not False:
        raise ValueError('Raw observations cannot certify exit/qualification or permutation')
    records = {r['key']: r for r in manifest['fields']}
    if len(records) != len(manifest['fields']) or len({r['file'] for r in records.values()}) != len(records):
        raise ValueError('Unique complete fields and primitive files')
    for r in records.values():
        if type(r['bytes']) is not int or r['bytes'] < 10 or not re.fullmatch('[a-f0-9]{64}', r['sha256']):
            raise ValueError('Immutable primitive file metadata')
    def required(key):
        if key not in records:
            raise ValueError('Missing source-defined field: ' + key)
        return records[key]
    coords = manifest['coordinates']
    R, D, C = b['runs'], b['features'], b['channels']
    if not coords or coords['profile'] != 'literal_historical_native' or coords['sampling_frequency'] != b['hz']:
        raise ValueError('Native coordinate profile/frequency')
    if coords['preparation_binding'] != trusted_context['preparation_binding'] or coords['source_inputs'] != [r['source_input'] for r in trusted_context['runs']]:
        raise ValueError('Authenticated original input/preparation order')
    if len(coords['prepared']) != R or len(coords['raw']) != R:
        raise ValueError('Complete coordinate run identities')
    for mode, width in [('prepared', D), ('raw', C)]:
        for r in coords[mode]:
            if len(r['shape']) != 2 or r['shape'][0] <= 0 or r['shape'][1] != width or not re.fullmatch('[a-f0-9]{64}', r['c_order_body_sha256']):
                raise ValueError('Native complete shape/dtype/body coordinate identity')
    axes = {}
    if branch != 'ctf_static':
        axes.update(auxiliary_axes(manifest, records, trusted_context))
        axes['alpha_samples'] = [r['shape'][0] // b['sequence'] * b['sequence'] for r in coords['prepared']]
        if not all(axes['alpha_samples']):
            raise ValueError('Native sequence support absent; no shorter sequence substitution')
    elif manifest.get('structured') not in (None, {}) or manifest.get('model_state') is not None:
        raise ValueError('Static source has no fitted-network/training auxiliary')
    if branch != 'elekta_ae':
        axes['frequencies'] = required('spectra.f')['shape'][0]
        if axes['frequencies'] < 1:
            raise ValueError('Complete nonempty frequency axis')
    if branch == 'ctf_bursts':
        axes['envelope_samples'] = required('burst_envelopes.envelopes')['shape'][0]
        if axes['envelope_samples'] != sum(axes['alpha_samples']):
            raise ValueError('Complete concatenated source envelope/alpha support')
    if branch.startswith('elekta_'):
        axes['event_times'] = required('event.t')['shape'][0]
        if axes['event_times'] <= 0 or manifest['event_files'] != coords['source_inputs'] or len(manifest['event_trials']) != R:
            raise ValueError('Complete Elekta event/run capture')
        axes['event_trials'], axes['events_found'] = [], []
        for i, row in enumerate(manifest['event_trials']):
            if row != {'run_index': i, 'source_input': coords['source_inputs'][i], 'event_id': EVENT_IDS}:
                raise ValueError('Exact original event-code/ordered-run support')
            prefix = 'event_trials/' + str(i).zfill(6)
            axes['event_trials'].append(required(prefix + '.trials')['shape'][0])
            axes['events_found'].append(required(prefix + '.events_found')['shape'][0])
    schema = fields(trusted_context, axes)
    if set(records) != {r['key'] for r in schema}:
        raise ValueError('Missing or extra source-defined fields: ' + str(set(records) ^ {r['key'] for r in schema}))
    if branch in ('ctf_tde', 'elekta_tde', 'ctf_dynemo') and manifest['source_weights'] != {'native_w_npy': 'absent', 'group_average': 'equal', 'sample_counts_are_separate_not_injected_weights': True}:
        raise ValueError('Preserve native absent w.npy and equal group average')
    if branch not in ('ctf_static', 'elekta_ae'):
        trimmed = manifest['spectral_input']
        if not trimmed or len(trimmed) != R or [r['shape'][0] for r in trimmed] != axes['alpha_samples'] or any(r['shape'][1] != C for r in trimmed):
            raise ValueError('Original raw spectral trim is complete and matches inferred alpha')
    ordered = []
    compact_axes = {}
    for spec in schema:
        r = records[spec['key']]
        if r['shape'] != spec['shape']:
            raise ValueError('Full source-derived axes mismatch: ' + spec['key'])
        body = read(r['file'])
        if len(body) != r['bytes'] or hashlib.sha256(body).hexdigest() != r['sha256']:
            raise ValueError('Primitive capture pin mismatch: ' + spec['key'])
        x = primitive_npy(body)
        if list(x.shape) != r['shape'] or x.dtype.str != r['dtype'] or x.nbytes != r['numeric_bytes'] or hashlib.sha256(x.tobytes(order='C')).hexdigest() != r['c_order_body_sha256']:
            raise ValueError('Primitive body shape/dtype/identity mismatch')
        support = np.zeros(x.shape, dtype='u1')
        support[np.isnan(x)] = 1
        support[np.isposinf(x)] = 2
        support[np.isneginf(x)] = 3
        counts = np.bincount(support.ravel(), minlength=4).tolist()
        if spec['key'] in ('spectra.f', 'event.t'):
            if counts[0] != x.size or (x.size > 1 and not np.all(np.diff(x) > 0)):
                raise ValueError('Finite strictly increasing complete native axis')
            compact_axes[spec['key']] = x.tolist()
        if spec['key'] == 'summary.alp_corr' and not np.all(np.diagonal(x, axis1=-2, axis2=-1) == 0):
            raise ValueError('Source-zeroed DyNeMo correlation diagonal')
        if spec['key'] == 'spectra.nnmf':
            peaks = np.argmax(x, axis=-1).tolist()
            if peaks != sorted(peaks):
                raise ValueError('Literal source ascending NNMF peak order')
            compact_axes['nnmf_peak_indices'] = peaks
            compact_axes['nnmf_peak_tie'] = len(set(peaks)) != len(peaks)
        ordered.append({**spec, 'artifact': r, 'support': dict(zip(('finite', 'nan', 'positive_infinity', 'negative_infinity'), counts)),
                        'support_pattern_sha256': hashlib.sha256(support.tobytes()).hexdigest()})
    return {'schema': 'osl19_complete_literal_output_v1', 'branch': branch,
            'context': trusted_context, 'capture_manifest_sha256': hashlib.sha256(manifest_body).hexdigest(),
            'ordered_fields': ordered, 'dynamic_axes': axes, 'native_axes': compact_axes,
            'semantic_axes': semantic_axes(branch),
            'coordinates': coords, 'coordinate_signature': coordinate_signature(trusted_context, coords),
            'spectral_input': manifest['spectral_input'], 'source_weights': manifest['source_weights'],
            'structured': manifest.get('structured', {}),
            'model_state': manifest.get('model_state'),
            'auxiliary_admission': {'required': branch != 'ctf_static' and trusted_context['role'] != 'A',
                                    'role': trusted_context['role'],
                                    'candidate_reported_free_energy_is_selection_authority': False,
                                    'A_hmm_operator_parameter_route': 'selection.native_hmm_parameters',
                                    'A_dynemo_original_trajectory_selector_reconstructed': False},
            'raw_state_order': 'literal_original', 'comparison_permutation_applied': False,
            'logical_input_bytes': consumed, 'native_external_closure': 'required_separately',
            'scientific_qualification': False}


def restore_model_state(model, literal, read_bytes, *, max_input_bytes):
    """Future operator-only installation into an already approved native model.

    No model is constructed/imported here. Names, ordered shapes and primitive
    pins must exactly match the approved historical architecture. A final-epoch
    DyNeMo training loss cannot be reconstructed from this post-fit state.
    """
    state = literal['model_state']
    if not state or state['family'] != ('dynemo' if literal['branch'] == 'ctf_dynemo' else 'hmm'):
        raise ValueError('Native model family')
    table = {r['key']: r['artifact'] for r in literal['ordered_fields']}
    consumed = 0
    def load(key):
        nonlocal consumed
        r = table[key]
        body = read_bytes(r['file'], max_input_bytes - consumed)
        consumed += len(body)
        if consumed > max_input_bytes or len(body) != r['bytes'] or hashlib.sha256(body).hexdigest() != r['sha256']:
            raise ValueError('Model-state primitive pin/read allocation')
        return primitive_npy(body)
    variables = list(model.model.weights)
    if len(variables) != len(state['keras_weights']):
        raise ValueError('Complete original architecture variable count')
    weights = []
    for variable, row in zip(variables, state['keras_weights']):
        if str(variable.name) != row['name'] or list(variable.shape) != row['shape'] or bool(variable.trainable) != row['trainable']:
            raise ValueError('Exact native architecture variable identity')
        weights.append(load(row['key']))
    model.model.set_weights(weights)
    if state['family'] == 'hmm':
        model.set_trans_prob(load('model.transition'))
        model.set_state_probs_t0(load('model.initial'))
    for key, value in state['nonweight_layer_state'].items():
        if key != 'static_loss_scaling_factor.n_batches' or type(value) is not int or value < 1:
            raise ValueError('Exact reviewed native non-weight state')
        model.model.get_layer('static_loss_scaling_factor').n_batches = value
    return {'installed_complete_numeric_model_state': True, 'logical_input_bytes': consumed,
            'training_trajectory_reconstructed': False, 'native_evaluation_executed': False,
            'dyne_mo_original_final_history_loss_reconstructible_from_state': False}


def project_all_nnmf_components(spectra, components):
    """Source-equivalent derived per-run maps, explicitly not a saved literal.

    The exact held power.py197-201/connectivity.py257-261 arithmetic uses a
    matrix product followed by division by each component sum. No fit, frequency
    selection, sample weighting or state rematching occurs here. Undefined
    component support remains NaN/Inf, not replaced or omitted.
    """
    import numpy as np
    if spectra.ndim not in (4, 5) or components.ndim != 2 or components.shape[0] != 2 or spectra.shape[-1] != components.shape[1]:
        raise ValueError('Complete per-run spectra and both source NNMF components')
    result = []
    for run in spectra:
        flattened = run.reshape(-1, run.shape[-1]).real
        values = components @ flattened.T
        with np.errstate(divide='ignore', invalid='ignore'):
            for j in range(2):
                values[j] /= np.sum(components[j])
        result.append(values.reshape((2,) + run.shape[:-1]))
    return np.array(result)


def assemble_nnmf_derivations(literal, read_bytes, output_store, *, max_input_bytes):
    """Emit both per-run component maps from authenticated full literal arrays.

    output_store supplies its own explicit write cap. It writes primitive NPY
    through CaptureSink.array; no pickle/model reader or author import is used.
    These additional arrays are named derived_nnmf, not relabeled source files.
    """
    from .sink import CaptureSink
    if literal['branch'] not in ('ctf_tde', 'elekta_tde'):
        raise ValueError('Only native two-component NNMF branches')
    table = {x['key']: x['artifact'] for x in literal['ordered_fields']}
    consumed = 0
    def load(key):
        nonlocal consumed
        r = table[key]
        data = read_bytes(r['file'], max_input_bytes - consumed)
        consumed += len(data)
        if consumed > max_input_bytes or len(data) != r['bytes'] or hashlib.sha256(data).hexdigest() != r['sha256']:
            raise ValueError('Derived-map original primitive pin or explicit read cap')
        return primitive_npy(data)
    components = load('spectra.nnmf')
    sink = CaptureSink(output_store, literal['context'])
    for key, target in [('spectra.psd', 'derived_nnmf.person_power'), ('spectra.coh', 'derived_nnmf.person_coherence')]:
        source = load(key)
        result = project_all_nnmf_components(source, components)
        sink.array(target, result)
        del source, result
    receipt = {'schema': 'osl19_separate_nnmf_derived_maps_v1',
               'source_literal_capture_sha256': literal['capture_manifest_sha256'],
               'fields': [{**r, 'axes': (['run', 'nnmf_component_peak_order', 'state', 'channel'] if r['key'].endswith('power') else ['run', 'nnmf_component_peak_order', 'state', 'channel', 'channel_2']),
                           'run_axis': 0, 'state_axes': [2], 'panel': 'derived_nnmf',
                           'aggregation': {'level': 'run', 'operation': 'source_component_weighted_frequency_average'}} for r in sink.fields.values()],
               'component_order': 'literal_source_ascending_peak_frequency',
               'state_order': 'literal_original', 'source_saved_files': False,
               'arithmetic': 'held_power_197_201_and_connectivity_257_261',
               'logical_input_bytes': consumed, 'scientific_qualification': False}
    output_store.write('NNMF_DERIVED.json', encoded(receipt))
    return receipt


def comparison_array(array, spec, order):
    """Apply the same externally reviewed RV order on every state axis only."""
    import numpy as np
    if spec.get('comparison') is False:
        raise ValueError('Auxiliary reconstruction/training state is not a scientific comparison panel')
    if type(order) not in (list, tuple) or sorted(order) != list(range(len(order))):
        raise ValueError('Complete one-to-one state order')
    result = array
    for axis in spec['state_axes']:
        if result.shape[axis] != len(order):
            raise ValueError('Correspondence/state axis mismatch')
        result = np.take(result, order, axis=axis)
    return result


def comparison_view(literal, reference, order, correspondence_receipt):
    """A separately named metadata view; raw artifacts are never overwritten."""
    if literal['coordinate_signature'] != reference['coordinate_signature']:
        raise ValueError('Different/unauthenticated native representation: correspondence unavailable')
    K = BRANCHES[literal['branch']]['states']
    if K is None or len(order) != K or sorted(order) != list(range(K)):
        raise ValueError('All states/modes in the one correspondence')
    if not correspondence_receipt:
        raise ValueError('Externally bound covariance RV/cost/environment/tie receipt required')
    return {'schema': 'osl19_separate_comparison_view_v1',
            'literal_capture_sha256': literal['capture_manifest_sha256'],
            'reference_capture_sha256': reference['capture_manifest_sha256'],
            'coordinate_signature': literal['coordinate_signature'],
            'state_order': list(order), 'correspondence_receipt': correspondence_receipt,
            'fields': [{'key': x['key'], 'state_axes': x['state_axes'],
                        'artifact': x['artifact']} for x in literal['ordered_fields'] if x.get('comparison', True)],
            'auxiliary_fields_retained_only_in_literal': [x['key'] for x in literal['ordered_fields'] if not x.get('comparison', True)],
            'raw_artifacts_mutated': False, 'scientific_qualification': False}
