"""Operator-only four-stream endpoint computation; no detector execution.

The target loader is called only after all four frozen streams validate.
Operator-selected hashes bind bytes; they do not prove fitting/custody history.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import types

ARMS = ('candidate', 'matched_no_eeg', 'signal_reference', 'montage_only')
METRICS = ('event_f1', 'event_sensitivity', 'false_alarms_per_24_observed_hours')
RECORDS_SHA256 = '72b640d6a3fef4b40de255933d1403823d1655c56f93d69761105a653798fc08'
EVENT_SHA256 = '462afe5bb002df77567bda53c232607b86552a658f99515c283774635956599c'
ID = re.compile(r'[0-9a-f]{24}\Z')
SHA = re.compile(r'[0-9a-f]{64}\Z')
CAP = 16 * 1024 * 1024


def need(value, message):
    if not value:
        raise ValueError(message)


def exact(value, fields):
    need(type(value) is dict and set(value) == set(fields), 'exact fields: ' + ', '.join(fields))


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def parse(raw, expected):
    need(type(raw) is bytes and 0 < len(raw) <= CAP, 'bounded bytes')
    need(type(expected) is str and SHA.fullmatch(expected), 'operator-selected SHA256')
    need(digest(raw) == expected, 'frozen operand hash mismatch')

    def pairs(items):
        value = {}
        for key, item in items:
            need(key not in value, 'duplicate JSON key')
            value[key] = item
        return value

    def bad(value):
        raise ValueError('nonfinite JSON constant: ' + value)

    return json.loads(raw.decode('utf-8'), object_pairs_hook=pairs, parse_constant=bad)


def event_policy():
    """Execute exactly the preserved task's small dependency-free event policy."""
    path = Path(__file__).parent.parent / 'programme-source/implementation-v1/program/public/event_protocol.py'
    raw = capture(path, 100000)
    need(digest(raw) == EVENT_SHA256, 'preserved event policy changed')
    module = types.ModuleType('neural010_scientific_event_policy')
    exec(compile(raw, str(path), 'exec'), module.__dict__)
    return module


def source_roster(raw):
    need(type(raw) is bytes and digest(raw) == RECORDS_SHA256, 'exact publisher RECORDS bytes')
    paths = raw.decode('ascii').splitlines()
    need(len(paths) == len(set(paths)) == 686, 'complete source roster')
    return set(paths)


def panel_rows(panel, roster):
    exact(panel, ('schema', 'records'))
    need(panel['schema'] == 'neural010-scientific-panel-v2', 'panel schema')
    rows = panel['records']
    need(type(rows) is list and len(rows) == 686, 'complete 686-record panel')
    by_id, sources, person_map, reverse_map = {}, set(), {}, {}
    for row in rows:
        exact(row, ('recording_id', 'patient_id', 'source_record', 'montage_id', 'duration_seconds'))
        rid, pid = row['recording_id'], row['patient_id']
        need(type(rid) is str and ID.fullmatch(rid) and rid not in by_id, 'unique opaque recording ID')
        need(type(pid) is str and ID.fullmatch(pid), 'opaque biological person ID')
        source = row['source_record']
        need(type(source) is str and source in roster and source not in sources, 'exact source membership')
        folder = source.split('/')[0]
        person = 'chb01' if folder == 'chb21' else folder
        need(person_map.setdefault(person, pid) == pid, 'source aliases must share one person ID')
        need(reverse_map.setdefault(pid, person) == person, 'distinct biological people must not collapse')
        need(type(row['montage_id']) is str and SHA.fullmatch(row['montage_id']), 'montage digest')
        duration = row['duration_seconds']
        need(type(duration) is int and 0 < duration <= 86400, 'integral positive observed duration')
        by_id[rid] = row
        sources.add(source)
    need(sources == roster and len(person_map) == len(reverse_map) == 23, 'complete biological support')
    need(sum(r['duration_seconds'] for r in rows) <= 10000000, 'source duration bound')
    return by_id


