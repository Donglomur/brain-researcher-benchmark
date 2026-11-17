"""Conditional DoSEI secondary metrics and paired participant uncertainty.

All metric choices are explicit prospective evaluator policy operands. This source
neither authenticates clinical data nor establishes an author-reported protocol.
The exact unchanged primary evaluator supplies scope, admission and primary RPS.
"""
import argparse
from collections import Counter
from fractions import Fraction
import hashlib
import json
import os
from pathlib import Path
import stat
import types

PRIMARY_BYTES = 15749
PRIMARY_SHA256 = '09560538d472f0b99c65532bf371c8e9af56635e1ec437f68dd2f83b5f7bde77'
TASK = 'clinical-dosei-responsiveness'
CAPS = {'policy': 4 * 1024**2, 'predictions': 16 * 1024**2,
        'targets': 1024**2, 'secondary': 128 * 1024}
OUTPUT_CAP = 40 * 1024**2
MAX_ARMS, MAX_CONTRASTS, MAX_REPLICATES, MAX_BINS = 8, 28, 4096, 20
BOOTSTRAP_DOMAIN = b'dosei-person-bootstrap-v2\x00'


def require(ok, message):
    if not ok:
        raise ValueError(message)


def primary_module(path):
    """Execute only the frozen original primary source, never cached bytecode."""
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        require(stat.S_ISREG(info.st_mode) and info.st_size == PRIMARY_BYTES,
                'exact ordinary primary source required')
        raw = stream.read(PRIMARY_BYTES + 1)
    require(len(raw) == PRIMARY_BYTES and hashlib.sha256(raw).hexdigest() == PRIMARY_SHA256,
            'accepted original primary source identity required')
    module = types.ModuleType('dosei_exact_original_primary')
    exec(compile(raw, str(path), 'exec'), module.__dict__)
    return module


