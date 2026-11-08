"""Label-free metadata admission; no path reads, arrays, targets or native imports."""
import hashlib
import json
import re

SOURCE_PIN = {'bytes': 17391, 'sha256': 'c62ba1c5161287d1915d7dd49165be79ca93632dee686be0ea29f0929c1791cf'}
SOURCE_CANONICAL_SHA256 = 'e942c94605b6d5ecb3857f7f1edb06a5a42a0b29ece6f06d084d5c14c712fd96'
SPLITS = ('train', 'val', 'test')
ID = re.compile(r'[0-9a-f]{32}\Z')
SHA = re.compile(r'[0-9a-f]{64}\Z')
SHIFT = {'split': 'test', 'bins': 10, 'axis': 1, 'window_bins': 50, 'operation': 'cyclic_positive'}
CONTEXT_FIELDS = {'case_id', 'session_id', 'history_speed', 'history_position', 'history_offsets',
                  'target_offsets', 'stimulus_block', 'stimulus_latency_s'}
REASONS = {'whole2s_context_not_inside_exactly_one_official_split',
           'outside_declared_wheel_or_spike_support', 'not50actual_samples_each_side'}


def need(ok, message):
    if not ok:
        raise ValueError(message)


def integer(value, minimum=0):
    return type(value) is int and value >= minimum


def keys(value, expected, message):
    need(type(value) is dict and set(value) == set(expected), message)


def pairs(items):
    result = {}
    for name, value in items:
        need(name not in result, 'Duplicate JSON key')
        result[name] = value
    return result


def decode(raw):
    need(type(raw) is bytes, 'Captured bytes required')
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite JSON')))


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def pin(raw):
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def admit_pin(value):
    keys(value, {'bytes', 'sha256'}, 'Exact content pin')
    need(integer(value['bytes'], 1) and type(value['sha256']) is str and SHA.fullmatch(value['sha256']),
         'Positive byte count and SHA256')
    return value


def descriptor(value, path):
    keys(value, {'path', 'bytes', 'sha256'}, 'Exact path descriptor')
    need(value['path'] == path, 'Exact selected packet path')
    admit_pin({k: value[k] for k in ('bytes', 'sha256')})
    return value


def admit_sources(raw):
    need(pin(raw) == SOURCE_PIN, 'Exact frozen complete original roster')
    value = decode(raw)
    need(value['schema'] == 'neural060_sources_v1' and
         value['source_commit'] == '6fbd666fe8170a2165f5198c1f490911424a654d' and
         value['dataset_build'] == 'ibl_brain_wide_bench_2026/all_units/eval', 'Original source edition')
    assets = value['assets']
    need(type(assets) is list and len(assets) == 29 and len({a['eid'] for a in assets}) == 29 and
         len({a['subject'] for a in assets}) == 13 and len({a['lab'] for a in assets}) == 7 and
         sum(a['bytes'] for a in assets) == 49113902269, 'Exact full source cohort')
    return value


