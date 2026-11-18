"""NEURAL-087 fixed-reference arithmetic and trusted-operator CLI.

No model fitting, source-data preparation, competence certification or sandbox.
The operator freezes the reference body digest before candidate evaluation.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path

from contract import VIEWS, need
from io_utils import capture, decode, write_json
from score import digest, load_bound_roster
from scorer import difference, encoded, grade, roster, summaries, validate_submission

REFERENCE_SCHEMA = 'neural087_fixed_reference_predictions_v1'
MAX_REFERENCE_BYTES = 2 * 1024 * 1024


def roster_commitment(rows):
    """Order-sensitive semantic roster commitment, including grouping identities."""
    roster(rows)
    raw = json.dumps(rows, sort_keys=True, separators=(',', ':'),
                     ensure_ascii=True, allow_nan=False).encode('ascii')
    return hashlib.sha256(b'neural087_reference_roster_v1\n' + raw).hexdigest()


def _reference(rows, body, expected_sha256):
    need(type(body) is bytes and 0 < len(body) <= MAX_REFERENCE_BYTES,
         'Bounded exact reference body required')
    need(hashlib.sha256(body).hexdigest() == digest(expected_sha256),
         'Externally frozen reference digest mismatch')
    bundle = decode(body)
    need(type(bundle) is dict and set(bundle) == {
        'schema', 'task_id', 'query_roster_sha256', 'reference_protocol_sha256', 'views'},
        'Exact fixed-reference envelope')
    need(bundle['schema'] == REFERENCE_SCHEMA and bundle['task_id'] == 'NEURAL-087',
         'Exact NEURAL-087 reference schema and task')
    need(bundle['query_roster_sha256'] == roster_commitment(rows),
         'Reference roster and endpoint grouping mismatch')
    digest(bundle['reference_protocol_sha256'])
    views = bundle['views']
    need(type(views) is dict and set(views) == set(VIEWS),
         'Both fixed-reference information views required')
    # All four prediction vectors must be valid before any target callback.
    aligned = {view: validate_submission(rows, views[view]) for view in VIEWS}
    return bundle, aligned


def _contrast(left, right):
    """Equal-presynaptic loss difference, retaining signed infinities/undefined."""
    need(set(left) == set(right) and bool(left), 'Identical presynaptic support')
    values = [difference(left[key], right[key]) for key in sorted(left)]
    if any(value is None for value in values) or (math.inf in values and -math.inf in values):
        return encoded(None)
    if math.inf in values:
        return encoded(math.inf)
    if -math.inf in values:
        return encoded(-math.inf)
    return encoded(math.fsum(values) / len(values))


def compare(rows, candidate, reference_body, reference_sha256, private_loader):
    """Compare complete paired predictions on an operator-selected roster.

    This arithmetic core permits bounded generated rosters. The CLI authenticates
    the complete historical 6691-pair roster through the unchanged score binding.
    Hashes bind chosen objects; they cannot prove independent fitting, adequate
    reference competence, freeze chronology or biological source eligibility.
    """
    roster(rows)
    need(type(candidate) is dict and set(candidate) == set(VIEWS),
         'Both candidate information views required')
    candidate_vectors = {view: validate_submission(rows, candidate[view]) for view in VIEWS}
    bundle, reference_vectors = _reference(rows, reference_body, reference_sha256)
    # The existing grader authenticates target shape and supplies unchanged
    # primary/companion arithmetic; the wrapper opens targets exactly once.
    target = private_loader()
    candidate_result = grade(rows, candidate, lambda: target)
    targets = [row['connected'] for row in target['targets']]
    reference_scores, reference_per, candidate_per = {}, {}, {}
    for view in VIEWS:
        reference_scores[view], reference_per[view] = summaries(rows, targets, reference_vectors[view])
        _, candidate_per[view] = summaries(rows, targets, candidate_vectors[view])
    return {
        'task_id': 'NEURAL-087',
        'status': 'scored',
        'primary_metric': candidate_result['primary_metric'],
        'primary': candidate_result['primary'],
        'direction': 'lower_is_better',
        'candidate': candidate_result,
        'fixed_reference': reference_scores,
        'fixed_anatomy_minus_fixed_joint': _contrast(reference_per[VIEWS[0]], reference_per[VIEWS[1]]),
        'fixed_minus_candidate_same_information': {
            view: _contrast(reference_per[view], candidate_per[view]) for view in VIEWS},
        'gain_direction': 'positive_means_lower_candidate_loss_for_same_information',
        'reference_predictions_sha256': reference_sha256,
        'reference_protocol_sha256': bundle['reference_protocol_sha256'],
        'query_roster_commitment': bundle['query_roster_sha256'],
        'private_loader_calls': 1,
        'qualification': 'comparison_arithmetic_only',
        'reference_competence': 'not_assessed',
        'reference_freeze_chronology': 'not_assessed',
        'uncertainty': None,
        'scientific_success': None,
        'research_qualified': False,
    }


def validate_comparison_paths(args):
    """Metadata-only alias check before reading any input body."""
    roles = ('binding', 'roster', 'anatomy', 'joint', 'reference', 'targets', 'output')
    paths = {role: Path(getattr(args, role)) for role in roles}
    resolved = {role: path.resolve() for role, path in paths.items()}

    def aliases(left, right):
        if resolved[left] == resolved[right]:
            return True
        try:
            return os.path.samefile(paths[left], paths[right])
        except FileNotFoundError:
            return False

    for role in roles[:-2]:
        need(not aliases('targets', role), f'Input role alias: targets and {role}')
    for role in roles[:-1]:
        need(not aliases('output', role), f'Output role alias: output and {role}')


def main(args):
    validate_comparison_paths(args)
    binding, rows = load_bound_roster(args.binding, args.binding_sha256, args.roster)
    reference_body = capture(args.reference, MAX_REFERENCE_BYTES)
    # Invalid operator reference is an operator error, never candidate failure.
    _reference(rows, reference_body, args.reference_sha256)
    try:
        candidate = {
            VIEWS[0]: decode(capture(args.anatomy, 1048576)),
            VIEWS[1]: decode(capture(args.joint, 1048576)),
        }
        for view in VIEWS:
            validate_submission(rows, candidate[view])
    except (ValueError, OSError, UnicodeError, OverflowError, RecursionError) as error:
        result = {'task_id': 'NEURAL-087', 'status': 'invalid_submission',
                  'reason': str(error), 'primary': None, 'private_loader_calls': 0,
                  'scientific_success': None, 'research_qualified': False}
    else:
        calls = 0

        def private():
            nonlocal calls
            calls += 1
            return decode(capture(args.targets, 1048576, binding['query_targets']))

        result = compare(rows, candidate, reference_body, args.reference_sha256, private)
        need(calls == 1, 'Exactly one protected target read')
    result['operator_binding_sha256'] = args.binding_sha256
    result['weighting_scope'] = 'unit_pair_weights_within_equal_presynaptic_groups'
    pin = write_json(args.output, result, 4194304)
    print(json.dumps({'status': result['status'], 'result': pin,
                      'private_loader_calls': result['private_loader_calls']}))
    return 2 if result['status'] == 'invalid_submission' else 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('binding', 'roster', 'targets', 'anatomy', 'joint', 'reference', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--binding-sha256', required=True)
    parser.add_argument('--reference-sha256', required=True,
                        help='Exact reference-file SHA256 frozen independently by the operator')
    raise SystemExit(main(parser.parse_args()))
