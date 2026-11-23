"""One-case NEURAL-044 response exchange, inactive without an admitted host.

This module starts a fresh participant process and validates its response. It
does not restrict the process's filesystem/network, enforce CPU/RAM/model-call
budgets, freeze an entire code environment, or deliver the separate investigation
channel. Never mount the cohort's public directory into a participant: another
case's training labels can contain this case's withheld responses.
"""
import hashlib
import json
import math
import os
from pathlib import Path
import selectors
import signal
import subprocess
import threading
import time

from .contracts import Refusal, digest, require
from .response_comparison_v2 import SCHEMA, FEATURES, RECIPE, UNITS

TRANSPORT_SCHEMA = 'neural044-response-transport/v1'
ARMS = ('frozen_program', 'case_adaptive')
PUBLIC_KEYS = {
    'task', 'case_id', 'training_features', 'training_responses', 'query_features',
    'ids', 'prohibited_inputs', 'claim', 'comparison_schema', 'feature_names',
    'response_units', 'source_digest', 'disposition_digest', 'reference_recipe',
    'training_unit_ids',
}
LIMIT_KEYS = {'wall_seconds', 'cpu_seconds', 'memory_bytes', 'output_bytes',
              'model_calls', 'model_tokens'}


def _hash(value, name):
    require(type(value) is str and len(value) == 64 and
            all(c in '0123456789abcdef' for c in value), name)


def _numbers(values, length, name):
    def finite(value):
        if type(value) not in (int, float):
            return False
        try:
            return math.isfinite(value)
        except OverflowError:
            return False
    require(type(values) is list and len(values) == length and
            all(finite(x) for x in values), name)


def _matrix(values, length, name):
    require(type(values) is list and len(values) == length, name)
    for row in values:
        _numbers(row, len(FEATURES), name)


def validate_public(public):
    """Accept the current prepared comparison packet, never an arbitrary dict."""
    require(type(public) is dict and set(public) == PUBLIC_KEYS,
            'exact public response-packet fields; no extra private data')
    require(public['task'] == 'NEURAL-044' and
            public['claim'] == 'held_mouse_response_prediction' and
            public['comparison_schema'] == SCHEMA, 'fixed response task and claim')
    recipe = public['reference_recipe']
    fixed_recipe = (type(recipe) is dict and set(recipe) == set(RECIPE) and
                    all(type(recipe[k]) is type(v) and recipe[k] == v
                        for k, v in RECIPE.items()))
    require(public['feature_names'] == FEATURES and public['response_units'] == UNITS
            and fixed_recipe, 'fixed features, units and type-sensitive recipe')
    require(public['prohibited_inputs'] ==
            ['held_mouse_response', 'held_mouse_stimulation_signals'],
            'held-response exclusion policy')
    for key in ('case_id', 'source_digest', 'disposition_digest'):
        _hash(public[key], key)
    ids = public['ids']
    require(type(ids) is list and ids, 'nonempty response identity list')
    for value in ids:
        _hash(value, 'opaque response identity')
    require(len(ids) == len(set(ids)), 'unique response identities')
    units = public['training_unit_ids']
    require(type(units) is list and units, 'training-unit identities')
    for value in units:
        _hash(value, 'opaque training-unit identity')
    require(len(set(units)) >= 2, 'at least two training mice')
    _matrix(public['training_features'], len(units), 'finite complete training design')
    _numbers(public['training_responses'], len(units), 'finite training responses')
    _matrix(public['query_features'], len(ids), 'finite complete query design')
    return digest(public)


