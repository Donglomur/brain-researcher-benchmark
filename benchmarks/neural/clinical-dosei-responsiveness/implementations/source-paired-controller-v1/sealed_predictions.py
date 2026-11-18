"""Pure complete-cohort prediction sealing; no I/O or automatic scoring."""
from collections import Counter
import hashlib
import json
import math
import re

ARMS = ('viewer_only', 'code_enabled')
CASE_COUNT = 7345
RECORDING_COUNT = 171
CONDITION = 'native_marker_relative_30s_v1'
TERMINAL_POLICY_SHA256 = '82674ea847a74e7f4e3229f14cb7beac75a35d033d03451031c05a0695a4e4c3'
SCORING_POLICY_SHA256 = 'f3d8bc83cfd233fca3882b39a633354837216311a466a2b711056838ad170952'
SOURCE_PINS = {
    'terminal_mapping': 'c3b6933d70d3ef377c7c160ffec65363ef29af78016b2125296c9a268ac5e179',
    'transport': '69fd0c85374240bba63fc212304b4af9882c8afee0ff8b7d0fbeea3e5b6ef048',
    'scorer': 'e0c4be9ebbc10a88d9f49c0839a4a6b6c6471227d2a40fb31311948e22dbfada',
    'target_projection': '8cfb4f7af2792b8b688336e1d9146c8c2197fc83848d24c86ef6683276b51333',
}
CAPS = {'manifest': 2*1024**2, 'targets': 2*1024**2, 'budgets': 4*1024**2,
        'predictions': 8*1024**2, 'audit': 32*1024**2, 'receipt': 65536,
        'score_report': 4*1024**2}
BUDGET_REASONS = frozenset(('participant_wall_budget', 'participant_token_budget',
    'participant_tool_cpu_budget', 'participant_tool_memory_budget', 'participant_tool_call_budget'))
RESPONSE_REASONS = frozenset(('model_answer', 'voluntary_abstention', 'invalid_model_response'))
SNAPSHOT_FIELDS = {'schema', 'arm', 'binding', 'policy_sha256', 'budget_sha256', 'state',
    'reason', 'prediction', 'events', 'paired_run_must_be_invalidated',
    'evidence_custody_authenticated_by_this_mapper'}
SEAL_FIELDS = {'schema', 'prediction_bytes', 'audit_bytes', 'receipt_bytes', 'receipt_sha256'}


class SealingRefusal(ValueError):
    pass


def require(ok, message):
    if not ok:
        raise SealingRefusal(message)


def valid_sha(value):
    return type(value) is str and re.fullmatch('[0-9a-f]{64}', value) is not None


def canonical(value, cap):
    """Bound serialization incrementally; excess host audit capacity refuses."""
    result = bytearray()
    encoder = json.JSONEncoder(sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False)
    for piece in encoder.iterencode(value):
        raw = piece.encode('ascii')
        require(len(result)+len(raw) <= cap, 'canonical host artifact exceeds source capacity')
        result.extend(raw)
    return bytes(result)


def binding(raw):
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def object_binding(value, kind):
    return binding(canonical(value, CAPS[kind]))


def require_canonical_match(value, raw, kind):
    """Compare the canonical stream without materializing a second whole blob."""
    require(type(raw) is bytes and len(raw) <= CAPS[kind], 'bounded canonical bytes required')
    offset = 0
    encoder = json.JSONEncoder(sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False)
    for piece in encoder.iterencode(value):
        part = piece.encode('ascii')
        require(raw[offset:offset+len(part)] == part, 'sealed JSON is not exact canonical encoding')
        offset += len(part)
    require(offset == len(raw), 'sealed canonical stream extent differs')


