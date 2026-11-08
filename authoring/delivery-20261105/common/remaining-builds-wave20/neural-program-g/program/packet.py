"""Full-cohort metadata admission and exact physical per-channel view planning.

No original data is opened on import. Candidate views are derived here from the
complete operator index, never accepted as candidate-labelled train/test lists.
"""
from pathlib import Path
import hashlib
import re
from .common import capture, decode, descriptor, need, npy_header, stream_pin, VIEWS


def digest(text):
    return hashlib.sha256(text.encode('ascii')).hexdigest()


def derive_folds(people):
    need(len(people) == 78 and len(set(people)) == 78 and all(type(x) is int for x in people), 'Exact original78 people')
    rank = sorted(people, key=lambda x: (digest(f'NEURAL007-full153-v1|outer|{x}'), x))
    result = []
    for ordinal in range(1, 7):
        query = rank[(ordinal - 1) * 13:ordinal * 13]
        remaining = sorted(set(people) - set(query))
        validation = sorted(remaining, key=lambda x: (digest(f'NEURAL007-full153-v1|inner|{ordinal}|{x}'), x))[:13]
        result.append({'fold': ordinal, 'query_people': query, 'validation_people': validation,
                       'fit_people': [x for x in remaining if x not in validation],
                       'final_training_people': remaining})
    return result


def roster(roster_body, folds_body):
    r, f = decode(roster_body), decode(folds_body)
    need(r['schema'] == 'neural007_full153_original_roster_v1' and r['candidate_mount_allowed'] is False, 'Operator original roster')
    rows = r['nights_rows']
    need(type(rows) is list and len(rows) == 153, 'All153 original nights')
    keys = [(x['official_subject'], x['official_night']) for x in rows]
    need(len(set(keys)) == 153 and all(type(a) is int and type(b) is int and b in (1, 2) for a, b in keys), 'Exact unique source-person/night keys')
    people = sorted({a for a, _ in keys}); need(len(people) == 78, 'All78 source people')
    names = []
    for row in rows:
        assets = row['source_assets']; need(len(assets) == 2 and {x['kind'] for x in assets} == {'PSG', 'Hypnogram'}, 'Original paired objects')
        for a in assets:
            need(re.fullmatch(r'SC[0-9]{4}[A-Z][0-9A-Z]-(PSG|Hypnogram)\.edf', a['filename']), 'Exact publisher filename syntax')
            need(a['source_path'] == 'sleep-cassette/' + a['filename'] and re.fullmatch('[0-9a-f]{64}', a['publisher_sha256']), 'Source path/hash')
            names.append(a['filename'])
    need(len(set(names)) == 306, 'All306 distinct original objects')
    derived = derive_folds(people)
    need(f['schema'] == 'neural007_full153_folds_v1' and len(f['folds']) == 6, 'Frozen six outer folds')
    for got, want in zip(f['folds'], derived):
        need(all(got[k] == v for k, v in want.items()), 'Exact outcome-independent fold/inner allocation')
        expected = [{'official_subject': a, 'official_night': b} for a, b in keys if a in want['query_people']]
        need(got['query_nights'] == expected and got['query_night_count'] == len(expected), 'All grouped query nights')
    return rows, derived


def artifact(row):
    need(type(row) is dict and set(row) == {'path', 'bytes', 'sha256'}, 'Exact operator artifact locator')
    descriptor({k: row[k] for k in ('bytes', 'sha256')})
    p = Path(row['path']); need(p.is_absolute(), 'Absolute operator locator')
    return p


