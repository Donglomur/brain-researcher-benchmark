"""Pure metadata validation for the prospective NEURAL094 native export.

No files, arrays, numerical libraries, native calls or execution authority here.
Binary/public-boundary qualification remains a separate future worker check.
"""
import re

ARMS = ('context_wheel', 'context_wheel_neural')
PHASES = ('fitval', 'query')
PUBLIC_PACKET_CAP = 128 * 1024 * 1024
PRIVATE_METADATA_CAP = 4 * 1024 * 1024
PUBLIC_MANIFEST_KEYS = frozenset(('schema', 'candidate_id', 'arm', 'phase',
    'session_token', 'case_tokens', 'case_splits', 'unit_count',
    'wheel_observations_present', 'neural_observations_present', 'query_labels_present', 'observation', 'files'))
OBSERVATION = {'window_seconds': [0.0, 0.1],
    'bin_edges_seconds': [0.0, 0.02, 0.04, 0.06, 0.08, 0.1],
    'interval': 'left_closed_right_open',
    'time_encoding': 'authoritative_bin_id_and_within_bin_seconds',
    'wheel_units': 'encoder_ticks_relative_to_first_observed_trial_sample'}
COMMON_FILES = {'context.npz': 'stimulus_history_context', 'wheel.npz': 'wheel_samples'}


def need(condition, label):
    if not condition:
        raise ValueError(label)


def digest(value):
    return type(value) is str and re.fullmatch('[a-f0-9]{64}', value) is not None


def roles(arm, phase):
    need(arm in ARMS and phase in PHASES, 'Exactly two arms and two phases')
    result = dict(COMMON_FILES)
    if arm == ARMS[1]:
        result['neural.npz'] = 'neural_events'
        result['units.npz'] = 'units'
    if phase == 'fitval':
        result['labels.npz'] = 'labels'
    return result


def validate_manifest(value):
    need(type(value) is dict and set(value) == PUBLIC_MANIFEST_KEYS,
         'Exact public metadata; no private identity/target fields')
    need(value['schema'] == 'neural094-candidate-public-packet-v1'
         and value['candidate_id'] == 'NEURAL-094', 'Exact packet identity')
    arm, phase = value['arm'], value['phase']
    expected = roles(arm, phase)
    need(digest(value['session_token']), 'Opaque session token')
    tokens, splits = value['case_tokens'], value['case_splits']
    need(type(tokens) is list and 10 <= len(tokens) <= 10000
         and all(digest(t) for t in tokens) and len(set(tokens)) == len(tokens),
         'Bounded unique opaque case tokens')
    need(type(splits) is list and len(splits) == len(tokens), 'One split per case')
    if phase == 'query':
        need(splits == ['query'] * len(tokens), 'Query phase contains query rows only')
    else:
        fit = splits.count('fit')
        validation = splits.count('validation')
        need(fit >= 40 and validation >= 10 and fit + validation == len(tokens)
             and splits == ['fit'] * fit + ['validation'] * validation,
             'Original chronological fitting/validation blocks')
    need(type(value['unit_count']) is int and 0 <= value['unit_count'] <= 10000,
         'Complete bounded QC unit inventory, including zero-event units')
    need((arm==ARMS[1] or value['unit_count']==0), 'Context-only packet exposes no neural inventory')
    need(value['wheel_observations_present'] is True
         and value['neural_observations_present'] is (arm == ARMS[1])
         and value['query_labels_present'] is False
         and value['observation'] == OBSERVATION, 'Exact observation and modality boundary')
    need(type(value['files']) is dict and set(value['files']) == set(expected),
         'Exact arm/phase file allowlist')
    for name, role in expected.items():
        entry = value['files'][name]
        need(type(entry) is dict and set(entry) == {'bytes', 'sha256', 'role'}
             and type(entry['bytes']) is int and 0 < entry['bytes'] <= PUBLIC_PACKET_CAP
             and digest(entry['sha256']) and entry['role'] == role,
             'Exact ordinary basename descriptor and permitted role')
    return True


def validate_panel(manifests, manifest_bytes):
    """Check all four public JSON objects, including declared retained bytes.

    Callers must additionally pin/read ordinary files and enforce isolation;
    this pure function cannot prove filesystem custody or binary contents.
    """
    need(type(manifests) is dict and set(manifests) == set(ARMS)
         and type(manifest_bytes) is dict and set(manifest_bytes) == set(ARMS),
         'Complete two-arm manifest panel')
    total = 0
    for arm in ARMS:
        need(set(manifests[arm]) == set(PHASES)
             and set(manifest_bytes[arm]) == set(PHASES), 'Both phases retained')
        for phase in PHASES:
            value = manifests[arm][phase]
            validate_manifest(value)
            need(value['arm'] == arm and value['phase'] == phase, 'Panel key identity')
            length = manifest_bytes[arm][phase]
            need(type(length) is int and 0 < length <= PRIVATE_METADATA_CAP,
                 'Bounded actual encoded manifest size')
            total += length + sum(f['bytes'] for f in value['files'].values())
    for phase in PHASES:
        a, b = (manifests[arm][phase] for arm in ARMS)
        need(all(a[k] == b[k] for k in ('session_token', 'case_tokens', 'case_splits',
                                      'observation')),
             'Matched paired source cases, split and observation; physically distinct neural access')
        for name in roles(ARMS[0], phase):
            need(a['files'][name] == b['files'][name],
                 'Byte-identical common modality data across isolated arms')
    fit, query = manifests[ARMS[0]]['fitval'], manifests[ARMS[0]]['query']
    need(fit['session_token'] == query['session_token']
         and fit['unit_count'] == query['unit_count']
         and len(fit['case_tokens']) + len(query['case_tokens']) <= 10000
         and set(fit['case_tokens']).isdisjoint(query['case_tokens']),
         'Disjoint bounded phases of one session')
    joint_fit,joint_query=(manifests[ARMS[1]][phase] for phase in PHASES)
    need(joint_fit['unit_count']==joint_query['unit_count']
         and joint_fit['files']['units.npz']==joint_query['files']['units.npz'],
         'One complete QC unit inventory across the neural arm phases')
    need(total <= PUBLIC_PACKET_CAP, 'Complete128MiB public cap; no partial subset')
    return {'declared_public_bytes': total, 'public_packet_cap_bytes': PUBLIC_PACKET_CAP,
            'four_manifests_validated': True, 'filesystem_or_binary_checks_performed': False}