def make_request(public, arm, limits, recipe_commitment, max_input_bytes):
    """Serialize exactly one case; recipe commitment must be issued by the host.

    The commitment identifies host-recorded code/recipe provenance; accepting a
    supplied digest does not establish pre-query freezing or immutable code.
    """
    require(arm in ARMS, 'fixed participant arm')
    require(type(limits) is dict, 'exact positive limits')
    # The allowed values are immutable integers. Copy before validation so a
    # caller's later changes cannot alter the limits sent with this request.
    limits = limits.copy()
    require(set(limits) == LIMIT_KEYS and
            all(type(v) is int and v > 0 for v in limits.values()), 'exact positive limits')
    require(type(max_input_bytes) is int and max_input_bytes > 0, 'positive input cap')
    _hash(recipe_commitment, 'host-issued recipe commitment')
    require(type(public) is dict, 'public packet must be an object')
    try:
        snapshot = json.loads(json.dumps(public, allow_nan=False))
    except (TypeError, ValueError, OverflowError, RecursionError, RuntimeError) as error:
        raise Refusal('JSON-safe public packet snapshot required') from error
    # Validate, hash and serialize only this detached snapshot. The caller may
    # retain mutable objects; later edits must never change the transmitted view.
    packet_digest = validate_public(snapshot)
    request = {'schema': TRANSPORT_SCHEMA, 'task': 'NEURAL-044', 'arm': arm,
               'packet_digest': packet_digest, 'public_packet': snapshot,
               'limits': limits, 'recipe_commitment': recipe_commitment}
    raw = json.dumps(request, sort_keys=True, separators=(',', ':'),
                     allow_nan=False).encode('utf8') + b'\n'
    require(len(raw) <= max_input_bytes, 'participant input cap')
    return raw, packet_digest


def parse_answer(raw, public, packet_digest):
    """Return the existing scorer submission only after exact envelope checks."""
    require(type(raw) is bytes and raw.endswith(b'\n') and raw.count(b'\n') == 1,
            'one newline-terminated JSON response, no extra stdout')
    def unique_pairs(pairs):
        value = {}
        for key, item in pairs:
            require(key not in value, 'duplicate response JSON key')
            value[key] = item
        return value
    def invalid_constant(_):
        raise Refusal('nonfinite response JSON constant')
    try:
        value = json.loads(raw.decode('utf8'), object_pairs_hook=unique_pairs,
                           parse_constant=invalid_constant)
    except (UnicodeError, json.JSONDecodeError, RecursionError) as error:
        raise Refusal('invalid response JSON') from error
    require(type(value) is dict and set(value) ==
            {'schema', 'packet_digest', 'case_id', 'ids', 'responses'},
            'exact response envelope')
    require(value['schema'] == TRANSPORT_SCHEMA and
            value['packet_digest'] == packet_digest, 'response packet binding')
    require(value['case_id'] == public['case_id'] and value['ids'] == public['ids'],
            'complete ordered case response identities')
    _numbers(value['responses'], len(public['ids']), 'finite complete response vector')
    return {key: value[key] for key in ('case_id', 'ids', 'responses')}


def _retire(proc):
    """Retire only the process group created by this call, including descendants."""
    if proc is None:
        return
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    proc.wait(timeout=1)
    for stream in (proc.stdin, proc.stdout, proc.stderr):
        if stream is not None:
            stream.close()