def _sessions(value, sources):
    """Metadata joins only; authentic file-body qualification is separate."""
    rows = value['sessions']
    need(type(rows) is list and len(rows) == 29, 'All29 original sessions')
    seen_sessions, seen_cases = set(), set()
    total = dict(train_cases=0, val_cases=0, test_cases=0, movements=0,
                 included=0, excluded=0, uncompressed_count_bytes=0)
    for ordinal, (row, asset) in enumerate(zip(rows, sorted(sources['assets'], key=lambda x: x['eid'])), 1):
        keys(row, {'ordinal', 'session_id', 'source', 'unit_count', 'unit_axis_sha256', 'splits',
                   'disposition_summary', 'overlap'}, 'Exact session projection')
        session = row['session_id']
        need(type(row['ordinal']) is int and row['ordinal'] == ordinal and type(session) is str and
             ID.fullmatch(session) and session not in seen_sessions, 'Ordered unique opaque session')
        seen_sessions.add(session)
        keys(row['source'], {'eid', 'bytes', 'etag', 'sha256'}, 'Exact original source identity')
        source = row['source']
        need(source['eid'] == asset['eid'] and type(source['bytes']) is int and source['bytes'] == asset['bytes']
             and source['etag'] == asset['etag'] and type(source['sha256']) is str
             and SHA.fullmatch(source['sha256']), 'Original source-set identity; no replacement')
        if asset.get('inherited_sha256') is not None:
            need(source['sha256'] == asset['inherited_sha256'], 'Inherited full-source hash')
        need(integer(row['unit_count'], 1) and type(row['unit_axis_sha256']) is str and
             SHA.fullmatch(row['unit_axis_sha256']), 'Full native unit axis identity')
        keys(row['splits'], SPLITS, 'All original splits')
        counts = {}
        for split in SPLITS:
            view = row['splits'][split]
            fields = {'case_ids', 'context', 'neural'} | ({'neural_shift10'} if split == 'test' else set())
            keys(view, fields, 'Exact phase-specific fields; shifted fitting prohibited')
            ids = view['case_ids']
            need(type(ids) is list and len(ids) > 0, 'Each session contributes every split')
            for case in ids:
                need(type(case) is str and ID.fullmatch(case) and case not in seen_cases,
                     'Globally unique complete case IDs')
                seen_cases.add(case)
            prefix = 'public/' + session + '/' + split + '/'
            descriptor(view['context'], prefix + 'context.json')
            descriptor(view['neural'], prefix + 'neural.h5')
            if split == 'test':
                descriptor(view['neural_shift10'], prefix + 'neural_shift10.h5')
            counts[split] = len(ids)
            total[split + '_cases'] += len(ids)
        summary = row['disposition_summary']
        keys(summary, {'movements', 'included', 'excluded', 'reasons'}, 'Complete disposition closure')
        need(all(integer(summary[k]) for k in ('movements', 'included', 'excluded')) and
             summary['included'] == sum(counts.values()) and
             summary['movements'] == summary['included'] + summary['excluded'], 'All source movements disposed')
        need(type(summary['reasons']) is dict and set(summary['reasons']) <= REASONS and
             all(integer(v, 1) for v in summary['reasons'].values()) and
             sum(summary['reasons'].values()) == summary['excluded'], 'Exclusion reasons exactly account')
        keys(row['overlap'], SPLITS, 'All split overlap summaries')
        need(all(integer(row['overlap'][s]) and row['overlap'][s] <= counts[s] * (counts[s] - 1) // 2
                 for s in SPLITS), 'Bounded overlapping context pair counts')
        for key in ('movements', 'included', 'excluded'):
            total[key] += summary[key]
        total['uncompressed_count_bytes'] += 200 * row['unit_count'] * (sum(counts.values()) + counts['test'])
    return total


def admit_projection(value, sources):
    need(hashlib.sha256(encode(sources)).hexdigest() == SOURCE_CANONICAL_SHA256,
         'Previously authenticated exact source roster, not a cardinality substitute')
    keys(value, {'schema', 'task_id', 'source_manifest', 'producer_sources', 'query', 'sessions',
                 'dispositions', 'protected_gold', 'totals', 'shift'}, 'Exact label-free projection schema')
    need(value['schema'] == 'neural060_projection_v2' and value['task_id'] == 'NEURAL-060', 'Projection identity')
    admit_pin(value['source_manifest'])
    need(value['source_manifest'] == SOURCE_PIN, 'Exact original roster binding')
    keys(value['producer_sources'], {'prepare.py', 'native.py', 'projection.py'}, 'Complete preparation source closure')
    for body in value['producer_sources'].values():
        admit_pin(body)
    need(type(value['shift']) is dict and encode(value['shift']) == encode(SHIFT), 'Exact test-only10-bin replay')
    descriptor(value['query'], 'public/QUERY_INDEX.json')
    descriptor(value['dispositions'], 'operator/DISPOSITIONS.json')
    descriptor(value['protected_gold'], 'private/gold.json')
    totals = _sessions(value, sources)
    expected = dict(sessions=29, mice=13, labs=7, source_bytes=49113902269, **totals)
    keys(value['totals'], expected, 'Complete full-cohort totals')
    need(all(type(value['totals'][k]) is int and value['totals'][k] == v for k, v in expected.items()),
         'Derived full support and byte component totals')
    return value


def admit_query(value, projection):
    keys(value, {'schema', 'cases', 'sessions'}, 'Exact query index')
    expected = [{'case_id': c, 'session_id': row['session_id']} for row in projection['sessions']
                for c in row['splits']['test']['case_ids']]
    need(value['schema'] == 'neural060_query_v2' and value['sessions'] == [r['session_id'] for r in projection['sessions']],
         'All ordered original sessions')
    need(type(value['cases']) is list and encode(value['cases']) == encode(expected), 'All ordered query cases')
    return value


def public_file_map(projection):
    result = {projection['query']['path']: projection['query']}
    for row in projection['sessions']:
        for split in SPLITS:
            for key, desc in row['splits'][split].items():
                if key != 'case_ids':
                    need(desc['path'] not in result, 'Duplicate projected output path')
                    result[desc['path']] = desc
    return result
