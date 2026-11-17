"""Full NEURAL083 metadata and artifact contracts; no scientific execution."""
import math
import re

SETTINGS = ('target20', 'transfer0', 'target100', 'other_session20')
ARMS = ('EEG', 'CONTEXT', 'PERMUTED_EEG')
PANELS = ('candidate', 'reference')


def need(value, message):
    if not value:
        raise ValueError(message)


def exact(value, fields):
    need(type(value) is dict and set(value) == set(fields), 'Exact metadata fields')


def token(value, prefix):
    need(type(value) is str and re.fullmatch(prefix + r'_[0-9a-f]{24}', value), 'Opaque identity')


def content_pin(value):
    exact(value, ('bytes', 'sha256'))
    need(type(value['bytes']) is int and 0 < value['bytes'] <= 100000000000, 'Positive bounded extent')
    need(type(value['sha256']) is str and re.fullmatch('[0-9a-f]{64}', value['sha256']), 'SHA256 identity')
    return value


def canonical(value):
    """Require the complete operator-only index, excluding online truth."""
    exact(value, ('schema', 'generation', 'records', 'projection_provenance'))
    need(value['schema'] == 'neural083_canonical_store_v1', 'Canonical schema')
    need(type(value['generation']) is str and re.fullmatch('[0-9a-f]{64}', value['generation']), 'Generation')
    content_pin(value['projection_provenance'])
    need(type(value['records']) is list and len(value['records']) == 108, 'All 108 source records')
    ids = set()
    source_ids = set()
    people = {}
    files = set()
    cases = []
    for ordinal, row in enumerate(value['records']):
        exact(row, ('person', 'session', 'person_id', 'case', 'source_pin', 'schema_binding_pin',
                    'epochs', 'offline_ids', 'query_ids', 'offline_labels', 'offline_onsets', 'online_onsets'))
        person, session = ordinal // 2 + 1, ordinal % 2 + 1
        need(type(row['person']) is int and type(row['session']) is int and
             (row['person'], row['session']) == (person, session), 'Complete numeric source order')
        token(row['person_id'], 'person')
        token(row['case'], 'case')
        need(people.setdefault(person, row['person_id']) == row['person_id'], 'Same opaque person across sessions')
        for key in ('source_pin', 'schema_binding_pin'):
            content_pin(row[key])
        need(row['source_pin']['sha256'] not in source_ids, 'Distinct original objects')
        source_ids.add(row['source_pin']['sha256'])
        exact(row['epochs'], ('path', 'bytes', 'sha256'))
        content_pin({key: row['epochs'][key] for key in ('bytes', 'sha256')})
        path = row['epochs']['path']
        need(type(path) is str and re.fullmatch(r'[A-Za-z0-9_-]+/epochs\.npy', path) and path not in files,
             'Distinct relative epoch member')
        files.add(path)
        for key in ('offline_ids', 'query_ids'):
            need(type(row[key]) is list and len(row[key]) == 100, 'All chronological trial identities')
            for identity in row[key]:
                token(identity, 'training' if key == 'offline_ids' else 'trial')
                need(identity not in ids, 'Globally distinct trial identities')
                ids.add(identity)
        labels = row['offline_labels']
        need(type(labels) is list and len(labels) == 100 and
             all(type(v) is int and v in (0, 1) for v in labels) and labels.count(0) == labels.count(1) == 50,
             'Exact offline binary support')
        for key in ('offline_onsets', 'online_onsets'):
            seq = row[key]
            need(type(seq) is list and len(seq) == 100 and
                 all(type(v) is int and v > 0 for v in seq) and
                 all(a < b for a, b in zip(seq, seq[1:])), 'Chronological native source onsets')
        cases.append(dict(case=row['case'], person=row['person_id'], session=session, query=sorted(row['query_ids'])))
    need(len(set(people.values())) == 54 and len({r['case'] for r in cases}) == 108, 'Full biological identity support')
    return dict(schema='neural083_panel_v1', generation=value['generation'], settings=list(SETTINGS),
                arms=list(ARMS), cases=cases)


def schedule(panel):
    """One schedule; versions and access conditions never create task IDs."""
    need(len(panel['cases']) == 108, 'Full panel schedule')
    ordinal = 0
    for name in PANELS:
        for case in panel['cases']:
            for setting in SETTINGS:
                for arm in ARMS:
                    yield dict(panel=name, case=case['case'], setting=setting, arm=arm, ordinal=ordinal)
                    ordinal += 1
    need(ordinal == 2592, 'Both complete panels')


def prediction(value, metadata):
    need(type(value) is dict and value.get('status') in ('complete', 'abstain'), 'Explicit outcome status')
    exact(value, ('schema', 'generation', 'case', 'setting', 'arm', 'status',
                  'predictions' if value['status'] == 'complete' else 'reason'))
    need(value['schema'] == 'neural083_case_prediction_v1', 'Original result schema')
    for key in ('generation', 'case', 'setting', 'arm'):
        need(value[key] == metadata[key], 'Exact condition identity')
    if value['status'] == 'abstain':
        need(type(value['reason']) is str and 0 < len(value['reason']) <= 256, 'Bounded abstention')
        return value
    rows = value['predictions']
    need(type(rows) is list and len(rows) == 100, 'Every original query')
    for identity, row in zip(metadata['query'], rows):
        exact(row, ('trial', 'p_right'))
        probability = row['p_right']
        need(row['trial'] == identity and type(probability) in (int, float) and
             math.isfinite(probability) and 0 <= probability <= 1, 'Ordered finite probability')
    return value


def numerical_work():
    training = (10620 + 10600 + 10700 + 10620) * (2 * 251 * 20 * 4 + 5 * 4)
    query = 4 * 100 * (2 * 251 * 20 * 4 + 5 * 4)
    # These are explicit conservative allocation components from the output
    # contracts, not measured allocation/RSS. Actual admission still counts
    # filesystem allocation, names, directories, failed work and all I/O.
    native_receipt_cap = 5184 * 262144
    ordinary_condition_metadata = 2592 * 7 * 8192
    predictions = 2592 * 100000
    phase_intents = 5184 * 3 * 8192
    retained_upper_components = (native_receipt_cap + ordinary_condition_metadata + predictions + phase_intents +
                                 214856000 + 536870912 + 67108864)
    return dict(native_phases=5184, condition_results=2592, prediction_values=259200,
                canonical_numeric_bytes=433728000, training_numeric_copy_bytes=2 * 108 * training,
                query_numeric_copy_bytes=2 * 108 * query, max_training_numeric_bytes=214856000,
                max_model_bytes=536870912, all_model_capture_max_bytes=1391569403904,
                native_receipt_cap_bytes=native_receipt_cap, condition_metadata_cap_bytes=ordinary_condition_metadata,
                prediction_cap_bytes=predictions, phase_intent_cap_bytes=phase_intents,
                retained_upper_components_bytes=retained_upper_components,
                native_reply_reservation_bytes=2592 * (1000000000 + 16000000))
