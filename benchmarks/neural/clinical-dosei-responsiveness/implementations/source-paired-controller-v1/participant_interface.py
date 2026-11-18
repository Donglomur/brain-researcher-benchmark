"""Pure byte protocol for two trusted-host participant interfaces.

This is neither an execution backend nor a sandbox. The controller owns fresh
case contexts, declared tools, complete input authentication and runtime limits.
Participants receive only byte responses, never this object or its backend.
"""
import base64
import hashlib
import json
import math
import re

ARMS = frozenset(('viewer_only', 'code_enabled'))
MAX_REQUEST_BYTES = 65536
MAX_PAYLOAD_BYTES = 2097152
MAX_RESPONSE_BYTES = 3145728
MAX_DISCLOSURE_BYTES = 16384
MAX_JSON_DEPTH = 8
MAX_TOOLS = 16
SCIENTIFIC_DISCLOSURE_SHA256 = '75a07d919ec77567777ca76cd1b2cc15212a3acd6417a1acacd5d5f4a4536df5'
HASH = re.compile(r'[0-9a-f]{64}\Z')
TOOL_NAME = re.compile(r'[a-z][a-z0-9_]{0,47}\Z')
PUBLIC_CODES = frozenset(('invalid_json', 'request_too_large', 'invalid_request',
                          'action_not_allowed', 'undeclared_tool'))
FAILURE_CATEGORIES = frozenset(('configuration_error', 'backend_budget_exhausted',
    'backend_failure', 'invalid_backend_response', 'observation_binding_mismatch',
    'interface_poisoned'))
BUDGET_REASONS = frozenset(('participant_tool_cpu_budget', 'participant_tool_memory_budget',
                          'participant_tool_call_budget'))
OBSERVATION_FIELDS = frozenset(('schema', 'condition', 'case_id', 'channels', 'units',
    'interval_ms', 'relative_time_ms', 'values_uv', 'observation_mask',
    'source_endpoint_mask', 'coverage'))
DISCLOSURE_FIELDS = frozenset(('schema', 'condition', 'target', 'time_relation',
    'table_clock_hz', 'documented_nominal_EEG_channel_hz', 'source_blank_cells',
    'source_hardware_endpoints', 'display_policy', 'display_connections',
    'dataset_label_training', 'demonstrations', 'cross_case_feedback_or_memory',
    'task_specific_pretrained_detector', 'clinical_diagnosis'))


class RequestRefusal(ValueError):
    """Recoverable participant-input refusal; code is safe to return publicly."""
    def __init__(self, code):
        if type(code) is not str or code not in PUBLIC_CODES:
            raise ValueError('unknown public refusal code')
        self.code = code
        super().__init__(code)


class InterfaceFailure(RuntimeError):
    """Host-private infrastructure failure; never serialize its causal chain."""
    def __init__(self, category, *, budget_reason=None, budget_evidence=None):
        if type(category) is not str or category not in FAILURE_CATEGORIES:
            raise ValueError('unknown private failure category')
        if category == 'backend_budget_exhausted':
            if type(budget_reason) is not str or budget_reason not in BUDGET_REASONS:
                raise ValueError('unknown trusted budget reason')
            budget_evidence = _evidence(budget_evidence)
        elif budget_reason is not None or budget_evidence is not None:
            raise ValueError('budget fields require budget category')
        self.category = category
        self.budget_reason = budget_reason
        self.budget_evidence = budget_evidence
        super().__init__(category)


class BackendBudgetExceeded(RuntimeError):
    """Trusted backend signals a declared resource limit, not provider failure."""
    def __init__(self, reason, evidence=None):
        if type(reason) is not str or reason not in BUDGET_REASONS:
            raise ValueError('unknown trusted budget reason')
        self.reason = reason
        self.evidence = _evidence(evidence)
        super().__init__(reason)


def _require(condition):
    if not condition:
        raise ValueError('invalid interface value')


def _evidence(value):
    _require(type(value) is dict and set(value) == {'sha256', 'bytes'} and
             type(value['sha256']) is str and HASH.fullmatch(value['sha256']) and
             type(value['bytes']) is int and 0 <= value['bytes'] <= 2**63-1)
    return dict(value)


def _depth(text):
    level = 0
    quoted = escaped = False
    for char in text:
        if quoted:
            if escaped:
                escaped = False
            elif char == '\\':
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
        elif char in '[{':
            level += 1
            _require(level <= MAX_JSON_DEPTH)
        elif char in ']}':
            level -= 1
            _require(level >= 0)


def _pairs(items):
    result = {}
    for key, value in items:
        _require(key not in result)
        result[key] = value
    return result


def _integer(text):
    _require(len(text) <= 32)
    return int(text)


def _float(text):
    _require(len(text) <= 128)
    value = float(text)
    _require(math.isfinite(value))
    return value