def decode(primary, raw, expected, kind):
    primary.digest(expected)
    require(type(raw) is bytes and len(raw) <= CAPS[kind], 'bounded ' + kind + ' bytes required')
    require(hashlib.sha256(raw).hexdigest() == expected, 'frozen ' + kind + ' hash mismatch')
    try:
        return json.loads(raw, object_pairs_hook=primary.strict_object,
                          parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite JSON')))
    except (RecursionError, UnicodeError) as exc:
        raise ValueError('invalid bounded JSON structure') from exc


def decimal_probability(primary, value):
    # Reuse the original exact decimal grammar without normalizing input.
    import re
    require(type(value) is str and re.fullmatch(r'(0(?:\.[0-9]{1,18})?|1(?:\.0{1,18})?)', value),
            'exact decimal probability string required')
    return Fraction(value)


def admit_secondary(primary, secondary, policy_sha256):
    primary.fields(secondary,
                   'schema task primary_policy_sha256 original_packet_set_sha256 arms contrasts hard_category mae_aggregation recall_aggregation calibration bootstrap freeze_receipts',
                   'secondary policy')
    require(secondary['schema'] == 'dosei_secondary_policy_v2' and secondary['task'] == TASK,
            'secondary schema/task')
    require(secondary['primary_policy_sha256'] == policy_sha256, 'secondary-to-primary policy binding')
    primary.digest(secondary['original_packet_set_sha256'])
    arms = primary.ids(secondary['arms'])
    require(2 <= len(arms) <= MAX_ARMS, 'paired full arm roster must contain 2..8 arms')
    contrasts = primary.by_id(secondary['contrasts'], 'contrast_id')
    require(1 <= len(contrasts) <= MAX_CONTRASTS, 'finite explicit contrast roster required')
    pairs = set()
    for row in contrasts.values():
        primary.fields(row, 'contrast_id comparison_arm reference_arm', 'contrast')
        pair = row['comparison_arm'], row['reference_arm']
        require(all(type(a) is str and a in arms for a in pair) and pair[0] != pair[1],
                'contrast needs distinct admitted arms')
        require(pair not in pairs, 'duplicate arm contrast')
        pairs.add(pair)
    require(secondary['hard_category'] in ('lower_probability_median', 'lowest_probability_mode'),
            'explicit supported hard-category rule required')
    require(secondary['mae_aggregation'] == 'equal_person_equal_within_person', 'explicit participant-macro MAE policy required')
    require(secondary['recall_aggregation'] == 'equal_supported_person_per_category', 'explicit class-support recall policy required')
    calibration = secondary['calibration']
    primary.fields(calibration, 'method weighting bin_edges boundary', 'calibration')
    require(calibration['method'] == 'classwise_reliability_ece'
            and calibration['weighting'] == 'equal_person_equal_within_person'
            and calibration['boundary'] == 'left_closed_right_open_last_closed', 'explicit supported calibration policy required')
    require(type(calibration['bin_edges']) is list and 2 <= len(calibration['bin_edges']) <= MAX_BINS + 1,
            '2..21 explicit calibration bin edges required')
    edges = [decimal_probability(primary, v) for v in calibration['bin_edges']]
    require(edges[0] == 0 and edges[-1] == 1 and all(a < b for a, b in zip(edges, edges[1:])),
            'calibration bins must strictly partition [0,1]')
    bootstrap = secondary['bootstrap']
    primary.fields(bootstrap, 'method seed_sha256 replicates confidence quantile metrics difference', 'bootstrap')
    require(bootstrap['method'] == 'iid_biological_person_percentile'
            and bootstrap['quantile'] == 'linear_type7'
            and bootstrap['difference'] == 'comparison_minus_reference'
            and bootstrap['metrics'] == ['normalized_rps', 'ordinal_mae'], 'explicit supported paired interval policy required')
    primary.digest(bootstrap['seed_sha256'])
    require(type(bootstrap['replicates']) is int and 2 <= bootstrap['replicates'] <= MAX_REPLICATES,
            'bootstrap replicate format bound: 2..4096')
    confidence = decimal_probability(primary, bootstrap['confidence'])
    require(0 < confidence < 1, 'confidence must be strictly between zero and one')
    primary.fields(secondary['freeze_receipts'], 'metric_policy before_outcomes same_inputs_and_training', 'freeze receipts')
    for pin in secondary['freeze_receipts'].values():
        primary.digest(pin)
    return secondary


def admit_predictions(primary, bundle, admitted, secondary):
    primary.fields(bundle, 'schema task original_packet_set_sha256 arms', 'prediction bundle')
    require(bundle['schema'] == 'dosei_secondary_predictions_v2' and bundle['task'] == TASK,
            'prediction bundle schema/task')
    require(bundle['original_packet_set_sha256'] == secondary['original_packet_set_sha256'],
            'same original packet-set receipt required')
    rows = primary.by_id(bundle['arms'], 'arm_id')
    require(set(rows) == set(secondary['arms']), 'exact full frozen arm roster required')
    probabilities = {}
    for arm in secondary['arms']:
        primary.fields(rows[arm], 'arm_id predictions', 'arm predictions')
        probabilities[arm] = primary.admit_predictions(rows[arm]['predictions'], admitted)
    return probabilities


def hard_category(probabilities, rule):
    """A declared decision rule; no implicit mode/median selection or tie rule."""
    require(len(probabilities) == 5 and all(isinstance(v, Fraction) and 0 <= v <= 1 for v in probabilities)
            and sum(probabilities) == 1, 'admitted exact five-probability vector required')
    if rule == 'lowest_probability_mode':
        return probabilities.index(max(probabilities)) + 1
    require(rule == 'lower_probability_median', 'unknown hard-category rule')
    cumulative = Fraction(0)
    for category, probability in enumerate(probabilities, 1):
        cumulative += probability
        if cumulative >= Fraction(1, 2):
            return category
    raise AssertionError('admitted probability vector has no median')


def linear_quantile(values, probability):
    """Type-7 linear quantile of an explicitly nonempty exact sample."""
    require(bool(values) and isinstance(probability, Fraction) and 0 <= probability <= 1,
            'nonempty exact quantile sample and probability required')
    require(all(isinstance(v, Fraction) for v in values), 'exact quantile sample required')
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = position.numerator // position.denominator
    remainder = position - lower
    return ordered[lower] if lower == len(ordered) - 1 else ordered[lower] + remainder * (ordered[lower + 1] - ordered[lower])


def bootstrap_indices(people, seed_sha256, replicates):
    """Reproducible unbiased SHA256 rejection draws, in declared person order."""
    import re
    require(type(people) in (list, tuple) and 2 <= len(people) <= 171
            and len(set(people)) == len(people), 'distinct complete person roster required')
    require(type(seed_sha256) is str and re.fullmatch('[0-9a-f]{64}', seed_sha256), 'bootstrap seed identity')
    require(type(replicates) is int and 2 <= replicates <= MAX_REPLICATES, 'bootstrap replicate format bound')
    seed = bytes.fromhex(seed_sha256)
    n = len(people)
    limit = ((1 << 256) // n) * n
    draws = []
    for replicate in range(replicates):
        row = []
        for position in range(n):
            attempt = 0
            while True:
                payload = (BOOTSTRAP_DOMAIN + seed + replicate.to_bytes(8, 'big')
                           + position.to_bytes(8, 'big') + attempt.to_bytes(8, 'big'))
                value = int.from_bytes(hashlib.sha256(payload).digest(), 'big')
                if value < limit:
                    row.append(value % n)
                    break
                attempt += 1
        draws.append(tuple(row))
    return tuple(draws)


def mean(values):
    return sum(values, Fraction(0)) / len(values) if values else None


def as_fraction(value):
    return None if value is None else Fraction(int(value['numerator']), int(value['denominator']))


def secondary_for_arm(primary, admitted, probabilities, labels, secondary_policy):
    people, recordings, assessments, transitions, person_fold = admitted
    cases = {person: [] for person in people}
    for aid, row in assessments.items():
        if primary.eligible(row):
            person = recordings[row['recording_id']]['person_id']
            category = labels[aid]
            decision = hard_category(probabilities[aid], secondary_policy['hard_category'])
            cases[person].append((aid, category, decision))
    unsupported = [person for person in people if not cases[person]]
    person_rows = []
    for person in people:
        values = cases[person]
        per_category = []
        for category in primary.CATEGORIES:
            relevant = [v for v in values if v[1] == category]
            correct = sum(v[2] == category for v in relevant)
            per_category.append({'category': category, 'support': len(relevant), 'correct': correct,
                                 'recall': primary.exact(Fraction(correct, len(relevant)) if relevant else None)})
        person_rows.append({'person_id': person, 'outer_fold': person_fold[person], 'evaluable_assessments': len(values),
                            'ordinal_mae': primary.exact(mean([Fraction(abs(y - decision)) for _, y, decision in values])),
                            'per_category_recall': per_category})
    mae = None if unsupported else mean([as_fraction(p['ordinal_mae']) for p in person_rows])
    recalls = []
    for category in primary.CATEGORIES:
        rows = [(person['person_id'], person['per_category_recall'][category - 1]) for person in person_rows]
        supported = [(person, row) for person, row in rows if row['support']]
        recalls.append({'category': category, 'supported_people': [person for person, _ in supported],
                        'people_without_category_support': [person for person, row in rows if not row['support']],
                        'support_assessments': sum(row['support'] for _, row in rows),
                        'supported_person_macro_recall': primary.exact(mean([as_fraction(row['recall']) for _, row in supported])),
                        'status': 'defined_on_declared_category_support' if supported else 'undefined_no_category_support'})
    edges = [Fraction(v) for v in secondary_policy['calibration']['bin_edges']]
    calibration_rows = []
    for category in primary.CATEGORIES:
        bins = [{'count': 0, 'people': set(), 'weight': Fraction(0), 'predicted': Fraction(0), 'observed': Fraction(0)}
                for _ in range(len(edges) - 1)]
        # Full-person calibration is undefined when any declared person lacks support.
        # No supported-person substitute is silently supplied.
        for person in people:
            weight = Fraction(1, len(people) * len(cases[person])) if not unsupported else None
            for aid, target, _ in cases[person]:
                probability = probabilities[aid][category - 1]
                index = next(i for i, (left, right) in enumerate(zip(edges, edges[1:]))
                             if left <= probability < right or (i == len(edges) - 2 and probability == right))
                row = bins[index]
                row['count'] += 1; row['people'].add(person)
                if weight is not None:
                    row['weight'] += weight; row['predicted'] += weight * probability
                    row['observed'] += weight * int(target == category)
        reports = []
        for i, row in enumerate(bins):
            mass = row['weight']
            predicted = row['predicted'] / mass if mass else None
            observed = row['observed'] / mass if mass else None
            reports.append({'lower': primary.exact(edges[i]), 'upper': primary.exact(edges[i + 1]),
                            'upper_inclusive': i == len(bins) - 1, 'assessment_count': row['count'],
                            'person_count': len(row['people']), 'weight_mass': primary.exact(mass) if not unsupported else None,
                            'mean_probability': primary.exact(predicted), 'observed_frequency': primary.exact(observed),
                            'absolute_gap': primary.exact(abs(predicted - observed) if mass else None)})
        ece = None if unsupported else sum((abs(row['predicted'] - row['observed']) for row in bins), Fraction(0))
        calibration_rows.append({'category': category, 'ece': primary.exact(ece), 'bins': reports})
    return {'hard_category_rule': secondary_policy['hard_category'], 'ordinal_mae': primary.exact(mae),
            'ordinal_distance_unit': 'released_category_index_steps_not_equal_clinical_severity',
            'mae_status': 'undefined_person_without_evaluable_assessment' if unsupported else 'defined_for_frozen_natural_coverage',
            'people_without_evaluable_assessments': unsupported, 'people': person_rows,
            'per_category_recall': recalls,
            'calibration': {'method': 'classwise_reliability_ece', 'weighting': 'equal_person_equal_within_person',
                            'status': 'undefined_person_without_evaluable_assessment' if unsupported else 'defined_descriptive_calibration',
                            'per_category': calibration_rows,
                            'macro_ece': primary.exact(None if unsupported else mean([as_fraction(row['ece']) for row in calibration_rows])),
                            'calibration_or_coverage_verified': False}}


def paired_uncertainty(primary, people, original_reports, secondary_reports, secondary_policy):
    bootstrap = secondary_policy['bootstrap']
    draws = bootstrap_indices(people, bootstrap['seed_sha256'], bootstrap['replicates'])
    # Canonical JSON is a public reproducibility digest, not evidence of pre-outcome freezing.
    draw_sha = hashlib.sha256(json.dumps(draws, separators=(',', ':')).encode('ascii')).hexdigest()
    alpha = (1 - Fraction(bootstrap['confidence'])) / 2
    output = []
    for contrast in secondary_policy['contrasts']:
        comparison, reference = contrast['comparison_arm'], contrast['reference_arm']
        first = {r['person_id']: r for r in original_reports[comparison]['people']}
        second = {r['person_id']: r for r in original_reports[reference]['people']}
        first_secondary = {r['person_id']: r for r in secondary_reports[comparison]['people']}
        second_secondary = {r['person_id']: r for r in secondary_reports[reference]['people']}
        rows = []
        for person in people:
            rps = [as_fraction(source[person]['normalized_rps']) for source in (first, second)]
            mae = [as_fraction(source[person]['ordinal_mae']) for source in (first_secondary, second_secondary)]
            rows.append({'person_id': person,
                         'normalized_rps': primary.exact(rps[0] - rps[1]) if all(v is not None for v in rps) else None,
                         'ordinal_mae': primary.exact(mae[0] - mae[1]) if all(v is not None for v in mae) else None})
        unsupported = [row['person_id'] for row in rows if row['normalized_rps'] is None or row['ordinal_mae'] is None]
        metrics = {}
        for metric in bootstrap['metrics']:
            values = [as_fraction(row[metric]) for row in rows]
            if unsupported:
                estimate = lower = upper = None
            else:
                estimate = mean(values)
                samples = [mean([values[index] for index in draw]) for draw in draws]
                lower, upper = linear_quantile(samples, alpha), linear_quantile(samples, 1 - alpha)
            metrics[metric] = {'estimate': primary.exact(estimate), 'lower': primary.exact(lower), 'upper': primary.exact(upper)}
        output.append({**contrast, 'status': 'undefined_person_without_evaluable_assessment' if unsupported else 'defined_conditional_cluster_percentile_interval',
                       'people_without_evaluable_assessments': unsupported, 'people': rows,
                       'bootstrap': {**bootstrap, 'people_order': list(people), 'draws_sha256': draw_sha,
                                     'draws_shared_across_arms_metrics_and_contrasts': True, 'metrics': metrics},
                       'interval_coverage_verified': False, 'pre_outcome_freezing_verified': False,
                       'conditional_scope': 'Fixed cross-fitted predictions, including overlapping training folds; descriptive conditional uncertainty, not a validated new-patient or generalization interval.'})
    return output


def grade(primary, targets, admitted, probabilities, secondary):
    original = {arm: primary.score_admitted(targets, admitted, probabilities[arm]) for arm in secondary['arms']}
    labels = {row['assessment_id']: row['category'] for row in targets['assessments']}
    reports = {arm: secondary_for_arm(primary, admitted, probabilities[arm], labels, secondary) for arm in secondary['arms']}
    return {'schema': 'dosei_secondary_report_v2', 'task': TASK,
            'complete_original_scores': original, 'secondary_scores': reports,
            'paired_uncertainty': paired_uncertainty(primary, admitted[0], original, reports, secondary),
            'prospective_policy': secondary, 'primary_source_sha256': PRIMARY_SHA256,
            'physical_input_parity_verified': False, 'authentic_census_verified': False,
            'scientifically_qualified': False, 'new_benchmark_count': 0,
            'interpretation': 'Conditional prospective secondary metrics and original-arm participant-cluster paired intervals. Existing transformed-packet diagnostics are unchanged and separate. No clinical, causal, consciousness, permutation-test or empirical interval-coverage claim.'}


def score_artifacts(policy_raw, predictions_raw, targets_raw, secondary_raw, *, primary_source,
                    expected_policy_sha256, expected_predictions_sha256,
                    expected_targets_sha256, expected_secondary_sha256):
    primary = primary_module(primary_source)
    admitted = primary.admit_policy(decode(primary, policy_raw, expected_policy_sha256, 'policy'))
    secondary = admit_secondary(primary, decode(primary, secondary_raw, expected_secondary_sha256, 'secondary'), expected_policy_sha256)
    probabilities = admit_predictions(primary, decode(primary, predictions_raw, expected_predictions_sha256, 'predictions'), admitted, secondary)
    report = grade(primary, decode(primary, targets_raw, expected_targets_sha256, 'targets'), admitted, probabilities, secondary)
    report['input_sha256'] = {'policy': expected_policy_sha256, 'predictions': expected_predictions_sha256,
                              'targets': expected_targets_sha256, 'secondary': expected_secondary_sha256}
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--primary-source', required=True)
    for kind in CAPS:
        parser.add_argument('--' + kind, required=True)
        parser.add_argument('--expected-' + kind + '-sha256', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    primary = primary_module(args.primary_source)
    pins = {kind: primary.digest(getattr(args, 'expected_' + kind + '_sha256')) for kind in CAPS}
    read = lambda kind: decode(primary, primary.read_regular(getattr(args, kind), CAPS[kind]), pins[kind], kind)
    admitted = primary.admit_policy(read('policy'))
    secondary = admit_secondary(primary, read('secondary'), pins['policy'])
    probabilities = admit_predictions(primary, read('predictions'), admitted, secondary)
    # Protected targets are not opened until all policy and candidate arms are admitted.
    report = grade(primary, read('targets'), admitted, probabilities, secondary)
    report['input_sha256'] = pins
    raw = (json.dumps(report, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode('utf-8')
    require(len(raw) <= OUTPUT_CAP, 'complete output format cap exceeded; no truncation')
    with Path(args.output).open('xb') as stream:
        stream.write(raw)


if __name__ == '__main__':
    main()
