"""Recompute the complete NEURAL-038 report from an operator-pinned public export.

This is a numerical evaluator, not a participant runtime or biological inference.
The three recovered modules beside this file retain their original source bytes.
"""
import argparse
import io
from pathlib import Path
import re

import numpy as np

import delivery_io as transport
from analysis_core import BLOCKS, ORIGINAL, REVISION, decompose, summarize_blocks
from scorer_core import admit, public_contract, score

COUNTS = (9, 13, 10, 108)
MAX_ARRAY_BYTES = 200000
REPORT_CAP = 16000000


def metadata(panel, inputs):
    """Validate full declared scope and the row-to-array join before array reads."""
    wanted = public_contract(panel)
    transport.exact(inputs, ('schema', 'packet_id', 'blocks'))
    transport.need(inputs['schema'] == 'neural038-input-v1' and
                   inputs['packet_id'] == panel['packet_id'], 'Same public packet')
    transport.need(type(inputs['blocks']) is list and len(inputs['blocks']) == 4,
                   'Complete four input blocks')
    for position, block in enumerate(inputs['blocks']):
        name = BLOCKS[position]
        revision = name == 'revision_pool'
        fields = ['block_id', 'kind', 'cell_keys', 'arrays', 'shape', 'window',
                  'source_members', 'source_full_condition_shape', 'animal_identity']
        if revision:
            fields.append('revision_independence_established')
        transport.exact(block, fields)
        transport.need(block['block_id'] == name and
                       block['kind'] == ('revision' if revision else 'original'),
                       'Original blocks and revision remain separate')
        frames = 200 if revision else 300
        count = COUNTS[position]
        transport.need(block['shape'] == [count, frames] and
                       all(type(x) is int for x in block['shape']) and
                       block['window'] == ([123, 126] if revision else [125, 128]) and
                       all(type(x) is int for x in block['window']),
                       'Exact native frame window and complete membership shape')
        keys = block['cell_keys']
        transport.need(type(keys) is list and len(keys) == count and
                       all(type(key) is str for key in keys) and len(set(keys)) == count and
                       set(keys) == set(wanted[name]) and len(wanted[name]) == count,
                       'Exact complete membership join')
        full = block['source_full_condition_shape']
        transport.need(type(full) is list and len(full) == 2 and
                       all(type(x) is int and x > 0 for x in full) and
                       full[1] == frames and block['animal_identity'] is None,
                       'Retained source shape and unresolved animal identity')
        conditions = REVISION if revision else ORIGINAL
        if revision:
            transport.need(keys == ['revision_row_%d' % i for i in range(count)] and
                           full == [count, frames] and
                           block['revision_independence_established'] is False,
                           'Complete revision pool with no invented biological grouping')
            members = ['panelGI_new_' + condition for condition in conditions]
        else:
            transport.need(all(re.fullmatch(r'source_row_(0|[1-9][0-9]*)', key)
                               and int(key.removeprefix('source_row_')) < full[0]
                               for key in keys), 'Original source ROI row identities')
            prefix = 'panelGI_expt%d_' % (position + 1)
            members = [prefix + condition for condition in (*conditions, 'stim')]
        transport.need(block['source_members'] == members, 'Exact source condition semantics')
        transport.exact(block['arrays'], conditions)
        for condition, record in block['arrays'].items():
            transport.exact(record, ('path', 'bytes', 'sha256'))
            transport.need(record['path'] == 'arrays/' + name + '_' + condition + '.npy',
                           'One canonical public array per condition')
            transport.check_pin({key: record[key] for key in ('bytes', 'sha256')},
                                MAX_ARRAY_BYTES)
    return wanted


def load_array(root, record, shape):
    body = transport.read(transport.resolve(root, record['path']), MAX_ARRAY_BYTES,
                          {key: record[key] for key in ('bytes', 'sha256')})
    stream = io.BytesIO(body)
    version = np.lib.format.read_magic(stream)
    transport.need(version in ((1, 0), (2, 0)), 'Supported NPY header')
    reader = (np.lib.format.read_array_header_1_0 if version == (1, 0)
              else np.lib.format.read_array_header_2_0)
    found_shape, _, dtype = reader(stream, max_header_size=16384)
    transport.need(found_shape == tuple(shape) and dtype.kind == 'f' and
                   dtype.itemsize in (4, 8) and
                   stream.tell() + shape[0] * shape[1] * dtype.itemsize == len(body),
                   'Exact bounded numeric NPY payload, no objects or trailing bytes')
    return np.load(io.BytesIO(body), allow_pickle=False, max_header_size=16384)


def recompute(root, panel, inputs):
    wanted = metadata(panel, inputs)
    calculated = {}
    for block in inputs['blocks']:
        arrays = {condition: load_array(root, record, block['shape'])
                  for condition, record in block['arrays'].items()}
        result = decompose(arrays, block['kind'], block['cell_keys'], np)
        transport.need({row['cell_key']: row['availability'] for row in result['cells']}
                       == wanted[block['block_id']], 'Measured availability equals public mask')
        calculated[block['block_id']] = result
    return {'schema': 'neural038-reference-v1', 'packet_id': panel['packet_id'],
            'blocks': [{'block_id': name, **calculated[name]} for name in BLOCKS],
            **summarize_blocks(calculated)}


def evaluate(root, panel, inputs, submission):
    metadata(panel, inputs)
    admit(panel, submission)
    expected = recompute(root, panel, inputs)
    result = score(panel, submission, lambda: expected)
    result['recomputed_reference_callbacks'] = result.pop('private_target_callbacks')
    result['reference_origin'] = 'independent_recomputation_from_pinned_public_traces'
    result['access_mode_result'] = None
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--public-root', type=Path, required=True)
    parser.add_argument('--panel-sha256', required=True)
    parser.add_argument('--input-sha256', required=True)
    parser.add_argument('--submission', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    values = []
    for name, expected in [('panel.json', args.panel_sha256), ('input.json', args.input_sha256)]:
        transport.need(re.fullmatch('[a-f0-9]{64}', expected), 'Operator-frozen metadata digest')
        body = transport.read(args.public_root / name, 100000)
        transport.need(transport.pin(body)['sha256'] == expected, 'Exact frozen public metadata')
        values.append(transport.decode(body))
    submission = transport.json_file(args.submission, REPORT_CAP)
    result = evaluate(args.public_root, *values, submission)
    transport.put(args.output, result, 100000)


if __name__ == '__main__':
    main()
