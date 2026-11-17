"""Target-withholding detector submissions joined to the preserved event scorer.

This is an operator library, not a process sandbox, EEG loader or viewer provider.
Participants receive only explicitly projected fold observations and submit event
intervals. Independent operators own preparation, references and target loaders.
"""
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import types

CAP = 16 * 1024 * 1024
RAW_EVENT_CAP = 200000
ID = re.compile(r'[0-9a-f]{24}\Z')
SHA = re.compile(r'[0-9a-f]{64}\Z')
SCORER_SHA256 = 'e72a814446744f1ca5ecb7b581c702c671983b4280ee876347d36016d8edd0c5'
MODES = ('typed_viewer', 'frozen_program')
SUPPORT_FIELDS = ('recording_id', 'patient_id', 'duration_seconds', 'montage_id',
                  'channel_labels', 'signal_handle')


def need(value, message):
    if not value:
        raise ValueError(message)


def exact(value, fields):
    need(type(value) is dict and set(value) == set(fields), 'exact fields: ' + ', '.join(fields))


def sha(value):
    need(type(value) is str and SHA.fullmatch(value), 'typed SHA256')
    return value


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True,
                      allow_nan=False).encode('ascii')


def pin(raw):
    need(type(raw) is bytes and 0 < len(raw) <= CAP, 'bounded nonempty bytes')
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def descriptor(value):
    exact(value, ('bytes', 'sha256'))
    need(type(value['bytes']) is int and 0 < value['bytes'] <= 2 ** 40, 'positive byte extent')
    sha(value['sha256'])
    return value


def parse(raw, expected=None):
    actual = pin(raw)
    if expected is not None:
        descriptor(expected)
        need(actual == expected, 'operator-selected operand identity')

    def pairs(items):
        result = {}
        for key, value in items:
            need(key not in result, 'duplicate JSON key')
            result[key] = value
        return result

    def bad(value):
        raise ValueError('nonfinite JSON constant')

    return json.loads(raw.decode('utf-8'), object_pairs_hook=pairs, parse_constant=bad)


