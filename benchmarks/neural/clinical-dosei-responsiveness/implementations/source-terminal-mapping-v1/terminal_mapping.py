"""Pure trusted-host case lifecycle; not a participant API or isolation boundary."""
import hashlib
import json
import math
import re

POLICY_SHA256 = '82674ea847a74e7f4e3229f14cb7beac75a35d033d03451031c05a0695a4e4c3'
TRANSPORT_SHA256 = '69fd0c85374240bba63fc212304b4af9882c8afee0ff8b7d0fbeea3e5b6ef048'
BUDGET_REASONS = frozenset(('participant_wall_budget', 'participant_token_budget',
    'participant_tool_cpu_budget', 'participant_tool_memory_budget', 'participant_tool_call_budget'))
INVALID_REASONS = frozenset(('authentication_failure', 'provider_quota', 'provider_outage',
    'transport_timeout', 'transport_failure', 'uncertain_delivery', 'source_failure',
    'observation_hash_failure', 'runtime_failure', 'isolation_failure',
    'unavailable_interface', 'unclassified_failure'))
MAX_RESPONSE = 65536
MAX_EVENTS = 1024


class MappingRefusal(ValueError):
    pass


def require(ok, message):
    if not ok:
        raise MappingRefusal(message)


def sha(value):
    require(type(value) is str and re.fullmatch('[0-9a-f]{64}', value), 'exact SHA256 required')
    return value


def artifact(value):
    require(type(value) is dict and set(value) == {'sha256', 'bytes'}, 'exact retained evidence binding required')
    require(type(value['bytes']) is int and 0 <= value['bytes'] <= 2**63-1, 'exact evidence byte count required')
    return {'sha256': sha(value['sha256']), 'bytes': value['bytes']}


