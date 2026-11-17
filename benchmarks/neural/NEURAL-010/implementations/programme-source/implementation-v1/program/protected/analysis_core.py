"""Matched full-monitoring investigation; no fitting and no empirical execution on import."""
import hashlib
import math
import re

from vendor import event_protocol as event

TASK = 'NEURAL-010'
ARMS = ('candidate', 'signal_reference', 'montage_only')
METRICS = ('event_f1', 'event_sensitivity', 'false_alarms_per_24_observed_hours')
ID = re.compile(r'[0-9a-f]{24}\Z')
SHA = re.compile(r'[0-9a-f]{64}\Z')
COUNTS = frozenset(('n', 'positive', 'negative', 'zero', 'recordings', 'biological_patients',
                    'observed_seconds', 'reference_events', 'true_positive_events',
                    'false_alarm_events', 'false_negative_events', 'nonictal_seconds'))
SUPPORT = frozenset(('n', 'recordings', 'biological_patients', 'observed_seconds'))


def need(value, message):
    if not value:
        raise ValueError(message)


def fields(value, names):
    need(type(value) is dict and set(value) == set(names), 'exact fields: ' + ','.join(names))


def finite(value):
    try:
        return type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        return False


def intervals(value, duration, integral=False):
    need(type(value) is list and len(value) <= duration, 'bounded interval list')
    previous = 0
    for pair in value:
        need(type(pair) is list and len(pair) == 2 and all(finite(x) for x in pair), 'finite interval')
        a, b = pair
        need(0 <= a < b <= duration and a >= previous, 'sorted disjoint in-file intervals')
        need(not integral or (a == int(a) and b == int(b)), 'integral-second source annotation')
        previous = b
    return value


def validate_packet(value):
    fields(value, ('schema_version', 'task_id', 'phase', 'sealed_inputs', 'records'))
    need(type(value['schema_version']) is int and value['schema_version'] == 1
         and value['task_id'] == TASK and value['phase'] == 'post_prediction_analysis', 'exact analysis stage')
    seals = value['sealed_inputs']
    fields(seals, ('panel', 'targets', 'candidate', 'signal_reference', 'montage_only', 'phase1_seal'))
    need(all(type(x) is str and SHA.fullmatch(x) for x in seals.values()), 'all six frozen input identities')
    rows = value['records']
    need(type(rows) is list and len(rows) == 686, 'complete 686-recording monitoring panel')
    seen, people, total_seconds, total_events = set(), set(), 0, 0
    for row in rows:
        fields(row, ('recording_id', 'patient_id', 'montage_id', 'duration_seconds', 'signal', 'annotations', 'arms'))
        rid, pid, mid = row['recording_id'], row['patient_id'], row['montage_id']
        need(type(rid) is str and ID.fullmatch(rid) and rid not in seen, 'unique opaque recording')
        need(type(pid) is str and ID.fullmatch(pid), 'opaque biological patient')
        need(type(mid) is str and SHA.fullmatch(mid), 'montage signature')
        seen.add(rid); people.add(pid)
        duration = row['duration_seconds']
        need(type(duration) is int and 0 < duration <= 86400, 'full positive recording duration')
        total_seconds += duration
        fields(row['signal'], ('path', 'bytes', 'sha256'))
        signal = row['signal']
        need(signal['path'] == 'signals/' + rid + '.h5' and type(signal['bytes']) is int
             and 0 < signal['bytes'] < 1000000000 and type(signal['sha256']) is str
             and SHA.fullmatch(signal['sha256']), 'exact target-free signal binding')
        intervals(row['annotations'], duration, integral=True)
        total_events += len(row['annotations'])
        fields(row['arms'], ARMS)
        for arm in ARMS:
            hyp = intervals(row['arms'][arm], duration)
            need(event.canonical(hyp, duration) == hyp, 'canonical frozen detector events')
            total_events += len(hyp)
    need(len(people) == 23 and total_seconds <= 10000000 and total_events <= 200000,
         '23 biological people and bounded complete panel')
    return rows


def paired(values):
    """Descriptive patient-paired mean and SE; no causal or significance verdict."""
    n = len(values)
    if not n:
        return {'n': 0, 'mean': None, 'standard_error': None, 'positive': 0, 'negative': 0, 'zero': 0}
    mean = math.fsum(values) / n
    se = math.sqrt(math.fsum((v - mean) ** 2 for v in values) / (n * (n - 1))) if n > 1 else None
    return {'n': n, 'mean': mean, 'standard_error': se, 'positive': sum(v > 0 for v in values),
            'negative': sum(v < 0 for v in values), 'zero': sum(v == 0 for v in values)}