def decode_canonical(raw, kind):
    require(type(raw) is bytes and len(raw) <= CAPS[kind], 'bounded immutable canonical bytes required')
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, 'duplicate key in sealed artifact')
            result[key] = value
        return result
    def finite(value):
        result = float(value)
        require(math.isfinite(result), 'nonfinite sealed value')
        return result
    def constant(value):
        raise SealingRefusal('nonfinite sealed constant')
    try:
        value = json.loads(raw.decode('ascii'), object_pairs_hook=pairs,
                           parse_float=finite, parse_constant=constant)
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise SealingRefusal('invalid sealed JSON') from exc
    require_canonical_match(value, raw, kind)
    return value


def admit_population(public_manifest, private_targets, transport):
    require(type(public_manifest) is list and len(public_manifest) == CASE_COUNT,
            'complete7345 public bindings required')
    expected = transport.admit_manifest(public_manifest)
    require(type(private_targets) is dict and set(private_targets) == {'schema', 'condition', 'cases'}
            and private_targets['schema'] == 'dosei_private_zero_shot_targets_v1'
            and private_targets['condition'] == CONDITION, 'exact private target envelope required')
    rows = private_targets['cases']
    require(type(rows) is list and len(rows) == CASE_COUNT, 'complete7345 private target slots required')
    found = set(); recordings = set()
    for row in rows:
        require(type(row) is dict and set(row) == {'case_id', 'recording_id', 'category'},
                'exact private target fields required')
        ident, rid, category = row['case_id'], row['recording_id'], row['category']
        require(type(ident) is str and ident in expected and ident not in found, 'unique matched target required')
        require(type(rid) is str and len(rid) <= 64 and re.fullmatch('[1-9][0-9]*', rid),
                'canonical positive source recording identifier required')
        require(category is None or type(category) is int and 1 <= category <= 5,
                'source category must remain nullable exact integer1..5')
        found.add(ident); recordings.add(rid)
    require(found == set(expected) and len(recordings) == RECORDING_COUNT,
            'complete matched targets and171 recording groups required')
    return expected


def admit_budgets(expected_budget_hashes, expected):
    require(type(expected_budget_hashes) is dict and set(expected_budget_hashes) == set(ARMS),
            'both complete prospective arm budgets required')
    copied = {}
    for arm in ARMS:
        values = expected_budget_hashes[arm]
        require(type(values) is dict and set(values) == set(expected), 'complete exact per-case budgets required')
        require(all(valid_sha(key) and valid_sha(value) for key, value in values.items()),
                'exact case and prospective budget hashes required')
        copied[arm] = dict(values)
    return copied


def admit_snapshot(value, arm, expected, budgets):
    require(type(value) is dict and set(value) == SNAPSHOT_FIELDS, 'exact terminal snapshot fields required')
    require(value['schema'] == 'dosei_host_case_terminal_state_v1' and value['arm'] == arm
            and value['state'] == 'terminal' and value['paired_run_must_be_invalidated'] is False
            and value['evidence_custody_authenticated_by_this_mapper'] is False,
            'only valid terminal snapshots may enter a paired seal')
    host = value['binding']
    require(type(host) is dict and set(host) == {'case_id', 'observation_sha256'}, 'exact host case binding required')
    ident = host['case_id']
    require(valid_sha(ident) and ident in expected and valid_sha(host['observation_sha256'])
            and host['observation_sha256'] == expected[ident], 'terminal case/observation differs')
    require(value['policy_sha256'] == TERMINAL_POLICY_SHA256 and valid_sha(value['policy_sha256'])
            and value['budget_sha256'] == budgets[ident] and valid_sha(value['budget_sha256']),
            'terminal policy or prospective budget differs')
    reason = value['reason']
    require(type(reason) is str and reason in RESPONSE_REASONS | BUDGET_REASONS,
            'unclassified or infrastructure terminal reason refuses the paired run')
    prediction = value['prediction']
    require(type(prediction) is dict and set(prediction) == {'case_id', 'observation_sha256', 'status', 'probabilities'}
            and prediction['case_id'] == ident and prediction['observation_sha256'] == expected[ident],
            'prediction must carry the exact trusted host identity')
    require(prediction['status'] == ('ok' if reason == 'model_answer' else 'abstain'),
            'terminal status and operational reason differ')
    events = value['events']
    require(type(events) is list and 2 <= len(events) <= 1024, 'complete bounded lifecycle evidence required')
    for position, event in enumerate(events):
        require(type(event) is dict and set(event) == {'position', 'kind', 'evidence'}
                and type(event['position']) is int and event['position'] == position,
                'exact ordered lifecycle event required')
        kind = 'trusted_delivery_and_interface_available' if position == 0 else (
            reason if position == len(events)-1 and reason in BUDGET_REASONS else
            'retained_model_response' if position == len(events)-1 else 'participant_tool_error')
        require(type(event['kind']) is str and event['kind'] == kind, 'delivery/tool/terminal event sequence differs')
        evidence = event['evidence']
        require(type(evidence) is dict and set(evidence) == {'sha256', 'bytes'} and valid_sha(evidence['sha256'])
                and type(evidence['bytes']) is int and 0 <= evidence['bytes'] <= 2**63-1,
                'exact retained original evidence reference required')
    # Input stability is a trusted caller obligation. Returned seals contain
    # immutable bytes, so a second in-memory copy of every audit event is not needed.
    return ident, value