def intervals(value, duration, integral=False):
    need(type(value) is list and len(value) <= duration, 'bounded event list')
    previous = 0
    for pair in value:
        need(type(pair) is list and len(pair) == 2, 'event pair')
        for endpoint in pair:
            try:
                valid = type(endpoint) in (int, float) and math.isfinite(endpoint)
            except OverflowError:
                valid = False
            need(valid, 'finite numeric event endpoint, not bool')
        a, b = pair
        need(previous <= a < b <= duration, 'sorted disjoint in-record events')
        need(not integral or (a == int(a) and b == int(b)), 'integral source annotation endpoints')
        previous = b


def stream_rows(value, arm, panel_sha256, by_id, policy):
    fields = ('schema', 'panel_sha256', 'records') if arm == 'targets' else ('schema', 'panel_sha256', 'arm', 'records')
    exact(value, fields)
    schema = 'neural010-scientific-targets-v2' if arm == 'targets' else 'neural010-scientific-events-v2'
    need(value['schema'] == schema and value['panel_sha256'] == panel_sha256, 'exact stream panel binding')
    if arm != 'targets':
        need(value['arm'] == arm, 'fixed arm identity')
    rows = value['records']
    need(type(rows) is list and len(rows) == len(by_id), 'all stream records required')
    result = {}
    total = 0
    for row in rows:
        exact(row, ('recording_id', 'events'))
        rid = row['recording_id']
        need(type(rid) is str and rid in by_id and rid not in result, 'exact unique stream ID')
        duration = by_id[rid]['duration_seconds']
        intervals(row['events'], duration, integral=arm == 'targets')
        if arm != 'targets':
            need(policy.canonical(row['events'], duration) == row['events'], 'canonical frozen stream events')
        result[rid] = row['events']
        total += len(row['events'])
    need(total <= 200000, 'bounded stream events')
    return result


def paired(scores, comparator, metric):
    differences, undefined = {}, []
    for pid, arms in sorted(scores.items()):
        a, b = arms['candidate'][metric], arms[comparator][metric]
        if a is None or b is None:
            undefined.append(pid)
        else:
            differences[pid] = a - b
    values = list(differences.values())
    n = len(values)
    mean = math.fsum(values) / n if n else None
    se = math.sqrt(math.fsum((v - mean) ** 2 for v in values) / (n * (n - 1))) if n > 1 else None
    return {'n': n, 'mean': mean, 'standard_error': se, 'differences': differences,
            'undefined_person_ids': undefined, 'positive': sum(v > 0 for v in values),
            'negative': sum(v < 0 for v in values), 'zero': sum(v == 0 for v in values)}


def contrasts(scores):
    return {arm: {metric: paired(scores, arm, metric) for metric in METRICS} for arm in ARMS[1:]}


def false_alarms(reference, hypothesis, duration, policy):
    detected = []
    for a, b in policy.canonical(reference, duration):
        window = [max(0., a - policy.TOLERANCE_START), min(float(duration), b + policy.TOLERANCE_END)]
        occupancy = math.fsum(policy.overlap(window, h) for h in hypothesis)
        if occupancy / (window[1] - window[0]) > 1e-6:
            detected.append(window)
    return [h for h in hypothesis if not any(policy.overlap(h, r) > 0 for r in detected)]


