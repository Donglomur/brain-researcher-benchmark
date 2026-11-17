"""Original MARBLE data-only intake, storage views and explicit source support.

The published pickle is decoded only by the unchanged restricted predecessor.
No original result, temporal boundary or count integrality is inferred here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import types

import numpy as np

SOURCE_SHA256 = '29dffd951853a98615827e7b8f3507907f9e0f0ef67e875410778ab4aadd42ab'
DECODER_SHA256 = 'de8eee64c1400251d18a59bd8c09c8138e352f39f91d15b40201002b19c07d07'
RATS = ('achilles', 'buddy', 'cicero', 'gatsby')
LAYOUTS = {
    'achilles': {'neural': ((10000, 120), (1, 10178), 0, 1221360),
                 'continuous_index': ((10000, 3), (3, 1), 0, 30534)},
    'buddy': {'neural': ((6577, 48), (48, 1), 0, 315696),
              'continuous_index': ((6577, 3), (3, 1), 0, 19731)},
    'cicero': {'neural': ((10000, 55), (55, 1), 2035000, 2608705),
               'continuous_index': ((10000, 3), (3, 1), 111000, 142293)},
    'gatsby': {'neural': ((10000, 66), (66, 1), 165000, 1123716),
               'continuous_index': ((10000, 3), (3, 1), 7500, 51078)}
}
DECODING = 'released-decoding-pca20-segmented-v1'
CONSISTENCY = 'released-consistency-pca10-whole-v1'
PAPER = 'paper-described-pca5-physical10ms-unresolved'


class InputError(ValueError):
    pass


class SourceViews(dict):
    """Views returned only after the exact released file passes its source pin."""

    def __init__(self, arrays):
        super().__init__(arrays)
        self.array_pins = {rat: {name: array_pin(value) for name, value in row.items()}
                           for rat, row in arrays.items()}


def require(condition, message):
    if not condition:
        raise InputError(message)


def sha256(body):
    return hashlib.sha256(body).hexdigest()


def is_sha(value):
    return type(value) is str and len(value) == 64 and all(c in '0123456789abcdef' for c in value)


def read_bytes(path, maximum):
    fd = os.open(Path(path), os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0))
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and 0 < info.st_size <= maximum,
                'bounded ordinary singly linked input required')
        body = stream.read(maximum + 1)
        require(len(body) == info.st_size, 'input extent changed')
    return body


def read_json(path, maximum=4 * 1024**2):
    def unique(rows):
        result = {}
        for key, value in rows:
            require(key not in result, 'duplicate JSON field')
            result[key] = value
        return result
    body = read_bytes(path, maximum)
    value = json.loads(body, object_pairs_hook=unique,
                       parse_constant=lambda _: require(False, 'nonfinite JSON'))
    return value, sha256(body)


def write_json(path, value, public=False):
    body = (json.dumps(value, indent=2, allow_nan=False) + '\n').encode()
    with Path(path).open('xb') as stream:
        stream.write(body)
    Path(path).chmod(0o444 if public else 0o600)
    return {'path': Path(path).name, 'bytes': len(body), 'sha256': sha256(body)}


def array_pin(array):
    value = np.ascontiguousarray(array)
    return {'shape': list(value.shape), 'dtype': value.dtype.str,
            'sha256_C_numeric_bytes': sha256(value.tobytes(order='C'))}


def save_array(path, array, public=False):
    with Path(path).open('xb') as stream:
        np.save(stream, np.ascontiguousarray(array), allow_pickle=False)
    Path(path).chmod(0o444 if public else 0o600)
    body = read_bytes(path, array.nbytes + 4096)
    return {'path': Path(path).name, 'bytes': len(body), 'sha256': sha256(body), **array_pin(array)}


def load_decoder():
    path = Path(__file__).parent / 'dependencies/intake.py'
    body = read_bytes(path, 65536)
    require(sha256(body) == DECODER_SHA256, 'restricted source decoder changed')
    module = types.ModuleType('marble_original_restricted_decoder')
    module.__file__ = str(path)
    exec(compile(body, str(path), 'exec'), module.__dict__)
    return module


def tensor_view(tensor, expected_layout=None):
    require(type(tensor) is dict and set(tensor) == {
        'shape', 'stride', 'storage_offset', 'storage_elements', 'dtype', 'raw'},
        'restricted decoder tensor descriptor required')
    shape, stride = tensor['shape'], tensor['stride']
    offset, count = tensor['storage_offset'], tensor['storage_elements']
    require(type(shape) is tuple and len(shape) == 2 and type(stride) is tuple and len(stride) == 2
            and all(type(n) is int and n > 0 for n in (*shape, *stride))
            and type(offset) is int and offset >= 0 and type(count) is int and 0 < count <= 6000000,
            'invalid bounded rank-two storage geometry')
    require(tensor['dtype'] == '<f4' and type(tensor['raw']) is bytes
            and len(tensor['raw']) == count * 4, 'exact little-endian float32 storage required')
    require(offset + sum((n - 1) * s for n, s in zip(shape, stride)) < count,
            'tensor view exceeds source storage')
    if expected_layout is not None:
        require((shape, stride, offset, count) == expected_layout, 'original source view layout changed')
    return np.ndarray(shape, dtype='<f4', buffer=tensor['raw'], offset=4 * offset,
                      strides=tuple(4 * s for s in stride))


def validate_release(decoded):
    require(type(decoded) is dict and tuple(decoded) == RATS, 'complete original four-rat source required')
    arrays = {}
    for rat in RATS:
        require(type(decoded[rat]) is dict and set(decoded[rat]) == {'neural', 'continuous_index'},
                'original source fields changed')
        arrays[rat] = {}
        for name, layout in LAYOUTS[rat].items():
            view = tensor_view(decoded[rat][name], layout)
            require(np.isfinite(view).all(), 'nonfinite original source values')
            # Noninteger/negative magnitudes are retained: the source helper
            # turns every nonzero value into one event, not a count expansion.
            arrays[rat][name] = view
    return arrays


def read_release(path):
    return SourceViews(validate_release(load_decoder().read_pinned(path)))


def row_id(rat, index):
    require(rat in RATS and type(index) is int and 0 <= index < LAYOUTS[rat]['neural'][0][0],
            'source row outside original view')
    return f'rat_data:{SOURCE_SHA256}:{rat}:row:{index}'


def row_index(identity, rat='achilles'):
    prefix = f'rat_data:{SOURCE_SHA256}:{rat}:row:'
    require(type(identity) is str and identity.startswith(prefix), 'foreign source row identity')
    suffix = identity[len(prefix):]
    require(suffix.isdecimal() and str(int(suffix)) == suffix, 'noncanonical source row identity')
    index = int(suffix)
    require(row_id(rat, index) == identity, 'invalid source row identity')
    return index


def source_rows(rat, start, stop):
    require(type(start) is int and type(stop) is int and 0 <= start < stop <= LAYOUTS[rat]['neural'][0][0],
            'invalid original source interval')
    return [row_id(rat, i) for i in range(start, stop)]


def recipe_support(recipe, rat='achilles'):
    require(rat in RATS, 'unknown source rat')
    if recipe == PAPER:
        raise InputError('Paper PCA5/physical10ms route unavailable: event timing, smoothing boundaries, '
                         'derivative boundaries and complete 2000-query source mapping need independent definition')
    require(recipe in (DECODING, CONSISTENCY), 'unknown explicit source recipe')
    n, channels = LAYOUTS[rat]['neural'][0]
    if recipe == DECODING:
        require(rat == 'achilles', 'Figure5d released decoding selects Achilles only')
        intervals = {'training': (0, 8000), 'query': (8000, 10000)}
        pca_n, scope = 20, 'training source rows [0,8000); query transformed without refit'
    else:
        intervals = {'whole': (0, n)}
        pca_n, scope = 10, 'all released source rows for this rat; Figure5e consistency only'
    segments = {}
    for name, (start, stop) in intervals.items():
        segments[name] = {'input_source_row_interval': [start, stop],
            'marble_anchor_source_row_interval': [start, stop - 1],
            'marble_forward_partner_source_row_interval': [start + 1, stop],
            'marble_rows': stop - start - 1, 'cebra_native_rows': stop - start,
            'omitted_terminal_anchor_source_row': stop - 1,
            'difference': 'PCA[t+1]-PCA[t], no division by either time step',
            'smoothing_context': 'this complete segment only; no cross-split convolution'}
    return {'schema': 'marble-released-support/v1', 'recipe': recipe, 'source_sha256': SOURCE_SHA256,
        'rat': rat, 'row_identity_rule': f'rat_data:{SOURCE_SHA256}:{rat}:row:ZERO_BASED_VIEW_ROW',
        'source_view_rows': n, 'neurons': channels, 'recording_bin_width_seconds': 0.025,
        'absolute_recording_time_or_bin_phase_known': False,
        'helper_event_index_step_ms': 1.0, 'helper_gaussian_sigma_ms': 10.0,
        'equivalent_recording_bin_sigma_seconds': 0.25,
        'event_conversion': 'one event at each nonzero bin index; magnitudes/multiplicity discarded',
        'pca_components': pca_n, 'pca_fit_scope': scope, 'segments': segments,
        'graph_call': {'k': 15, 'delta': 1.5, 'spacing': 'source default 0.0; all input nodes retained'},
        'MARBLE_model_derivative_order': 1,
        'figure5d_2000_query_eligible': False,
        'historical_source_qualified': False}


def export_source(arrays, destination, *, _generated=False):
    """Export complete original views; no smoothing, PCA, models or scoring."""
    require(type(_generated) is bool and (type(arrays) is SourceViews or _generated),
            'verified source views required; generated injection is a test-only API boundary')
    require(set(arrays) == set(RATS), 'complete original source views required')
    destination = Path(destination)
    require(not destination.exists(), 'fresh source output directory required')
    for rat in RATS:
        for name, layout in LAYOUTS[rat].items():
            value = arrays[rat][name]
            require(type(value) in (np.ndarray, np.memmap) and value.shape == layout[0]
                    and value.dtype == np.dtype('<f4') and np.isfinite(value).all(), 'source array changed')
            if not _generated:
                require(array_pin(value) == arrays.array_pins[rat][name], 'source view changed after authentication')
    destination.mkdir(mode=0o700)
    public, private = destination / 'public', destination / 'private'
    public.mkdir(mode=0o700); private.mkdir(mode=0o700)
    visible, protected = {}, {}
    for rat in RATS:
        neural, labels = arrays[rat]['neural'], arrays[rat]['continuous_index']
        visible[rat] = {'neural': save_array(public / f'{rat}-neural.npy', neural, True),
                       'original_layout': {key: {'shape': list(v[0]), 'stride_elements': list(v[1]),
                       'storage_offset_elements': v[2], 'storage_elements': v[3]} for key, v in LAYOUTS[rat].items()},
                       'row_identity_rule': f'rat_data:{SOURCE_SHA256}:{rat}:row:ZERO_BASED_VIEW_ROW',
                       'source_view_row_interval': [0, len(neural)], 'recording_bin_width_seconds': 0.025}
        protected[rat] = {'continuous_index': save_array(private / f'{rat}-labels.npy', labels),
                         'columns': ['position_m', 'right_direction_indicator', 'left_direction_indicator']}
    public_manifest = {'schema': 'marble-original-public-input/v1', 'source_sha256': SOURCE_SHA256,
                       'source_authentication': 'generated_control_views' if _generated else 'publisher_sha256',
                       'rats': visible, 'qualification': 'source_views_only_no_fit_or_scientific_admission'}
    write_json(public / 'inputs.json', public_manifest, True)
    write_json(private / 'labels.json', {'schema': 'marble-original-private-labels/v1',
               'source_sha256': SOURCE_SHA256, 'rats': protected,
               'public_manifest_sha256': sha256(read_bytes(public / 'inputs.json', 65536)),
               'public_source_exposure': 'These released labels are not an untouched holdout.'})
    public.chmod(0o555)
    return {'public_manifest': str(public / 'inputs.json'), 'private_manifest': str(private / 'labels.json'),
            'rats': 4, 'scientific_preprocessing_or_model_run': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-pickle', type=Path, required=True)
    parser.add_argument('--output-root', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(export_source(read_release(args.source_pickle), args.output_root), indent=2))


if __name__ == '__main__':
    main()