def admit_index(value, source_rows, expected_roster_pin, authenticate=False, meter=None):
    need(type(value) is dict and set(value) == {'schema', 'roster', 'originals', 'nights', 'preparation_source', 'preparation_receipt'}, 'Exact full-input envelope')
    need(value['schema'] == 'neural007_full153_input_v1' and value['roster'] == expected_roster_pin, 'Bound original full scope')
    descriptor(value['preparation_source']); descriptor(value['preparation_receipt'])
    expected_objects = {a['filename']: a for r in source_rows for a in r['source_assets']}
    originals = value['originals']; need(type(originals) is list and len(originals) == 306, 'All original payload descriptors')
    seen = set()
    for row in originals:
        need(type(row) is dict and set(row) == {'filename', 'path', 'bytes', 'sha256'}, 'Original object descriptor')
        name = row['filename']; need(name in expected_objects and name not in seen, 'Exact original identity set'); seen.add(name)
        need(row['sha256'] == expected_objects[name]['publisher_sha256'] and row['bytes'] > 0, 'Publisher body identity, not metadata-only placeholder')
        a = {k: row[k] for k in ('path', 'bytes', 'sha256')}; artifact(a)
        if authenticate:
            stream_pin(a['path'], {k: a[k] for k in ('bytes', 'sha256')}, meter)
    expected = {(x['official_subject'], x['official_night']) for x in source_rows}
    need(type(value['nights']) is list and len(value['nights']) == 153, 'Full prepared153-night index')
    rows, opaque, paths = {}, set(), set()
    for r in value['nights']:
        need(type(r) is dict and set(r) == {'official_subject', 'official_night', 'opaque_night', 'epochs', 'channels', 'clock', 'stages', 'mask', 'disposition'}, 'Exact prepared-night descriptor')
        need(type(r['official_subject']) is int and type(r['official_night']) is int, 'Exact nonboolean integer source keys')
        key = (r['official_subject'], r['official_night'])
        need(key in expected and key not in rows, 'No removed or duplicate night')
        need(type(r['opaque_night']) is str and re.fullmatch('[a-f0-9]{32}', r['opaque_night']) and r['opaque_night'] not in opaque, 'Unique opaque night')
        opaque.add(r['opaque_night']); need(type(r['epochs']) is int and r['epochs'] >= 2, 'Full known epoch count, not capped/cropped')
        need(type(r['channels']) is dict and set(r['channels']) == {'0', '1', '2'}, 'All three separate physical channels')
        members = [(r['channels'][str(c)], '<f8', [r['epochs'] * 3000]) for c in range(3)]
        members += [(r['clock'], '<f8', [r['epochs'], 4]), (r['stages'], '|i1', [r['epochs']]), (r['mask'], '|b1', [r['epochs']])]
        for a, dtype, shape in members:
            path = artifact(a); need(str(path) not in paths, 'No aliasing prepared artifacts across roles/nights'); paths.add(str(path))
            if authenticate:
                stream_pin(path, {k: a[k] for k in ('bytes', 'sha256')}, meter)
                header = npy_header(path, a['bytes'], meter)
                need(header['dtype'] == dtype and header['shape'] == shape, 'Exact per-night typed geometry')
        artifact(r['disposition'])
        if authenticate:
            capture(r['disposition']['path'], {k: r['disposition'][k] for k in ('bytes', 'sha256')}, meter=meter)
        rows[key] = r
    need(set(rows) == expected, 'Whole original prepared support')
    return rows


def view_plan(rows, fold, current_person, view, role, handles):
    """Pure mount plan. Only trusted staging materializes this exact plan."""
    need(view in VIEWS and role in ('probe', 'fit52', 'fit65', 'infer', 'validation'), 'Declared view/role')
    need(current_person in fold['query_people'], 'Current held person belongs to this outer fold')
    need(type(handles) is dict and set(handles) == {str(x) for x in fold['final_training_people'] + [current_person]}, 'Context-local full person binding')
    need(len(set(handles.values())) == 66 and all(re.fullmatch('[a-f0-9]{32}', x) for x in handles.values()), 'Distinct opaque person handles')
    allowed, labels = set(), set()
    if role == 'probe':
        allowed = set(fold['final_training_people']) | {current_person}; labels = set(fold['final_training_people'])
    elif role == 'fit52':
        allowed = labels = set(fold['fit_people'])
    elif role == 'fit65':
        allowed = labels = set(fold['final_training_people'])
    elif role == 'validation':
        allowed = set(fold['validation_people'])
    else:
        allowed = {current_person}
    members, nights, membership = [], [], []
    for (person, night), row in sorted(rows.items()):
        if person not in allowed:
            continue
        person_handle = handles[str(person)]
        # A night-local ordinal is not the source filename/acquisition ID.
        logical = 'nights/' + person_handle + '/night-' + str(night)
        packet = {'person': person_handle, 'night': 'night-' + str(night), 'epochs': row['epochs'], 'channels': list(VIEWS[view]), 'directory': logical,
                  'target_role': 'training' if person in labels else 'unlabeled',
                  'split_role': ('fit52' if person in fold['fit_people'] else 'validation13') if person in fold['final_training_people'] else 'current_query'}
        for c in VIEWS[view]:
            members.append({'target': logical + '/channel-' + str(c) + '.npy', 'artifact': row['channels'][str(c)], 'role': 'signal'})
        members.append({'target': logical + '/clock.npy', 'artifact': row['clock'], 'role': 'clock'})
        if person in labels:
            members += [{'target': logical + '/stages.npy', 'artifact': row['stages'], 'role': 'training_stage'},
                        {'target': logical + '/mask.npy', 'artifact': row['mask'], 'role': 'training_mask'}]
        nights.append(packet)
        membership.append({'directory':logical,'subject':person,'night':night,'epochs':row['epochs']})
    need(nights and len({(x['person'], x['night']) for x in nights}) == len(nights), 'Complete unique planned view')
    return {'schema': 'neural007_public_view_v1', 'view': view, 'role': role, 'current_person': handles[str(current_person)] if role in ('probe', 'infer') else None,
            'class_order': ['W', 'N1', 'N2', 'N3', 'R'], 'nights': nights, 'members': members,
            'source_membership':membership, 'presentation':None, 'operator_identity_fields_must_be_removed_before_publication': True}
