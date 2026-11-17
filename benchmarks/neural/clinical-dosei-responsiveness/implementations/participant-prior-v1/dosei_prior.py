"""Training-only participant-macro ordinal prior for the existing DOSE-I task.

No EEG, protected evaluation labels, model selection or native source preparation
is performed. Fold labels are separately exported by the evaluator; hashes bind
their bytes, not their clinical truth or the exporter isolation.
"""
import argparse
from collections import Counter
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import types

TASK = 'clinical-dosei-responsiveness'
PRIMARY_BYTES = 15749
PRIMARY_SHA256 = '09560538d472f0b99c65532bf371c8e9af56635e1ec437f68dd2f83b5f7bde77'
SCALE = 10**18
CAPS = {'policy': 4 * 1024**2, 'training': 1024**2, 'bundle': 2 * 1024**2}
OUTPUT_CAP = 2 * 1024**2
RECIPE = 'equal_training_person_equal_eligible_assessment_no_smoothing_v1'


def require(ok, message):
    if not ok:
        raise ValueError(message)


def primary_module(path):
    # Read a single bounded source and execute only the preserved implementation.
    import os
    import stat
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        require(stat.S_ISREG(info.st_mode) and info.st_size == PRIMARY_BYTES,
                'exact ordinary primary source required')
        raw = stream.read(PRIMARY_BYTES + 1)
    require(len(raw) == PRIMARY_BYTES and hashlib.sha256(raw).hexdigest() == PRIMARY_SHA256,
            'accepted primary source identity required')
    module = types.ModuleType('dosei_prior_exact_primary')
    exec(compile(raw, str(path), 'exec'), module.__dict__)
    return module


