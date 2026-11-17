"""Complete selected-panel parameter transport, with no numerical private reads."""
import hashlib
import json
from pathlib import Path
import importlib.util
import numpy as np

_path = Path(__file__).resolve().parent / 'sources.py'
_spec = importlib.util.spec_from_file_location('_visual_alpha_spatial_sources', _path)
_source = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_source)
S = _source.load()
ROLES = ('full', 'train_first', 'train_second')
PANELS = ('reproduction_A', 'reproduction_B', 'corrected_A', 'corrected_B')
PROFILE = 'visual_alpha_trainonly_sourcegrid_varpro_scipy1171_v1'


def need(ok, message):
    if not ok:
        raise ValueError(message)


def encode(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()


def pin(raw):
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def full_roster(persons):
    """Preserve released native ordering, 433 electrodes and 3,464 cases."""
    need(type(persons) is list and len(persons) == 9, 'complete nine-person metadata')
    need([r.get('participant') for r in persons] == list(S.protocol.PARTICIPANTS), 'ordered participants')
    rows = []
    for person in persons:
        pid = person['participant']; ids = person.get('electrode_ids')
        need(type(ids) is list and len(ids) == S.protocol.RELEASED_COUNTS[pid]
             and all(type(x) is str and x for x in ids) and len(set(ids)) == len(ids),
             'complete ordered native electrode identities')
        for signal, model, sign in S.protocol.CONDITIONS:
            key = S.protocol.condition_key(signal, model, sign)
            for i, ident in enumerate(ids):
                rows.append({'case_id': pid + '__' + key + '__' + str(i).zfill(4),
                             'participant': pid, 'electrode_id': ident, 'signal': signal,
                             'model': model, 'allow_negative_gain': sign})
    need(len(rows) == 3464, 'complete 433 times eight case count')
    return rows


def context_rows(rows, person):
    S.interface.validate_roster(rows)
    persons = []
    for pid in S.protocol.PARTICIPANTS:
        ids = [r['electrode_id'] for r in rows if r['participant'] == pid
               and (r['signal'], r['model'], r['allow_negative_gain']) == S.protocol.CONDITIONS[0]]
        persons.append({'participant': pid, 'electrode_ids': ids})
    need(rows == full_roster(persons), 'exact complete native case ordering and condition bijection')
    need(person in S.protocol.PARTICIPANTS, 'declared participant')
    selected = [r for r in rows if r['participant'] == person]
    need(len(selected) == S.protocol.RELEASED_COUNTS[person] * 8, 'complete context case count')
    return selected


def indices(role):
    need(role in ROLES, 'fixed parameter role')
    return list(range(75)) if role == 'full' else list(range(38)) if role == 'train_first' else list(range(38, 75))


def source_responses(value, shape):
    """Preserve every source nonfinite value for the fixed finite-support mask."""
    need(type(value) is np.ndarray and value.dtype == np.dtype('float64')
         and value.shape == shape, 'exact role response shape; no hidden test half')
    return value


def admit_context(raw, rows, roster_sha256, person, role):
    need(type(raw) is bytes and 0 < len(raw) <= S.interface.MAX_BYTES, 'bounded exact context bytes')
    value = S.interface._parse(raw)
    need(type(value) is dict and set(value) == {'schema', 'roster_sha256', 'participant', 'role', 'cases'}, 'exact context fields')
    need(value['schema'] == 'visual_alpha_context_parameters_v1'
         and value['roster_sha256'] == roster_sha256 and S.interface._sha(roster_sha256)
         and value['participant'] == person and value['role'] == role and role in ROLES,
         'bound context identity')
    selected = context_rows(rows, person)
    need(type(value['cases']) is list and len(value['cases']) == len(selected), 'all context cases')
    by = {}
    expected = {r['case_id']: r for r in selected}
    for row in value['cases']:
        need(type(row) is dict and set(row) == {'case_id', 'parameters'}, 'exact parameter row')
        ident = row['case_id']
        need(type(ident) is str and ident in expected and ident not in by, 'context case bijection')
        by[ident] = S.interface._parameters(row['parameters'], expected[ident])
    return {'schema': value['schema'], 'roster_sha256': roster_sha256,
            'participant': person, 'role': role,
            'cases': [{'case_id': r['case_id'], 'parameters': by[r['case_id']]} for r in selected]}


def assemble_contexts(raw_by_context, rows, roster_sha256):
    expected = [(p, role) for p in S.protocol.PARTICIPANTS for role in ROLES]
    need(type(raw_by_context) is dict and set(raw_by_context) == set(expected), 'all 27 independent contexts')
    by = {}
    for person, role in expected:
        doc = admit_context(raw_by_context[(person, role)], rows, roster_sha256, person, role)
        for row in doc['cases']:
            by.setdefault(row['case_id'], {'case_id': row['case_id']})[role] = row['parameters']
    return S.interface.validate_submission({'schema': 'visual_alpha_parameters_v1',
        'roster_sha256': roster_sha256, 'cases': [by[r['case_id']] for r in rows]}, rows, roster_sha256)


def admit_panel(raw, rows, roster_sha256):
    need(type(raw) is bytes and 0 < len(raw) <= S.interface.MAX_BYTES, 'bounded full parameter bytes')
    context_rows(rows, S.protocol.PARTICIPANTS[0])
    return S.interface.validate_submission(S.interface._parse(raw), rows, roster_sha256)
