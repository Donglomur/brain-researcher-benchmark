"""Closed metadata operations; importing this module performs no I/O."""
import hashlib
import math
from ach_resource_common import bounded_encode, bounded_decode, close_all


class Refusal(ValueError):
    pass


def require(ok, message):
    if not ok:
        raise Refusal(message)


def integer(value, low=0):
    require(type(value) is int and value >= low, 'exact nonnegative integer')
    return value


def fields(value, names):
    require(type(value) is dict and set(value) == set(names), 'closed metadata fields: ' + ','.join(names))
    return value


def token(value):
    require(type(value) is str and 0 < len(value) <= 160 and
            all(c.isalnum() or c in '._-' for c in value) and value not in ('.', '..'), 'safe opaque token')
    return value


def pin(raw):
    require(type(raw) is bytes, 'exact bytes for identity')
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def checked_pin(value):
    fields(value, ('bytes', 'sha256'))
    integer(value['bytes'])
    require(type(value['sha256']) is str and len(value['sha256']) == 64 and
            all(c in '0123456789abcdef' for c in value['sha256']), 'full lowercase SHA256')
    return value


def canonical(value, limits):
    return bounded_encode(value, limits)


def identity(value, limits):
    return pin(canonical(value, limits))


def descriptor(value):
    fields(value, ('path', 'bytes', 'sha256'))
    path = value['path']
    require(type(path) is str and path and not path.startswith('/') and
            all(part not in ('', '.', '..') for part in path.split('/')) and
            '\\' not in path and '\x00' not in path, 'canonical relative material path')
    checked_pin({k: value[k] for k in ('bytes', 'sha256')})
    return value


def finite(value):
    require(type(value) in (float, int) and math.isfinite(value), 'finite numeric scalar')
    return float(value)


def error_record(error):
    return {'type': type(error).__name__,
            'secondary': list(getattr(error, 'typed_secondary_errors', [])) +
                         list(getattr(error, 'ach_cleanup_errors', [])),
            'known_prefix': getattr(error, 'n079_prefix', None),
            'transport_prefix': getattr(error, 'typed_transport_prefix', None),
            'io_prefix': getattr(error, 'typed_io_prefix', None)}


def fail_prefix(error, prefix):
    error.n079_prefix = prefix
    return error


def join_unique(rows, key):
    require(type(rows) is list, 'explicit ordered metadata roster')
    result = {}
    for row in rows:
        value = row[key]
        require(value not in result, 'duplicate identity: ' + key)
        result[value] = row
    return result
