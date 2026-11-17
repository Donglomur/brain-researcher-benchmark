"""Prospective four-arm metadata projection; no files, arrays, fits or targets.

The trusted operator supplies authenticated original public manifest bytes.
The result contains operator-only support and two additional public controls.
It is not a process/isolation/custody attestation or execution authority.
"""
import copy
import hashlib
import json
import math
import parent_validation as parent

TASK = 'NEURAL-093'
BINDING_PIN = {'bytes': 61814, 'sha256': 'e9eeb6faea33f28a65fc27ba0d21ea57a72cf3759eb9796587563acccef1f001'}
ORIGINAL_ARMS = parent.ARMS
CONTROL_ARMS = ('context', 'wheel_plus_context')
ARMS = ('context', 'neural_plus_context', 'wheel_plus_context', 'neural_wheel_plus_context')
PHASES = ('fitval', 'query')
CONTROL_KEYS = (parent.PUBLIC_MANIFEST_KEYS - {'unit_count'}) | {'neural_observations_present'}
CONTROL_SCHEMA = 'neural093-prospective-nonneural-control-packet-v1'
MAX_MANIFEST = 1_048_576
MAX_PANEL_METADATA = 8_000_000


def need(value, message):
    if not value:
        raise ValueError(message)


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)+'\n').encode()


def pin(raw):
    need(type(raw) is bytes, 'exact bytes')
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def parse(raw, cap):
    need(type(raw) is bytes and 0 < len(raw) <= cap, 'bounded JSON bytes')
    def pairs(items):
        out = {}
        for k, v in items:
            need(k not in out, 'duplicate metadata key'); out[k] = v
        return out
    return json.loads(raw, object_pairs_hook=pairs,
        parse_constant=lambda _: need(False, 'nonfinite JSON'))


def load_binding(raw):
    need(type(raw) is bytes and len(raw) == BINDING_PIN['bytes'] <= 100_000,
         'exact bounded binding extent before hashing')
    need(pin(raw) == BINDING_PIN, 'exact selected full39 source binding')
    value = parse(raw, 100_000)
    _binding(value)
    return value


def _binding(value):
    need(value['schema'] == 'neural093_prospective_control_binding_v1' and value['task_id'] == TASK,
         'correct prospective binding')
    roster = value['roster']
    need(type(roster) is list and len(roster) == 39 and [x['ordinal'] for x in roster] == list(range(1, 40))
         and len({x['session'] for x in roster}) == 39 and len({x['mouse'] for x in roster}) == 10,
         'all39 original sessions and ten mice')
    need(value['required_queries'] == sum(x['counts']['query'] for x in roster) == 2042,
         'all2042 original query cases')
    for row in roster:
        need(set(row['counts']) == set(PHASES)
             and all(type(n) is int and n > 0 for n in row['counts'].values()), 'declared phase support')
        need(set(row['original_manifests']) == set(ORIGINAL_ARMS), 'both original arms')
        for arm in ORIGINAL_ARMS:
            need(set(row['original_manifests'][arm]) == set(PHASES), 'both original phases')
    return roster


def roles(arm, phase):
    need(arm in CONTROL_ARMS and phase in PHASES, 'additional nonneural arm/phase')
    result = {'context.npz': 'context'}
    if arm == 'wheel_plus_context': result['wheel.npz'] = 'wheel_samples'
    if phase == 'fitval': result['labels.npz'] = 'labels'
    return result


def validate_control(value):
    need(type(value) is dict and set(value) == CONTROL_KEYS, 'exact nonneural metadata; no unit count or provenance leak')
    need(value['schema'] == CONTROL_SCHEMA and value['candidate_id'] == TASK,
         'prospective control identity')
    arm, phase = value['arm'], value['phase']; expected = roles(arm, phase)
    need(parent.digest(value['session_token']), 'opaque session token')
    tokens, splits = value['case_tokens'], value['case_splits']
    need(type(tokens) is list and 10 <= len(tokens) <= 10000
         and all(parent.digest(x) for x in tokens) and len(set(tokens)) == len(tokens), 'unique opaque case roster')
    need(type(splits) is list and len(splits) == len(tokens), 'one split per case')
    if phase == 'query': need(splits == ['query']*len(tokens), 'hidden-label query phase')
    else:
        f, v = splits.count('fit'), splits.count('validation')
        need(f >= 40 and v >= 10 and f+v == len(tokens) and splits == ['fit']*f+['validation']*v,
             'unaltered chronological fit/validation order')
    need(value['neural_observations_present'] is False and value['query_labels_present'] is False
         and value['wheel_observations_present'] is (arm == 'wheel_plus_context')
         and value['observation'] == parent.OBSERVATION, 'exact constant observation/modality declarations')
    need(type(value['files']) is dict and set(value['files']) == set(expected), 'exact nuisance-only file allowlist')
    for name, role in expected.items():
        d = value['files'][name]
        need(type(d) is dict and set(d) == {'bytes', 'sha256', 'role'}
             and type(d['bytes']) is int and 0 < d['bytes'] <= parent.PUBLIC_PACKET_CAP
             and parent.digest(d['sha256']) and d['role'] == role, 'exact permitted descriptor')
    return True


