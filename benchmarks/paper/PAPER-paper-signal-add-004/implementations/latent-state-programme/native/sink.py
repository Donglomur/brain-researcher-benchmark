"""Future trusted observation sink. No author imports and no pickle loading.

Installing a sink is not execution authorization or an exit/isolation receipt.
Calls observe already computed objects; original scientific assignments remain.
All files are new primitive NPY or JSON, under explicit future byte ceilings.
"""
import hashlib
import io
import json
import math
from pathlib import Path
import re

_SINK = None


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()


def install_sink(sink):
    global _SINK
    if _SINK is not None:
        raise ValueError('One fresh observation sink per process')
    _SINK = sink


def observe(label, values, kind='arrays'):
    if _SINK is None:
        raise RuntimeError('Externally installed trusted native sink required')
    _SINK.observe(label, values, kind)


class DirectoryStore:
    def __init__(self, root, byte_limit):
        self.root = Path(root)
        if not self.root.is_dir() or self.root.is_symlink() or any(self.root.iterdir()):
            raise ValueError('Existing empty non-symlink capture directory required')
        if type(byte_limit) is not int or byte_limit <= 0:
            raise ValueError('Explicit future output allocation')
        self.limit, self.used = byte_limit, 0

    def write(self, name, body):
        if not re.fullmatch(r'[a-zA-Z0-9_.-]+', name) or self.used + len(body) > self.limit:
            raise ValueError('Capture path or future output byte limit')
        from safe_io import durable_new
        # Reserve the attempted write before publication; a failed write is not
        # free retry capacity. The external provider records physical I/O costs.
        self.used += len(body)
        durable_new(self.root / name, body)


def ordinary(value):
    import numpy as np
    if type(value) in (list, tuple):
        # Historical multitaper returns nested primitive lists under keepdims.
        # Validate leaves before conversion; never call arbitrary __array__ code.
        def leaves(v, depth=0):
            if depth > 8:
                raise ValueError('Bounded primitive nesting')
            if type(v) in (list, tuple):
                for child in v:
                    leaves(child, depth + 1)
            elif type(v) not in (np.ndarray, np.memmap, int, float, bool) and not isinstance(v, np.generic):
                raise ValueError('Primitive numeric leaves only')
            elif hasattr(v, 'dtype') and (v.dtype.hasobject or v.dtype.kind not in 'biuf'):
                raise ValueError('Primitive numeric leaves only')
        leaves(value)
        value = np.asarray(value)
    if type(value) in (int, float, bool) or isinstance(value, np.generic):
        value = np.asarray(value)
    if type(value) not in (np.ndarray, np.memmap) or value.dtype.kind not in 'biuf':
        raise ValueError('Only ordinary primitive numeric arrays/scalars')
    if value.dtype.fields or value.dtype.hasobject:
        raise ValueError('No structured/object array')
    return np.ascontiguousarray(value) if value.ndim else value


def identity(value):
    x = ordinary(value)
    return {'shape': list(x.shape), 'dtype': x.dtype.str, 'numeric_bytes': x.nbytes,
            'c_order_body_sha256': hashlib.sha256(x.tobytes(order='C')).hexdigest()}