def validate_pair(public_manifest, private_targets, terminal_snapshots, expected_budget_hashes, transport):
    expected = admit_population(public_manifest, private_targets, transport)
    budgets = admit_budgets(expected_budget_hashes, expected)
    require(type(terminal_snapshots) is dict and set(terminal_snapshots) == set(ARMS),
            'both complete terminal arms required')
    snapshots = {}; submitted = {}; reasons = {}
    for arm in ARMS:
        items = terminal_snapshots[arm]
        require(type(items) is list and len(items) == CASE_COUNT, 'every case requires exactly one terminal snapshot')
        found = {}
        for item in items:
            ident, detached = admit_snapshot(item, arm, expected, budgets[arm])
            require(ident not in found, 'duplicate terminal case refuses the paired run')
            found[ident] = detached
        require(set(found) == set(expected), 'complete terminal set required')
        snapshots[arm] = [found[item['case_id']] for item in public_manifest]
        submitted[arm] = {'schema': 'dosei_paired_workflow_predictions_v1', 'arm': arm,
                          'cases': [row['prediction'] for row in snapshots[arm]]}
        reasons[arm] = dict(sorted(Counter(row['reason'] for row in snapshots[arm]).items()))
    admitted = transport.admit_pair(public_manifest, submitted)
    predictions = {arm: {'schema': 'dosei_paired_workflow_predictions_v1', 'arm': arm,
                        'cases': admitted[arm]} for arm in ARMS}
    audit = {'schema': 'dosei_complete_terminal_audit_v1', 'visibility': 'evaluator_private',
             'expected_budget_hashes': budgets, 'snapshots': snapshots, 'reason_counts': reasons}
    return predictions, audit


def receipt(public_manifest, private_targets, budgets, prediction_bytes, audit_bytes):
    return {'schema': 'dosei_sealed_paired_predictions_receipt_v1', 'visibility': 'evaluator_private',
            'condition': CONDITION, 'case_slots_per_arm': CASE_COUNT, 'recording_groups': RECORDING_COUNT,
            'terminal_policy_sha256': TERMINAL_POLICY_SHA256, 'required_source_sha256': dict(SOURCE_PINS),
            'public_manifest': object_binding(public_manifest, 'manifest'),
            'private_targets': object_binding(private_targets, 'targets'),
            'prospective_budgets': object_binding(budgets, 'budgets'),
            'predictions': binding(prediction_bytes), 'private_terminal_audit': binding(audit_bytes),
            'authentic_custody_established_by_sealer': False, 'participant_runtime_qualified_by_sealer': False,
            'scoring_invoked': False}