def _control(original, arm):
    # A whitelist, never a recursive copy/redaction of unknown source metadata.
    result = {key: copy.deepcopy(original[key]) for key in
        ('candidate_id', 'phase', 'session_token', 'case_tokens', 'case_splits',
         'query_labels_present', 'observation')}
    result.update(schema=CONTROL_SCHEMA, arm=arm, neural_observations_present=False,
                  wheel_observations_present=(arm == 'wheel_plus_context'),
                  files={name: copy.deepcopy(original['files'][name]) for name in roles(arm, original['phase'])})
    validate_control(result)
    return result


def prepare_panel(original_raw, binding_raw):
    """Authenticate the whole original panel, then derive two metadata controls.

    No filesystem copy is performed. Public control consumers receive only one
    returned arm/phase manifest and its exact allowlisted file bytes; they must
    never receive this operator-only whole-panel return object or BINDING.
    """
    return _prepare_panel(original_raw, load_binding(binding_raw))


def _prepare_panel(original_raw, binding):
    roster = _binding(binding)
    need(type(original_raw) is dict and set(original_raw) == set(range(1, 40)), 'all39 source sessions, no subset')
    total = 0
    # Authenticate every original manifest before parsing or emitting controls.
    for row in roster:
        supplied = original_raw[row['ordinal']]
        need(type(supplied) is dict and set(supplied) == set(ORIGINAL_ARMS), 'exact original paired arms')
        for arm in ORIGINAL_ARMS:
            need(type(supplied[arm]) is dict and set(supplied[arm]) == set(PHASES), 'both original phases')
            for phase in PHASES:
                raw = supplied[arm][phase]; expected = row['original_manifests'][arm][phase]
                need(type(raw) is bytes and 0 < len(raw) <= MAX_MANIFEST, 'bounded original manifest')
                total += len(raw); need(total <= MAX_PANEL_METADATA, 'whole metadata cap without omission')
                need(pin(raw) == {k: expected[k] for k in ('bytes', 'sha256')}, 'exact original public manifest pin')
    sessions = []; seen = set()
    for row in roster:
        supplied = original_raw[row['ordinal']]
        originals = {arm: {phase: parse(supplied[arm][phase], MAX_MANIFEST) for phase in PHASES} for arm in ORIGINAL_ARMS}
        parent.validate_panel(originals, {arm: {phase: len(supplied[arm][phase]) for phase in PHASES} for arm in ORIGINAL_ARMS})
        session_token = originals[ORIGINAL_ARMS[0]]['query']['session_token']
        need(session_token not in seen, 'distinct opaque session identities'); seen.add(session_token)
        for arm in ORIGINAL_ARMS:
            for phase in PHASES:
                need(len(originals[arm][phase]['case_tokens']) == row['counts'][phase], 'exact bound case count')
        controls = {arm: {phase: _control(originals['neural_wheel_plus_context'][phase], arm) for phase in PHASES}
                    for arm in CONTROL_ARMS}
        sessions.append(dict(ordinal=row['ordinal'], session=row['session'], mouse=row['mouse'],
            session_token=session_token, query_tokens=list(originals[ORIGINAL_ARMS[0]]['query']['case_tokens']),
            original_manifests=originals, original_manifest_bytes=supplied, controls=controls,
            control_manifest_bytes={arm: {phase: encoded(controls[arm][phase]) for phase in PHASES} for arm in CONTROL_ARMS}))
    return dict(schema='neural093_operator_only_four_arm_panel_v1', sessions=sessions,
        required_sessions=39, required_mice=10, required_queries=2042, prediction_tables=156,
        original_78_output_endpoint_modified=False, binary_contents_validated=False,
        files_copied=False, isolation_or_execution_attested=False)