def scorer():
    """Capture and load the unchanged, pinned sibling scorer."""
    path = Path(__file__).parent.parent / 'scientific-scorer-v2/scorer.py'
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_size == 13273, 'ordinary exact scorer source')
        raw = b''
        while len(raw) <= 13273:
            part = os.read(fd, 13274 - len(raw))
            if not part:
                break
            raw += part
        after = os.fstat(fd)
        need(all(getattr(before, key) == getattr(after, key)
                 for key in ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns')),
             'stable scorer source')
    finally:
        os.close(fd)
    need(len(raw) == 13273 and hashlib.sha256(raw).hexdigest() == SCORER_SHA256,
         'preserved scientific scorer identity')
    module = types.ModuleType('neural010_detection_scientific_scorer')
    module.__file__ = str(path)
    exec(compile(raw, str(path), 'exec'), module.__dict__)
    return module


def _by_id(rows, count=686):
    need(type(rows) is list and len(rows) == count, 'complete record count')
    result = {}
    for row in rows:
        need(type(row) is dict, 'record object')
        rid = row.get('recording_id')
        need(type(rid) is str and ID.fullmatch(rid) and rid not in result,
             'unique opaque record identity')
        result[rid] = row
    return result


def _channels(row):
    labels = row['channel_labels']
    need(type(labels) is list and 0 < len(labels) <= 512
         and all(type(v) is str and 0 < len(v) <= 256 and v.isprintable() for v in labels),
         'bounded ordered channel labels, including duplicates')
    need(hashlib.sha256(encoded(sorted(labels))).hexdigest() == row['montage_id'],
         'exact montage multiset')


def project_preparation(*, records_bytes, panel_bytes, metadata_bytes,
                        provenance_bytes, expected):
    """Project original preparer outputs without reading an assessment or signal.

    The protected provenance is required only to bind complete source membership
    and biological aliases. It is never a participant operand. The caller must
    independently authenticate the original preparer's process and source lineage.
    """
    exact(expected, ('panel', 'metadata', 'provenance'))
    s = scorer()
    roster = s.source_roster(records_bytes)
    original = parse(panel_bytes, expected['panel'])
    exact(original, ('schema_version', 'task_id', 'records'))
    need(type(original['schema_version']) is int and original['schema_version'] == 1
         and original['task_id'] == 'NEURAL-009', 'original preparation carrier')
    metadata = parse(metadata_bytes, expected['metadata'])
    exact(metadata, ('schema', 'records'))
    need(metadata['schema'] == 'neural010-target-free-metadata-v1', 'preparer metadata schema')
    provenance = parse(provenance_bytes, expected['provenance'])
    exact(provenance, ('records',))
    p, m, source = (_by_id(value['records']) for value in (original, metadata, provenance))
    need(set(p) == set(m) == set(source), 'same complete preparation identities')
    scientific, public, bindings = [], [], []
    for rid in sorted(p):
        a, b, c = p[rid], m[rid], source[rid]
        exact(a, ('recording_id', 'patient_id', 'duration_seconds', 'observed_intervals',
                  'path', 'bytes', 'sha256'))
        exact(b, ('recording_id', 'patient_id', 'duration_seconds', 'montage_id',
                  'channel_count', 'channel_labels', 'source_edf', 'target_free_projection'))
        exact(c, ('recording_id', 'source_path', 'source_edf', 'header', 'annotation_evidence'))
        for key in ('recording_id', 'patient_id', 'duration_seconds'):
            need(type(a[key]) is type(b[key]) and a[key] == b[key], 'panel/metadata geometry join')
        duration = a['duration_seconds']
        need(type(duration) is int and 0 < duration <= 86400, 'whole observed seconds')
        need(a['observed_intervals'] == [[0, duration]]
             and all(type(v) is int for pair in a['observed_intervals'] for v in pair),
             'complete observed [0,duration), not interfile gaps')
        need(a['path'] == 'signals/' + rid + '.h5', 'opaque original projection path')
        descriptor(b['source_edf']); descriptor(b['target_free_projection'])
        descriptor(c['source_edf']); descriptor({k: a[k] for k in ('bytes', 'sha256')})
        need(c['source_edf'] == b['source_edf'], 'original source identity join')
        need(b['target_free_projection'] == {k: a[k] for k in ('bytes', 'sha256')},
             'exact target-free projection identity')
        _channels(b)
        need(type(b['channel_count']) is int and b['channel_count'] == len(b['channel_labels']),
             'complete ordered channel multiset')
        scientific.append({k: b[k] for k in ('recording_id', 'patient_id', 'duration_seconds', 'montage_id')}
                          | {'source_record': c['source_path']})
        # Strict allowlist: no source paths/digests, annotations or filenames.
        public.append({k: b[k] for k in ('recording_id', 'patient_id', 'duration_seconds',
                                        'montage_id', 'channel_labels')}
                      | {'signal_handle': 'signal:' + rid})
        bindings.append({'recording_id': rid, 'signal_handle': 'signal:' + rid,
                         'projection_path': a['path'], 'projection': b['target_free_projection']})
    panel = encoded({'schema': 'neural010-scientific-panel-v2', 'records': scientific})
    s.panel_rows(parse(panel), roster)  # Includes the exact chb01/chb21 biological join.
    support = encoded({'schema': 'neural010-detection-support-v1', 'task_id': 'NEURAL-010',
                       'panel_sha256': pin(panel)['sha256'],
                       'original_panel_sha256': expected['panel']['sha256'], 'records': public})
    private = encoded({'schema': 'neural010-detection-private-bindings-v1',
                       'original_preparation_inputs': expected, 'support': pin(support),
                       'scientific_panel': pin(panel), 'signals': bindings})
    return {'support': support, 'scientific_panel': panel, 'private_bindings': private}


def support_rows(raw):
    value = parse(raw)
    exact(value, ('schema', 'task_id', 'panel_sha256', 'original_panel_sha256', 'records'))
    need(value['schema'] == 'neural010-detection-support-v1' and value['task_id'] == 'NEURAL-010',
         'detection support schema')
    sha(value['panel_sha256'])
    sha(value['original_panel_sha256'])
    rows = _by_id(value['records'])
    people = set()
    for rid, row in rows.items():
        exact(row, SUPPORT_FIELDS)
        pid = row['patient_id']
        need(type(pid) is str and ID.fullmatch(pid), 'opaque person identity')
        people.add(pid)
        need(type(row['duration_seconds']) is int and 0 < row['duration_seconds'] <= 86400,
             'positive integral duration')
        need(row['signal_handle'] == 'signal:' + rid, 'opaque signal handle')
        _channels(row)
    need(len(people) == 23 and sum(r['duration_seconds'] for r in rows.values()) <= 10000000,
         'complete biological support and observed-time bound')
    return value, rows


def make_query(support_bytes, *, held_person, mode, method_sha256, fold_state_sha256):
    """Create one complete held-person query after method/state freeze.

    Method/state hashes identify externally frozen recipe and state; they do not
    certify learning history. Viewer and programme input budgets remain separate.
    """
    _, rows = support_rows(support_bytes)
    sha(method_sha256); sha(fold_state_sha256)
    need(type(mode) is str and mode in MODES, 'explicit supported representation mode')
    selected = [row for _, row in sorted(rows.items()) if row['patient_id'] == held_person]
    need(selected, 'existing held biological person')
    return encoded({'schema': 'neural010-detection-query-v1', 'support_sha256': pin(support_bytes)['sha256'],
                    'held_person': held_person, 'mode': mode, 'method_sha256': method_sha256,
                    'fold_state_sha256': fold_state_sha256, 'records': selected})


def project_training_view(raw, expected_pin, support_bytes, *, held_person):
    """Allow only the original final-fold TRAIN.json and all 22 other people.

    This document contains legitimate training annotations. It must never enter a
    different outer person's participant context or a zero-shot viewer condition.
    """
    _, rows = support_rows(support_bytes)
    doc = parse(raw, expected_pin)
    exact(doc, ('schema', 'task_id', 'outer_person', 'inner_person', 'role', 'records'))
    need(doc['schema'] == 'neural010-detector-view-v1' and doc['task_id'] == 'NEURAL-010'
         and doc['outer_person'] == held_person and doc['inner_person'] is None
         and doc['role'] == 'training', 'original final-fold training view')
    selected = {rid: row for rid, row in rows.items() if row['patient_id'] != held_person}
    need(len({r['patient_id'] for r in selected.values()}) == 22, 'complete 22-person training support')
    source = _by_id(doc['records'], len(selected))
    need(set(source) == set(selected), 'exact training support excludes whole held person')
    result = []
    s = scorer()
    for rid, row in sorted(source.items()):
        exact(row, ('recording_id', 'patient_id', 'duration_seconds', 'montage_id',
                    'channel_count', 'channel_labels', 'source_edf', 'target_free_projection', 'events'))
        for key in ('recording_id', 'patient_id', 'duration_seconds', 'montage_id', 'channel_labels'):
            need(type(row[key]) is type(selected[rid][key]) and row[key] == selected[rid][key],
                 'same training observation geometry')
        need(type(row['channel_count']) is int and row['channel_count'] == len(row['channel_labels']),
             'training channel count')
        descriptor(row['source_edf']); descriptor(row['target_free_projection'])
        s.intervals(row['events'], row['duration_seconds'], integral=True)
        result.append(dict(selected[rid], events=row['events']))
    return encoded({'schema': 'neural010-detection-training-v1', 'support_sha256': pin(support_bytes)['sha256'],
                    'held_person': held_person, 'records': result})


def freeze_candidate(*, support_bytes, queries, submissions, mode, method_sha256):
    """Validate all 23 frozen query/submission pairs before making a full stream.

    Query bytes and method identity are operator-owned. Submissions cannot select
    references, labels, support or representation. There is no target operand.
    """
    doc, rows = support_rows(support_bytes)
    people = {row['patient_id'] for row in rows.values()}
    need(type(mode) is str and mode in MODES, 'one declared mode per complete campaign')
    sha(method_sha256)
    need(type(queries) is dict and type(submissions) is dict and set(queries) == set(submissions) == people,
         'all 23 complete outer contexts')
    need(sum(pin(raw)['bytes'] for raw in queries.values()) <= CAP, 'aggregate query byte bound')
    need(sum(pin(raw)['bytes'] for raw in submissions.values()) <= CAP, 'aggregate submission byte bound')
    s, event = scorer(), scorer().event_policy()
    raw_rows, folds, total_raw_events = [], [], 0
    for person in sorted(people):
        query = parse(queries[person])
        exact(query, ('schema', 'support_sha256', 'held_person', 'mode', 'method_sha256',
                      'fold_state_sha256', 'records'))
        need(queries[person] == make_query(support_bytes, held_person=person, mode=mode,
             method_sha256=method_sha256, fold_state_sha256=query['fold_state_sha256']),
             'operator-owned exact frozen query')
        output = parse(submissions[person])
        exact(output, ('schema', 'query_sha256', 'records'))
        need(output['schema'] == 'neural010-detection-submission-v1'
             and output['query_sha256'] == pin(queries[person])['sha256'], 'exact submitted query binding')
        expected = {rid: row for rid, row in rows.items() if row['patient_id'] == person}
        observed = _by_id(output['records'], len(expected))
        need(set(observed) == set(expected), 'every held-person recording, including explicit empty events')
        for rid, row in sorted(observed.items()):
            exact(row, ('recording_id', 'events'))
            s.intervals(row['events'], expected[rid]['duration_seconds'])
            total_raw_events += len(row['events'])
            need(total_raw_events <= RAW_EVENT_CAP, 'complete pre-canonical raw-event bound')
            raw_rows.append(row)
        folds.append({'held_person': person, 'query': pin(queries[person]),
                      'submission': pin(submissions[person]), 'records': len(expected),
                      'fold_state_sha256': query['fold_state_sha256']})
    # All raw counts and complete campaign bytes pass before canonicalization.
    merged = [{'recording_id': row['recording_id'],
               'events': event.canonical(row['events'], rows[row['recording_id']]['duration_seconds'])}
              for row in raw_rows]
    need(sum(len(r['events']) for r in merged) <= 200000, 'bounded complete event count')
    stream = encoded({'schema': 'neural010-scientific-events-v2', 'panel_sha256': doc['panel_sha256'],
                      'arm': 'candidate', 'records': sorted(merged, key=lambda r: r['recording_id'])})
    receipt = encoded({'schema': 'neural010-detection-freeze-v1', 'support': pin(support_bytes),
                       'mode': mode, 'method_sha256': method_sha256, 'folds': folds,
                       'candidate': pin(stream), 'records': 686, 'people': 23,
                       'event_policy_sha256': s.EVENT_SHA256,
                       'scope': 'complete frozen submission bytes; fitting chronology and process custody are external'})
    return {'candidate': stream, 'freeze': receipt}


def grade_frozen(*, records_bytes, panel_bytes, support_bytes, queries, submissions,
                 frozen, mode, method_sha256, reference_bytes, operator_reference_pins,
                 original_panel_pin, original_assessment_pin, assessment_loader):
    """Admit complete frozen candidate/references, then open original assessment.

    The independent caller owns all reference bytes and pins. Rechecking immutable
    supplied submissions is not proof of actual isolation or a pre-query freeze.
    """
    exact(frozen, ('candidate', 'freeze'))
    pin(frozen['candidate']); pin(frozen['freeze'])
    expected = freeze_candidate(support_bytes=support_bytes, queries=queries, submissions=submissions,
                                mode=mode, method_sha256=method_sha256)
    need(frozen == expected, 'unaltered complete candidate freeze')
    s = scorer()
    support, public = support_rows(support_bytes)
    roster = s.source_roster(records_bytes)
    panel = s.panel_rows(parse(panel_bytes), roster)
    need(pin(panel_bytes)['sha256'] == support['panel_sha256'] and set(public) == set(panel),
         'same scientific panel and participant support')
    for rid, row in panel.items():
        for key in ('recording_id', 'patient_id', 'duration_seconds', 'montage_id'):
            need(type(row[key]) is type(public[rid][key]) and row[key] == public[rid][key],
                 'same full scoring and query geometry')
    exact(reference_bytes, s.ARMS[1:]); exact(operator_reference_pins, s.ARMS[1:])
    streams = {'candidate': frozen['candidate'], **reference_bytes}
    hashes = {'panel': pin(panel_bytes)['sha256'], 'candidate': pin(frozen['candidate'])['sha256']}
    event = s.event_policy()
    for arm in s.ARMS:
        raw = streams[arm]
        if arm != 'candidate':
            descriptor(operator_reference_pins[arm])
            need(pin(raw) == operator_reference_pins[arm], 'independent operator reference identity')
            hashes[arm] = operator_reference_pins[arm]['sha256']
        s.stream_rows(parse(raw), arm, hashes['panel'], panel, event)
    descriptor(original_panel_pin); descriptor(original_assessment_pin)
    need(original_panel_pin['sha256'] == support['original_panel_sha256'],
         'same original preparation panel identity')
    # This is the first access to the protected assessment. Training-view reads
    # happen only in separately isolated outer-fold contexts, outside this API.
    original = parse(assessment_loader(), original_assessment_pin)
    exact(original, ('schema_version', 'task_id', 'panel_sha256', 'records'))
    need(type(original['schema_version']) is int and original['schema_version'] == 1
         and original['task_id'] == 'NEURAL-009'
         and original['panel_sha256'] == original_panel_pin['sha256'], 'original prepared assessment binding')
    converted = encoded({'schema': 'neural010-scientific-targets-v2', 'panel_sha256': hashes['panel'],
                         'records': original['records']})
    hashes['targets'] = pin(converted)['sha256']
    result = s.evaluate(records_bytes=records_bytes, panel_bytes=panel_bytes, stream_bytes=streams,
                        target_loader=lambda: converted, expected_sha256=hashes)
    result['detection_interface'] = {
        'freeze': pin(frozen['freeze']), 'support': pin(support_bytes), 'mode': mode,
        'method_sha256': method_sha256, 'original_panel': original_panel_pin,
        'original_assessment': original_assessment_pin, 'converted_assessment': pin(converted),
        'operator_reference_pins': operator_reference_pins,
        'qualified_provider_or_process_isolation': False,
        'independent_reference_matching_or_competence_established': False,
        'scientific_or_model_performance_established_by_interface': False,
        'interpretation': 'Arithmetic of supplied frozen detector streams. An EEG-ablation claim additionally requires independently established learner, tuning, metadata and fitting matches; an arbitrary candidate versus the fixed no-EEG stream does not establish incremental EEG information.',
        'access_comparison': 'A zero-shot viewer and a programme trained on22 other people have different information budgets unless explicitly matched.'}
    return result