def run_case(public, arm, limits, recipe_commitment, command, cwd,
             *, max_input_bytes, stderr_limit=4096):
    """One fresh process, bounded pipe I/O, deadline and no target/scorer access.

    An external host must supply a genuine case-only filesystem/network policy,
    own code freezing and all remaining budgets, and commit every case in BOTH
    arms plus the separate investigation report before scoring. No readiness is
    granted by this function or its software tests.
    """
    started = time.monotonic()
    require(threading.current_thread() is threading.main_thread(),
            'main-thread lifecycle owner required')
    request, packet_digest = make_request(public, arm, limits, recipe_commitment,
                                          max_input_bytes)
    delivered = json.loads(request)
    expected = delivered['public_packet']
    # Enforce the exact limits in the serialized request, never the caller's
    # still-mutable mapping. This binds admission, deadline and output caps.
    limits = delivered['limits']
    require(type(command) in (list, tuple) and command and
            all(type(x) is str and x and '\x00' not in x for x in command),
            'explicit argument vector without a shell')
    require(type(stderr_limit) is int and 0 <= stderr_limit <= limits['output_bytes'],
            'bounded stderr limit')
    cwd = Path(cwd)
    require(cwd.is_dir(), 'host-provisioned working directory')
    deadline = started + limits['wall_seconds']
    require(time.monotonic() < deadline, 'deadline before participant launch')
    env = {'PATH': '/usr/bin:/bin', 'PYTHONDONTWRITEBYTECODE': '1',
           'OMP_NUM_THREADS': '1', 'OPENBLAS_NUM_THREADS': '1', 'MKL_NUM_THREADS': '1',
           'VECLIB_MAXIMUM_THREADS': '1', 'NUMEXPR_NUM_THREADS': '1'}
    proc = None
    selector = selectors.DefaultSelector()
    output, diagnostics = bytearray(), bytearray()
    sent = total_output = 0
    caught_signals = (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)
    old_handlers = {}
    phase = 'acquiring'
    pending_signals = []
    def interrupted(signum, _frame):
        pending_signals.append(signum)
        if phase == 'active':
            raise Refusal('participant exchange interrupted by signal ' + str(signum))
    try:
        for sig in caught_signals:
            old_handlers[sig] = signal.signal(sig, interrupted)
        # Defer catchable interruption across child acquisition/registration.
        # Do not mask signals at fork: the participant must not inherit a block.
        proc = subprocess.Popen(tuple(command), cwd=cwd, env=env, stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=True,
            start_new_session=True)
        phase = 'active'
        require(not pending_signals, 'participant launch interrupted')
        for stream, event, kind in ((proc.stdin, selectors.EVENT_WRITE, 'input'),
                (proc.stdout, selectors.EVENT_READ, 'output'),
                (proc.stderr, selectors.EVENT_READ, 'diagnostics')):
            os.set_blocking(stream.fileno(), False)
            selector.register(stream, event, kind)
        while selector.get_map():
            remaining = deadline - time.monotonic()
            require(remaining > 0, 'participant wall deadline')
            for key, _ in selector.select(min(remaining, .05)):
                stream, kind = key.fileobj, key.data
                if kind == 'input':
                    try:
                        count = os.write(stream.fileno(), request[sent:sent + 16384])
                    except BrokenPipeError as error:
                        raise Refusal('participant closed request input early') from error
                    sent += count
                    if sent == len(request):
                        selector.unregister(stream)
                        stream.close()
                    continue
                chunk = os.read(stream.fileno(), 16384)
                if not chunk:
                    selector.unregister(stream)
                    stream.close()
                    continue
                total_output += len(chunk)
                require(total_output <= limits['output_bytes'], 'participant total output cap')
                target = output if kind == 'output' else diagnostics
                target.extend(chunk)
                if kind == 'diagnostics':
                    require(len(target) <= stderr_limit, 'participant stderr cap')
        require(time.monotonic() < deadline, 'participant wall deadline')
        try:
            code = proc.wait(timeout=max(.001, deadline - time.monotonic()))
        except subprocess.TimeoutExpired as error:
            raise Refusal('participant wall deadline') from error
        require(code == 0 and sent == len(request), 'participant completed full exchange')
        # Validation is part of the exchange budget, not unmetered postprocessing.
        # Retirement remains mandatory even when parsing or this check refuses.
        submission = parse_answer(bytes(output), expected, packet_digest)
        require(time.monotonic() < deadline, 'participant answer validation deadline')
    finally:
        # Defer further catchable interruption until retirement completes.
        phase = 'closing'
        try:
            selector.close()
            _retire(proc)
        finally:
            for sig, handler in old_handlers.items():
                signal.signal(sig, handler)
    require(not pending_signals, 'participant exchange interrupted during retirement')
    # The valid answer is returned only after the owned process was retired.
    return {'submission': submission,
            'receipt': {'schema': TRANSPORT_SCHEMA, 'arm': arm,
                'case_id': expected['case_id'], 'packet_digest': packet_digest,
                'request_sha256': hashlib.sha256(request).hexdigest(),
                'response_sha256': hashlib.sha256(output).hexdigest(),
                'recipe_commitment': recipe_commitment, 'participant_pid': proc.pid,
                'participant_exit_code': code, 'child_waited_and_group_retirement_requested': True,
                'wall_seconds': time.monotonic() - started, 'input_bytes': sent,
                'stdout_bytes': len(output), 'stderr_bytes': len(diagnostics),
                'stderr_sha256': hashlib.sha256(diagnostics).hexdigest(),
                'provider_verified': False, 'scientific_qualification': False,
                'state_reset': 'fresh process only; external isolation unqualified',
                'unverified_budgets': ['cpu_seconds', 'memory_bytes', 'model_calls', 'model_tokens']}}