def encode(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()


def decode(primary, raw, expected, kind):
    primary.digest(expected)
    require(type(raw) is bytes and len(raw) <= CAPS[kind], 'bounded ' + kind + ' input required')
    require(hashlib.sha256(raw).hexdigest() == expected, kind + ' hash mismatch')
    return json.loads(raw, object_pairs_hook=primary.strict_object,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite JSON')))


def simplex_decimal(probabilities):
    """Nearest lattice simplex by largest remainders; ties use category order.

    Each coordinate differs from the exact prior by less than 1e-18. This explicit
    prospective transport rule avoids silently renormalizing a rounded vector.
    """
    require(len(probabilities) == 5 and all(type(p) is Fraction and 0 <= p <= 1 for p in probabilities)
            and sum(probabilities) == 1, 'exact five-category simplex required')
    scaled = [p * SCALE for p in probabilities]
    ticks = [p.numerator // p.denominator for p in scaled]
    remaining = SCALE - sum(ticks)
    order = sorted(range(5), key=lambda i: (-(scaled[i] - ticks[i]), i))
    for i in order[:remaining]:
        ticks[i] += 1
    return [str(t // SCALE) if t % SCALE == 0 else f'0.{t:018d}'.rstrip('0') for t in ticks]


def fold_scope(primary, policy, admitted, fold_id):
    primary.identity(fold_id)
    folds = {f['fold_id']: f for f in policy['folds']}
    require(fold_id in folds, 'unknown outer fold')
    fold = folds[fold_id]
    people, recordings, assessments, _, person_fold = admitted
    training = set(fold['training_people'])
    person_for = {aid: recordings[row['recording_id']]['person_id'] for aid, row in assessments.items()}
    training_cases = {aid for aid, row in assessments.items()
                      if person_for[aid] in training and primary.eligible(row)}
    held_cases = [aid for aid in assessments if person_fold[person_for[aid]] == fold_id]
    return fold, person_for, training_cases, held_cases


def prior_from_counts(primary, people_rows):
    require(bool(people_rows), 'nonempty training people required')
    totals = [Fraction(0) for _ in range(5)]
    for row in people_rows:
        counts = row['category_counts']
        require(type(counts) is list and len(counts) == 5
                and all(type(n) is int and n >= 0 for n in counts), 'five nonnegative integer counts required')
        n = row['eligible_assessments']
        require(type(n) is int and n > 0 and sum(counts) == n,
                'every training person needs eligible assessment support; no dropping')
        for i, count in enumerate(counts):
            totals[i] += Fraction(count, n)
    return tuple(total / len(people_rows) for total in totals)


def held_predictions(primary, admitted, held_cases, fold_id, probabilities):
    assessments = admitted[2]
    return [{'assessment_id': aid, 'outer_fold': fold_id,
             'status': 'ok' if primary.eligible(assessments[aid]) else 'not_evaluable',
             'probabilities': probabilities.copy() if primary.eligible(assessments[aid]) else None}
            for aid in held_cases]


def fit_fold(primary, policy, admitted, labels, policy_sha256, training_sha256):
    primary.fields(labels, 'schema task policy_sha256 outer_fold assessments', 'training labels')
    require(labels['schema'] == 'dosei_prior_training_v1' and labels['task'] == TASK,
            'training label schema/task')
    require(labels['policy_sha256'] == policy_sha256, 'training labels must bind this policy')
    fold_id = labels['outer_fold']
    fold, person_for, expected, held_cases = fold_scope(primary, policy, admitted, fold_id)
    rows = primary.by_id(labels['assessments'], 'assessment_id')
    require(set(rows) == expected,
            'exact eligible outer-training cases required; no held-out labels, omissions or extras')
    counts = {p: [0] * 5 for p in fold['training_people']}
    for aid, row in rows.items():
        primary.fields(row, 'assessment_id category', 'training label')
        require(type(row['category']) is int and row['category'] in primary.CATEGORIES,
                'released integer category 1..5 required')
        counts[person_for[aid]][row['category'] - 1] += 1
    people_rows = [{'person_id': p, 'eligible_assessments': sum(counts[p]), 'category_counts': counts[p]}
                   for p in fold['training_people']]
    exact = prior_from_counts(primary, people_rows)
    probabilities = simplex_decimal(exact)
    primary.probability_vector(probabilities)
    return {'schema': 'dosei_prior_fold_v1', 'task': TASK, 'policy_sha256': policy_sha256,
            'training_sha256': training_sha256, 'primary_source_sha256': PRIMARY_SHA256,
            'outer_fold': fold_id, 'recipe': RECIPE, 'training_people': people_rows,
            'exact_prior': [{'numerator': str(p.numerator), 'denominator': str(p.denominator)} for p in exact],
            'probabilities': probabilities,
            'assessments': held_predictions(primary, admitted, held_cases, fold_id, probabilities)}


def fit_artifacts(policy_raw, training_raw, *, primary_source, expected_policy_sha256, expected_training_sha256):
    primary = primary_module(primary_source)
    policy = decode(primary, policy_raw, expected_policy_sha256, 'policy')
    admitted = primary.admit_policy(policy)
    labels = decode(primary, training_raw, expected_training_sha256, 'training')
    return fit_fold(primary, policy, admitted, labels, expected_policy_sha256, expected_training_sha256)


def admit_fold(primary, policy, admitted, bundle, policy_sha256):
    primary.fields(bundle, 'schema task policy_sha256 training_sha256 primary_source_sha256 outer_fold recipe training_people exact_prior probabilities assessments', 'fold bundle')
    require(bundle['schema'] == 'dosei_prior_fold_v1' and bundle['task'] == TASK
            and bundle['policy_sha256'] == policy_sha256 and bundle['primary_source_sha256'] == PRIMARY_SHA256
            and bundle['recipe'] == RECIPE, 'fold recipe/source/policy binding')
    primary.digest(bundle['training_sha256'])
    fold_id = bundle['outer_fold']
    fold, person_for, expected, held_cases = fold_scope(primary, policy, admitted, fold_id)
    people = primary.by_id(bundle['training_people'], 'person_id')
    require(list(people) == fold['training_people'], 'exact ordered training people required')
    support = Counter(person_for[aid] for aid in expected)
    for p, row in people.items():
        primary.fields(row, 'person_id eligible_assessments category_counts', 'training person')
        require(type(row['eligible_assessments']) is int and row['eligible_assessments'] == support[p],
                'training support must match frozen eligible case census')
    exact = prior_from_counts(primary, list(people.values()))
    require(bundle['exact_prior'] == [{'numerator': str(p.numerator), 'denominator': str(p.denominator)} for p in exact],
            'exact prior differs from equal-person category frequencies')
    probabilities = simplex_decimal(exact)
    require(bundle['probabilities'] == probabilities, 'decimal prior differs from deterministic simplex rounding')
    require(bundle['assessments'] == held_predictions(primary, admitted, held_cases, fold_id, probabilities),
            'complete ordered held-out predictions must equal fitted prior with frozen nulls')
    return bundle


def merge_artifacts(policy_raw, bundle_raws, *, primary_source, expected_policy_sha256, expected_bundle_sha256):
    """Merge only complete fold bundles; never accept or open any target artifact."""
    primary = primary_module(primary_source)
    policy = decode(primary, policy_raw, expected_policy_sha256, 'policy')
    admitted = primary.admit_policy(policy)
    require(type(bundle_raws) is list and type(expected_bundle_sha256) is list
            and len(bundle_raws) == len(expected_bundle_sha256) == len(policy['folds']),
            'one hash-bound bundle per outer fold required')
    bundles = {}
    for raw, pin in zip(bundle_raws, expected_bundle_sha256):
        bundle = admit_fold(primary, policy, admitted, decode(primary, raw, pin, 'bundle'), expected_policy_sha256)
        fid = bundle['outer_fold']
        require(fid not in bundles, 'duplicate outer fold bundle')
        bundles[fid] = bundle
    require(set(bundles) == {f['fold_id'] for f in policy['folds']}, 'complete outer fold roster required')
    rows = {r['assessment_id']: r for b in bundles.values() for r in b['assessments']}
    result = {'schema': 'dosei_predictions_v1', 'task': TASK,
              'assessments': [rows[aid] for aid in admitted[2]]}
    primary.admit_predictions(result, admitted)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['fit', 'merge'])
    parser.add_argument('--primary-source', required=True)
    parser.add_argument('--policy', required=True)
    parser.add_argument('--expected-policy-sha256', required=True)
    parser.add_argument('--training')
    parser.add_argument('--expected-training-sha256')
    parser.add_argument('--fold-bundle', action='append', default=[])
    parser.add_argument('--expected-bundle-sha256', action='append', default=[])
    parser.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    primary = primary_module(args.primary_source)
    policy_raw = primary.read_regular(args.policy, CAPS['policy'])
    kwargs = {'primary_source': args.primary_source, 'expected_policy_sha256': args.expected_policy_sha256}
    if args.command == 'fit':
        require(args.training is not None and args.expected_training_sha256 is not None
                and not args.fold_bundle and not args.expected_bundle_sha256, 'fit requires only training input')
        # Reject policy before opening the training labels.
        primary.admit_policy(decode(primary, policy_raw, args.expected_policy_sha256, 'policy'))
        result = fit_artifacts(policy_raw, primary.read_regular(args.training, CAPS['training']),
                               expected_training_sha256=args.expected_training_sha256, **kwargs)
    else:
        require(args.training is None and args.expected_training_sha256 is None, 'merge never accepts labels')
        policy = decode(primary, policy_raw, args.expected_policy_sha256, 'policy')
        primary.admit_policy(policy)
        require(len(args.fold_bundle) == len(args.expected_bundle_sha256) == len(policy['folds']),
                'one path and expected hash per fold required')
        result = merge_artifacts(policy_raw, [primary.read_regular(p, CAPS['bundle']) for p in args.fold_bundle],
                                 expected_bundle_sha256=args.expected_bundle_sha256, **kwargs)
    raw = encode(result)
    require(len(raw) <= OUTPUT_CAP, 'complete output cap exceeded; no truncation')
    with Path(args.output).open('xb') as stream:
        stream.write(raw)


if __name__ == '__main__':
    main()
