"""Bind existing complete clean operands to the exact original source, without copies.

An ASSETS digest is only a cache declaration. Only bitwise comparison with the
restricted, publisher-pinned source views establishes the source binding.
These receipts describe trusted operator files; they do not isolate labels.
"""
from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
import stat
import struct

import numpy as np

import inputs


def expected_files():
    result = []
    for rat in inputs.RATS:
        n, channels = inputs.LAYOUTS[rat]['neural'][0]
        cut = int(n * 0.8)
        result.append({'path': f'private/labels/{rat}.npy', 'rat': rat,
                       'source_field': 'continuous_index', 'shape': [n, 3],
                       'source_row_interval': [0, n], 'role': 'operator_private_labels'})
        for segment, start, stop in (('train', 0, cut), ('test', cut, n)):
            result.append({'path': f'public/input/clean-{rat}-{segment}.npy', 'rat': rat,
                           'source_field': 'neural', 'shape': [stop-start, channels],
                           'source_row_interval': [start, stop], 'role': 'participant_neural_input'})
    return result


def inspect_npy(body, expected_shape):
    inputs.require(type(body) is bytes and body[:6] == b'\x93NUMPY', 'NPY magic required')
    version = tuple(body[6:8])
    inputs.require(version in ((1, 0), (2, 0)), 'bounded NPY version 1 or 2 required')
    prefix = 10 if version == (1, 0) else 12
    inputs.require(len(body) >= prefix, 'truncated NPY header length')
    length = struct.unpack('<H' if prefix == 10 else '<I', body[8:prefix])[0]
    inputs.require(0 < length <= 4096 and len(body) >= prefix + length, 'bounded NPY header required')
    try:
        node = ast.parse(body[prefix:prefix+length].decode('latin1').strip(), mode='eval').body
        inputs.require(type(node) is ast.Dict and len(node.keys) == 3
                       and all(type(k) is ast.Constant and type(k.value) is str for k in node.keys)
                       and len({k.value for k in node.keys}) == 3, 'unique literal NPY fields required')
        header = ast.literal_eval(node)
    except (ValueError, SyntaxError, UnicodeError) as exc:
        raise inputs.InputError('invalid literal NPY header') from exc
    inputs.require(type(header) is dict and set(header) == {'descr', 'fortran_order', 'shape'},
                   'exact NPY header fields required')
    shape = header['shape']
    inputs.require(type(shape) is tuple and len(shape) == 2
                   and all(type(v) is int and v > 0 for v in shape)
                   and list(shape) == list(expected_shape), 'original cache shape required')
    inputs.require(header['descr'] == '<f4' and header['fortran_order'] is False,
                   'little-endian float32 C-order cache required')
    offset = prefix + length
    inputs.require(len(body) == offset + shape[0] * shape[1] * 4, 'exact NPY numeric extent required')
    return {'version': list(version), 'shape': list(shape), 'dtype': '<f4',
            'fortran_order': False, 'data_offset_bytes': offset,
            'numeric_bytes': shape[0] * shape[1] * 4}


def inspect_cache(root):
    """Read file bytes for hashing/header checks only; no numeric decoding."""
    root = Path(root)
    assets, assets_sha = inputs.read_json(root / 'private/ASSETS.json', 65536)
    inputs.require(type(assets) is dict and assets.get('schema') == 'marble_preparation_v1'
                   and assets.get('input_sha256') == inputs.SOURCE_SHA256
                   and type(assets.get('files')) is list, 'expected source cache manifest required')
    declared = {}
    for row in assets['files']:
        inputs.require(type(row) is dict and type(row.get('path')) is str
                       and row['path'] not in declared, 'unique declared cache paths required')
        declared[row['path']] = row
    rows = []
    for expected in expected_files():
        path = root / expected['path']
        row = declared.get(expected['path'])
        inputs.require(type(row) is dict and row.get('shape') == expected['shape']
                       and row.get('dtype') == 'float32'
                       and type(row.get('bytes')) is int and inputs.is_sha(row.get('sha256')),
                       'complete expected clean/label cache declaration required')
        maximum = expected['shape'][0] * expected['shape'][1] * 4 + 4108
        body = inputs.read_bytes(path, maximum)
        inputs.require(len(body) == row['bytes'] and inputs.sha256(body) == row['sha256'],
                       'cache file differs from declared digest or size')
        header = inspect_npy(body, expected['shape'])
        info = path.stat(follow_symlinks=False)
        rows.append({**expected, 'bytes': len(body), 'sha256': row['sha256'],
                     'header': header, 'observed_mode': oct(stat.S_IMODE(info.st_mode))})
    return {'schema': 'marble-existing-cache-header-inventory/v1',
            'source_sha256_declared': inputs.SOURCE_SHA256,
            'assets_sha256': assets_sha, 'files': rows,
            'source_binding_verified': False, 'numeric_values_decoded': False,
            'half_neuron_files_read': False, 'file_bytes_hashed': sum(r['bytes'] for r in rows),
            'label_isolation_verified': False}


