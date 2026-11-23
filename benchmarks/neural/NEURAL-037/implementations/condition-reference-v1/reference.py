#!/usr/bin/env python3
"""Prospective training-only mean reference; no fitting, targets, or scoring."""
import argparse
from fractions import Fraction
import hashlib
import math
from pathlib import Path
import types

import numpy as np

HERE = Path(__file__).resolve().parent
BOOTSTRAP_BYTES = 4065
BOOTSTRAP_SHA256 = '5a40ba3cc5f3359c162c38c399f96526aec5f941407231fc615a7b44e3a078b4'
RULE = 'neural037-opposite-order-observed-frame-mean-zero-empty-roi-v1'
CONTEXT_CAP = 4_500_000
PANEL_CAP = 64_000_000


def source_bundle():
    """Reuse the existing captured source and exact single-context view loader."""
    path = HERE.parent / 'condition-viewer-v1' / 'source.py'
    body = path.read_bytes()
    if len(body) != BOOTSTRAP_BYTES or hashlib.sha256(body).hexdigest() != BOOTSTRAP_SHA256:
        raise ValueError('Selected view bootstrap changed')
    module = types.ModuleType('_neural037_reference_source')
    module.__file__ = str(path)
    exec(compile(body, str(path), 'exec'), module.__dict__)
    return module.load()


def signed_mean(values):
    """Equal-frame mean with exact finite-float summation and one final rounding."""
    values = tuple(float(value) for value in values)
    if not values or not all(math.isfinite(value) for value in values):
        raise ValueError('Finite nonempty observed training values required')
    # Finite binary64 ratios have power-of-two denominators. Common-denominator
    # integer summation avoids overflow and preserves tiny residuals after large
    # positive/negative cancellation. Only the final mean is rounded to float64.
    ratios = [value.as_integer_ratio() for value in values]
    denominator = max(bottom for _, bottom in ratios)
    numerator = sum(top * (denominator // bottom) for top, bottom in ratios)
    result = float(Fraction(numerator, denominator * len(values)))
    if not math.isfinite(result):
        raise ValueError('Reference mean is outside finite float64 range')
    return result


def predict(metadata, arrays, bundle):
    """Use only the query acquisition's opposite order; complete every ROI/frame."""
    io = bundle.io
    query = metadata['query']
    contexts = {row['context_id']: row for row in bundle.panel['contexts']}
    name = query.get('context_id')
    io.need(name in contexts and query == contexts[name], 'Exact complete original query geometry')
    other = 'CBA' if query['query_order'] == 'ABC' else 'ABC'
    selected = query['acquisition'] + '_' + other
    io.need(selected in arrays, 'Visible same-acquisition opposite order required')
    means, counts = arrays[selected]
    shape = (len(query['cell_keys']), query['frames'])
    io.need(type(means) is np.ndarray and type(counts) is np.ndarray and
            means.dtype == np.float64 and counts.dtype == np.uint16 and
            means.shape == counts.shape == shape and np.isfinite(means).all() and
            np.all(counts <= 50) and np.any(counts > 0) and
            np.all(means[counts == 0] == 0), 'Exact observed training means/counts')
    responses = []
    support = []
    for index, key in enumerate(query['cell_keys']):
        observed = counts[index] > 0
        size = int(observed.sum())
        # This zero is an explicit uninformed prediction convention, never an
        # observed response. The query availability mask is not an input.
        value = signed_mean(means[index, observed]) if size else 0.0
        responses.append({'cell_key': key, 'values': [value] * query['frames']})
        support.append(size)
    return {'context_id': name, 'status': 'complete', 'responses': responses}, support


def produce(view, context_id, bundle=None):
    b = source_bundle() if bundle is None else bundle
    metadata, input_pin, arrays = b.local('viewer').load_view(view, context_id, b)
    outcome, support = predict(metadata, arrays, b)
    return {'schema': 'neural037-training-mean-reference-v1', 'rule': RULE,
            'packet_id': b.panel['packet_id'], 'context_id': context_id,
            'source_binding': b.source_binding, 'input_pin': input_pin,
            'training_observed_frames_per_roi': support, 'outcome': outcome,
            'scientific_qualified': False}


def collect(records, bundle=None):
    """Assemble complete separately captured programme outputs, without targets."""
    b = source_bundle() if bundle is None else bundle
    io = b.io
    io.need(type(records) is list and len(records) == 12, 'All twelve reference captures required')
    received = {}
    contexts = {row['context_id']: row for row in b.panel['contexts']}
    for record in records:
        io.exact(record, ['context_id', 'path', 'bytes', 'sha256'])
        name = record['context_id']
        io.need(type(name) is str and name in contexts and name not in received,
                'Exact unique original reference context')
        value = io.decode(io.read(Path(record['path']), CONTEXT_CAP,
                                 {key: record[key] for key in ('bytes', 'sha256')}))
        io.exact(value, ['schema', 'rule', 'packet_id', 'context_id', 'source_binding',
                        'input_pin', 'training_observed_frames_per_roi', 'outcome',
                        'scientific_qualified'])
        index = b.lock['contexts'].index(name)
        selected = [row for row in b.lock['files'] if row['fold'] is None or row['fold'] == index]
        descriptor = next(row for row in selected if row['target'] == 'view/input.json')
        io.need(value['schema'] == 'neural037-training-mean-reference-v1' and value['rule'] == RULE and
                value['packet_id'] == b.panel['packet_id'] and value['context_id'] == name and
                value['source_binding'] == b.source_binding and
                value['input_pin'] == {key: descriptor[key] for key in ('bytes', 'sha256')} and
                value['scientific_qualified'] is False, 'Same fixed reference, source, and original input')
        support = value['training_observed_frames_per_roi']
        query = contexts[name]
        io.need(type(support) is list and len(support) == len(query['cell_keys']) and
                all(type(n) is int and 0 <= n <= query['frames'] for n in support),
                'Complete training support diagnostics')
        outcome = value['outcome']
        io.need(type(outcome) is dict and outcome.get('context_id') == name and
                outcome.get('status') == 'complete', 'Same complete reference outcome')
        received[name] = outcome
    submission = {'schema': 'neural037-predictions-v1', 'packet_id': b.panel['packet_id'],
                  'outcomes': [received[name] for name in b.lock['contexts']]}
    b.core.admit(b.panel, submission, np)
    io.need(len(io.canonical(submission)) <= PANEL_CAP, 'Original complete prediction byte cap')
    return submission


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_subparsers(dest='mode', required=True)
    one = modes.add_parser('predict', help='Run once on one externally isolated original view')
    one.add_argument('--view', type=Path, required=True)
    one.add_argument('--context', required=True)
    one.add_argument('--output', type=Path, required=True)
    all_cases = modes.add_parser('collect', help='Assemble all twelve externally captured reference outcomes')
    all_cases.add_argument('--captures', type=Path, required=True)
    all_cases.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    b = source_bundle()
    output = b.io.regular(args.output)
    b.io.need(not output.is_relative_to(HERE.parents[4]), 'Reference outputs stay outside the source checkout')
    if args.mode == 'predict':
        b.io.need(not output.is_relative_to(b.io.regular(args.view)), 'Reference output stays outside the input view')
        result, cap = produce(args.view, args.context, b), CONTEXT_CAP
    else:
        result, cap = collect(b.io.json_file(args.captures, 65536), b), PANEL_CAP
    pin = b.io.put(output, result, cap)
    print(b.io.canonical({'output': pin, 'rule': RULE, 'scored': False,
                         'scientific_qualified': False}).decode('ascii'), end='')


if __name__ == '__main__':
    main()
