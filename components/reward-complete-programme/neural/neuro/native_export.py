"""Explicit operator NWB export interface, without discovery or implicit source access.

The reader is injected by a separately authorized data phase. Tests inject invented
in-memory objects. This module does not import pynwb or open original files itself.
"""
from .base import require, finite, digest
from .prepare import normalized_event, validate_corpus


def export_corpus(manifest, reader):
    require(manifest['schema'] == 'reward_neural_native_export_manifest_v1', 'native_manifest')
    require(manifest['source_access_authorized'] is True, 'native_access_not_authorized')
    require(manifest['shared_contract_sha256'] ==
            'cb50037867459c69ac4399f951c894fd3ea33fd3b10b3feb70885a6ccf7065c1',
            'native_shared_contract')
    animals, receipts = [], []
    for animal in manifest['animals']:
        sessions = []
        for item in animal['sessions']:
            # The operator supplies exact asset identity, prior byte verification and biological join.
            require(item['asset_id'] and len(item['sha256']) == 64 and
                    item['biological_join_verified'] is True, 'native_identity_gate')
            obj = reader(item['asset_id'], item['sha256'])
            require(obj['subject_id'] == item['expected_source_subject_id'], 'native_subject_mismatch')
            scale, offset = finite(item['timestamp_scale']), finite(item['clock_offset'])
            require(scale > 0, 'native_time_scale')
            times = [finite(t) * scale + offset for t in obj['photometry_times']]
            values = [finite(y) * finite(item['fluorescence_scale']) for y in obj['photometry_values']]
            events = []
            for e in obj['events']:
                if animal['condition'].startswith('FC-'):
                    require(e['kind'] in ('cue', 'shock_on', 'shock_off'), 'aversive_event_kind')
                    kind, delivered = e['kind'], True if e['kind'] == 'shock_on' else None
                else:
                    kind, delivered = normalized_event(e['code'], e['flag'], animal['condition'])
                events.append({'id': e['id'], 'trial_id': e['trial_id'], 'kind': kind,
                               'time': finite(e['time']) * scale + offset, 'delivered': delivered})
            sessions.append({'id': item['session_id'], 'day': item['day'],
                             'duration': finite(item['duration_seconds']), 'times': times,
                             'fluorescence': values, 'events': events,
                             'max_gap': finite(item['max_gap_seconds']), 'history': item['history']})
            receipts.append({'asset_id': item['asset_id'], 'source_sha256': item['sha256'],
                             'operator_member_digest': digest(obj),
                             'session_digest': digest(sessions[-1]),
                             'units_verified': item['units_verified'],
                             'raw_or_causal_pipeline_claim': False})
        animals.append({'id': animal['biological_id'], 'aliases': animal['aliases'],
                        'condition': animal['condition'], 'sex': animal['sex'],
                        'hardware': animal['hardware'], 'sessions': sessions})
    result = {'schema': 'reward_neural_operator_export_v1', 'synthetic': manifest['synthetic'],
              'corpus_id': manifest['corpus_id'], 'animals': animals,
              'support': manifest['support'], 'qualification': manifest['qualification'],
              'source_receipts': receipts, 'processing': 'released_retrospective_dff'}
    validate_corpus(result)
    return result
