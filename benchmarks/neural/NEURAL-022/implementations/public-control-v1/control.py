"""Fit public active-only controls, then predict from a hash-bound frozen artifact.

This is a transparent software control, not a candidate sandbox or provenance
attestation. No private target, reference, operator manifest or network is used.
"""
import argparse
import json
import math
from pathlib import Path
import re
import stat
import sys

VENDOR = Path(__file__).resolve().parents[1] / 'artifact-grading/private/vendor'
sys.path.insert(0, str(VENDOR))
import candidate
import io_support as io
import packet
import numpy as np

CONTROLS = ('active_direction', 'active_mean', 'zero')
DIRECTIONS = tuple(range(0, 360, 45))
TRAINING_SCHEMA = {
    'ids': ('<U24', (141,)), 'counts': ('<i8', (141, 390)),
    'velocity': ('<f8', (141, 2)), 'directions': ('<i8', (141,)),
}


def need(ok, message):
    if not ok:
        raise ValueError(message)


def capture(path, sha256, maximum):
    """Capture a bounded ordinary file before decoding any content."""
    path = Path(path).absolute()
    need(type(sha256) is str and re.fullmatch('[0-9a-f]{64}', sha256), 'Exact SHA256')
    need(all(not p.is_symlink() for p in (path, *path.parents)), 'No symbolic links')
    state = path.lstat()
    need(stat.S_ISREG(state.st_mode) and state.st_nlink == 1
         and 0 < state.st_size <= maximum, 'Bounded ordinary input')
    return io.capture(path, {'bytes': state.st_size, 'sha256': sha256}, maximum)


def directions(values, n):
    need(values.shape == (n,) and values.dtype == np.dtype('<i8')
         and set(values.tolist()) == set(DIRECTIONS), 'All eight integer directions')


def training_arrays(raw):
    value = io.npz(raw, TRAINING_SCHEMA)
    packet.identifiers(value['ids'], 141)
    packet.counts(value['counts'], 141)
    packet.velocity(value['velocity'], 141)
    directions(value['directions'], 141)
    return value


def mean_velocity(values):
    means = []
    for j in range(2):
        column = [float(v[j]) for v in values]
        try:
            mean = math.fsum(column) / len(column)
        except OverflowError:
            # A representable mean can have an unrepresentable unnormalized sum.
            scale = max(abs(v) for v in column)
            mean = (math.fsum(v / scale for v in column) / len(column)) * scale
        means.append(mean)
    return means


def fit(raw, control):
    """Only the 141-row public training archive is an input to this phase."""
    need(control in CONTROLS, 'Declared control chosen before query access')
    training = training_arrays(raw)
    if control == 'active_direction':
        parameters = {'templates': [mean_velocity(training['velocity'][training['directions'] == d])
                                    for d in DIRECTIONS]}
    elif control == 'active_mean':
        parameters = {'mean': mean_velocity(training['velocity'])}
    else:
        parameters = {}
    frozen = {'schema': 'neural022_public_control_v1', 'control': control,
              'units': 'm/s', 'training': io.pin(raw),
              'training_ids': training['ids'].tolist(), 'parameters': parameters}
    validate_frozen(frozen)
    return frozen


def finite_pair(value):
    return type(value) is list and len(value) == 2 and all(
        type(x) in (int, float) and math.isfinite(x) for x in value)


def validate_frozen(value):
    need(type(value) is dict and set(value) == {
        'schema', 'control', 'units', 'training', 'training_ids', 'parameters'}
        and value['schema'] == 'neural022_public_control_v1'
        and value['control'] in CONTROLS and value['units'] == 'm/s', 'Exact frozen schema')
    pin = value['training']
    need(type(pin) is dict and set(pin) == {'bytes', 'sha256'}
         and type(pin['bytes']) is int and 0 < pin['bytes'] <= 600000
         and type(pin['sha256']) is str and re.fullmatch('[0-9a-f]{64}', pin['sha256']),
         'Exact training commitment')
    ids = value['training_ids']
    need(type(ids) is list and len(ids) == 141 and all(type(i) is str
         and re.fullmatch('[0-9a-f]{24}', i) for i in ids) and len(set(ids)) == 141,
         'All unique training identities')
    parameters = value['parameters']
    need(type(parameters) is dict, 'Parameter object')
    if value['control'] == 'active_direction':
        need(set(parameters) == {'templates'} and type(parameters['templates']) is list
             and len(parameters['templates']) == 8
             and all(finite_pair(v) for v in parameters['templates']), 'Eight finite templates')
    elif value['control'] == 'active_mean':
        need(set(parameters) == {'mean'} and finite_pair(parameters['mean']), 'Finite active mean')
    else:
        need(parameters == {}, 'Zero control has no fitted parameters')
    return value


def predict(frozen, query_raw, public):
    """No fitting, normalization or adaptation to query counts occurs here."""
    validate_frozen(frozen)
    rows = candidate.cases(public)
    query = io.npz(query_raw, io.schema('query', candidate.METHODS))
    packet.identifiers(query['ids'], 92)
    packet.counts(query['counts'], 92)
    directions(query['directions'], 92)
    need(query['ids'].tolist() == [r['id'] for r in rows]
         and query['directions'].tolist() == [r['direction'] for r in rows]
         and query['modes'].tolist() == [r['mode'] for r in rows],
         'Query identity, direction and mode must equal complete public roster in order')
    need(not set(query['ids'].tolist()) & set(frozen['training_ids']), 'Disjoint training/query IDs')
    predictions = []
    for row in rows:
        if frozen['control'] == 'active_direction':
            velocity = frozen['parameters']['templates'][DIRECTIONS.index(row['direction'])]
        elif frozen['control'] == 'active_mean':
            velocity = frozen['parameters']['mean']
        else:
            velocity = [0.0, 0.0]
        predictions.append({'id': row['id'], 'velocity': list(velocity)})
    result = {'schema': candidate.SCHEMA, 'predictions': predictions}
    candidate.validate(io.encoded_json(result), public)
    return result


def write_new(path, value, maximum):
    path = Path(path).absolute()
    need(all(not p.is_symlink() for p in (path, *path.parents)), 'No symbolic output links')
    return io.output(path.parent, path.name, io.encoded_json(value), maximum)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    fit_parser = commands.add_parser('fit')
    fit_parser.add_argument('--training', type=Path, required=True)
    fit_parser.add_argument('--training-sha256', required=True)
    fit_parser.add_argument('--control', choices=CONTROLS, required=True)
    fit_parser.add_argument('--out', type=Path, required=True)
    prediction_parser = commands.add_parser('predict')
    for name in ('frozen', 'queries', 'cases'):
        prediction_parser.add_argument('--' + name, type=Path, required=True)
        prediction_parser.add_argument('--' + name + '-sha256', required=True)
    prediction_parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == 'fit':
        value = fit(capture(args.training, args.training_sha256, 600000), args.control)
        pin = write_new(args.out, value, 16384)
    else:
        # Admit the immutable frozen artifact before any query or roster capture.
        frozen = validate_frozen(candidate.strict(capture(args.frozen, args.frozen_sha256, 16384)))
        query_raw = capture(args.queries, args.queries_sha256, 400000)
        public = candidate.strict(capture(args.cases, args.cases_sha256, 16384))
        pin = write_new(args.out, predict(frozen, query_raw, public), candidate.MAX_SUBMISSION_BYTES)
    print(json.dumps({'phase': args.command, 'output': pin}, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
