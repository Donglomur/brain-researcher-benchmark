"""Compare two complete frozen hierarchy collections on one operator packet.

This is descriptive comparison of program/analysis outputs. A signed hierarchy
interaction is not an accuracy reward, and this route supplies no direct/viewer
condition. Both full collections are admitted before any target load.
"""
import argparse
import json
from pathlib import Path

from artifacts import public_contract, validate_submission, load
from core import PEOPLE, ROIS, FAMILIES, PHASES, need, feature_score, participant_summary
from io_utils import read_json
from score import PRIMARY, authenticated_public, load_gold, validate_gold, summarize

SCHEMA = 'neural076_paired_hierarchy_v1'


def difference(first, second):
    return None if first is None or second is None else first - second


def paired_summary(first, second):
    """Retain all dependent cells and all five biological participants."""
    need(first['primary_name'] == second['primary_name'] == PRIMARY, 'Same current primary')
    need(first['coverage'] == second['coverage'], 'Same complete coverage')
    deltas = {person: {phase: {roi: {
        family: difference(first['per_person_cells'][person][phase][roi][family],
                           second['per_person_cells'][person][phase][roi][family])
        for family in FAMILIES} for roi in ROIS} for phase in PHASES} for person in PEOPLE}
    contrasts = {name: participant_summary([
        difference(first['signed_contrasts'][name]['per_person'][person],
                   second['signed_contrasts'][name]['per_person'][person])
        for person in PEOPLE]) for name in first['signed_contrasts']}
    absolute = participant_summary([
        difference(first['absolute_imagery_companion']['per_person'][person],
                   second['absolute_imagery_companion']['per_person'][person])
        for person in PEOPLE])
    return {
        'direction': 'first_minus_second; descriptive signed differences, not a superiority ranking',
        'primary_name': PRIMARY,
        'primary_difference': contrasts[PRIMARY],
        'per_person_cell_differences': deltas,
        'signed_contrast_differences': contrasts,
        'absolute_imagery_companion_difference': absolute,
        'inference': 'Five paired participants; no p-value, confidence interval or multiplicity claim.',
    }


def failure(status, calls, error, condition=None):
    return {'schema': SCHEMA, 'status': status, 'primary_difference': None,
            'target_loader_calls': calls, 'failed_condition': condition, 'error': str(error)}


def assess_pair(first, second, public, first_base, second_base, private_loader):
    """Trusted caller supplies one authenticated public packet and isolated gold.

    This intentionally reads each prediction twice, as the single scorer does.
    No condition's targets are exposed before both complete preflight passes.
    Frozen program provenance/custody is a caller responsibility, not a JSON claim.
    """
    calls = 0
    try:
        public_contract(public)
    except Exception as error:
        return failure('operator_error', calls, error)
    prepared = []
    for condition, submission, base in [('first', first, first_base), ('second', second, second_base)]:
        try:
            parts = validate_submission(submission)
            need(submission['source_design_sha256'] == public['source_design_sha256'],
                 'Exact source design binding')
            pins = []
            for row in parts:
                person, _, family = row['key'].split('/')
                ids = public['people'][person]['imagery_ids'] + public['people'][person]['perception_ids']
                _, sha = load(Path(base) / row['path'], ids, public['unit_ids'][family])
                pins.append(sha)
            prepared.append((condition, parts, Path(base), pins))
        except Exception as error:
            return failure('invalid_submission', calls, error, condition)
    try:
        calls += 1
        gold = private_loader()
        validate_gold(gold)
    except Exception as error:
        return failure('operator_error', calls, error)
    reports = {}
    for condition, parts, base, pins in prepared:
        matrix = {p: {s: {r: {} for r in ROIS} for s in PHASES} for p in PEOPLE}
        diagnostics = {}
        try:
            for row, sha in zip(parts, pins):
                person, roi, family = row['key'].split('/')
                ids = public['people'][person]['imagery_ids'] + public['people'][person]['perception_ids']
                predictions, _ = load(base / row['path'], ids, public['unit_ids'][family], sha)
                for phase, selection, repeats in [('imagery', slice(0, 500), 10),
                                                    ('perception', slice(500, None), 35)]:
                    cell = feature_score(predictions[selection], gold[person + '_' + phase],
                                         gold['bank_' + family], repeats)
                    matrix[person][phase][roi][family] = cell['mean_r']
                    diagnostics[row['key'] + '/' + phase] = cell
        except (ArithmeticError, FloatingPointError) as error:
            return failure('valid_unscorable_arithmetic', calls, error, condition)
        except Exception as error:
            return failure('invalid_submission', calls, error, condition)
        report = summarize(matrix, diagnostics)
        report['source_design_sha256'] = public['source_design_sha256']
        report['ordered_prediction_sha256'] = pins
        reports[condition] = report
    result = paired_summary(reports['first'], reports['second'])
    result.update({
        'schema': SCHEMA,
        'status': ('scored' if all(r['status'] == 'scored' for r in reports.values())
                   else 'complete_with_undefined_correlations'),
        'target_loader_calls': calls,
        'source_design_sha256': public['source_design_sha256'],
        'coverage_per_condition': reports['first']['coverage'],
        'conditions': reports,
        'access_scope': 'Frozen program/analysis collections only; direct/viewer suitability is not established.',
    })
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--public', required=True)
    parser.add_argument('--operator', required=True)
    parser.add_argument('--first', required=True)
    parser.add_argument('--second', required=True)
    parser.add_argument('--out', required=True)
    args = parser.parse_args()
    try:
        operator = read_json(args.operator, 2**20)
        public = authenticated_public(args.public, operator)
    except Exception as error:
        result = failure('operator_error', 0, error)
    else:
        for condition in ('first', 'second'):
            try:
                submission = read_json(getattr(args, condition), 2**20)
            except Exception as error:
                result = failure('invalid_submission', 0, error, condition)
                break
            if condition == 'first':
                first = submission
        else:
            result = assess_pair(first, submission, public, Path(args.first).parent,
                                 Path(args.second).parent,
                                 lambda: load_gold(Path(args.operator).parent, operator['gold']))
    with Path(args.out).open('x') as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write('\n')
    return 0 if result['status'] in ('scored', 'complete_with_undefined_correlations') else 1


if __name__ == '__main__':
    raise SystemExit(main())