def seal_pair(public_manifest, private_targets, terminal_snapshots, *, expected_budget_hashes,
              terminal_policy_bytes, transport):
    """Seal both full arms without invoking a scorer; all output is evaluator-private.

    Caller-authenticated input objects and injected source modules must remain
    stable through the call. Hash consistency does not authenticate custody,
    lifecycle truth, budget enforcement, targets or participant isolation.
    """
    require(type(terminal_policy_bytes) is bytes and len(terminal_policy_bytes) <= 65536
            and hashlib.sha256(terminal_policy_bytes).hexdigest() == TERMINAL_POLICY_SHA256,
            'exact adopted terminal policy bytes required')
    predictions, audit = validate_pair(public_manifest, private_targets, terminal_snapshots,
                                       expected_budget_hashes, transport)
    prediction_bytes = canonical(predictions, CAPS['predictions'])
    audit_bytes = canonical(audit, CAPS['audit'])
    raw_receipt = canonical(receipt(public_manifest, private_targets, audit['expected_budget_hashes'],
                                    prediction_bytes, audit_bytes), CAPS['receipt'])
    return {'schema': 'dosei_sealed_paired_predictions_v1', 'prediction_bytes': prediction_bytes,
            'audit_bytes': audit_bytes, 'receipt_bytes': raw_receipt,
            'receipt_sha256': hashlib.sha256(raw_receipt).hexdigest()}


def score_sealed(sealed, scoring_policy_bytes, public_manifest, private_targets, *, transport, scorer):
    """Explicit scoring boundary; validate the whole detached seal first.

    This API has no authority to execute on authentic data. Its trusted caller
    admits numerical execution separately. It never fills or repairs a slot.
    """
    require(type(sealed) is dict and set(sealed) == SEAL_FIELDS
            and sealed['schema'] == 'dosei_sealed_paired_predictions_v1', 'exact sealed envelope required')
    raw_receipt = sealed['receipt_bytes']
    decode_canonical(raw_receipt, 'receipt')
    require(valid_sha(sealed['receipt_sha256']) and hashlib.sha256(raw_receipt).hexdigest() == sealed['receipt_sha256'],
            'sealed receipt hash differs')
    audit = decode_canonical(sealed['audit_bytes'], 'audit')
    require(type(audit) is dict and set(audit) == {'schema', 'visibility', 'expected_budget_hashes', 'snapshots', 'reason_counts'}
            and audit['schema'] == 'dosei_complete_terminal_audit_v1' and audit['visibility'] == 'evaluator_private',
            'exact private lifecycle audit required')
    rebuilt, rebuilt_audit = validate_pair(public_manifest, private_targets, audit['snapshots'],
                                           audit['expected_budget_hashes'], transport)
    require_canonical_match(rebuilt, sealed['prediction_bytes'], 'predictions')
    require_canonical_match(rebuilt_audit, sealed['audit_bytes'], 'audit')
    require_canonical_match(receipt(public_manifest, private_targets, audit['expected_budget_hashes'],
                                    sealed['prediction_bytes'], sealed['audit_bytes']), raw_receipt, 'receipt')
    require(type(scoring_policy_bytes) is bytes and len(scoring_policy_bytes) <= 65536
            and hashlib.sha256(scoring_policy_bytes).hexdigest() == SCORING_POLICY_SHA256,
            'exact adopted scoring policy bytes required')
    report = scorer.score_pair(scoring_policy_bytes, public_manifest, private_targets, rebuilt, transport=transport)
    report_bytes = canonical(report, CAPS['score_report'])
    return {'schema': 'dosei_sealed_paired_score_v1', 'visibility': 'evaluator_private',
            'condition': CONDITION, 'prediction_seal_sha256': sealed['receipt_sha256'],
            'scoring_policy_sha256': SCORING_POLICY_SHA256,
            'scorer_source_sha256_required_of_caller': SOURCE_PINS['scorer'],
            'score_report_bytes': report_bytes, 'score_report_binding': binding(report_bytes),
            'authentic_input_or_execution_admission_established_by_this_api': False}
