"""Operator-only scorer for a frozen, complete 650-context prediction collection.

All candidate arrays are validated and hashed before the target loader is called.
The second pass checks the same hashes. Candidate programs are never executed.
Only the compact authenticated operator-bundle route is supported here.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
import re
import zipfile

import numpy as np

from core import PEOPLE, ROIS, FAMILIES, PHASES, UNITS, need, feature_score, contrasts, participant_summary, strict_mean
from io_utils import read_json, ordinary_bytes, strict_json
from artifacts import public_contract, validate_submission, load

PRIMARY = 'imagery_cnn7_minus_cnn1_HVC_minus_LVC'


def validate_gold(gold):
    expected = {p + '_' + s for p in PEOPLE for s in PHASES} | {'bank_' + f for f in FAMILIES}
    need(type(gold) is dict and set(gold) == expected, 'Exact private target members')
    for person in PEOPLE:
        for phase, n, repeat in [('imagery', 500, 10), ('perception', 1750, 35)]:
            y = gold[person + '_' + phase]
            need(isinstance(y, np.ndarray) and y.shape == (n,) and y.dtype.kind in 'iu'
                 and set(y.tolist()) == set(range(50))
                 and all(np.sum(y == c) == repeat for c in range(50)), 'Full fixed private label support')
    for family in FAMILIES:
        bank = gold['bank_' + family]
        need(isinstance(bank, np.ndarray) and bank.shape == (50, UNITS)
             and bank.dtype.kind == 'f' and np.isfinite(bank).all(), 'Finite matched private category bank')


def summarize(matrix, diagnostics):
    need(set(matrix) == set(PEOPLE), 'All five participants required')
    per_person = {p: contrasts(matrix[p]) for p in PEOPLE}
    report = {k: participant_summary([per_person[p][k] for p in PEOPLE])
              for k in per_person[PEOPLE[0]]}
    absolute = participant_summary([
        strict_mean([matrix[p]['imagery'][r][f] for r in ROIS for f in FAMILIES]) for p in PEOPLE])
    undefined = sum(v['mean_r'] is None for v in diagnostics.values())
    return {
        'schema': 'neural076_hierarchy_score_v2',
        'status': 'scored' if undefined == 0 else 'complete_with_undefined_correlations',
        'primary_name': PRIMARY,
        'primary': report[PRIMARY],
        'direction': 'two_sided; the sign is not an accuracy reward',
        'per_person_cells': matrix,
        'signed_contrasts': report,
        'absolute_imagery_companion': absolute,
        'cell_diagnostics': diagnostics,
        'undefined_phase_cells': undefined,
        'coverage': {'contexts': 650, 'phase_cells': 1300, 'participants': 5,
                     'imagery_repeats_per_category': 10, 'perception_repeats_per_category': 35,
                     'feature_units_per_cell': UNITS},
        'inference': 'Descriptive five-person effects only; no p-value, confidence interval or multiplicity claim.',
        'comparators': 'Not supplied or executed by this scorer. Required no-neural and training-permuted controls remain separate frozen collections.',
    }


def assess(submission, public, base, private_loader):
    """Trusted caller supplies authenticated public metadata and isolated targets."""
    calls = 0
    try:
        public_contract(public)
    except Exception as error:
        return failure('operator_error', calls, error)
    try:
        parts = validate_submission(submission)
        need(submission['source_design_sha256'] == public['source_design_sha256'], 'Exact source design binding')
        pins = []
        for row in parts:
            person, _, family = row['key'].split('/')
            ids = public['people'][person]['imagery_ids'] + public['people'][person]['perception_ids']
            _, sha = load(Path(base) / row['path'], ids, public['unit_ids'][family])
            pins.append(sha)
    except Exception as error:
        return failure('invalid_submission', calls, error)
    try:
        calls += 1
        gold = private_loader()
        validate_gold(gold)
    except Exception as error:
        return failure('operator_error', calls, error)
    matrix = {p: {s: {r: {} for r in ROIS} for s in PHASES} for p in PEOPLE}
    diagnostics = {}
    try:
        for row, sha in zip(parts, pins):
            person, roi, family = row['key'].split('/')
            ids = public['people'][person]['imagery_ids'] + public['people'][person]['perception_ids']
            predictions, _ = load(Path(base) / row['path'], ids, public['unit_ids'][family], sha)
            for phase, selection, repeats in [('imagery', slice(0, 500), 10),
                                                ('perception', slice(500, None), 35)]:
                cell = feature_score(predictions[selection], gold[person + '_' + phase],
                                     gold['bank_' + family], repeats)
                matrix[person][phase][roi][family] = cell['mean_r']
                diagnostics[row['key'] + '/' + phase] = cell
    except (ArithmeticError, FloatingPointError) as error:
        return failure('valid_unscorable_arithmetic', calls, error)
    except Exception as error:
        return failure('invalid_submission', calls, error)
    result = summarize(matrix, diagnostics)
    result['target_loader_calls'] = calls
    result['source_design_sha256'] = public['source_design_sha256']
    result['ordered_prediction_sha256'] = pins
    return result


def failure(status, calls, error):
    return {'schema': 'neural076_hierarchy_score_v2', 'status': status, 'primary': None,
            'target_loader_calls': calls, 'error': str(error)}


def descriptor(row, limit):
    need(type(row) is dict and set(row) == {'path', 'bytes', 'sha256'}, 'Exact operator descriptor')
    need(type(row['path']) is str and re.fullmatch(r'[A-Za-z0-9_-]+\.(?:npz|json)', row['path']),
         'Flat operator asset path')
    need(type(row['bytes']) is int and 0 < row['bytes'] <= limit
         and type(row['sha256']) is str and re.fullmatch('[a-f0-9]{64}', row['sha256']), 'Bounded operator pin')


def pinned_body(base, row, limit):
    descriptor(row, limit)
    body = ordinary_bytes(Path(base) / row['path'], limit)
    need(len(body) == row['bytes'] and hashlib.sha256(body).hexdigest() == row['sha256'], 'Exact operator asset bytes')
    return body


def authenticated_public(path, operator):
    need(type(operator) is dict and set(operator) == {'schema', 'source_design_sha256', 'public_manifest', 'gold'}
         and operator['schema'] == 'neural076_operator_v1', 'Compact operator manifest required')
    descriptor(operator['public_manifest'], 4 * 2**20)
    descriptor(operator['gold'], 16 * 2**20)
    need(operator['public_manifest']['path'] == 'public_manifest.json', 'Fixed public manifest name')
    body = ordinary_bytes(path, 4 * 2**20)
    pin = operator['public_manifest']
    need(len(body) == pin['bytes'] and hashlib.sha256(body).hexdigest() == pin['sha256'], 'Exact trusted public bytes/order')
    public = public_contract(strict_json(body))
    need(public['source_design_sha256'] == operator['source_design_sha256'], 'Exact public/source fingerprint')
    return public


def load_gold(base, row):
    """Authenticate and check expanded/header sizes before any NumPy allocation."""
    body = pinned_body(base, row, 16 * 2**20)
    shapes = {p + '_' + s: (n,) for p in PEOPLE for s, n in [('imagery', 500), ('perception', 1750)]}
    shapes.update({'bank_' + f: (50, UNITS) for f in FAMILIES})
    with zipfile.ZipFile(io.BytesIO(body)) as archive:
        entries = archive.infolist()
        need(len(entries) == len(shapes) and {e.filename for e in entries} == {k + '.npy' for k in shapes},
             'Exact private archive members')
        need(sum(e.file_size for e in entries) <= 16 * 2**20, 'Bounded expanded private arrays')
        for entry in entries:
            need(entry.compress_type in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED)
                 and not entry.flag_bits & 1, 'Ordinary private archive members')
            with archive.open(entry) as stream:
                version = np.lib.format.read_magic(stream)
                need(version in ((1, 0), (2, 0)), 'NPY version1/2 only')
                reader = np.lib.format.read_array_header_1_0 if version == (1, 0) else np.lib.format.read_array_header_2_0
                shape, fortran, dtype = reader(stream, max_header_size=65536)
                name = entry.filename[:-4]
                need(shape == shapes[name] and not fortran and not dtype.hasobject, 'Exact private array shape')
                need((dtype.kind == 'f' if name.startswith('bank_') else dtype.kind in 'iu')
                     and dtype.itemsize <= 8, 'Private numeric dtype')
                need(entry.file_size == stream.tell() + int(np.prod(shape)) * dtype.itemsize, 'Exact private payload length')
    with np.load(io.BytesIO(body), allow_pickle=False) as archive:
        gold = {k: archive[k] for k in shapes}
    validate_gold(gold)
    return gold


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--public', required=True)
    parser.add_argument('--submission', required=True)
    parser.add_argument('--operator', required=True)
    parser.add_argument('--out', required=True)
    args = parser.parse_args()
    try:
        operator = read_json(args.operator, 2**20)
        public = authenticated_public(args.public, operator)
    except Exception as error:
        result = failure('operator_error', 0, error)
    else:
        try:
            submission = read_json(args.submission, 2**20)
        except Exception as error:
            result = failure('invalid_submission', 0, error)
        else:
            result = assess(submission, public, Path(args.submission).parent,
                            lambda: load_gold(Path(args.operator).parent, operator['gold']))
    # Never overwrite an earlier scientific report.
    with Path(args.out).open('x') as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write('\n')
    return 0 if result['status'] in ('scored', 'complete_with_undefined_correlations') else 1


if __name__ == '__main__':
    raise SystemExit(main())
