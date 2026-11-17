"""DoSEI evaluator-only exact ordinal RPS on a separately authenticated policy.

Logical joins and declared completeness are checked; biological/source truth,
pre-outcome freezing and participant isolation require an external evaluator.
"""
import argparse
from collections import Counter
from fractions import Fraction
import hashlib
import json
import os
from pathlib import Path
import re
import stat

TASK = 'clinical-dosei-responsiveness'
COUNTS = {'recordings': 171, 'assessments': 7328, 'transitions': 1129}
CATEGORIES = [1, 2, 3, 4, 5]
INPUT_CAPS = {'policy': 4 * 1024**2, 'predictions': 2 * 1024**2,
              'targets': 1024**2}
OUTPUT_CAP = 4 * 1024**2
PROVENANCE = {'person_join', 'assessment_census', 'transition_census',
              'missingness', 'group_split', 'packet_causality'}
STATUSES = {
    'label_status': {'valid', 'missing', 'ambiguous'},
    'window_status': {'complete', 'incomplete', 'unresolved'},
    'timing_status': {'verified', 'unresolved'},
    'artifact_status': {'included', 'excluded', 'unresolved'},
}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def fields(value, names, context):
    require(type(value) is dict and set(value) == set(names.split()),
            context + ': exact fields required')


def identity(value):
    require(type(value) is str and re.fullmatch('[A-Za-z0-9_-]{1,64}', value),
            'invalid opaque identity')
    return value


def digest(value):
    require(type(value) is str and re.fullmatch('[0-9a-f]{64}', value), 'invalid SHA256')
    return value


def ids(values):
    require(type(values) is list, 'identity list required')
    result = [identity(v) for v in values]
    require(len(set(result)) == len(result), 'duplicate identity')
    return result


def by_id(rows, key):
    require(type(rows) is list, 'row list required')
    result = {}
    for row in rows:
        require(type(row) is dict and key in row, 'row identity required')
        value = identity(row[key])
        require(value not in result, 'duplicate row identity')
        result[value] = row
    return result


def eligible(row):
    return (row['label_status'] == 'valid' and row['window_status'] == 'complete'
            and row['timing_status'] == 'verified' and row['artifact_status'] == 'included')


def admit_policy(policy):
    """No person equivalence or missingness is inferred from recording names."""
    fields(policy, 'schema task categories label_source provenance people folds recordings assessments transitions', 'policy')
    require(policy['schema'] == 'dosei_complete_policy_v1' and policy['task'] == TASK,
            'policy schema/task')
    require(type(policy['categories']) is list and
            all(type(c) is int for c in policy['categories']) and
            policy['categories'] == CATEGORIES, 'ordered released categories must be 1..5')
    require(policy['label_source'] == 'original_EVENT_MOAAS_assessment',
            'original assessments required; forwarded pEEG rows are not a census')
    require(type(policy['provenance']) is dict and set(policy['provenance']) == PROVENANCE,
            'complete external provenance receipt roles required')
    for pin in policy['provenance'].values():
        digest(pin)
    people = ids(policy['people'])
    require(2 <= len(people) <= COUNTS['recordings'], 'person count incompatible with grouped folds')
    recordings = by_id(policy['recordings'], 'recording_id')
    require(len(recordings) == COUNTS['recordings'], 'complete 171-recording census required')
    for row in recordings.values():
        fields(row, 'recording_id person_id', 'recording')
        require(identity(row['person_id']) in people, 'unknown recording person')
    require({r['person_id'] for r in recordings.values()} == set(people), 'person without a recording')
    folds = by_id(policy['folds'], 'fold_id')
    require(2 <= len(folds) <= len(people), 'complete grouped outer folds required')
    person_fold = {}
    for fid, fold in folds.items():
        fields(fold, 'fold_id training_people heldout_people', 'fold')
        train, test = ids(fold['training_people']), ids(fold['heldout_people'])
        require(bool(train) and bool(test) and set(train).isdisjoint(test)
                and set(train) | set(test) == set(people), 'fold must partition all people')
        for person in test:
            require(person not in person_fold, 'person held out in multiple folds')
            person_fold[person] = fid
    require(set(person_fold) == set(people), 'every person held out exactly once')
    assessments = by_id(policy['assessments'], 'assessment_id')
    require(len(assessments) == COUNTS['assessments'], 'complete 7328-assessment census required')
    events = set()
    for row in assessments.values():
        fields(row, 'assessment_id recording_id source_event_id label_status window_status timing_status artifact_status', 'assessment')
        rid = identity(row['recording_id'])
        require(rid in recordings, 'unknown assessment recording')
        event = (rid, identity(row['source_event_id']))
        require(event not in events, 'repeated original assessment event; no forward filling')
        events.add(event)
        for field, allowed in STATUSES.items():
            require(type(row[field]) is str and row[field] in allowed, 'unknown ' + field)
    transitions = by_id(policy['transitions'], 'transition_id')
    require(len(transitions) == COUNTS['transitions'], 'complete 1129-transition accounting required')
    events = set()
    for tid, row in transitions.items():
        fields(row, 'transition_id recording_id source_event_id', 'transition')
        rid = identity(row['recording_id'])
        require(rid in recordings and tid not in assessments, 'transition identity/recording')
        event = (rid, identity(row['source_event_id']))
        require(event not in events, 'duplicate original transition event')
        events.add(event)
    return people, recordings, assessments, transitions, person_fold