def comparisons(patient_scores):
    result = {}
    for comparator in ARMS[1:]:
        result[comparator] = {}
        for metric in METRICS:
            values = [arms['candidate'][metric] - arms[comparator][metric]
                      for arms in patient_scores.values()
                      if arms['candidate'][metric] is not None and arms[comparator][metric] is not None]
            result[comparator][metric] = paired(values)
    return result


def false_alarms(reference, hypothesis, duration):
    """Return every canonical FP interval under the same tolerant event policy."""
    refs = event.canonical(reference, duration)
    hypotheses = event.canonical(hypothesis, duration)
    detected = []
    for a, b in refs:
        window = [max(0., a - event.TOLERANCE_START), min(float(duration), b + event.TOLERANCE_END)]
        if math.fsum(event.overlap(window, h) for h in hypotheses) / (window[1] - window[0]) > 1e-6:
            detected.append(window)
    return [h for h in hypotheses if not any(event.overlap(h, r) > 0 for r in detected)]


def reconstruct(packet):
    rows = validate_packet(packet)
    people, montages, localization = {}, {}, []
    for row in sorted(rows, key=lambda r: r['recording_id']):
        pid, mid, duration = row['patient_id'], row['montage_id'], row['duration_seconds']
        people.setdefault(pid, {a: [] for a in ARMS})
        montages.setdefault(mid, {}).setdefault(pid, {a: [] for a in ARMS})
        for arm in ARMS:
            counts = event.count_events(row['annotations'], row['arms'][arm], duration)
            fp = false_alarms(row['annotations'], row['arms'][arm], duration)
            need(len(fp) == counts['false_alarm_events'], 'localized false-alarm count must reconcile')
            people[pid][arm].append(counts)
            montages[mid][pid][arm].append(counts)
            localization.append({'recording_id': row['recording_id'], 'arm': arm, 'intervals': fp})
    patient_scores = {p: {a: event.summarize(v) for a, v in arms.items()} for p, arms in sorted(people.items())}
    need(all(v['candidate']['reference_events'] > 0 for v in patient_scores.values()),
         'complete source requires annotated events for every biological person')
    strata = {}
    for montage, persons in sorted(montages.items()):
        scores = {p: {a: event.summarize(v) for a, v in arms.items()} for p, arms in sorted(persons.items())}
        strata[montage] = {'biological_patients': len(scores), 'patients': scores,
                          'candidate_minus_comparator': comparisons(scores),
                          'single_patient_support': len(scores) == 1}
    return {'patients': patient_scores, 'candidate_minus_comparator': comparisons(patient_scores),
            'montages': strata, 'false_alarm_localization': localization,
            'recordings': 686, 'biological_patients': 23,
            'observed_seconds': sum(r['duration_seconds'] for r in rows),
            'interfile_gaps_included': False,
            'artifact_class_or_causal_attribution_supported': False}


def numeric_error(actual, expected, path='report'):
    """Exact structure/nulls/IDs; scale-aware numerical reconstruction error."""
    if type(expected) is dict:
        fields(actual, expected)
        return max((numeric_error(actual[k], expected[k], path + '.' + k) for k in expected), default=0.)
    if type(expected) is list:
        need(type(actual) is list and len(actual) == len(expected), 'complete ordered list at ' + path)
        return max((numeric_error(a, e, path + '[' + str(i) + ']')
                    for i, (a, e) in enumerate(zip(actual, expected))), default=0.)
    if type(expected) in (int, float):
        need(finite(actual), 'finite numeric value at ' + path)
        field = path.rsplit('.', 1)[-1]
        if field in COUNTS:
            need(actual == int(actual) and actual >= 0, 'nonnegative integral count at ' + path)
        if field in SUPPORT:
            need(actual == expected, 'exact input support at ' + path)
        try:
            scale = max(1., abs(expected))
            error = abs(actual / scale - expected / scale)
        except OverflowError as error:
            raise ValueError('unrepresentable numerical error at ' + path) from error
        need(math.isfinite(error), 'unrepresentable numerical error at ' + path)
        return error
    need(type(actual) is type(expected) and actual == expected, 'exact value at ' + path)
    return 0.


def grade(packet, packet_sha256, submission):
    fields(submission, ('schema_version', 'task_id', 'input_sha256', 'report'))
    need(type(submission['schema_version']) is int and submission['schema_version'] == 1
         and submission['task_id'] == TASK and submission['input_sha256'] == packet_sha256,
         'submission bound to exact analysis input')
    error = numeric_error(submission['report'], reconstruct(packet))
    return {'task_id': TASK, 'metric': 'maximum_scaled_reconstruction_error', 'lower_is_better': True,
            'error': error, 'within_numerical_tolerance': error <= 1e-8,
            'scientific_improvement_proven': False, 'interpretation': 'Numerical evidence reconstruction only.'}
