"""Protected SenseFOG primary and support-limited paired probability scoring.

Consumes evaluator-owned labels only. Does not construct labels, extract signals,
run candidates, or authenticate clinical provenance. All values are JSON types.
"""
import argparse
from collections import Counter
import hashlib
import types
import json
import math
from pathlib import Path
import random

TASK = 'clinical-sensefog-stn-state'
MAPPER_SHA256 = 'd833d2c7637d73ce047578788a75c0ab30a98cee89b694efde27b5f79fe8ef40'
MAPPER_PATH = Path(__file__).resolve().parent.parent / 'recording-lag-controls' / 'sensefog_pairing.py'
_raw = MAPPER_PATH.read_bytes()
if hashlib.sha256(_raw).hexdigest() != MAPPER_SHA256:
    raise ValueError('reviewed recording-grid mapper source changed')
_mapper = types.ModuleType('_sensefog_frozen_mapper')
_mapper.__file__ = str(MAPPER_PATH)
exec(compile(_raw, str(MAPPER_PATH), 'exec'), _mapper.__dict__)
require, keys, integer = _mapper.require, _mapper.keys, _mapper.integer
STATUSES = ('evaluable', 'ambiguous', 'missing_annotation', 'missing_signal', 'artifact')


def canonical_sha256(value):
    """Semantic JSON binding; CLI additionally authenticates exact input bytes."""
    raw = json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True,
                     allow_nan=False).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()


def validate_policy(policy):
    keys(policy, 'schema task classes finite_probability_floor bootstrap_replicates bootstrap_seed', 'policy')
    require(policy['schema'] == 'sensefog_score_policy_v1' and policy['task'] == TASK, 'policy identity')
    classes = policy['classes']
    require(type(classes) is list and 2 <= len(classes) <= 128, 'authenticated class list required')
    require(all(type(c) is str and 0 < len(c) <= 128 for c in classes), 'class names')
    require(len(set(classes)) == len(classes), 'duplicate class')
    floor = policy['finite_probability_floor']
    require(type(floor) in (int, float) and math.isfinite(floor) and 0 < floor <= 1 / len(classes),
            'finite positive probability floor at most 1/K')
    n = integer(policy['bootstrap_replicates'], 1, 'bootstrap replicates')
    require(n <= 10000, 'bootstrap replicate cap')
    integer(policy['bootstrap_seed'], 0, 'bootstrap seed')
    return classes, floor


def probability_loss(probabilities, true_index, size, floor):
    require(type(probabilities) is list and len(probabilities) == size, 'probability vector/class order')
    require(all(type(p) in (int, float) and math.isfinite(p) and 0 <= p <= 1 for p in probabilities),
            'probabilities must be finite numbers in [0,1], not booleans')
    require(abs(math.fsum(probabilities) - 1.0) <= 1e-9, 'probabilities must sum to one')
    bounded = [max(p, floor) for p in probabilities]
    # Difference of logs avoids underflow from division when floor is subnormal.
    return None if true_index is None else math.log(math.fsum(bounded)) - math.log(bounded[true_index])


def percentile(values, probability):
    position = (len(values) - 1) * probability
    lo, hi = math.floor(position), math.ceil(position)
    return values[lo] + (values[hi] - values[lo]) * (position - lo)


def cluster_interval(values, policy):
    """Resample participant means, never overlapping windows or gait cycles."""
    if len(values) < 2:
        return {'lower': None, 'upper': None, 'reason': 'fewer_than_two_evaluable_participants'}
    rng = random.Random(policy['bootstrap_seed'])
    samples = sorted(math.fsum(rng.choices(values, k=len(values))) / len(values)
                     for _ in range(policy['bootstrap_replicates']))
    return {'lower': percentile(samples, .025), 'upper': percentile(samples, .975),
            'reason': None}


def validate_submission(document, schema, grid_hash, policy_hash, expected_keys, classes, floor, labels):
    keys(document, 'schema task grid_sha256 policy_sha256 rows', 'submission')
    require(document['schema'] == schema and document['task'] == TASK, 'submission identity')
    require(document['grid_sha256'] == grid_hash and document['policy_sha256'] == policy_hash,
            'submission grid/policy binding mismatch')
    require(type(document['rows']) is list, 'submission rows')
    require(len(document['rows']) == len(expected_keys), 'complete prediction census required')
    paired = schema == 'sensefog_paired_predictions_v1'
    result = {}
    for row in document['rows']:
        keys(row, 'case_id multiple probabilities' if paired else 'case_id probabilities', 'prediction')
        cid = _mapper.identity(row['case_id'])
        if paired:
            require(type(row['multiple']) is int and row['multiple'] in _mapper.MULTIPLIERS,
                    'only the twenty fixed nonzero integer multipliers')
        key = (cid, row['multiple']) if paired else cid
        require(key in expected_keys and key not in result, 'unknown/unsupported/duplicate prediction identity')
        label = labels[cid]['label']
        true_index = None if label is None else classes.index(label)
        result[key] = probability_loss(row['probabilities'], true_index, len(classes), floor)
    require(set(result) == expected_keys, 'complete prediction census required')
    return result