def bind_cache(root, source_views, inventory):
    """Trusted operator API; caller must first obtain views via read_release()."""
    inputs.require(type(source_views) is inputs.SourceViews, 'publisher-pinned source views required')
    inputs.require(type(inventory) is dict and inventory.get('schema') ==
                   'marble-existing-cache-header-inventory/v1', 'cache header inventory required')
    # Independently reread the manifest/files. Do not trust edited receipt fields.
    current = inspect_cache(root)
    inputs.require(current == inventory, 'cache declaration, headers or files changed since inspection')
    bindings = []
    for rat in inputs.RATS:
        for field in inputs.LAYOUTS[rat]:
            value = source_views[rat][field]
            inputs.require(inputs.array_pin(value) == source_views.array_pins[rat][field],
                           'source view changed after authentication')
    for row in current['files']:
        body = inputs.read_bytes(Path(root) / row['path'], row['bytes'])
        inputs.require(inputs.sha256(body) == row['sha256'], 'cache changed before value comparison')
        start, stop = row['source_row_interval']
        source = source_views[row['rat']][row['source_field']][start:stop]
        cached_bits = np.frombuffer(body, dtype='<u4', offset=row['header']['data_offset_bytes'])
        source_bits = np.ascontiguousarray(source).view('<u4').reshape(-1)
        inputs.require(cached_bits.shape == source_bits.shape and np.array_equal(cached_bits, source_bits),
                       'cache numeric bytes differ from exact original source rows')
        layout = inputs.LAYOUTS[row['rat']][row['source_field']]
        bindings.append({**row, 'bitwise_original_view_match': True,
                         'source_layout': {'shape': list(layout[0]), 'stride_elements': list(layout[1]),
                                           'storage_offset_elements': layout[2], 'storage_elements': layout[3]},
                         'row_identity_rule': f'rat_data:{inputs.SOURCE_SHA256}:{row["rat"]}:row:ZERO_BASED_VIEW_ROW',
                         'first_row_id': inputs.row_id(row['rat'], start),
                         'last_row_id': inputs.row_id(row['rat'], stop-1)})
    return {'schema': 'marble-existing-cache-original-binding/v1',
            'source_sha256': inputs.SOURCE_SHA256, 'decoder_sha256': inputs.DECODER_SHA256,
            'assets_sha256': current['assets_sha256'], 'files': bindings,
            'source_binding_verified': True, 'complete_original_views': 8,
            'source_view_rows_by_rat': {r: inputs.LAYOUTS[r]['neural'][0][0] for r in inputs.RATS},
            'new_numeric_files_written': 0, 'half_neuron_files_read': False,
            'smoothing_PCA_models_or_scoring_run': False,
            'label_isolation_verified': False,
            'authority': 'trusted operator source-to-cache comparison; receipt is not an independent attestation',
            'figure5d_2000_query_eligible': False, 'historical_source_qualified': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache-root', type=Path, required=True)
    parser.add_argument('--output-json', type=Path, required=True)
    parser.add_argument('--source-pickle', type=Path,
                        help='Omit for header/hash inventory; provide only for admitted original-source comparison.')
    args = parser.parse_args()
    result = inspect_cache(args.cache_root)
    if args.source_pickle is not None:
        result = bind_cache(args.cache_root, inputs.read_release(args.source_pickle), result)
    inputs.write_json(args.output_json, result)
    print(json.dumps({'schema': result['schema'], 'files': len(result['files']),
                      'source_binding_verified': result['source_binding_verified']}))


if __name__ == '__main__':
    main()
