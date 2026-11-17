"""Strict inert control records and versioned content identities."""
from __future__ import annotations
import hashlib
import json
import math
from pathlib import PurePosixPath

FRAME_LIMIT = 1024 * 1024
RESULT_LIMIT = 16 * 1024
STATUSES = frozenset({'ok', 'undefined_denominator', 'nonphysical_estimate',
    'insufficient_support', 'unidentified_target', 'unsupported_noise_assumption',
    'unavailable_source', 'timeout', 'resource_exceeded', 'process_failure',
    'invalid_artifact', 'no_call', 'abstained'})
ROUTES = frozenset({'full-A', 'full-B', 'reproduce-A', 'reproduce-B',
    'improve-A', 'improve-B', 'source-diagnostic-A', 'source-diagnostic-B'})

class Refusal(Exception):
    def __init__(self, code, detail=None):
        self.code, self.detail = str(code), detail
        super().__init__(self.code)

def require(condition, code, detail=None):
    if not condition:
        raise Refusal(code, detail)

def fail_constant(value):
    raise Refusal('NONFINITE_JSON_NUMBER', value)

def pairs_unique(pairs):
    obj = {}
    for key, value in pairs:
        require(key not in obj, 'DUPLICATE_JSON_KEY', key)
        obj[key] = value
    return obj

def encode(obj, limit=FRAME_LIMIT):
    try:
        value = json.dumps(obj, ensure_ascii=False, sort_keys=True,
                           separators=(',', ':'), allow_nan=False).encode('utf-8')
    except (ValueError, TypeError, UnicodeError) as exc:
        raise Refusal('INVALID_JSON_VALUE', str(exc)) from exc
    require(len(value) <= limit, 'CONTROL_FRAME_TOO_LARGE', len(value))
    return value

def decode_any(body, limit=FRAME_LIMIT):
    require(type(body) is bytes and len(body) <= limit, 'INVALID_CONTROL_FRAME')
    try:
        obj = json.loads(body.decode('utf-8'), parse_constant=fail_constant,
                         object_pairs_hook=pairs_unique)
    except (UnicodeError, ValueError) as exc:
        raise Refusal('INVALID_CONTROL_JSON', str(exc)) from exc
    return obj

def decode(body, limit=FRAME_LIMIT):
    obj=decode_any(body,limit)
    require(type(obj) is dict,'OBJECT_REQUIRED')
    return obj

def digest_bytes(body):
    return hashlib.sha256(body).hexdigest()

def identity(obj):
    # Full finite indices may exceed one wire frame; hash their canonical stream.
    h=hashlib.sha256()
    encoder=json.JSONEncoder(ensure_ascii=False,sort_keys=True,separators=(',', ':'),allow_nan=False)
    for piece in encoder.iterencode(obj):h.update(piece.encode('utf-8'))
    return h.hexdigest()

def relative_path(value):
    require(type(value) is str and value and '\\' not in value and '\x00' not in value,
            'INVALID_RELATIVE_PATH')
    p = PurePosixPath(value)
    require(not p.is_absolute() and value == p.as_posix()
            and all(x not in {'', '.', '..'} for x in p.parts), 'NONCANONICAL_PATH', value)
    return value

def exact_keys(value, required, optional=()):
    require(type(value) is dict, 'OBJECT_REQUIRED')
    require(set(required) <= set(value) <= set(required) | set(optional),
            'CLOSED_SCHEMA_MISMATCH', {'required': sorted(required), 'observed': sorted(value)})

def finite_scalar(value):
    require(type(value) in (int, float) and math.isfinite(value), 'FINITE_SCALAR_REQUIRED')
    return value

def content_descriptor(value):
    exact_keys(value, {'path', 'bytes', 'sha256', 'media_type', 'role', 'producer'},
               {'shape', 'dtype', 'units', 'groups', 'coordinates', 'aliases', 'format', 'logical_output', 'prediction_origin'})
    relative_path(value['path'])
    require(type(value['bytes']) is int and 0 <= value['bytes'], 'INVALID_BYTE_COUNT')
    require(type(value['sha256']) is str and len(value['sha256']) == 64
            and all(x in '0123456789abcdef' for x in value['sha256']), 'INVALID_SHA256')
    require(type(value['producer']) is str and value['producer'], 'PRODUCER_REQUIRED')
    require(value.get('dtype') not in {'object', 'pickle'}, 'EXECUTABLE_ARRAY_FORMAT')
    return value

def error_record(exc):
    return {'type': type(exc).__name__, 'code': getattr(exc, 'code', None),
            'message': str(exc), 'detail': getattr(exc, 'detail', None)}