def _constant(text):
    raise ValueError('nonfinite JSON constant')


def _strings(value):
    if type(value) is str:
        value.encode('utf-8', 'strict')
    elif type(value) is dict:
        for key, child in value.items():
            _strings(key)
            _strings(child)
    elif type(value) is list:
        for child in value:
            _strings(child)


def _decode(raw, maximum):
    _require(type(raw) is bytes and 0 < len(raw) <= maximum)
    text = raw.decode('utf-8', 'strict')
    _depth(text)
    value = json.loads(text, object_pairs_hook=_pairs, parse_int=_integer,
                       parse_float=_float, parse_constant=_constant)
    _strings(value)
    return value


def _encode(value, maximum=MAX_RESPONSE_BYTES):
    output = bytearray()
    for part in json.JSONEncoder(sort_keys=True, separators=(',', ':'),
                                 ensure_ascii=True, allow_nan=False).iterencode(value):
        raw = part.encode('ascii')
        _require(len(output) + len(raw) <= maximum)
        output.extend(raw)
    return bytes(output)


def request_error(refusal):
    """Fixed recoverable error only; no raw request, backend detail or partials."""
    if type(refusal) is not RequestRefusal or type(refusal.code) is not str or refusal.code not in PUBLIC_CODES:
        raise TypeError('only a participant request refusal is public')
    return _encode({'schema': 'dosei_participant_request_error_v1',
                    'code': refusal.code, 'recoverable': True}, 256)


def _request(raw, arm, tools):
    if type(raw) is not bytes:
        raise RequestRefusal('invalid_request')
    if len(raw) > MAX_REQUEST_BYTES:
        raise RequestRefusal('request_too_large')
    try:
        command = _decode(raw, MAX_REQUEST_BYTES)
    except (ValueError, TypeError, OverflowError, RecursionError):
        raise RequestRefusal('invalid_json') from None
    if type(command) is not dict or type(command.get('action')) is not str:
        raise RequestRefusal('invalid_request')
    action = command['action']
    if action not in ('view', 'window', 'gain', 'observation', 'tool'):
        raise RequestRefusal('action_not_allowed')
    if arm == 'viewer_only' and action in ('observation', 'tool'):
        raise RequestRefusal('action_not_allowed')
    good = False
    if action in ('view', 'observation'):
        good = set(command) == {'action'}
    elif action == 'window':
        good = set(command) == {'action', 'start_ms', 'end_ms'} and \
            type(command['start_ms']) is int and type(command['end_ms']) is int and \
            -30000 <= command['start_ms'] < command['end_ms'] <= 0 and \
            100 <= command['end_ms'] - command['start_ms'] <= 30000
    elif action == 'gain':
        good = set(command) == {'action', 'limit_uv'} and \
            type(command['limit_uv']) in (int, float) and command['limit_uv'] in (25, 50, 100, 187.5)
    elif action == 'tool':
        good = set(command) == {'action', 'name', 'input'} and \
            type(command['name']) is str and TOOL_NAME.fullmatch(command['name']) is not None and \
            type(command['input']) is str
        if good and command['name'] not in tools:
            raise RequestRefusal('undeclared_tool')
    if not good:
        raise RequestRefusal('invalid_request')
    return command