class CaptureSink:
    def __init__(self, store, trusted_context):
        # A caller cannot certify trusted execution by supplying this dictionary.
        # The orchestrator authenticates it and external natural exit separately.
        self.store = store
        self.context = json.loads(encoded(trusted_context))
        self.fields = {}
        self.coordinates = None
        self.spectral_input = None
        self.event_files = None
        self.event_trials = []
        self.weights = None
        self.structured = {}
        self.model_state = None
        self.finished = False

    def array(self, key, value):
        import numpy as np
        if self.finished or key in self.fields:
            raise ValueError('No duplicate/late capture: ' + key)
        x = ordinary(value)
        b = io.BytesIO()
        np.save(b, x, allow_pickle=False)
        body = b.getvalue()
        name = hashlib.sha256(key.encode()).hexdigest() + '.npy'
        self.store.write(name, body)
        self.fields[key] = dict(key=key, file=name, bytes=len(body), sha256=hashlib.sha256(body).hexdigest(),
                                **identity(x))

    def runs(self, prefix, arrays):
        if type(arrays) not in (list, tuple) or len(arrays) != len(self.context['runs']):
            raise ValueError('Complete ordered run list required: ' + prefix)
        for i, value in enumerate(arrays):
            self.array(prefix + '/' + str(i).zfill(6), value)

    def structure(self, prefix, value, depth=0):
        import numpy as np
        if depth > 32:
            raise ValueError('Bounded source training metadata tree')
        if value is None or type(value) in (bool, str, int):
            return value
        if type(value) is float and math.isfinite(value):
            return value
        if type(value) in (list, tuple):
            return [self.structure(prefix + '/' + str(i), v, depth + 1) for i, v in enumerate(value)]
        if type(value) is dict:
            if any(type(k) is not str for k in value):
                raise ValueError('Literal string-key source training metadata')
            return {k: self.structure(prefix + '/' + k.replace('~', '~0').replace('/', '~1'), v, depth + 1) for k, v in value.items()}
        if type(value) in (np.ndarray, np.memmap) or isinstance(value, np.generic) or type(value) is float:
            self.array(prefix, value)
            return {'$primitive_array': prefix}
        raise ValueError('Unsupported source training metadata; no pickle/repr substitution')

    def observe(self, label, values, kind='arrays'):
        if self.finished or type(values) is not dict:
            raise ValueError('Capture lifecycle or operand dictionary')
        if kind == 'coordinates':
            if self.coordinates is not None:
                raise ValueError('Only initial prepared coordinate identity is admitted')
            data = values['data']
            inputs = [str(x) for x in data.inputs]
            expected = [r['source_input'] for r in self.context['runs']]
            if inputs != expected or len(data.arrays) != len(expected) or len(data.raw_data_arrays) != len(expected):
                raise ValueError('Native input/run order differs from authenticated preparation')
            self.coordinates = {'source_inputs': inputs, 'prepared': [identity(x) for x in data.arrays],
                                'raw': [identity(x) for x in data.raw_data_arrays],
                                'sampling_frequency': float(data.sampling_frequency),
                                'n_embeddings': getattr(data, 'n_embeddings', None),
                                'n_window': getattr(data, 'n_window', None),
                                'profile': 'literal_historical_native',
                                'preparation_binding': self.context['preparation_binding']}
            if getattr(data, 'pca_components', None) is not None:
                self.array('coordinates.pca_components', data.pca_components)
                self.coordinates['pca_components'] = identity(data.pca_components)
            else:
                self.coordinates['pca_components'] = None
        elif kind == 'structured':
            if label in self.structured:
                raise ValueError('Duplicate source training metadata')
            values = dict(values)
            if label == 'training':
                native_config = dict(values['config'])
                constructor = dict(native_config)
                runtime_objects = {}
                # Exact historical ModelBase.save_config policy (449-470):
                # runtime strategy/regularizers are not constructor payloads.
                for key, value in native_config.items():
                    if key == 'strategy' or 'regularizer' in key:
                        constructor[key] = None
                        if value is not None:
                            info = {'module': type(value).__module__, 'qualified_name': type(value).__qualname__}
                            runtime_objects[key] = info
                            native_config[key] = {'$external_runtime_object': info}
                values['config'] = native_config
                values['config_constructor'] = constructor
                values['config_runtime_objects'] = runtime_objects
            self.structured[label] = self.structure(label, values)
        elif kind == 'run_identity':
            arrays = values['runs']
            if type(arrays) not in (list, tuple) or len(arrays) != len(self.context['runs']):
                raise ValueError('Complete source-trimmed spectral input runs required')
            self.spectral_input = [identity(x) for x in arrays]
        elif kind in ('model_hmm', 'model_dynemo'):
            self.array('model.means', values['means'])
            self.array('model.covs', values['covs'])
            self.runs('model.alpha', values['alpha'])
            model = values['model']
            weights, variables = model.model.get_weights(), list(model.model.weights)
            if len(weights) != len(variables) or not weights:
                raise ValueError('Complete ordered native Keras weights')
            entries = []
            for i, (weight, variable) in enumerate(zip(weights, variables)):
                key = 'model.weights/' + str(i).zfill(6)
                self.array(key, weight)
                entries.append({'index': i, 'key': key, 'name': str(variable.name),
                                'trainable': bool(variable.trainable), 'shape': list(weight.shape),
                                'dtype': weight.dtype.str})
            layer_names = [layer.name for layer in model.model.layers]
            extra = {}
            if 'static_loss_scaling_factor' in layer_names:
                extra['static_loss_scaling_factor.n_batches'] = int(model.model.get_layer('static_loss_scaling_factor').n_batches)
            self.model_state = {'family': 'hmm' if kind == 'model_hmm' else 'dynemo',
                                'keras_weights': entries, 'nonweight_layer_state': extra,
                                'complete_model_weight_list': True, 'optimizer_state_exported': False,
                                'historical_training_rng_state_exported': False,
                                'training_trajectory_reconstruction': False,
                                'postfit_evaluation_runtime_validated': False}
            if kind == 'model_hmm':
                self.array('model.initial', model.state_probs_t0)
                self.array('model.transition', model.get_trans_prob())
        elif kind == 'weights':
            if values['weights'] is not None:
                raise ValueError('Pinned six scripts do not request source spectral weights')
            self.weights = {'native_w_npy': 'absent', 'group_average': 'equal',
                            'sample_counts_are_separate_not_injected_weights': True}
        elif kind == 'event_input':
            self.event_files = list(values['parc_files'])
            if self.event_files != [r['source_input'] for r in self.context['runs']]:
                raise ValueError('Elekta event file order/run identity mismatch')
            self.runs('event.stc', values['stc'])
        elif kind == 'event_trials':
            i = len(self.event_trials)
            if i >= len(self.context['runs']) or values['parc_file'] != self.context['runs'][i]['source_input']:
                raise ValueError('Elekta epoch loop omitted/reordered a run')
            prefix = 'event_trials/' + str(i).zfill(6)
            for key in ('trials', 'events_found', 'events_retained', 'times'):
                self.array(prefix + '.' + key, values[key])
            self.event_trials.append({'run_index': i, 'source_input': values['parc_file'],
                                      'event_id': dict(values['event_id'])})
        else:
            if kind != 'arrays':
                raise ValueError('Unknown trusted capture kind')
            for key, value in values.items():
                self.array(label + '.' + key, value)

    def finish(self):
        if self.finished:
            raise ValueError('Capture already finalized')
        receipt = {'schema': 'osl19_primitive_native_capture_v1', 'context': self.context,
                   'fields': list(self.fields.values()), 'coordinates': self.coordinates,
                   'spectral_input': self.spectral_input, 'source_weights': self.weights,
                   'event_files': self.event_files, 'event_trials': self.event_trials,
                   'structured': self.structured,
                   'model_state': self.model_state,
                   'state_order': 'literal_original', 'external_natural_exit_verified': False,
                   'scientific_qualification': False}
        self.store.write('CAPTURE.json', encoded(receipt))
        self.finished = True
        return receipt
