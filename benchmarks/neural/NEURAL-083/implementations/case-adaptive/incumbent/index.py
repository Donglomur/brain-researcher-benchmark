"""Future trusted preparation adapter; never opens a key or a neural file.

The operator supplies all original validated record documents and the already
authorized identity key in memory. This function does not attest to their
authenticity. Source/array/clock support must be independently admitted later.
"""
import hashlib


def make_index(records, secret, projection_provenance):
    c.need(type(secret) is bytes and len(secret) == 32, 'Original private identity-key shape')
    c.need(type(records) is list and len(records) == 108, 'All original108 records')
    contracts.content_pin(projection_provenance)
    for ordinal, row in enumerate(records):
        fields = {'schema', 'person', 'session', 'source_pin', 'schema_binding_pin', 'epochs',
                  'offline_labels', 'online_labels', 'offline_onsets', 'online_onsets', 'array_shape'}
        c.need(type(row) is dict and set(row) == fields and row['schema'] == 'neural083_record_v1' and
               type(row['person']) is int and type(row['session']) is int and
               (row['person'], row['session']) == (ordinal // 2 + 1, ordinal % 2 + 1) and
               row['array_shape'] == [200, 251, 20], 'Exact original record shape and order')
        for key in ('source_pin', 'schema_binding_pin', 'epochs'):
            contracts.content_pin(row[key])
        for phase in ('offline', 'online'):
            labels = row[phase + '_labels']
            c.need(type(labels) is list and len(labels) == 100 and
                   all(type(v) is int and v in (0, 1) for v in labels) and
                   labels.count(0) == labels.count(1) == 50, 'Original full phase labels')
            scientific.indices(row[phase + '_onsets'])
    # c.encoded uses the same ASCII JSON canonicalization as original io.canonical.
    generation = hashlib.sha256(secret + c.encoded(records)).hexdigest()
    output = []
    for row in records:
        person, session = row['person'], row['session']
        output.append(dict(person=person, session=session,
             person_id=scientific.token(secret, 'person', person),
             case=scientific.token(secret, 'case', f'{person}:{session}'),
             source_pin=row['source_pin'], schema_binding_pin=row['schema_binding_pin'],
             epochs=dict(path=f'person{person:02d}_session{session}/epochs.npy', **row['epochs']),
             offline_ids=[scientific.token(secret, 'training', f'{person}:{session}:{i}') for i in range(100)],
             query_ids=[scientific.token(secret, 'trial', f'{person}:{session}:{i}') for i in range(100)],
             offline_labels=row['offline_labels'], offline_onsets=row['offline_onsets'],
             online_onsets=row['online_onsets']))
    result = dict(schema='neural083_canonical_store_v1', generation=generation, records=output,
                  projection_provenance=projection_provenance)
    contracts.canonical(result)
    return result