def decode(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('duplicate JSON key')
            result[key] = value
        return result
    def finite(value):
        result = float(value)
        if not math.isfinite(result):
            raise ValueError('nonfinite number')
        return result
    def constant(_):
        raise ValueError('nonfinite constant')
    # A response is exactly one UTF-8 JSON object, without fences or extraction.
    return json.loads(raw.decode('utf-8'), object_pairs_hook=pairs,
                      parse_float=finite, parse_constant=constant)


def trusted_transition(function):
    def wrapped(self, *args, **kwargs):
        try:
            return function(self, *args, **kwargs)
        except BaseException:
            if self._state != 'invalid':
                self._reason = 'trusted_host_call_failed'
            self._state = 'invalid'
            self._prediction = None
            raise
    return wrapped


class CaseTerminal:
    """Trusted host only. Evidence truth/custody and budget enforcement are external.

    Each instance serves exactly one arm/case. The caller must invalidate the
    entire paired run if any instance is invalid or a trusted call raises.
    The state is not tamper-proof against its host and must not be exposed to a
    model, participant code, or any process able to inspect evaluator memory.
    """
    def __init__(self, policy_bytes, binding, arm, budget_sha256, *, transport):
        require(type(policy_bytes) is bytes and hashlib.sha256(policy_bytes).hexdigest() == POLICY_SHA256,
                'exact adopted terminal policy bytes required')
        transport.admit_manifest([binding])
        require(type(arm) is str and arm in transport.ARMS, 'declared arm required')
        self._binding = dict(binding)
        self._arm = arm
        self._budget = sha(budget_sha256)
        self._transport = transport
        self._state = 'awaiting_delivery'
        self._events = []
        self._prediction = None
        self._reason = None

    def _in(self, *states):
        require(self._state in states, 'illegal lifecycle transition; do not retry or reuse this case')

    def _event(self, kind, evidence):
        bound = artifact(evidence)
        if len(self._events) >= MAX_EVENTS:
            self._state = 'invalid'
            self._prediction = None
            self._reason = 'operational_evidence_capacity_exceeded'
            raise MappingRefusal('host audit capacity exhausted; paired run invalid')
        self._events.append({'position': len(self._events), 'kind': kind, 'evidence': bound})

    @trusted_transition
    def establish_delivery(self, *, observation_sha256, delivery_evidence):
        """Host asserts source custody, exact delivery, interface and fresh isolation.

        The retained evidence must establish all four facts. A hash-shaped
        reference alone does not prove them; this function cannot inspect it.
        """
        self._in('awaiting_delivery')
        sha(observation_sha256)
        if observation_sha256 != self._binding['observation_sha256']:
            self._state = 'invalid'
            self._reason = 'observation_hash_failure'
            raise MappingRefusal('delivered observation differs; paired run invalid')
        self._event('trusted_delivery_and_interface_available', delivery_evidence)
        self._state = 'active'

    @trusted_transition
    def participant_tool_error(self, evidence):
        """Record attributable participant code/analysis error without ending a case."""
        self._in('active')
        self._event('participant_tool_error', evidence)

    def _finish(self, row, reason):
        self._prediction = row
        self._reason = reason
        self._state = 'terminal'

    def _abstain(self, reason):
        self._finish({**self._binding, 'status': 'abstain', 'probabilities': None}, reason)

    @trusted_transition
    def budget_exhausted(self, reason, evidence):
        """Only trusted host attribution to the frozen participant budget is valid."""
        self._in('active')
        require(type(reason) is str and reason in BUDGET_REASONS, 'explicit participant budget attribution required')
        self._event(reason, evidence)
        self._abstain(reason)

    @trusted_transition
    def infrastructure_failure(self, reason, evidence):
        """Invalidate even an earlier terminal snapshot when later evidence contradicts it."""
        self._in('awaiting_delivery', 'active', 'terminal')
        require(type(reason) is str and reason in INVALID_REASONS, 'trusted infrastructure/unknown reason required')
        self._event(reason, evidence)
        self._state = 'invalid'
        self._prediction = None
        self._reason = reason

    @trusted_transition
    def model_response(self, raw, *, retained_response):
        """Parse one retained final response; host adds identity, never the model.

        Only malformed participant content maps to abstention. Invalid evidence
        bindings and unexpected transport errors propagate as trusted-run faults.
        Complete original raw bytes must already be retained by the host.
        """
        self._in('active')
        require(type(raw) is bytes, 'trusted response transport must provide bytes')
        evidence = artifact(retained_response)
        require(evidence == {'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)},
                'raw response and retained evidence differ; paired run invalid')
        self._event('retained_model_response', evidence)
        try:
            if len(raw) > MAX_RESPONSE:
                raise ValueError('model response exceeds frozen response byte limit')
            decoded = decode(raw)
            if type(decoded) is not dict or set(decoded) != {'status', 'probabilities'}:
                raise ValueError('model response must contain only status and probabilities')
            row = {**self._binding, **decoded}
            submitted = {'schema': 'dosei_paired_workflow_predictions_v1',
                         'arm': self._arm, 'cases': [row]}
        except (ValueError, UnicodeError, RecursionError):
            self._abstain('invalid_model_response')
            return
        try:
            admitted = self._transport.admit_predictions([self._binding], submitted, self._arm)
        except self._transport.PredictionRefusal:
            self._abstain('invalid_model_response')
            return
        require(type(admitted) is list and len(admitted) == 1, 'trusted transport returned invalid result')
        self._finish(admitted[0], 'model_answer' if admitted[0]['status'] == 'ok' else 'voluntary_abstention')

    def snapshot(self):
        """Detached evaluator-private state; not a sealed run or scored prediction file."""
        return json.loads(json.dumps({'schema': 'dosei_host_case_terminal_state_v1',
            'arm': self._arm, 'binding': self._binding, 'policy_sha256': POLICY_SHA256,
            'budget_sha256': self._budget, 'state': self._state, 'reason': self._reason,
            'prediction': self._prediction, 'events': self._events,
            'paired_run_must_be_invalidated': self._state == 'invalid',
            'evidence_custody_authenticated_by_this_mapper': False}, allow_nan=False))