def score(grid, policy, targets, predictions, *, max_cases, paired_predictions=None):
    """Score full natural coverage and, optionally, every supported fixed lag.

    Grid is the existing mapper's strict target-free input. Targets require all
    original case IDs, including unknown or excluded labels. Original predictions
    cover every original case; paired predictions cover every map-supported case,
    including cases whose target is unavailable. A failed/missing prediction is
    rejected, never replaced by a favorable subset or skipped in a mean.
    """
    classes, floor = validate_policy(policy)
    maps = _mapper.build_maps(grid, max_cases=max_cases)
    grid_hash, policy_hash = canonical_sha256(grid), canonical_sha256(policy)
    people = grid['participants']
    cases = {c['case_id']: {'participant': rec['participant'], 'recording_id': rec['recording_id']}
             for rec in grid['recordings'] for c in rec['cases']}
    keys(targets, 'schema task grid_sha256 label_protocol_sha256 rows', 'targets')
    require(targets['schema'] == 'sensefog_protected_targets_v1' and targets['task'] == TASK,
            'target identity')
    require(targets['grid_sha256'] == grid_hash, 'target grid binding mismatch')
    require(type(targets['label_protocol_sha256']) is str and
            _mapper.re.fullmatch('[0-9a-f]{64}', targets['label_protocol_sha256']), 'label protocol hash')
    require(type(targets['rows']) is list and len(targets['rows']) == len(cases), 'complete target census required')
    labels = {}
    for row in targets['rows']:
        keys(row, 'case_id participant status label', 'target row')
        cid = _mapper.identity(row['case_id'])
        require(cid in cases and cid not in labels, 'unknown/duplicate target case')
        require(row['participant'] == cases[cid]['participant'], 'target participant mismatch')
        require(type(row['status']) is str and row['status'] in STATUSES, 'target evaluation status')
        if row['status'] == 'evaluable':
            require(type(row['label']) is str and row['label'] in classes, 'target outside frozen classes')
        else:
            require(row['label'] is None, 'unevaluable labels must remain null')
        labels[cid] = row
    original = validate_submission(predictions, 'sensefog_predictions_v1', grid_hash, policy_hash,
                                   set(cases), classes, floor, labels)
    by_person = {p: [] for p in people}
    for cid in cases:
        if original[cid] is not None:
            by_person[cases[cid]['participant']].append(original[cid])
    folds = []
    for p in people:
        ids = [cid for cid in cases if cases[cid]['participant'] == p]
        losses = by_person[p]
        folds.append({'participant': p, 'original_cases': len(ids), 'evaluable_cases': len(losses),
                      'status_counts': dict(Counter(labels[c]['status'] for c in ids)),
                      'class_counts': {s: sum(labels[c]['label'] == s for c in ids) for s in classes},
                      'log_loss_nats': math.fsum(losses) / len(losses) if losses else None})
    missing_people = [r['participant'] for r in folds if r['log_loss_nats'] is None]
    means = [r['log_loss_nats'] for r in folds if r['log_loss_nats'] is not None]
    primary = {'name': 'ordinary_participant_macro_multiclass_log_loss', 'units': 'nats',
               'score': None if missing_people else math.fsum(means) / len(people),
               'undefined_reason': 'participant_without_evaluable_windows' if missing_people else None,
               'participants_without_evaluable_windows': missing_people,
               'participant_folds': folds,
               'participant_cluster_percentile_interval_95':
                   {'lower': None, 'upper': None, 'reason': 'full_cohort_primary_undefined'}
                   if missing_people else cluster_interval(means, policy)}
    recording_coverage = []
    for rec in grid['recordings']:
        ids = [c['case_id'] for c in rec['cases']]
        recording_coverage.append({'recording_id': rec['recording_id'], 'participant': rec['participant'],
                                   'original_cases': len(ids),
                                   'status_counts': dict(Counter(labels[c]['status'] for c in ids)),
                                   'class_counts': {s: sum(labels[c]['label'] == s for c in ids) for s in classes}})
    result = {'schema': 'sensefog_probability_score_v1', 'task': TASK,
              'grid_sha256': grid_hash, 'policy_sha256': policy_hash,
              'label_protocol_sha256': targets['label_protocol_sha256'],
              'mapper_source_sha256': MAPPER_SHA256,
              'original_case_count': len(cases), 'class_order': classes,
              'finite_probability_rule': 'q[k]=max(p[k],floor)/sum_j(max(p[j],floor))',
              'finite_probability_floor': floor, 'primary': primary,
              'recording_coverage': recording_coverage,
              'uncertainty': {'method': 'participant-cluster percentile bootstrap of participant means',
                              'replicates': policy['bootstrap_replicates'], 'seed': policy['bootstrap_seed'],
                              'scope': 'Descriptive small-cohort uncertainty; windows are not resampling units.'},
              'paired_diagnostics': None}
    if paired_predictions is None:
        return result
    supported = {(r['case_id'], r['multiple']) for r in maps['maps'] if r['status'] == 'supported'}
    transformed = validate_submission(paired_predictions, 'sensefog_paired_predictions_v1', grid_hash,
                                      policy_hash, supported, classes, floor, labels)
    transforms = []
    for multiple in _mapper.MULTIPLIERS:
        person_rows = []
        for p in people:
            ids = [cid for cid in cases if cases[cid]['participant'] == p and (cid, multiple) in supported]
            evaluable = [cid for cid in ids if original[cid] is not None]
            n = len(evaluable)
            original_mean = math.fsum(original[cid] for cid in evaluable) / n if n else None
            transformed_mean = math.fsum(transformed[cid, multiple] for cid in evaluable) / n if n else None
            # Compute within-case paired differences before either group average.
            delta = math.fsum(transformed[cid, multiple] - original[cid] for cid in evaluable) / n if n else None
            person_rows.append({'participant': p, 'supported_cases': len(ids), 'paired_evaluable_cases': n,
                                'status_counts': dict(Counter(labels[c]['status'] for c in ids)),
                                'class_counts': {s: sum(labels[c]['label'] == s for c in ids) for s in classes},
                                'original_log_loss_nats': original_mean,
                                'transformed_log_loss_nats': transformed_mean,
                                'transformed_minus_original_nats': delta})
        deltas = [r['transformed_minus_original_nats'] for r in person_rows
                  if r['transformed_minus_original_nats'] is not None]
        transforms.append({'multiple': multiple, 'participant_folds': person_rows,
                           'participants_without_paired_support': [r['participant'] for r in person_rows
                                                                  if r['paired_evaluable_cases'] == 0],
                           'paired_participant_macro_delta_nats': math.fsum(deltas) / len(deltas) if deltas else None,
                           'participant_cluster_percentile_interval_95': cluster_interval(deltas, policy)})
    valid = [t['paired_participant_macro_delta_nats'] for t in transforms
             if t['paired_participant_macro_delta_nats'] is not None]
    result['paired_diagnostics'] = {
        'scope': 'Support-limited descriptive temporal pairing diagnostic; not primary loss, causality or a permutation p-value.',
        'transforms': transforms, 'requested_transform_count': 20,
        'distinct_map_supported_transform_count': maps['distinct_supported_transform_count'],
        'evaluable_transform_count': len(valid),
        'equal_transform_mean_delta_nats': math.fsum(valid) / len(valid) if valid else None,
        'map_support_coverage': {k: maps[k] for k in ('participants', 'recordings', 'segments', 'transform_coverage')},
        'unsupported_cases': [{'case_id': r['case_id'], 'participant': r['participant'],
                               'recording_id': r['recording_id'], 'multiple': r['multiple'], 'reason': r['reason']}
                              for r in maps['maps'] if r['status'] != 'supported']}
    return result


