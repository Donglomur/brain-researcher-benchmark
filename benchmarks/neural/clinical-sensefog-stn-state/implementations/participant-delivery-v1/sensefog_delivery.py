"""Operator-owned complete SenseFOG request/response bridge, not a sandbox."""
import hashlib
import json
from pathlib import Path
import re
import secrets
import types

ROOT = Path(__file__).resolve().parent.parent
SOURCE_PINS = {
    'signal-packets-v1/sensefog_packets.py': 'c51ade4d35d35d910d432475c6d141f703e2bc5fef21f1f4bff9de035c184eea',
    'primary-scoring-v1/sensefog_score.py': 'a1f9ed00292de575436a86860c3856646df22050f864b20f59e53296de99192c',
}


def _load(relative):
    path = ROOT / relative
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != SOURCE_PINS[relative]:
        raise ValueError('reviewed source dependency changed: ' + relative)
    module = types.ModuleType('_sensefog_' + path.stem)
    module.__file__ = str(path)
    exec(compile(raw, str(path), 'exec'), module.__dict__)
    return module


_packets = _load('signal-packets-v1/sensefog_packets.py')
_score = _load('primary-scoring-v1/sensefog_score.py')
TASK = _packets.TASK
canonical_bytes = _packets.canonical_bytes
canonical_sha256 = _packets.canonical_sha256
require, keys, integer = _packets.require, _packets.keys, _packets.integer


def _snapshot(value):
    return json.loads(canonical_bytes(value))


def prepare_delivery(grid, policy, signal_metadata, aliases, read_segment, *,
                     substrate, include_paired, max_cases, max_packet_values,
                     max_total_values, max_output_bytes):
    """Build every original request and optionally all map-supported lag requests.

    Keep the returned object private. Serve only individual public_requests
    entries, with separately matched training evidence and access enforcement.
    Freeze canonical_sha256(result) independently before candidate outcomes.
    """
    require(substrate in ('original_core', 'original_authorized_support'),
            'declare core-only or complete authorized-support substrate')
    require(type(include_paired) is bool, 'explicit paired diagnostic choice')
    require(not include_paired or substrate == 'original_authorized_support',
            'paired lags require the same complete-support original substrate')
    integer(max_output_bytes, 1, 'max_output_bytes')
    policy = _snapshot(policy)
    _score.validate_policy(policy)
    # The pinned projector validates and snapshots grid/metadata/aliases before reads.
    projection = _packets.project_packets(
        grid, signal_metadata, aliases, read_segment, max_cases=max_cases,
        max_packet_values=max_packet_values, max_total_values=max_total_values,
        max_output_bytes=max_output_bytes)
    requests, bindings, tokens = [], [], set()
    for row in projection['private_manifest']:
        original = row['role'] == substrate
        paired = (include_paired and row['role'] == 'lag_authorized_support'
                  and row['status'] == 'available')
        if not original and not paired:
            continue
        token = secrets.token_hex(16)
        require(token not in tokens, 'request token collision; no implicit retry')
        tokens.add(token)
        packet = (None if row['packet_sha256'] is None
                  else projection['packets'][row['packet_sha256']])
        request = {'schema': 'sensefog_probability_request_v1', 'request_token': token,
                   'class_order': list(policy['classes']),
                   'observation_status': row['status'], 'observation': packet}
        requests.append(request)
        bindings.append({'request_token': token, 'request_sha256': canonical_sha256(request),
                         'case_id': row['case_id'], 'participant': row['participant'],
                         'multiple': row['multiple'] if paired else None,
                         'kind': 'paired' if paired else 'original'})
    require(sum(r['kind'] == 'original' for r in bindings) == projection['original_case_count'],
            'complete original request census required')
    result = {'schema': 'sensefog_private_delivery_v1', 'task': TASK,
              'grid_sha256': projection['grid_sha256'], 'policy': policy,
              'policy_sha256': canonical_sha256(policy),
              'substrate': substrate, 'include_paired': include_paired,
              'source_pins': dict(SOURCE_PINS),
              'projection_sha256': canonical_sha256(projection),
              'original_case_count': projection['original_case_count'],
              'private_manifest': projection['private_manifest'],
              'response_bindings': bindings, 'public_requests': requests,
              'readiness': False}
    require(len(canonical_bytes(result)) <= max_output_bytes,
            'whole delivery output byte cap; no partial cohort')
    return result


def collect_responses(delivery, responses, *, expected_delivery_sha256, max_output_bytes):
    """Return the unchanged scorer's complete prediction documents or reject all.

    expected_delivery_sha256 must be the independently stored pre-outcome digest,
    never a digest computed from a candidate-supplied or modified delivery object.
    Missing/failing responses are not imputed, filtered or scored as a subset.
    """
    integer(max_output_bytes, 1, 'max_output_bytes')
    require(type(expected_delivery_sha256) is str and
            re.fullmatch('[0-9a-f]{64}', expected_delivery_sha256), 'frozen delivery hash')
    delivery = _snapshot(delivery)
    require(canonical_sha256(delivery) == expected_delivery_sha256,
            'frozen delivery changed; refuse identity/packet/policy reassignment')
    require(delivery['schema'] == 'sensefog_private_delivery_v1' and delivery['task'] == TASK,
            'delivery identity')
    classes, floor = _score.validate_policy(delivery['policy'])
    require(delivery['policy_sha256'] == canonical_sha256(delivery['policy']), 'policy binding')
    expected = {r['request_token']: r for r in delivery['response_bindings']}
    require(len(expected) == len(delivery['response_bindings']), 'duplicate private response binding')
    require(type(responses) is list and len(responses) == len(expected),
            'complete response census required; failed/missing condition remains unscored')
    found = {}
    for response in responses:
        keys(response, 'schema request_token request_sha256 probabilities', 'response')
        require(response['schema'] == 'sensefog_probability_response_v1', 'response identity')
        token = response['request_token']
        require(type(token) is str and token in expected and token not in found,
                'unknown/duplicate request token')
        require(response['request_sha256'] == expected[token]['request_sha256'],
                'response does not identify the frozen class order and observation')
        _score.probability_loss(response['probabilities'], None, len(classes), floor)
        found[token] = list(response['probabilities'])
    originals, paired = [], []
    for binding in delivery['response_bindings']:
        row = {'case_id': binding['case_id'], 'probabilities': found[binding['request_token']]}
        if binding['kind'] == 'paired':
            row['multiple'] = binding['multiple']
            paired.append(row)
        else:
            originals.append(row)
    common = {'task': TASK, 'grid_sha256': delivery['grid_sha256'],
              'policy_sha256': delivery['policy_sha256']}
    predictions = dict(common, schema='sensefog_predictions_v1', rows=originals)
    paired_predictions = (dict(common, schema='sensefog_paired_predictions_v1', rows=paired)
                          if delivery['include_paired'] else None)
    result = {'schema': 'sensefog_collected_responses_v1', 'task': TASK,
              'delivery_sha256': expected_delivery_sha256,
              'substrate': delivery['substrate'], 'predictions': predictions,
              'paired_predictions': paired_predictions, 'readiness': False}
    require(len(canonical_bytes(result)) <= max_output_bytes,
            'whole collected output byte cap; no partial predictions')
    return result