def evaluate(*, records_bytes, panel_bytes, stream_bytes, target_loader, expected_sha256):
    """Compute the registered endpoint using protected operator-selected operands.

    All expected hashes and comparator bytes must come from the independent
    operator. This API authenticates operands and arithmetic, not their history.
    The caller owns closure/isolation; no candidate code is invoked here.
    """
    exact(expected_sha256, ('panel', 'targets', *ARMS))
    exact(stream_bytes, ARMS)
    for pin in expected_sha256.values():
        need(type(pin) is str and SHA.fullmatch(pin), 'valid frozen operand hash')
    roster = source_roster(records_bytes)
    panel = panel_rows(parse(panel_bytes, expected_sha256['panel']), roster)
    policy = event_policy()
    streams = {}
    # Do not call target_loader, hash targets or parse targets before every arm passes.
    for arm in ARMS:
        streams[arm] = stream_rows(parse(stream_bytes[arm], expected_sha256[arm]), arm,
                                   expected_sha256['panel'], panel, policy)
    targets = stream_rows(parse(target_loader(), expected_sha256['targets']), 'targets',
                          expected_sha256['panel'], panel, policy)
    people, montages, localization = {}, {}, []
    for rid, row in sorted(panel.items()):
        pid, mid, duration = row['patient_id'], row['montage_id'], row['duration_seconds']
        people.setdefault(pid, {arm: [] for arm in ARMS})
        montages.setdefault(mid, {}).setdefault(pid, {arm: [] for arm in ARMS})
        for arm in ARMS:
            counts = policy.count_events(targets[rid], streams[arm][rid], duration)
            fp = false_alarms(targets[rid], streams[arm][rid], duration, policy)
            need(len(fp) == counts['false_alarm_events'], 'false-alarm localization reconciliation')
            people[pid][arm].append(counts)
            montages[mid][pid][arm].append(counts)
            localization.append({'recording_id': rid, 'arm': arm, 'intervals': fp})

    def summarize(table):
        return {pid: {arm: policy.summarize(counts) for arm, counts in arms.items()}
                for pid, arms in sorted(table.items())}

    patient_scores = summarize(people)
    need(all(v['candidate']['reference_events'] > 0 for v in patient_scores.values()),
         'complete source requires reference events for every person; do not drop unsupported people')
    strata = {}
    for mid, table in sorted(montages.items()):
        scores = summarize(table)
        strata[mid] = {'patients': scores, 'biological_patients': len(scores),
                       'single_patient_support': len(scores) == 1,
                       'candidate_minus_comparator': contrasts(scores)}
    comparison = contrasts(patient_scores)
    primary = comparison['matched_no_eeg']['event_f1']
    need(primary['n'] == 23, 'all 23 people required for primary contrast')
    return {'schema': 'neural010-scientific-outcomes-v2', 'task_id': 'NEURAL-010',
            'primary': {'name': 'EEG_minus_matched_no_EEG_patient_macro_event_F1',
                        'direction': 'two_sided', **primary},
            'patients': patient_scores, 'candidate_minus_comparator': comparison,
            'montages': strata, 'false_alarm_localization': localization,
            'recordings': len(panel), 'biological_patients': len(people),
            'observed_seconds': sum(r['duration_seconds'] for r in panel.values()),
            'provenance': {'operand_sha256': dict(expected_sha256), 'records_sha256': RECORDS_SHA256,
                           'event_policy_sha256': EVENT_SHA256},
            'interpretation': {'scope': 'frozen detector outcomes; not analyst reconstruction or direct interpretation',
                               'uncertainty': 'descriptive paired standard error; overlapping training folds are not independent replication',
                               'montage': 'stratified associations; not causal montage effects',
                               'false_alarm_denominator': '24 observed hours; interfile gaps excluded',
                               'limits': 'Source preparation, independent comparator competence, fitting lineage and process isolation require external qualification.'}}


def capture(path, cap=CAP):
    """Bound local operands; reject FIFOs/symlinks before reading their contents."""
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
    try:
        initial = os.fstat(fd)
        need(stat.S_ISREG(initial.st_mode) and 0 < initial.st_size <= cap, 'bounded regular input file')
        parts, size = [], 0
        while size <= cap:
            part = os.read(fd, min(65536, cap + 1 - size))
            if not part:
                break
            parts.append(part)
            size += len(part)
        final = os.fstat(fd)
        need(size == initial.st_size and all(getattr(initial, k) == getattr(final, k)
             for k in ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns')), 'stable captured operand')
        return b''.join(parts)
    finally:
        os.close(fd)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('records', 'panel', 'targets', 'operator-pins', *ARMS):
        parser.add_argument('--' + name.replace('_', '-'), required=True)
    args = vars(parser.parse_args())
    # The trusted launcher selects this pin file; candidates cannot author it.
    pins_raw = capture(args['operator_pins'], 10000)
    pins = parse(pins_raw, digest(pins_raw))
    result = evaluate(records_bytes=capture(args['records'], 20000), panel_bytes=capture(args['panel']),
                      stream_bytes={arm: capture(args[arm]) for arm in ARMS},
                      target_loader=lambda: capture(args['targets']), expected_sha256=pins)
    print(json.dumps(result, sort_keys=True, allow_nan=False))


if __name__ == '__main__':
    main()
