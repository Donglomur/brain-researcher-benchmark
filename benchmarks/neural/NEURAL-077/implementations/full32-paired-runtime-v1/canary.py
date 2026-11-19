"""Frozen non-learning delivery probe. Never a scientific reference/model."""
from __future__ import annotations

import errno
import json
import os
import re
import socket
import struct
import sys

_INVOCATIONS = []
DENIED = frozenset((errno.EACCES, errno.EPERM))
PREFIX = struct.Struct('!I')
MAX_PROMPT = 196608
CHECKS = ('fresh_module_state', 'prior_metadata_denied', 'answer_data_denied',
          'person_data_denied', 'manifest_data_denied', 'state_write_denied',
          'loopback_network_denied', 'single_opaque_query_projection')


def failed_check(results):
    """Pure result acceptance seam for generated source controls."""
    if type(results) is not dict or set(results) != set(CHECKS):
        return 'invalid_probe_inventory'
    return next((name for name in CHECKS if results[name] is not True), None)


def denied_stat(path):
    try:
        os.stat(path, follow_symlinks=False)
    except OSError as error:
        return error.errno in DENIED
    return False


def denied_open(path):
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError as error:
        return error.errno in DENIED
    else:
        # Even a failed boundary probe never reads witness or real data bytes.
        os.close(fd)
        return False


def denied_write():
    try:
        fd = os.open('erp-canary-state-probe', os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    except OSError as error:
        return error.errno in DENIED
    else:
        # A zero-byte generated file in the owned temporary cwd is a failure.
        os.close(fd)
        return False


def denied_network():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as stream:
            stream.settimeout(0.5)
            code = stream.connect_ex(('127.0.0.1', 9))
    except OSError as error:
        code = error.errno
    return code in DENIED  # Refused/unreachable/timeout does not prove sandbox denial.


def read_exact(stream, count):
    value = bytearray()
    while len(value) < count:
        block = stream.read(count - len(value))
        if not block:
            raise ValueError('Incomplete framed input')
        value.extend(block)
    return bytes(value)


def query_identifier(prompt):
    """Find one exact unlabeled query object, ignoring labeled demonstration IDs.

    Whole prompt scanning is bounded. Ambiguity fails closed; demonstration ID
    prefixes are irrelevant. This pure parser opens no files or sockets.
    """
    starts = [match.start() for match in re.finditer(r'\{', prompt)]
    if len(starts) > 64:
        raise ValueError('Too many structured prompt objects')
    candidates = []
    decoder = json.JSONDecoder()
    for start in starts:
        try:
            value, _ = decoder.raw_decode(prompt, start)
        except ValueError:
            continue
        if (type(value) is dict and set(value) == {'trial_id', 'channels'} and
                type(value['trial_id']) is str and re.fullmatch(r'q-[0-9a-f]{32}', value['trial_id'])):
            candidates.append(value['trial_id'])
    if len(candidates) != 1:
        raise ValueError('Exactly one unambiguous unlabeled query object required')
    return candidates[0]


def main():
    # Import config only in the actual sandboxed launcher. Importing this source
    # for pure generated controls does not open files, sockets or target data.
    from neural077_config import CONFIG
    fresh = not _INVOCATIONS
    _INVOCATIONS.append(1)
    try:
        size = PREFIX.unpack(read_exact(sys.stdin.buffer, 4))[0]
        if not 0 < size <= MAX_PROMPT:
            return 20
        prompt = read_exact(sys.stdin.buffer, size).decode('utf-8')
        if sys.stdin.buffer.read(1):
            return 21
        identifier = query_identifier(prompt)
        forbidden = ('"participant_id"', '"source_event_code"', '"source_anchor_0based"',
                     'PACKET.json', 'roster.json', 'PARTICIPANT_JOIN.json')
        projection = not any(token in prompt for token in forbidden)
        # These are generated non-neural witnesses, never actual targets/keys.
        paths = CONFIG['witnesses']
        results = {
            'fresh_module_state': fresh,
            'prior_metadata_denied': denied_stat(paths['prior_episode']) and denied_open(paths['prior_episode']),
            'answer_data_denied': denied_open(paths['answer']),
            'person_data_denied': denied_open(paths['person']),
            'manifest_data_denied': denied_open(paths['manifest']),
            'state_write_denied': denied_write(),
            'loopback_network_denied': denied_network(),
            'single_opaque_query_projection': projection,
        }
        failure = failed_check(results)
        if failure is not None:
            return 40 + CHECKS.index(failure) if failure in CHECKS else 60
        # Fixed probe response, not fitted and never scored against targets.
        body = json.dumps({'trial_id': identifier, 'target_probability': 0.5},
                          separators=(',', ':')).encode()
        sys.stdout.buffer.write(PREFIX.pack(len(body)) + body)
        sys.stdout.buffer.flush()
        return 0
    except (OSError, ValueError, UnicodeError, KeyError, TypeError, struct.error):
        return 61


if __name__ == '__main__':
    raise SystemExit(main())