class ParticipantInterface:
    """Trusted host state. Never hand this Python object to participant code.

    Backend methods: viewer_action(command)->PNG bytes; code_observation()->
    canonical public packet bytes; run_tool(name,input)->{status:ok|participant_error,text:str}.
    Tool errors are declared scientific-tool results, not infrastructure faults.
    The backend must enforce process/file/network isolation and real budgets.
    """
    def __init__(self, arm, public_binding, *, backend, common_disclosure, declared_tools=()):
        self._failed = False
        try:
            _require(type(arm) is str and arm in ARMS)
            _require(type(public_binding) is dict and set(public_binding) ==
                     {'case_id', 'observation_sha256'} and all(type(v) is str and HASH.fullmatch(v)
                     for v in public_binding.values()))
            disclosure = _decode(common_disclosure, MAX_DISCLOSURE_BYTES)
            _require(hashlib.sha256(common_disclosure).hexdigest() == SCIENTIFIC_DISCLOSURE_SHA256)
            _require(type(disclosure) is dict and set(disclosure) == DISCLOSURE_FIELDS and
                     disclosure['schema'] == 'dosei_paired_workflow_disclosure_v1' and
                     disclosure['condition'] == 'native_marker_relative_30s_v1' and
                     _encode(disclosure, MAX_DISCLOSURE_BYTES) == common_disclosure)
            _require(type(declared_tools) in (list, tuple) and len(declared_tools) <= MAX_TOOLS)
            tools = {}
            for row in declared_tools:
                _require(type(row) is dict and set(row) == {'name', 'description', 'input_format'} and
                         type(row['name']) is str and TOOL_NAME.fullmatch(row['name']) and
                         row['name'] not in tools and type(row['description']) is str and
                         0 < len(row['description'].encode('utf-8', 'strict')) <= 1024 and
                         type(row['input_format']) is str and row['input_format'] == 'utf8_text')
                tools[row['name']] = dict(row)
            _require(arm != 'viewer_only' or not tools)
            _require(callable(getattr(backend, 'viewer_action', None)))
            if arm == 'code_enabled':
                _require(callable(getattr(backend, 'code_observation', None)))
            if tools:
                _require(callable(getattr(backend, 'run_tool', None)))
        except Exception:
            raise InterfaceFailure('configuration_error') from None
        self._arm = arm
        self._binding = dict(public_binding)
        self._backend = backend
        self._disclosure = bytes(common_disclosure)
        self._tools = tools

    @property
    def failed(self):
        return self._failed

    def describe(self):
        """Return public capability/disclosure bytes; not an authentication proof."""
        if self._failed:
            raise InterfaceFailure('interface_poisoned')
        actions = ['view', 'window', 'gain']
        if self._arm == 'code_enabled':
            actions += ['observation', 'tool']
        try:
            return _encode({'schema': 'dosei_participant_capabilities_v1', 'arm': self._arm,
                **self._binding, 'actions': actions, 'tools': list(self._tools.values()),
                'common_disclosure': {'encoding': 'utf8', 'text': self._disclosure.decode('ascii'),
                                      'sha256': hashlib.sha256(self._disclosure).hexdigest()},
                'limits': {'request_bytes': MAX_REQUEST_BYTES, 'payload_bytes': MAX_PAYLOAD_BYTES,
                           'response_bytes': MAX_RESPONSE_BYTES, 'json_depth': MAX_JSON_DEPTH},
                'runtime_isolation_established_by_interface': False})
        except BaseException:
            self._failed = True
            raise

    def handle(self, request_bytes):
        if self._failed:
            raise InterfaceFailure('interface_poisoned')
        command = _request(request_bytes, self._arm, self._tools)
        action = command['action']
        try:
            try:
                if action in ('view', 'window', 'gain'):
                    result = self._backend.viewer_action(dict(command))
                elif action == 'observation':
                    result = self._backend.code_observation()
                else:
                    result = self._backend.run_tool(command['name'], command['input'])
            except BackendBudgetExceeded as problem:
                reason = getattr(problem, 'reason', None)
                if type(problem) is not BackendBudgetExceeded or type(reason) is not str or reason not in BUDGET_REASONS:
                    raise InterfaceFailure('backend_failure') from None
                try:
                    evidence = _evidence(getattr(problem, 'evidence', None))
                except Exception:
                    raise InterfaceFailure('backend_failure') from None
                raise InterfaceFailure('backend_budget_exhausted', budget_reason=reason,
                                       budget_evidence=evidence) from None
            except Exception:
                raise InterfaceFailure('backend_failure') from None
            try:
                if action == 'tool':
                    _require(type(result) is dict and set(result) == {'status', 'text'} and
                             type(result['status']) is str and result['status'] in ('ok', 'participant_error') and
                             type(result['text']) is str and
                             len(result['text'].encode('utf-8', 'strict')) <= MAX_PAYLOAD_BYTES)
                    payload = {'kind': 'tool_result', 'name': command['name'], **result}
                else:
                    _require(type(result) is bytes and 0 < len(result) <= MAX_PAYLOAD_BYTES)
                    digest = hashlib.sha256(result).hexdigest()
                    if action == 'observation':
                        if digest != self._binding['observation_sha256']:
                            raise InterfaceFailure('observation_binding_mismatch')
                        packet = _decode(result, MAX_PAYLOAD_BYTES)
                        _require(type(packet) is dict and set(packet) == OBSERVATION_FIELDS and
                                 packet['schema'] == 'dosei_paired_observation_v1' and
                                 packet['condition'] == 'native_marker_relative_30s_v1' and
                                 packet['case_id'] == self._binding['case_id'] and
                                 _encode(packet, MAX_PAYLOAD_BYTES) == result)
                        kind = 'canonical_observation'
                    else:
                        _require(result.startswith(b'\x89PNG\r\n\x1a\n'))
                        kind = 'png'
                    payload = {'kind': kind, 'encoding': 'base64', 'bytes': len(result),
                               'sha256': digest, 'data': base64.b64encode(result).decode('ascii')}
                return _encode({'schema': 'dosei_participant_response_v1', 'arm': self._arm,
                                **self._binding, 'action': action, 'payload': payload})
            except InterfaceFailure:
                raise
            except Exception:
                raise InterfaceFailure('invalid_backend_response') from None
        except BaseException:
            self._failed = True
            raise