def probability_vector(value):
    """Exact decimal strings, <=18 fractional places, sum exactly to one.

    No clipping or renormalization can silently change a submitted distribution.
    """
    require(type(value) is list and len(value) == 5, 'five ordered probabilities required')
    require(all(type(x) is str and re.fullmatch(r'(0(?:\.[0-9]{1,18})?|1(?:\.0{1,18})?)', x)
                for x in value), 'probabilities must be decimal strings in [0,1], <=18 places')
    values = tuple(Fraction(x) for x in value)
    require(sum(values) == 1, 'probability sum must equal one exactly')
    return values


def admit_predictions(predictions, admitted):
    people, recordings, assessments, transitions, person_fold = admitted
    fields(predictions, 'schema task assessments', 'predictions')
    require(predictions['schema'] == 'dosei_predictions_v1' and predictions['task'] == TASK,
            'prediction schema/task')
    rows = by_id(predictions['assessments'], 'assessment_id')
    require(set(rows) == set(assessments), 'exact full assessment output required; no transitions or omissions')
    probabilities = {}
    for aid, row in rows.items():
        fields(row, 'assessment_id outer_fold status probabilities', 'prediction')
        expected = person_fold[recordings[assessments[aid]['recording_id']]['person_id']]
        require(row['outer_fold'] == expected, 'prediction outer fold disagrees with biological person grouping')
        if eligible(assessments[aid]):
            require(row['status'] == 'ok', 'missing/failed evaluable prediction refuses entire submission')
            probabilities[aid] = probability_vector(row['probabilities'])
        else:
            require(row['status'] == 'not_evaluable' and row['probabilities'] is None,
                    'ineligible assessment must retain an explicit not_evaluable row')
    return probabilities


def normalized_rps(probabilities, category):
    cumulative = Fraction(0)
    total = Fraction(0)
    for k, value in enumerate(probabilities[:-1], 1):
        cumulative += value
        total += (cumulative - int(category <= k)) ** 2
    return total / 4


def exact(value):
    return None if value is None else {'numerator': str(value.numerator),
                                      'denominator': str(value.denominator), 'value': float(value)}