def read_frozen(path, expected, cap):
    require(_mapper.re.fullmatch('[0-9a-f]{64}', expected), 'expected file hash')
    with Path(path).open('rb') as stream:
        raw = stream.read(cap + 1)
    require(len(raw) <= cap, 'input byte cap exceeded; no truncation')
    require(hashlib.sha256(raw).hexdigest() == expected, 'frozen input byte hash mismatch')
    return json.loads(raw, object_pairs_hook=_mapper.strict_object,
                      parse_constant=lambda v: (_ for _ in ()).throw(ValueError('nonfinite JSON')))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('grid', 'policy', 'targets', 'predictions', 'paired-predictions'):
        required = name != 'paired-predictions'
        parser.add_argument('--' + name, required=required)
        parser.add_argument('--' + name + '-sha256', required=required)
    parser.add_argument('--output', required=True)
    parser.add_argument('--max-input-bytes', type=int, required=True)
    parser.add_argument('--max-output-bytes', type=int, required=True)
    parser.add_argument('--max-cases', type=int, required=True)
    args = vars(parser.parse_args(argv))
    cap = integer(args['max_input_bytes'], 1, 'per-input byte cap')
    integer(args['max_output_bytes'], 1, 'output byte cap')
    require(bool(args['paired_predictions']) == bool(args['paired_predictions_sha256']),
            'paired predictions and frozen hash must be supplied together')
    docs, receipts = {}, {}
    for name in ('grid', 'policy', 'targets', 'predictions', 'paired_predictions'):
        if args[name] is not None:
            docs[name] = read_frozen(args[name], args[name + '_sha256'], cap)
            receipts[name] = args[name + '_sha256']
    result = score(**docs, max_cases=args['max_cases'])
    result['input_byte_sha256'] = receipts
    encoded = (json.dumps(result, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()
    require(len(encoded) <= args['max_output_bytes'], 'complete output exceeds byte cap; no truncation')
    with Path(args['output']).open('xb') as stream:
        stream.write(encoded)


if __name__ == '__main__':
    main()