def score_admitted(targets, admitted, probabilities):
    """Internal evaluator stage; call only after complete policy/prediction admission."""
    people, recordings, assessments, transitions, person_fold = admitted
    fields(targets, 'schema task assessments', 'targets')
    require(targets['schema'] == 'dosei_targets_v1' and targets['task'] == TASK, 'target schema/task')
    labels = by_id(targets['assessments'], 'assessment_id')
    require(set(labels) == set(assessments), 'complete original target accounting required')
    for aid, row in labels.items():
        fields(row, 'assessment_id category', 'target')
        if assessments[aid]['label_status'] == 'valid':
            require(type(row['category']) is int and row['category'] in CATEGORIES,
                    'valid label must be original released category 1..5, never binary SoC')
        else:
            require(row['category'] is None, 'missing/ambiguous original label must stay null')
    person_stats = {p: {'recordings': 0, 'assessments': 0, 'evaluable': 0,
                       'transitions': 0, 'statuses': Counter(), 'loss_sum': Fraction(0)} for p in people}
    recording_stats = {rid: {'assessments': 0, 'evaluable': 0, 'transitions': 0,
                           'statuses': Counter()} for rid in recordings}
    for row in recordings.values():
        person_stats[row['person_id']]['recordings'] += 1
    for row in transitions.values():
        rid = row['recording_id']; person = recordings[rid]['person_id']
        recording_stats[rid]['transitions'] += 1; person_stats[person]['transitions'] += 1
    scored = []
    for aid, row in assessments.items():
        rid = row['recording_id']; person = recordings[rid]['person_id']
        status = '|'.join(row[k] for k in STATUSES)
        is_evaluable = eligible(row)
        for group in (recording_stats[rid], person_stats[person]):
            group['assessments'] += 1
            group['evaluable'] += int(is_evaluable)
            group['statuses'][status] += 1
        loss = normalized_rps(probabilities[aid], labels[aid]['category']) if is_evaluable else None
        if loss is not None:
            person_stats[person]['loss_sum'] += loss
        scored.append({'assessment_id': aid, 'person_id': person, 'recording_id': rid,
                       'outer_fold': person_fold[person], 'evaluable': is_evaluable,
                       'status': status, 'normalized_rps': exact(loss)})
    person_rows, means, unsupported = [], [], []
    for person in people:
        row = person_stats[person]
        total_loss = row.pop('loss_sum')
        mean = total_loss / row['evaluable'] if row['evaluable'] else None
        if mean is None:
            unsupported.append(person)
        else:
            means.append(mean)
        person_rows.append({'person_id': person, 'outer_fold': person_fold[person],
                            **row, 'normalized_rps': exact(mean)})
    primary = None if unsupported else sum(means, Fraction(0)) / len(people)
    return {'schema': 'dosei_primary_score_v1', 'task': TASK,
            'counts': {**COUNTS, 'people': len(people), 'evaluable_assessments': len(probabilities)},
            'metric': 'normalized_RPS_mean_assessments_within_person_then_equal_person',
            'primary_normalized_rps': exact(primary),
            'primary_status': 'undefined_person_without_evaluable_assessment' if unsupported else 'defined_for_frozen_natural_coverage',
            'people_without_evaluable_assessments': unsupported, 'people': person_rows,
            'recordings': [{'recording_id': rid, 'person_id': recordings[rid]['person_id'], **row}
                           for rid, row in recording_stats.items()], 'assessments': scored,
            'transitions_are_targets': False, 'scientifically_qualified': False,
            'interpretation': 'Conditional on externally authenticated frozen census and missingness; observed bedside responsiveness, not consciousness or treatment advice.'}


def strict_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'duplicate JSON key')
        result[key] = value
    return result


def decode(raw, expected, kind):
    digest(expected)
    require(type(raw) is bytes and len(raw) <= INPUT_CAPS[kind], kind + ': input cap')
    require(hashlib.sha256(raw).hexdigest() == expected, kind + ': frozen hash mismatch')
    return json.loads(raw, object_pairs_hook=strict_object,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite JSON')))


def score_artifacts(policy_raw, predictions_raw, targets_raw, *, expected_policy_sha256,
                    expected_predictions_sha256, expected_targets_sha256):
    """Required external hashes; input bytes are evaluator-owned, not a sandbox."""
    admitted = admit_policy(decode(policy_raw, expected_policy_sha256, 'policy'))
    probabilities = admit_predictions(decode(predictions_raw, expected_predictions_sha256, 'predictions'), admitted)
    result = score_admitted(decode(targets_raw, expected_targets_sha256, 'targets'), admitted, probabilities)
    result['artifact_sha256'] = {'policy': expected_policy_sha256, 'predictions': expected_predictions_sha256,
                                 'targets': expected_targets_sha256}
    return result


def read_regular(path, cap):
    """No final-link/FIFO admission; read one opened inode, verify stable metadata.

    Ancestor path trust and hostile-filesystem isolation remain external.
    """
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        before = os.fstat(stream.fileno())
        require(stat.S_ISREG(before.st_mode) and before.st_size <= cap, 'regular bounded input required')
        raw = stream.read(cap + 1)
        after = os.fstat(stream.fileno())
    signature = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
    require(signature(before) == signature(after) and len(raw) == before.st_size <= cap,
            'input changed or exceeded cap')
    return raw


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in INPUT_CAPS:
        parser.add_argument('--' + name, required=True)
        parser.add_argument('--expected-' + name + '-sha256', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    pins = {k: digest(getattr(args, 'expected_' + k + '_sha256')) for k in INPUT_CAPS}
    policy = admit_policy(decode(read_regular(args.policy, INPUT_CAPS['policy']), pins['policy'], 'policy'))
    probabilities = admit_predictions(decode(read_regular(args.predictions, INPUT_CAPS['predictions']),
                                             pins['predictions'], 'predictions'), policy)
    # Protected targets are opened only after complete prediction admission.
    result = score_admitted(decode(read_regular(args.targets, INPUT_CAPS['targets']), pins['targets'], 'targets'),
                            policy, probabilities)
    result['artifact_sha256'] = pins
    encoded = (json.dumps(result, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()
    require(len(encoded) <= OUTPUT_CAP, 'full output cap exceeded; no truncation')
    with Path(args.output).open('xb') as stream:
        stream.write(encoded)


if __name__ == '__main__':
    main()
